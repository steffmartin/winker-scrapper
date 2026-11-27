import argparse
import json
import logging
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import threading
import urllib.request
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qs, unquote, urlparse

# Módulos internos independentes
from compartilhado.utils import logger, setup_logging, load_config

# Garantir dependências antes de importar libs externas
from compartilhado.setup_deps import install_dependencies
install_dependencies()

# Dependências externas e modelos
import pypdf
from playwright.sync_api import sync_playwright

from compartilhado import models
# Reexportações mantêm os chamadores existentes durante a migração.
from extrator.autenticacao import autenticar
from extrator.persistencia_condominio import save_condominio_and_gestao, atualizar_saldo_declarado
from extrator.auditoria import (get_ip_address, _get_ip_address, get_mac_address,
    create_auditoria, update_auditoria_condominio_id, update_auditoria)
from extrator.arquivos import download_http_file, download_file_from_button, download_anexos
from extrator.inadimplencia import extract_inadimplencia_from_pdf, extract_inadimplencia_boleto
from extrator.transacoes import extract_list_from_modal, ler_transacoes_mes
from extrator.prestacao_contas import extrair_prestacao_contas
from extrator.navegacao import (set_ion_datetime, wait_for_new_list_and_items,
    wait_for_list_close, close_last_modal)
from extrator.condominio import (extract_condominio_and_gestao, capturar_sessao_api,
    extrair_condominio_api, selecionar_condominio_fallback)
from extrator.interpretacao import (get_competencia, get_extensao, parse_currency,
    parse_receita_info, parse_conta, parse_fornecedor, get_date_chunks)
from extrator.persistencia import (evaluate_entity_consistency, _snapshot_revisoes,
    _motivos, _reaplicar_revisao_transacao, _restaurar_documentos,
    _atualizar_arquivos_mes, save_extraction_data_to_db, persistir_mes)

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

# ==========================================
# 1. Utilitários de String, Moeda e Data
# ==========================================










# ==========================================
# 2. Downloads HTTP e Interações Web (Playwright)
# ==========================================
















# ==========================================
# 3. Regras de Negócio e Persistência Banco de Dados (SQLite)
# ==========================================

def init_db(db_path=None):
    """
    Inicializa o banco de dados SQLite com a estrutura hierárquica e tipos reais através do ORM Peewee.
    """
    if db_path is None:
        db_path = os.path.join(project_root, "compartilhado", "database", "winker_data.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    models.init_models(db_path)
    return models.db
















# ==========================================
# 4. Orquestrador Principal do Script
# ==========================================

class WinkerScraper:
    """Executa uma extração com estado e dependências próprios."""

    def __init__(self, username, password, wl, start_date_obj, end_date_obj,
                 headless, portal_index=None, *, playwright_factory=None, init_db_factory=None, db_path=None):
        self.username = username
        self.password = password
        self.wl = wl
        self.start_date_obj = start_date_obj
        self.end_date_obj = end_date_obj
        self.headless = headless
        self.portal_index = portal_index
        self._playwright_factory = playwright_factory if playwright_factory is not None else sync_playwright
        self._init_db = init_db_factory if init_db_factory is not None else init_db
        self.db_path = db_path

    def _contabilizar_transacoes(self, quantidade):
        self.total_transacoes_lidas += quantidade

    def _contabilizar_prestacao(self):
        self.total_downloads_prestacoes += 1

    def run(self):
        """
        Fluxo principal de extração web de dados do Winker via Playwright.
        """
        logger.info("Iniciando extração Winker")

        # Inicializa rastreadores para auditoria
        self.start_time = time.time()
        self.total_transacoes_lidas = 0
        self.total_downloads_anexos = 0
        self.total_downloads_prestacoes = 0
        self.capturou_condominio = 0
        self.capturou_inadimplencia = 0
        self.capturou_membros = 0
        self.auditoria_id = None
        self.user_data = {}
        self.condo_id_extraido = None  # Será preenchido após a extração obrigatória do condomínio
        self.condo_nome = None
        self.lista_contas_db = []
        self.regras_preenchimento = []
    
        def update_current_audit(status=None, erro=None):
            if self.auditoria_id is not None:
                duration = time.time() - self.start_time
                update_auditoria(
                    auditoria_id=self.auditoria_id,
                    user_data=self.user_data,
                    downloads_realizados=self.total_downloads_anexos + self.total_downloads_prestacoes,
                    transacoes_lidas=self.total_transacoes_lidas,
                    tempo_duracao=duration,
                    capturou_condominio=self.capturou_condominio,
                    capturou_inadimplencia=self.capturou_inadimplencia,
                    capturou_membros=self.capturou_membros
                )
                if status:
                    try:
                        models.Auditoria.update(status=status, erro=erro).where(models.Auditoria.id == self.auditoria_id).execute()
                    except Exception as exc:
                        logger.error('Erro ao atualizar status da auditoria: %s', exc)
            
        with self._playwright_factory() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context()
            page = context.new_page()
            page_pc = context.new_page()
            page_pc2 = context.new_page()
            page_pc3 = context.new_page()

            page.bring_to_front()

            def handle_response(response):
                if "api.winker.com.br/v1/me" in response.url:
                    try:
                        if response.request.method == "GET" and 200 <= response.status < 300:
                            data = response.json()
                            self.user_data.update(data)
                    except Exception as e:
                        logger.error(f"Erro ao capturar dados do usuário na response: {e}")

            page.on("response", handle_response)

            try:
                if self.db_path is None:
                    self._init_db()
                else:
                    self._init_db(self.db_path)
                self.auditoria_id = create_auditoria(self.start_date_obj.strftime("%Y-%m"), self.end_date_obj.strftime("%Y-%m"))
                autenticar(page, self.username, self.password, self.wl, self.portal_index)

                portal_id, token_api = None, None
                try:
                    portal_id, token_api = capturar_sessao_api(page)
                except Exception as exc:
                    logger.warning("Não foi possível capturar a sessão da API: %s", exc)

                # 1. Extração do Condomínio e Corpo Diretivo (Membros da Gestão)
                membros = []
                administradora_api, telefone_api = None, None
                try:
                    logger.info("Lendo informações do condomínio")
                    self.condo_id_extraido, self.condo_nome, membros = extract_condominio_and_gestao(page)
                    if self.condo_id_extraido:
                        self.capturou_condominio = 1
                    if membros:
                        self.capturou_membros = 1
                except Exception as ex_condo:
                    logger.debug(f"Erro ao extrair informações do condomínio da página: {ex_condo}")

                if not self.condo_id_extraido:
                    try:
                        self.condo_id_extraido, self.condo_nome, membros, administradora_api, telefone_api = extrair_condominio_api(context, token_api, portal_id)
                        self.capturou_condominio = 1
                        self.capturou_membros = int(bool(membros))
                        logger.info("Condomínio identificado pela API para o portal da sessão.")
                    except Exception as exc:
                        logger.warning("Falha ao identificar condomínio pela API: %s", exc)

                # Fallback interativo: se o ID do condomínio não foi obtido automaticamente
                if not self.condo_id_extraido:
                    logger.warning("ID do condomínio não foi obtido automaticamente da página. Selecione o condomínio manualmente:")
                    self.condo_id_extraido, fallback_nome = selecionar_condominio_fallback()
                    if not self.condo_id_extraido:
                        raise ValueError("ID do condomínio não identificado; extração cancelada sem gravar dados do condomínio.")
                    self.condo_nome = fallback_nome or self.condo_nome or "Condomínio"
                    self.capturou_condominio = 1

                # 2. Extração de Inadimplência do boleto recente e dados da Administradora
                # Executada mesmo em caso de fallback da página sobre/index
                data_corte, unidades, valor, administradora, telefone = None, None, None, None, None
                try:
                    logger.info("Lendo informações de inadimplência e administradora do boleto")
                    data_corte, unidades, valor, administradora, telefone = extract_inadimplencia_boleto(page, context, raiz_projeto=project_root)
                    if data_corte:
                        self.capturou_inadimplencia = 1
                except Exception as ex_inad:
                    logger.warning(f"Erro ao extrair inadimplência do boleto: {ex_inad}")

                administradora = administradora or administradora_api
                telefone = telefone or telefone_api

                # 3. Salva condomínio, inadimplência e membros no banco de dados
                try:
                    save_condominio_and_gestao(self.condo_id_extraido, self.condo_nome, data_corte, unidades, valor, administradora, telefone, membros)
                except Exception as ex_save:
                    logger.error(f"Erro ao salvar dados do condomínio: {ex_save}")

                # 4. Atualiza condominio_id na auditoria assim que o id é obtido e carrega as contas do banco
                update_auditoria_condominio_id(self.auditoria_id, self.condo_id_extraido)
                self.regras_preenchimento = list(models.RegrasPreenchimento.select().where(models.RegrasPreenchimento.condominio_id == self.condo_id_extraido).order_by(models.RegrasPreenchimento.id).dicts())
                self.lista_contas_db = [c.conta for c in models.Contas.select().where(models.Contas.condominio_id == self.condo_id_extraido)]
                membros_salvos = list(models.MembrosGestao.select().where(models.MembrosGestao.condominio_id == self.condo_id_extraido))
                if membros_salvos:
                    nomes_gestao = [f"{m.cargo or 'Membro'}: {m.nome}" for m in membros_salvos]
                    logger.debug(f"Gestão no banco ({len(membros_salvos)} membro(s)): {', '.join(nomes_gestao)}")
                    if not self.capturou_membros:
                        self.capturou_membros = 1
                logger.debug(f"Condomínio ativo: {self.condo_nome} (ID: {self.condo_id_extraido}) | Contas identificadas ({len(self.lista_contas_db)}): {self.lista_contas_db}")
                update_current_audit()

                # 4. Navega para o Balancete
                balancete_url = "https://app.winker.com.br/intra/meuCondominio/balancete"
            
                # --- Aba principal (Transações) ---

                page.goto(balancete_url, wait_until="networkidle")
                page.wait_for_selector("iframe[name='pageIframe']", timeout=20000)
            
                iframe = page.frame(name="pageIframe") or page.frame(url=lambda u: "financial-summary" in u)
                if not iframe:
                    logger.error("Erro: Não foi possível carregar o iframe do Balancete na aba principal.")
                    return
                iframe.wait_for_load_state("domcontentloaded")
            
                # ---> CAPTURA DO SALDO DECLARADO (Antes de aplicar os filtros por mês)
                try:
                    saldo_el = iframe.locator("ion-card-content", has_text="Saldo final").locator("p > strong").first
                    saldo_el.wait_for(state="visible", timeout=10000)
                    saldo_text = saldo_el.inner_text().strip()
                    saldo_declarado = parse_currency(saldo_text)
                
                    # Atualiza o saldo_declarado no banco
                    atualizar_saldo_declarado(self.condo_id_extraido, saldo_declarado)
                except Exception as e:
                    logger.error(f"Erro ao capturar saldo declarado: {e}")
            
                # --- Aba secundária (Prestações de contas) ---
                page_pc.bring_to_front()
                page_pc.goto(balancete_url, wait_until="networkidle")
                page_pc.wait_for_selector("iframe[name='pageIframe']", timeout=20000)
            
                iframe_pc = page_pc.frame(name="pageIframe") or page_pc.frame(url=lambda u: "financial-summary" in u)
                if not iframe_pc:
                    logger.error("Erro: Não foi possível carregar o iframe do Balancete na aba secundária.")
                    return
                iframe_pc.wait_for_load_state("domcontentloaded")
            
                tab_pc = iframe_pc.locator("super-tab-button:has-text('PRESTAÇÃO DE CONTAS')")
                if "selected" not in (tab_pc.get_attribute("class") or ""):
                    tab_pc.click()
                    try:
                        iframe_pc.locator("button:has-text('VISUALIZAR')").first.wait_for(state="visible", timeout=15000)
                    except Exception:
                        time.sleep(3)
            
                # --- Aba terciária (Documentos - Demonstrativos financeiros) ---
                page_pc3.bring_to_front()
                page_pc3.goto("https://app.winker.com.br/intra/meuCondominio/documento", wait_until="networkidle")
                page_pc3.get_by_role("link", name=re.compile(r"Demonstrativos financeiros", re.IGNORECASE)).click()
                page_pc3.wait_for_load_state("networkidle")
            
                # --- Aba quaternária (Documentos - Balancetes) ---
                page_pc2.bring_to_front()
                page_pc2.goto("https://app.winker.com.br/intra/meuCondominio/documento", wait_until="networkidle")
                page_pc2.get_by_role("link", name=re.compile(r"Balancetes", re.IGNORECASE)).click()
                page_pc2.wait_for_load_state("networkidle")
            
                page.bring_to_front()
            
                # Atualiza auditoria com dados obtidos (ex: user_data)
                update_current_audit()
            
                # Itera sobre os períodos mensais (chunks)
                chunks = get_date_chunks(self.start_date_obj, self.end_date_obj)
                for chunk_start, chunk_end in chunks:
                    page.bring_to_front()
                    tab_apresentacao = iframe.locator("super-tab-button:has-text('APRESENTAÇÃO')")
                    if "selected" not in (tab_apresentacao.get_attribute("class") or ""):
                        tab_apresentacao.click()
                        iframe.locator("ion-datetime").first.wait_for(state="visible", timeout=15000)
                
                    logger.info(f"Filtrando período {chunk_start.strftime('%m/%Y')} a {chunk_end.strftime('%m/%Y')}")
                    set_ion_datetime(iframe, 0, chunk_start.strftime("%m"), chunk_start.strftime("%Y"))
                    set_ion_datetime(iframe, 1, chunk_end.strftime("%m"), chunk_end.strftime("%Y"))
                

                    time.sleep(5) # Ajustado: Atualização chunk data
                    month_buttons = iframe.locator("button.item.item-block.item-md").all()
                    for btn_index in range(len(month_buttons)):
                        current_btn = iframe.locator("button.item.item-block.item-md").nth(btn_index)
                        text = current_btn.inner_text().strip()
                        lines = text.split("\n")
                        if len(lines) >= 3:
                            nome_mes_abbr = lines[0].strip()[:3]
                            meses_map_reverso = {
                                "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
                                "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12
                            }
                            mes_num = meses_map_reverso.get(nome_mes_abbr)
                            if not mes_num:
                                continue
                            ano_item = chunk_start.year if mes_num >= chunk_start.month else chunk_end.year
                            chave_unica = f"{ano_item}{mes_num:02d}"
                        
                            rec_total_mes = parse_currency(lines[1].strip())
                            des_total_mes = parse_currency(lines[2].strip())
                            if abs(rec_total_mes) < 0.01 and abs(des_total_mes) < 0.01:
                                logger.info(f"  Pulo {nome_mes_abbr}/{ano_item} (Vazio).")
                                continue
 
                            if logger.isEnabledFor(logging.INFO):
                                sys.stdout.write(f"  Processando transações de {nome_mes_abbr}/{ano_item}: 0 transações lidas...")
                                sys.stdout.flush()
                            lists_before_month = iframe.locator("ion-list").count()
                            current_btn.click()
                            wait_for_new_list_and_items(iframe, lists_before_month, expected_non_zero=(abs(rec_total_mes) > 0.01 or abs(des_total_mes) > 0.01))
                        
                            detalhes_mes = ler_transacoes_mes(
                                iframe, context, rec_total_mes, des_total_mes, nome_mes_abbr, ano_item,
                                project_root, self._contabilizar_transacoes,
                                ler_lista=extract_list_from_modal, esperar_lista=wait_for_new_list_and_items,
                                fechar_modal=close_last_modal)

                            prestacao_contas_info = extrair_prestacao_contas(
                                page_pc, iframe_pc, page_pc2, page_pc3, context,
                                mes_num, ano_item, chave_unica, self.condo_id_extraido,
                                project_root, self._contabilizar_prestacao,
                                baixar=download_http_file, avaliar=evaluate_entity_consistency,
                                extensao_de=get_extensao)

                            page.bring_to_front() # Volta para a aba principal

                            try:
                                # 4. Salva no banco de dados e move anexos temporários (incluindo prestação de contas)
                                mes_id, quantidade_anexos = persistir_mes(
                                    chave_unica, nome_mes_abbr, ano_item, rec_total_mes, des_total_mes,
                                    detalhes_mes, project_root, self.condo_id_extraido, prestacao_contas_info,
                                    self.lista_contas_db, self.regras_preenchimento,
                                    salvar=save_extraction_data_to_db, atualizar_arquivos=_atualizar_arquivos_mes)
                                self.total_downloads_anexos += quantidade_anexos

                                update_current_audit()
                            except Exception:
                                logger.exception("Falha ao salvar mês e documentos")
                                raise
                            
                            close_last_modal(iframe)
            
                # Salvar dados de auditoria
                update_current_audit(status='concluida')
            except Exception as e:
                logger.error(f"Erro inesperado durante a extração: {e}", exc_info=True)
                update_current_audit(status='falha', erro=str(e))
            finally:
                update_current_audit()
                browser.close()
                # Limpa o diretório temporário de anexos se ele existir
                temp_dir = os.path.join(project_root, "anexos", "temp")
                if os.path.exists(temp_dir):
                    try:
                        shutil.rmtree(temp_dir, ignore_errors=True)
                    except Exception as err_temp:
                        logger.error(f"Erro ao remover a pasta temporária: {err_temp}")


def extract_winker(username, password, wl, start_date_obj, end_date_obj, headless, portal_index=None):
    """Mantém o ponto de entrada procedural para chamadores existentes."""
    return WinkerScraper(username, password, wl, start_date_obj, end_date_obj,
                         headless, portal_index).run()

