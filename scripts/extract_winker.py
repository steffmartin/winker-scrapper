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
import time
import urllib.request
import uuid
from datetime import datetime, timedelta
from urllib.parse import parse_qs, unquote, urlparse

# Módulos internos independentes
from utils import logger, setup_logging, load_config

# Garantir dependências antes de importar libs externas
from setup_deps import install_dependencies
install_dependencies()

# Dependências externas e modelos
import pypdf
from playwright.sync_api import sync_playwright

import models

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

# ==========================================
# 1. Utilitários de String, Moeda e Data
# ==========================================

def get_competencia(exibicao):
    if not exibicao or '/' not in exibicao:
        return None
    mes_str, ano_str = exibicao.split('/')
    meses_map = {'JAN': '01', 'FEV': '02', 'MAR': '03', 'ABR': '04', 'MAI': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08', 'SET': '09', 'OUT': '10', 'NOV': '11', 'DEZ': '12'}
    return f"{ano_str}-{meses_map.get(mes_str, '01')}"

def get_extensao(nome_arquivo):
    if not nome_arquivo:
        return None
    ext_match = re.search(r'\.([^.]+)$', nome_arquivo)
    if not ext_match:
        return None
    raw_ext = ext_match.group(1).lower()
    # Remove query strings e fragmentos
    raw_ext = raw_ext.split('?')[0].split('&')[0].split('#')[0]
    # Mantém apenas caracteres alfanuméricos
    clean_ext = re.sub(r'[^a-z0-9]', '', raw_ext)
    return clean_ext if clean_ext else None

def parse_currency(val_str):
    """
    Converte uma string de moeda (ex: 'R$ 1.234,56' ou '- R$ 10,00') para float.
    """
    if not val_str:
        return 0.0
    clean_val = val_str.replace("R$", "").replace(".", "").replace(",", ".").replace(" ", "").strip()
    try:
        return float(clean_val)
    except ValueError:
        return 0.0

def parse_receita_info(descricao):
    """
    Extrai apartamento e competência da descrição da receita.
    """
    apto = None
    competencia = None
    
    meses_map = {
        "JAN": "01", "FEV": "02", "MAR": "03", "ABR": "04", "MAI": "05", "JUN": "06",
        "JUL": "07", "AGO": "08", "SET": "09", "OUT": "10", "NOV": "11", "DEZ": "12"
    }
    
    match_apto = re.search(r"Apto\s*[/-]\s*(\d{3})(?!\d)", descricao)
    if match_apto:
        apto = match_apto.group(1)
        
    match_comp = re.search(r"([A-Z]{3})\s*(\d{4})", descricao)
    if match_comp:
        mes_abbr = match_comp.group(1)
        ano = match_comp.group(2)
        if mes_abbr in meses_map:
            competencia = f"{ano}-{meses_map[mes_abbr]}"
            
    return apto, competencia

def parse_conta(descricao):
    """
    Extrai a conta da descrição da transação.
    """
    if not descricao:
        return None
    match = re.search(r"(?:Conta|CTA\.\s*PGTO)\s*:\s*([^-\n]+)", descricao, re.IGNORECASE)
    if match:
        return match.group(1).strip().upper()
    return None

def parse_fornecedor(descricao):
    """
    Extrai o fornecedor da descrição de uma despesa.
    """
    if not descricao:
        return None
    
    desc_upper = descricao.upper()
        
    if any(desc_upper.startswith(prefix) for prefix in ["TARIFA", "IOF", "IRRF"]):
        return None
        
    # 1. Começando com "Pagamento "
    match_pag = re.search(r"^Pagamento\s+(.+?)(?:\s*-\s*Doc|\s+Doc|\s*-\s*Conta|\s*-\s*NF|\s*-\s*CTA\.|\s+CTA\.)", descricao, re.IGNORECASE)
    if match_pag:
        return match_pag.group(1).strip().upper()
        
    if desc_upper.startswith("PAGAMENTO"):
        nome = descricao[9:].strip()
        nome = re.split(r"\s+-\s+", nome)[0]
        return nome.strip().upper()
        
    # 2. Não começando com "Pagamento ", mas contendo " - NF:" ou " - CTA. PGTO:"
    match_nof_pag = re.search(r"^(.+?)(?:\s*-\s*NF|\s*-\s*CTA\.|\s+CTA\.)", descricao, re.IGNORECASE)
    if match_nof_pag:
        return match_nof_pag.group(1).strip().upper()
        
    return None

def get_date_chunks(start_date_obj, end_date_obj):
    """
    Divide o período informado em chunks mensais.
    """
    chunks = []
    current_start = start_date_obj
    while current_start <= end_date_obj:
        year = current_start.year + (current_start.month + 10) // 12
        month = (current_start.month + 10) % 12 + 1
        chunk_end = datetime(year, month, 1)
        if chunk_end > end_date_obj:
            chunk_end = end_date_obj
        chunks.append((current_start, chunk_end))
        next_year = chunk_end.year + (chunk_end.month) // 12
        next_month = (chunk_end.month) % 12 + 1
        current_start = datetime(next_year, next_month, 1)
    return chunks

def extract_inadimplencia_from_pdf(pdf_path):
    """
    Lê o PDF do boleto mais recente e extrai os dados de inadimplência utilizando Regex.
    Retorna uma tupla (data_corte, unidades, valor).
    """
    data_corte = None
    unidades = None
    valor = None
    
    try:
        reader = pypdf.PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
            
        # Regexes para extração de dados
        match_data = re.search(r"Inadimplência\s+do\s+condomínio\s+em\s+(\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
        if match_data:
            data_corte = match_data.group(1)
            
        match_unidades = re.search(r"Unidades\s+inadimplentes:\s*(\d+)", text, re.IGNORECASE)
        if match_unidades:
            unidades = int(match_unidades.group(1))
            
        match_valor = re.search(r"Valor\s+Total:\s*([\d.,]+)", text, re.IGNORECASE)
        if match_valor:
            valor = parse_currency(match_valor.group(1))
            
    except Exception as e:
        logger.error(f"Erro ao analisar o PDF de inadimplência: {e}")
        
    return data_corte, unidades, valor

# ==========================================
# 2. Downloads HTTP e Interações Web (Playwright)
# ==========================================

def download_http_file(context, url, dest_dir, filename_prefix="", default_filename=""):
    """
    Baixa um arquivo via requisição HTTP GET utilizando o contexto do Playwright e salva no destino.
    Retorna o caminho local completo do arquivo baixado e o nome original higienizado.
    """
    response = context.request.get(url)
    if response.status != 200:
        raise Exception(f"Erro HTTP {response.status} ao baixar arquivo de: {url}")
        
    body_bytes = response.body()
    content_type = response.headers.get("content-type", "").lower()
    
    # Determina a extensão correta
    ext = ""
    parsed_path = urlparse(url).path
    parsed_path_clean = re.split(r'[?&]', parsed_path)[0]
    _, url_ext = os.path.splitext(parsed_path_clean)
    if url_ext and len(url_ext) <= 5 and url_ext.startswith("."):
        ext = url_ext.lower()
        
    if not ext:
        if "application/pdf" in content_type or body_bytes.startswith(b"%PDF"):
            ext = ".pdf"
        elif "image/jpeg" in content_type or "image/jpg" in content_type:
            ext = ".jpg"
        elif "image/png" in content_type:
            ext = ".png"
        elif "image/gif" in content_type:
            ext = ".gif"
        else:
            ext = ".pdf" # Fallback padrão
            
    # Higieniza o nome original
    nome_orig = default_filename
    if not nome_orig:
        nome_orig = os.path.basename(unquote(parsed_path_clean))
    if not nome_orig:
        nome_orig = f"documento_{int(time.time())}"
        
    # Limpa query strings e caracteres inválidos para Windows
    nome_orig = re.sub(r'[\\/*?:"<>|&]', "", nome_orig)
    
    # Garante a extensão no fim
    nome_orig_base, _ = os.path.splitext(nome_orig)
    nome_orig = nome_orig_base + ext
    
    os.makedirs(dest_dir, exist_ok=True)
    temp_filename = f"{filename_prefix}{nome_orig}"
    local_path = os.path.join(dest_dir, temp_filename)
    
    with open(local_path, "wb") as f:
        f.write(body_bytes)
        
    return local_path, nome_orig

def download_file_from_button(context, btn, dest_dir, filename_prefix="", default_filename=""):
    """
    Clica em um botão que abre uma nova aba contendo um PDF ou arquivo,
    ou inicia um download direto (como em modo headless), e realiza o download.
    Retorna o caminho local completo do arquivo baixado e o nome original.
    """
    # Obtém a página onde o botão está localizado
    page = btn.page
    
    event_data = {"download": None, "popup": None}
    
    def on_download(download):
        event_data["download"] = download
        
    def on_popup(popup):
        event_data["popup"] = popup

    # Registra listeners temporários na página
    page.on("download", on_download)
    page.on("popup", on_popup)
    
    try:
        # Clica no botão para disparar a ação
        btn.click()
        
        # Aguarda até 15 segundos por um evento de popup ou download direto
        start_time = time.time()
        while time.time() - start_time < 15.0:
            # Caso 1: Foi disparado um evento de download direto (ex: em headless)
            if event_data["download"] is not None:
                dl = event_data["download"]
                os.makedirs(dest_dir, exist_ok=True)
                temp_filename = f"{filename_prefix}{default_filename or dl.suggested_filename}"
                local_path = os.path.join(dest_dir, temp_filename)
                dl.save_as(local_path)
                return local_path, default_filename or dl.suggested_filename
                
            # Caso 2: Foi aberto um popup (ex: em modo normal/headful)
            if event_data["popup"] is not None:
                popup = event_data["popup"]
                
                # Aguarda que o popup navegue para uma URL http válida
                target_url = ""
                popup_start = time.time()
                while time.time() - popup_start < 10.0:
                    target_url = popup.url
                    if target_url and target_url.startswith("http"):
                        break
                    page.wait_for_timeout(50)
                    
                if target_url and target_url.startswith("http"):
                    if "viewer.html" in target_url and "file=" in target_url:
                        parsed = urlparse(target_url)
                        query_params = parse_qs(parsed.query)
                        file_param = query_params.get("file", [None])[0]
                        if file_param:
                            target_url = file_param
                            
                    res = download_http_file(
                        context, target_url, dest_dir,
                        filename_prefix=filename_prefix, default_filename=default_filename
                    )
                    try:
                        popup.close()
                    except:
                        pass
                    return res[0], res[1]
                    
            page.wait_for_timeout(50)
            
        raise Exception("Não foi possível obter a URL ou o arquivo de download.")
    finally:
        # Remove os listeners temporários para evitar vazamento de memória ou eventos duplicados
        try:
            page.remove_listener("download", on_download)
        except:
            pass
        try:
            page.remove_listener("popup", on_popup)
        except:
            pass

def download_anexos(loc, context):
    """
    Identifica todos os botões de anexo de uma transação, realiza o download
    de cada arquivo (PDF, imagem, etc.), garante o fechamento de todas as abas
    e retorna uma tupla (downloaded_files, count) com os arquivos baixados e o total.
    """
    attach_buttons = loc.locator("button.button-docs:has(ion-icon[name='attach'])")
    count = attach_buttons.count()
    if count == 0:
        return [], 0
        
    downloaded_files = []
    temp_dir = os.path.join(project_root, "anexos", "temp")
    
    for idx in range(count):
        btn = attach_buttons.nth(idx)
        btn_text = btn.inner_text().strip()
        
        # Extrai o nome do arquivo de dentro dos parênteses
        match_name = re.search(r"\(([^)]+)\)", btn_text)
        nome_original = match_name.group(1).strip() if match_name else btn_text
        
        prefix = f"temp_{int(time.time() * 1000)}_{idx}_"
        try:
            temp_path, nome_orig_final = download_file_from_button(
                context, btn, temp_dir, 
                filename_prefix=prefix, default_filename=nome_original
            )
            
            downloaded_files.append({
                "temp_path": temp_path,
                "nome_original": nome_orig_final
            })
        except Exception as e:
            logger.error(f"Erro ao baixar anexo {nome_original}: {e}")
                    
    return downloaded_files, count

def set_ion_datetime(iframe, selector_index, target_month, target_year):
    """
    Interage com o componente ion-datetime selecionando mês e ano.
    """
    datetime_elements = iframe.locator("ion-datetime").all()
    if len(datetime_elements) <= selector_index:
        return False

    datetime_elements[selector_index].click()
    iframe.locator("ion-picker-cmp").wait_for(state="visible", timeout=10000)

    def navigate_sequentially(col_class, target_value, is_month):
        column = iframe.locator(f"ion-picker-cmp .{col_class}")
        if not column.is_visible():
            return False

        selected_locator = column.locator("button.picker-opt-selected")
        if not selected_locator.is_visible():
            column.get_by_role("button", name=target_value, exact=True).click()
            return

        current_val_text = selected_locator.inner_text().strip()
        current_val = int(current_val_text)
        target_val = int(target_value)

        if current_val == target_val:
            return

        step = -1 if target_val < current_val else 1
        for val in range(current_val + step, target_val + step, step):
            val_str = str(val).zfill(2) if is_month else str(val)
            column.get_by_role("button", name=val_str, exact=True).click()
            time.sleep(0.1) # Mantido: Navegação entre números

    try:
        navigate_sequentially("picker-opts-right", target_month, True)
        navigate_sequentially("picker-opts-left", target_year, False)
        iframe.get_by_role("button", name="Confirmar").click()
        
        # Aguarda o fechamento do picker ou a confirmação do alerta secundário
        alert_btn = iframe.locator("button.alert-button:has-text('Confirmar')")
        picker = iframe.locator("ion-picker-cmp")
        start_time = time.time()
        while time.time() - start_time < 3.0:
            if alert_btn.is_visible():
                alert_btn.click()
                break
            if not picker.is_visible():
                break
            time.sleep(0.05)
        return True
    except:
        return False

def extract_list_from_modal(iframe, context=None):
    """
    Extrai as categorias, subcategorias ou transações presentes no modal atual.
    """
    results = []
    last_list = iframe.locator("ion-list").last
    if last_list.count() == 0:
        return results
    locators = last_list.locator("button.item-block, ion-item.item-block")
    count = locators.count()
    for i in range(count):
        try:
            loc = locators.nth(i)
            label_el = loc.locator("ion-label")
            if label_el.count() == 0:
                continue
            h2_el = label_el.locator("h2")
            if h2_el.count() > 0:
                nome = h2_el.first.inner_text().strip()
                p_el = label_el.locator("p")
                if p_el.count() > 0:
                    nome += f" ({p_el.first.inner_text().strip()})"
            else:
                span_el = label_el.locator("span")
                nome = span_el.first.inner_text().strip() if span_el.count() > 0 else label_el.inner_text().strip()
            
            if "R$" in nome and len(nome) < 20:
                continue
                
            valor_el = loc.locator("span[item-right]").first
            valor = valor_el.inner_text().strip() if valor_el.count() > 0 else "R$ 0,00"
            valor = " ".join(valor.split())
            
            anexos = []
            anexos_count = 0
            if context:
                anexos, anexos_count = download_anexos(loc, context)
                
            if nome:
                results.append({
                    "nome": nome,
                    "valor": valor,
                    "index": i,
                    "anexos": anexos,
                    "anexos_count": anexos_count
                })
        except Exception as e:
            logger.error(f"Erro em extract_list_from_modal no item {i}: {e}", exc_info=True)
            continue
    return results

def wait_for_new_list_and_items(iframe, previous_list_count, expected_non_zero=True, timeout_ms=10000):
    """
    Aguarda a abertura de uma nova lista de itens (ion-list) no iframe.
    Se expected_non_zero for True, aguarda até que a nova lista tenha pelo menos um item.
    """
    start_time = time.time()
    while time.time() - start_time < (timeout_ms / 1000.0):
        lists = iframe.locator("ion-list")
        current_count = lists.count()
        if current_count > previous_list_count:
            last_list = lists.last
            if expected_non_zero:
                items_count = last_list.locator("button.item-block, ion-item.item-block").count()
                if items_count > 0:
                    return True
            else:
                return True
        time.sleep(0.05)
    return False

def wait_for_list_close(iframe, previous_list_count, timeout_ms=5000):
    """
    Aguarda o fechamento de um modal/lista monitorando a redução de elementos 'ion-list'.
    """
    start_time = time.time()
    while time.time() - start_time < (timeout_ms / 1000.0):
        current_count = iframe.locator("ion-list").count()
        if current_count < previous_list_count:
            return True
        time.sleep(0.05)
    return False

def close_last_modal(iframe):
    """
    Fecha o último modal/lista aberto clicando no botão 'close' e aguarda seu fechamento.
    """
    lists_before_close = iframe.locator("ion-list").count()
    iframe.get_by_role("button", name="close").last.click()
    wait_for_list_close(iframe, lists_before_close)

def extract_condominio_and_gestao(page):
    """
    Navega para a página de informações do condomínio, extrai o ID de segurança,
    o nome do condomínio e os membros da gestão.
    """
    condo_url = "https://app.winker.com.br/intra/condominio/sobre/index"
    page.goto(condo_url, wait_until="networkidle")
    
    # Aguarda o elemento chave carregar
    page.wait_for_selector("div.info_cond_codigo_seguranca strong", timeout=15000)
    
    # 1. Extração do ID de Segurança
    condo_id = page.locator("div.info_cond_codigo_seguranca strong").inner_text().strip()
    
    # 2. Extração do Nome do Condomínio do breadcrumb
    condo_nome = "Condomínio"
    breadcrumb_el = page.locator("#breadcrumb a").first
    if breadcrumb_el.count() > 0:
        condo_nome = breadcrumb_el.inner_text().strip()
        
    # 3. Extração do Síndico
    membros = []
    sindico_label = page.locator("div.panel.panel-info label.label-success").first
    if sindico_label.count() > 0:
        lbl_text = sindico_label.inner_text().strip()
        if " - " in lbl_text:
            sindico_name = lbl_text.split(" - ")[0].strip()
        else:
            sindico_name = re.sub(r"-?\s*síndico(a)?", "", lbl_text, flags=re.IGNORECASE).strip()
            sindico_name = re.sub(r"-?\s*sindico(a)?", "", sindico_name, flags=re.IGNORECASE).strip()
        membros.append({"nome": sindico_name, "cargo": "Síndico"})
    
    # 4. Outros membros da gestão
    rows = page.locator("#lista_corpo_diretivo .row").all()
    for r in rows:
        name_el = r.locator("b i")
        if name_el.count() > 0:
            nome_membro = name_el.first.inner_text().strip()
            texto_completo = r.inner_text().strip()
            cargo_membro = texto_completo.replace(nome_membro, "").replace("-", "").strip()
            cargo_membro = " ".join(cargo_membro.split())
            
            if nome_membro:
                membros.append({
                    "nome": nome_membro,
                    "cargo": cargo_membro or "Membro da Gestão"
                })
                
    return condo_id, condo_nome, membros

def extract_inadimplencia_boleto(page, context):
    """
    Navega para a página de boletos, faz o download do PDF do boleto mais recente,
    extrai os dados de inadimplência e as informações da administradora.
    Retorna uma tupla (data_corte, unidades, valor, administradora, telefone).
    """
    boleto_url = "https://app.winker.com.br/intra/meuCondominio/boleto"
    page.goto(boleto_url, wait_until="networkidle")
    
    administradora = None
    telefone = []
    try:
        locators = page.locator("strong, .panel-heading, div.alert.alert-info").all()
        for loc in locators:
            text = loc.inner_text().strip()
            text = " ".join(text.split())
            if re.search(r"\(\d{2}\)\s*\d{4,5}-?\d{4}", text):
                if " - " in text:
                    text = text.split(" - ")[-1].strip()
                        
                match_adm = re.search(r"([A-ZÀ-Úa-z\s]+)\s*\(", text)
                if match_adm and not administradora:
                    administradora = match_adm.group(1).strip()
                    
                phones = re.findall(r"\((\d{2})\)\s*([\d-]+)", text)
                for ddd, num in phones:
                    num_clean = num.replace("-", "").replace(" ", "").strip()
                    full_phone = f"{ddd}{num_clean}"
                    if full_phone not in telefone:
                        telefone.append(full_phone)
                
                if telefone:
                    break
    except Exception as ex_admin:
        logger.error(f"Erro ao extrair dados da administradora: {ex_admin}")
        
    try:
        page.wait_for_selector(".list-group-item", timeout=15000)
    except Exception:
        logger.warning("Aviso: Nenhum boleto listado na página de boletos.")
        return None, None, None, administradora, telefone
        
    first_item = page.locator(".list-group-item").first
    badge_btn = first_item.locator("a.badge")
    
    if badge_btn.count() == 0:
        logger.warning("Aviso: Botão de download/visualização do boleto não encontrado.")
        return None, None, None, administradora, telefone
        
    temp_dir = os.path.join(project_root, "anexos", "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Clicar no badge para abrir o modal de confirmação
        badge_btn.click()
        
        # Aguarda o botão do SweetAlert aparecer e ser visível por até 5s
        confirm_btn = page.locator("button.swal2-confirm")
        try:
            confirm_btn.wait_for(state="visible", timeout=5000)
        except Exception:
            logger.warning("Aviso: Botão de confirmação swal2-confirm não apareceu em 5s.")
            return None, None, None, administradora, telefone
            
        # Clica no botão de confirmação esperando a abertura da nova página (PDF)
        prefix = f"boleto_{int(time.time())}_"
        temp_path, nome_orig_final = download_file_from_button(
            context, confirm_btn, temp_dir,
            filename_prefix=prefix, default_filename="boleto_recente.pdf"
        )
        
        data_corte, unidades, valor = extract_inadimplencia_from_pdf(temp_path)
        
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
                
        return data_corte, unidades, valor, administradora, telefone
            
    except Exception as e:
        logger.error(f"Erro durante a extração de inadimplência do boleto: {e}")
        return None, None, None, administradora, telefone

# ==========================================
# 3. Regras de Negócio e Persistência Banco de Dados (SQLite)
# ==========================================

def init_db(db_path=None):
    """
    Inicializa o banco de dados SQLite com a estrutura hierárquica e tipos reais através do ORM Peewee.
    """
    if db_path is None:
        db_path = os.path.join(project_root, "database", "winker_data.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    models.init_models(db_path)
    return models.db

def save_condominio_and_gestao(condo_id, condo_nome, data_corte, unidades, valor, administradora, telefone, membros):
    """
    Salva ou atualiza os dados raiz do condomínio e sua gestão (síndico, conselheiros).
    """

    try:
        cond, created = models.Condominio.get_or_create(id=condo_id)
        cond.nome = condo_nome
        if data_corte and unidades is not None and valor is not None:
            cond.inadimplencia_data_corte = data_corte
            cond.inadimplencia_unidades = unidades
            cond.inadimplencia_valor = valor
        if administradora: cond.administradora = administradora
        if telefone is not None: cond.telefone_administradora = json.dumps(telefone)
        cond.ultima_atualizacao = datetime.now().isoformat()
        cond.save()
        
        models.MembrosGestao.delete().where(models.MembrosGestao.condominio_id == condo_id).execute()
        for m in membros:
            models.MembrosGestao.create(condominio_id=condo_id, nome=m['nome'], cargo=m['cargo'])
    except Exception as e:
        logger.error(f"Erro ao salvar dados do condomínio: {e}")

def save_prestacao_contas(mes_id, caminho_local, nome_original, extensao, consistente, motivo_inconsistencia):
    """
    Salva o registro do PDF da prestação de contas mensal no banco.
    """
    try:
        models.PrestacoesContas.create(
            mes_id=mes_id, caminho_local=caminho_local, nome_original=nome_original,
            extensao=extensao, consistente=consistente, motivo_inconsistencia=motivo_inconsistencia
        )
        if caminho_local:
            mes = models.Meses.get(models.Meses.id == mes_id)
            mes.anexos += 1
            if mes.motivo_inconsistencia:
                reasons = json.loads(mes.motivo_inconsistencia)
                if "Mês sem prestação de contas" in reasons:
                    reasons.remove("Mês sem prestação de contas")
                    if not reasons:
                        mes.consistente = 1
                        mes.motivo_inconsistencia = None
                    else:
                        mes.motivo_inconsistencia = json.dumps(reasons, ensure_ascii=False)
            mes.save()
    except Exception as e:
        logger.error(f"Erro ao salvar prestação de contas no banco: {e}")

def get_ip_address():
    url_list = ["https://api.ipify.org", "https://www.meuip.com/api/meuip.php", "https://ipinfo.io/ip"]
    for url in url_list:
        try:
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                ip = response.read().decode('utf-8').strip()
                if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip):
                    return ip
        except Exception:
            continue
            
    # Caso falhe, tenta obter o IP local como fallback
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return None

def get_mac_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        if local_ip:
            cmd = ["powershell", "-Command", f"(Get-NetIPAddress -IPAddress {local_ip} | Get-NetAdapter).MacAddress"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            mac = result.stdout.strip()
            if mac:
                mac_clean = mac.replace("-", ":").lower()
                if re.match(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", mac_clean):
                    return mac_clean
    except Exception:
        pass
    return None

def create_auditoria(periodo_inicio, periodo_fim):
    """
    Cria o registro inicial de auditoria da sessão de scraping.
    """
    try:
        aud = models.Auditoria.create(
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            data_hora_captura=datetime.now().isoformat()
        )
        return aud.id
    except Exception as e:
        logger.error(f"Erro ao iniciar registro de auditoria: {e}")
        return None

def update_auditoria_condominio_id(auditoria_id, condominio_id):
    """
    Atualiza o registro de auditoria com o ID do condomínio logo após descobri-lo.
    """
    if not auditoria_id or not condominio_id: return
    try:
        models.Auditoria.update(condominio_id=condominio_id).where(models.Auditoria.id == auditoria_id).execute()
    except Exception as e:
        logger.error(f"Erro ao atualizar condominio na auditoria: {e}")

def update_auditoria(auditoria_id, user_data, downloads_realizados, transacoes_lidas, tempo_duracao, capturou_condominio, capturou_inadimplencia, capturou_membros):
    """
    Finaliza o registro de auditoria adicionando dados do usuário e métricas de execução.
    """
    if not auditoria_id: return
    try:
        models.Auditoria.update(
            usuario_uuid=user_data.get("uuid"),
            usuario_id=user_data.get("id"),
            usuario_name=user_data.get("name"),
            usuario_cpf=user_data.get("cpf"),
            usuario_rg=user_data.get("rg"),
            usuario_fone=user_data.get("fone"),
            usuario_apto=user_data.get("apto"),
            ip=get_ip_address(),
            mac=get_mac_address(),
            downloads_realizados=downloads_realizados,
            transacoes_lidas=transacoes_lidas,
            tempo_duracao=tempo_duracao,
            capturou_condominio=int(capturou_condominio),
            capturou_inadimplencia=int(capturou_inadimplencia),
            capturou_membros=int(capturou_membros)
        ).where(models.Auditoria.id == auditoria_id).execute()
    except Exception as e:
        logger.error(f"Erro ao finalizar auditoria: {e}")

def evaluate_entity_consistency(entity_type, **kwargs):
    """
    Avalia as regras de negócio para consistência de diferentes entidades do sistema.
    Tipos suportados: 'mes', 'categoria', 'subcategoria', 'transacao', 'anexo', 'prestacao_contas'.
    Retorna uma tupla onde os dois primeiros elementos são sempre (consistente_flag, motivo_inconsistencia).
    Para 'transacao', retorna adicionalmente (apto, competencia, fornecedor, conta).
    """
    if entity_type == 'mes':
        rec_total = kwargs.get('rec_total_mes', 0.0)
        soma_rec = kwargs.get('soma_cat_rec', 0.0)
        desp_total = kwargs.get('desp_total_mes', 0.0)
        soma_desp = kwargs.get('soma_cat_desp', 0.0)
        
        anexos = kwargs.get('anexos', 0)
        
        mes_rec_ok = abs(rec_total - soma_rec) < 0.01
        mes_desp_ok = abs(desp_total - soma_desp) < 0.01
        mes_prestacao_ok = anexos > 0
        consistente = 1 if (mes_rec_ok and mes_desp_ok and mes_prestacao_ok) else 0
        
        motivo = None
        if not consistente:
            reasons = []
            if not mes_rec_ok:
                reasons.append("Divergência em receitas")
            if not mes_desp_ok:
                reasons.append("Divergência em despesas")
            if not mes_prestacao_ok:
                reasons.append("Mês sem prestação de contas")
            if not reasons:
                reasons.append("Divergência em receitas ou despesas")
            motivo = json.dumps(reasons, ensure_ascii=False)
            
        return consistente, motivo

    elif entity_type == 'categoria':
        nome = kwargs.get('cat_nome', '')
        val_num = kwargs.get('cat_val_num', 0.0)
        soma_sub = kwargs.get('soma_sub', 0.0)
        
        consistente = 1 if abs(val_num - soma_sub) < 0.01 else 0
        motivo = None
        if not consistente:
            logger.debug(f"    [AVISO CONSISTÊNCIA] Categoria '{nome}': Valor informado = R$ {val_num:.2f} | Soma subcategorias = R$ {soma_sub:.2f}")
            motivo = json.dumps(["Soma das subcategorias difere do total da categoria"], ensure_ascii=False)
            
        return consistente, motivo

    elif entity_type == 'subcategoria':
        nome = kwargs.get('sub_nome', '')
        val_num = kwargs.get('sub_val_num', 0.0)
        soma_itens = kwargs.get('soma_itens', 0.0)
        
        consistente = 1 if abs(val_num - soma_itens) < 0.01 else 0
        motivo = None
        if not consistente:
            logger.debug(f"    [AVISO CONSISTÊNCIA] Subcategoria '{nome}': Valor informado = R$ {val_num:.2f} | Soma transações = R$ {soma_itens:.2f}")
            motivo = json.dumps(["Soma das transações difere do total da subcategoria"], ensure_ascii=False)
            
        return consistente, motivo

    elif entity_type == 'transacao':
        tipo_flag = kwargs.get('tipo_flag', '')
        desc_completa = kwargs.get('desc_completa', '')
        desc_f = kwargs.get('desc_f', '')
        anexos_esperados = kwargs.get('anexos_esperados', 0)
        anexos_baixados = kwargs.get('anexos_baixados', 0)
        despesa_anexo_valido = kwargs.get('despesa_anexo_valido', True)
        
        fields_ok = True
        apto, comp = (None, None)
        fornecedor = None
        
        if tipo_flag == "R":
            apto, comp = parse_receita_info(desc_completa)
            if not (apto and apto.strip() and comp and comp.strip()):
                fields_ok = False
        elif tipo_flag == "D":
            fornecedor = parse_fornecedor(desc_f)
            if not (fornecedor and fornecedor.strip()):
                fields_ok = False
                
        conta = parse_conta(desc_completa)
        if not (conta and conta.strip()):
            fields_ok = False
            
        anexos_ok = (anexos_esperados == anexos_baixados)
        consistente = 1 if (fields_ok and anexos_ok and despesa_anexo_valido) else 0
        
        motivo = None
        if not consistente:
            reasons = []
            if tipo_flag == "R":
                if not (apto and apto.strip()):
                    reasons.append("Apartamento não identificado")
                if not (comp and comp.strip()):
                    reasons.append("Competência não identificada")
            elif tipo_flag == "D":
                if not (fornecedor and fornecedor.strip()):
                    reasons.append("Fornecedor não identificado")
                if not despesa_anexo_valido:
                    reasons.append("Despesa sem comprovantes")
            if not (conta and conta.strip()):
                reasons.append("Conta não identificada")
            if not anexos_ok:
                reasons.append("Quantidade de anexos divergente")
            if not reasons:
                reasons.append("Dados da transação inconsistentes")
            motivo = json.dumps(reasons, ensure_ascii=False)
            
        return consistente, motivo, apto, comp, fornecedor, conta

    elif entity_type == 'anexo':
        extensao = kwargs.get('extensao', '')
        # Anexo consistente se tiver uma extensão válida de 2 a 5 caracteres alfanuméricos
        consistente = 1 if extensao and re.match(r"^[a-zA-Z0-9]{2,5}$", extensao) else 0
        
        motivo = None
        if not consistente:
            motivo = json.dumps(["Extensão de arquivo inválida ou ausente"], ensure_ascii=False)
            
        return consistente, motivo

    elif entity_type == 'prestacao_contas':
        sucesso = kwargs.get('sucesso', False)
        consistente = 1 if sucesso else 0
        motivo = None if sucesso else json.dumps(["Prestação de contas indisponível"], ensure_ascii=False)
        
        return consistente, motivo

    else:
        raise ValueError(f"Tipo de entidade desconhecido para validação de consistência: {entity_type}")

def save_extraction_data_to_db(chave_unica, nome_mes_abbr, ano_item, rec_total_mes, des_total_mes, detalhes_mes, project_root, condominio_id=None):
    db_conn = models.db
    anexos_para_mover = []
    exibicao = f"{nome_mes_abbr}/{ano_item}"
    
    try:
        with db_conn.atomic():
            models.Meses.delete().where((models.Meses.exibicao == exibicao) & (models.Meses.condominio_id == condominio_id)).execute()
            
            soma_cat_rec = sum(parse_currency(cat['valor']) for cat in detalhes_mes["receitas"])
            soma_cat_desp = sum(parse_currency(cat['valor']) for cat in detalhes_mes["despesas"])
            
            mes_consistente, mes_motivo = evaluate_entity_consistency(
                'mes', rec_total_mes=rec_total_mes, soma_cat_rec=soma_cat_rec,
                desp_total_mes=des_total_mes, soma_cat_desp=soma_cat_desp
            )
            
            if not mes_consistente:
                logger.debug(f"    [AVISO CONSISTÊNCIA] Inconsistência no Mês {nome_mes_abbr}/{ano_item}:")
                logger.debug(f"      - Receitas: Total informado = R$ {rec_total_mes:.2f} | Soma categorias = R$ {soma_cat_rec:.2f}")
                logger.debug(f"      - Despesas: Total informado = R$ {des_total_mes:.2f} | Soma categorias = R$ {soma_cat_desp:.2f}")

            competencia = get_competencia(exibicao)
            
            mes = models.Meses.create(
                condominio_id=condominio_id, exibicao=exibicao, competencia=competencia,
                receita_total=rec_total_mes, despesa_total=des_total_mes,
                consistente=mes_consistente, motivo_inconsistencia=mes_motivo, revisado_usuario=mes_consistente
            )
            mes_id = mes.id
            
            for t_key in ["receitas", "despesas"]:
                tipo_flag = "R" if t_key == "receitas" else "D"
                for cat in detalhes_mes[t_key]:
                    cat_val_num = parse_currency(cat['valor'])
                    soma_sub = sum(parse_currency(sub['valor']) for sub in cat['subcategorias'])
                    
                    cat_consistente, cat_motivo = evaluate_entity_consistency('categoria', cat_nome=cat['nome'], cat_val_num=cat_val_num, soma_sub=soma_sub)
                    
                    cat_obj = models.Categorias.create(
                        mes_id=mes_id, tipo=tipo_flag, nome=cat['nome'], valor=cat_val_num,
                        consistente=cat_consistente, motivo_inconsistencia=cat_motivo, revisado_usuario=cat_consistente
                    )
                    cat_id = cat_obj.id
                    
                    for sub in cat['subcategorias']:
                        sub_val_num = parse_currency(sub['valor'])
                        soma_itens = sum(parse_currency(item['valor']) for item in sub['itens'])
                        
                        sub_consistente, sub_motivo = evaluate_entity_consistency('subcategoria', sub_nome=sub['nome'], sub_val_num=sub_val_num, soma_itens=soma_itens)
                        
                        sub_obj = models.Subcategorias.create(
                            categoria_id=cat_id, tipo=tipo_flag, nome=sub['nome'], valor=sub_val_num,
                            consistente=sub_consistente, motivo_inconsistencia=sub_motivo, revisado_usuario=sub_consistente
                        )
                        sub_id = sub_obj.id
                        
                        for item in sub['itens']:
                            desc_completa = item['nome']
                            data_t = None
                            if "(" in desc_completa and ")" in desc_completa:
                                partes = desc_completa.rsplit(" (", 1)
                                desc_f, data_t = partes[0], partes[1].replace(")", "")
                            else:
                                desc_f = desc_completa
                                
                            anexos_esperados = item.get("anexos_count", 0)
                            anexos_baixados = len(item.get("anexos", []))
                            despesa_anexo_valido = not (tipo_flag == "D" and anexos_esperados == 0)
                            
                            trans_consistente, trans_motivo, apto, comp, fornecedor, conta = evaluate_entity_consistency(
                                'transacao', tipo_flag=tipo_flag, desc_completa=desc_completa, desc_f=desc_f,
                                anexos_esperados=anexos_esperados, anexos_baixados=anexos_baixados, despesa_anexo_valido=despesa_anexo_valido
                            )

                            if not trans_consistente:
                                logger.debug(f"    [AVISO CONSISTÊNCIA] Transação '{desc_f}' [{tipo_flag}]: Inconsistente ({trans_motivo})")
                            
                            trans_obj = models.Transacoes.create(
                                subcategoria_id=sub_id, tipo=tipo_flag, data=data_t, descricao=desc_f,
                                valor=parse_currency(item['valor']), apartamento=apto, competencia=comp,
                                fornecedor=fornecedor, conta=conta, anexos=anexos_esperados,
                                consistente=trans_consistente, motivo_inconsistencia=trans_motivo, revisado_usuario=trans_consistente
                            )
                            transacao_id = trans_obj.id

                            for anexo in item.get("anexos", []):
                                temp_path = anexo["temp_path"]
                                nome_orig = anexo["nome_original"]
                                extensao = get_extensao(nome_orig)
                                
                                if os.path.exists(temp_path):
                                    anexo_consistente, anexo_motivo = evaluate_entity_consistency('anexo', extensao=extensao)
                                    
                                    anexo_obj = models.Anexos.create(
                                        transacao_id=transacao_id, caminho_local="", nome_original=nome_orig, extensao=extensao,
                                        consistente=anexo_consistente, motivo_inconsistencia=anexo_motivo, revisado_usuario=anexo_consistente
                                    )
                                    anexo_id = anexo_obj.id
                                    
                                    nome_final = f"{chave_unica}_{cat_id}_{sub_id}_{transacao_id}_{anexo_id}_{nome_orig}"
                                    caminho_relativo = f"anexos/{condominio_id}/{chave_unica}/{nome_final}"
                                    
                                    anexo_obj.caminho_local = caminho_relativo
                                    anexo_obj.save()
                                    
                                    mes_dir = os.path.join(project_root, "anexos", str(condominio_id), chave_unica)
                                    caminho_final = os.path.join(mes_dir, nome_final)
                                    
                                    anexos_para_mover.append({"temp_path": temp_path, "caminho_final": caminho_final})
    except Exception as e:
        logger.error(f"Erro DB {chave_unica}: {e}")
        raise e
        
    return mes_id, anexos_para_mover

# ==========================================
# 4. Orquestrador Principal do Script
# ==========================================

def extract_winker(username, password, wl, start_date_obj, end_date_obj, headless, portal_index=None):
    """
    Fluxo principal de extração web de dados do Winker via Playwright.
    """
    logger.info("Iniciando extração Winker")

    # Inicializa rastreadores para auditoria
    start_time = time.time()
    total_transacoes_lidas = 0
    total_downloads_anexos = 0
    total_downloads_prestacoes = 0
    capturou_condominio = 0
    capturou_inadimplencia = 0
    capturou_membros = 0
    auditoria_id = None
    user_data = {}
    condo_id_extraido = None  # Será preenchido após a extração obrigatória do condomínio
    
    def update_current_audit():
        if auditoria_id is not None:
            duration = time.time() - start_time
            update_auditoria(
                auditoria_id=auditoria_id,
                user_data=user_data,
                downloads_realizados=total_downloads_anexos + total_downloads_prestacoes,
                transacoes_lidas=total_transacoes_lidas,
                tempo_duracao=duration,
                capturou_condominio=capturou_condominio,
                capturou_inadimplencia=capturou_inadimplencia,
                capturou_membros=capturou_membros
            )
            
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()

        def handle_response(response):
            if "api.winker.com.br/v1/me" in response.url:
                try:
                    if response.request.method == "GET" and 200 <= response.status < 300:
                        data = response.json()
                        user_data.update(data)
                except Exception as e:
                    logger.error(f"Erro ao capturar dados do usuário na response: {e}")

        page.on("response", handle_response)

        try:
            # Login no portal
            login_url = f"https://app.winker.com.br/intra/default/login?wl={wl}"
            page.goto(login_url, wait_until="networkidle")
            page.fill("#LoginForm_username", username)
            page.fill("#LoginForm_password", password)
            page.click("#loginform > div.input-group.login-entrar > input")
            
            try:
                page.wait_for_url(lambda url: "/intra" in url, timeout=60000)
            except Exception:
                pass
                
            if "escolherPortal" in page.url:
                if portal_index is not None:
                    idx = int(portal_index) - 1
                    page.locator("#content hgroup > div > table tbody tr").nth(idx).locator("a").first.click()
                else:
                    page.locator("#content hgroup > div > table tbody tr").nth(0).locator("a").first.click()
                
                page.wait_for_url("**/intra", timeout=60000)
            else:
                page.wait_for_url("**/intra", timeout=60000)

            # Inicializa tabelas uma única vez no início
            init_db()

            # Cria registro inicial de auditoria (condominio_id começa como NULL)
            auditoria_id = create_auditoria(start_date_obj.strftime("%Y-%m"), end_date_obj.strftime("%Y-%m"))

            # 1. Extração OBRIGATÓRIA do Condomínio e Corpo Diretivo (Membros da Gestão)
            # A extração do condomínio não é mais condicional: todo scrapper deve preencher
            # a tabela condominio antes de registrar meses, membros ou qualquer dado vinculado.
            try:
                logger.info("Lendo informações do condomínio")
                condo_id_extraido, condo_nome, membros = extract_condominio_and_gestao(page)
                if condo_id_extraido:
                    capturou_condominio = 1
                if membros:
                    capturou_membros = 1

                # 2. Extração parcial de Inadimplência do boleto recente
                data_corte, unidades, valor, administradora, telefone = extract_inadimplencia_boleto(page, context)
                if data_corte:
                    capturou_inadimplencia = 1

                # 3. Salva condomínio e membros no banco de dados
                save_condominio_and_gestao(condo_id_extraido, condo_nome, data_corte, unidades, valor, administradora, telefone, membros)

                # 4. Atualiza condominio_id na auditoria assim que o id é obtido
                update_auditoria_condominio_id(auditoria_id, condo_id_extraido)
                update_current_audit()
            except Exception as ex_condo:
                logger.error(f"Erro ao extrair/salvar dados de gestão e inadimplência: {ex_condo}")

            # 4. Navega para o Balancete
            balancete_url = "https://app.winker.com.br/intra/meuCondominio/balancete"
            page.goto(balancete_url, wait_until="networkidle")
            page.wait_for_selector("iframe[name='pageIframe']", timeout=20000)
            
            iframe = page.frame(name="pageIframe") or page.frame(url=lambda u: "financial-summary" in u)
            if not iframe:
                logger.error("Erro: Não foi possível carregar o iframe do Balancete.")
                return
            iframe.wait_for_load_state("domcontentloaded")
            
            # Atualiza auditoria com dados obtidos (ex: user_data)
            update_current_audit()
            
            # Itera sobre os períodos mensais (chunks)
            chunks = get_date_chunks(start_date_obj, end_date_obj)
            for chunk_start, chunk_end in chunks:
                tab_apresentacao = iframe.locator("super-tab-button:has-text('APRESENTAÇÃO')")
                if "selected" not in (tab_apresentacao.get_attribute("class") or ""):
                    tab_apresentacao.click()
                    iframe.locator("ion-datetime").first.wait_for(state="visible", timeout=15000)
                
                logger.info(f"Filtrando período {chunk_start.strftime('%m/%Y')} a {chunk_end.strftime('%m/%Y')}")
                set_ion_datetime(iframe, 0, chunk_start.strftime("%m"), chunk_start.strftime("%Y"))
                set_ion_datetime(iframe, 1, chunk_end.strftime("%m"), chunk_end.strftime("%Y"))
                time.sleep(5) # Ajustado: Atualização chunk data
                
                processed_months_in_chunk = []
                month_buttons = iframe.locator("button.item.item-block.item-md").all()
                for btn_index in range(len(month_buttons)):
                    current_btn = iframe.locator("button.item.item-block.item-md").nth(btn_index)
                    text = current_btn.inner_text().strip()
                    lines = text.split("\n")
                    if len(lines) >= 3:
                        nome_mes_abbr = lines[0].strip()
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
                        
                        transacoes_lidas = 0
                        detalhes_mes = {"receitas": [], "despesas": []}
                        for tipo in ["Receita", "Despesa"]:
                            val_lado = rec_total_mes if tipo == "Receita" else des_total_mes
                            if val_lado == 0:
                                continue
                            iframe.get_by_role("button", name=tipo, exact=True).click()
                            time.sleep(0.5) # Ajustado: Troca rec/desp
                            
                            categorias = extract_list_from_modal(iframe)
                            for cat in categorias:
                                cat_val_num = parse_currency(cat['valor'])
                                lists_before_cat = iframe.locator("ion-list").count()
                                iframe.locator("ion-list").last.locator("button.item-block, ion-item.item-block").nth(cat['index']).click()
                                wait_for_new_list_and_items(iframe, lists_before_cat, expected_non_zero=(abs(cat_val_num) > 0.01))
                                
                                sub_categorias_lista = extract_list_from_modal(iframe)
                                sub_data_list = []
                                for sub in sub_categorias_lista:
                                    sub_val_num = parse_currency(sub['valor'])
                                    lists_before_sub = iframe.locator("ion-list").count()
                                    iframe.locator("ion-list").last.locator("button.item-block, ion-item.item-block").nth(sub['index']).click()
                                    wait_for_new_list_and_items(iframe, lists_before_sub, expected_non_zero=(abs(sub_val_num) > 0.01))
                                    
                                    itens_finais = extract_list_from_modal(iframe, context)
                                    transacoes_lidas += len(itens_finais)
                                    total_transacoes_lidas += len(itens_finais)

                                    if logger.isEnabledFor(logging.INFO):
                                        sys.stdout.write(f"\r  Processando transações de {nome_mes_abbr}/{ano_item}: {transacoes_lidas} transações lidas...")
                                        sys.stdout.flush()
                                    
                                    sub_data_list.append({
                                        "nome": sub['nome'],
                                        "valor": sub['valor'],
                                        "itens": [{
                                            "nome": i['nome'],
                                            "valor": i['valor'],
                                            "anexos": i.get("anexos", []),
                                            "anexos_count": i.get("anexos_count", 0)
                                        } for i in itens_finais]
                                    })
                                    
                                    close_last_modal(iframe)
                                    
                                detalhes_mes[tipo.lower() + "s"].append({
                                    "nome": cat['nome'], "valor": cat['valor'], "subcategorias": sub_data_list
                                })
                                close_last_modal(iframe)
                                
                        if logger.isEnabledFor(logging.INFO):
                            sys.stdout.write("\n")
                            sys.stdout.flush()
                                
                        try:
                            # 3. Salva no banco de dados e move anexos temporários
                            mes_id, anexos_para_mover = save_extraction_data_to_db(
                                chave_unica, nome_mes_abbr, ano_item, rec_total_mes, des_total_mes, detalhes_mes, project_root,
                                condominio_id=condo_id_extraido
                            )
                            if anexos_para_mover:
                                total_downloads_anexos += len(anexos_para_mover)
                            
                            mes_dir = os.path.join(project_root, "anexos", str(condo_id_extraido), chave_unica)
                            if os.path.exists(mes_dir):
                                shutil.rmtree(mes_dir, ignore_errors=True)
                                
                            if anexos_para_mover:
                                os.makedirs(mes_dir, exist_ok=True)
                                for mov in anexos_para_mover:
                                    t_path = mov["temp_path"]
                                    f_path = mov["caminho_final"]
                                    if os.path.exists(t_path):
                                        try:
                                            os.rename(t_path, f_path)
                                        except Exception as err_move:
                                            logger.error(f"  Erro ao mover anexo {t_path} para {f_path}: {err_move}")
                            
                            # Armazena mes_id (inteiro) junto com chave_unica (usada para dirs de anexos)
                            processed_months_in_chunk.append((mes_num, ano_item, chave_unica, mes_id))
                            update_current_audit()
                        except Exception as e:
                            # A exceção foi tratada internamente em save_extraction_data_to_db
                            pass
                            
                        close_last_modal(iframe)
                
                # 4. Extração de Prestações de Contas no final do chunk
                if processed_months_in_chunk:
                    tab_pc = iframe.locator("super-tab-button:has-text('PRESTAÇÃO DE CONTAS')")
                    if tab_pc.count() > 0:
                        tab_pc.click()
                        try:
                            iframe.locator("button:has-text('VISUALIZAR')").first.wait_for(state="visible", timeout=10000)
                        except Exception:
                            time.sleep(3) # Fallback para carregar a página
                        
                        meses_portugues = {
                            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
                            7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
                        }
                        meses_abbr_map = {
                            1: "JAN", 2: "FEV", 3: "MAR", 4: "ABR", 5: "MAI", 6: "JUN",
                            7: "JUL", 8: "AGO", 9: "SET", 10: "OUT", 11: "NOV", 12: "DEZ"
                        }
                        
                        for mes_num, ano_item, chave_unica, mes_id in processed_months_in_chunk:
                            mes_ext = f"{meses_portugues[mes_num]} {ano_item}"
                            mes_abbr = meses_abbr_map[mes_num]
                            col_locator = iframe.locator("ion-col").filter(has_text=mes_ext).first
                            visualizar_btn = col_locator.locator("button:has-text('VISUALIZAR')")
                            
                            if col_locator.count() > 0 and visualizar_btn.count() > 0:
                                try:
                                    logger.info(f"  Fazendo download da prestação de contas de {mes_abbr}/{ano_item}")
                                    visualizar_btn.click()
                                    
                                    action_sheet_btn = iframe.locator("button.action-sheet-button:has-text('Visualizar')")
                                    action_sheet_btn.wait_for(state="visible", timeout=10000)
                                    
                                    # Intercepta a resposta da API de register-access para obter o token/link direto
                                    created_pages = []
                                    def catch_page(p):
                                        created_pages.append(p)
                                    context.on("page", catch_page)
                                    
                                    try:
                                        with page.expect_response("**/register-access*", timeout=15000) as response_info:
                                            action_sheet_btn.click()
                                        response = response_info.value
                                    finally:
                                        context.remove_listener("page", catch_page)
                                        
                                    # Fecha abas/popups extras criados por essa ação
                                    for cp in created_pages:
                                        try:
                                            cp.close()
                                        except:
                                            pass
                                            
                                    res_data = response.json()
                                    target_url = res_data.get("return", {}).get("document_link", "")
                                    
                                    if target_url and target_url.startswith("http") and "default/login" not in target_url:
                                        mes_dir = os.path.join(project_root, "anexos", str(condo_id_extraido), chave_unica)
                                        default_pdf_name = f"Prestação de contas {mes_ext}"
                                        
                                        # Baixa o arquivo direto na pasta final
                                        temp_path, nome_orig_pdf = download_http_file(
                                            context, target_url, mes_dir,
                                            filename_prefix="", default_filename=default_pdf_name
                                        )
                                        
                                        # Extrai a extensão real
                                        ext_real = get_extensao(nome_orig_pdf) or "pdf"
                                        
                                        # Renomeia para o padrão da prestação de contas do mês
                                        caminho_final = os.path.join(mes_dir, f"{chave_unica}_prestacao_contas.{ext_real}")
                                        if os.path.exists(caminho_final):
                                            os.remove(caminho_final)
                                        os.rename(temp_path, caminho_final)
                                        
                                        caminho_rel = f"anexos/{condo_id_extraido}/{chave_unica}/{chave_unica}_prestacao_contas.{ext_real}"
                                        extensao = ext_real
                                        
                                        # Avalia consistência da prestação de contas de forma centralizada
                                        pc_consistente, pc_motivo = evaluate_entity_consistency('prestacao_contas', sucesso=True)
                                        save_prestacao_contas(mes_id, caminho_rel, nome_orig_pdf, extensao, pc_consistente, pc_motivo)
                                        total_downloads_prestacoes += 1
                                    else:
                                        raise Exception("Não foi possível obter URL final de download (redirecionamento falhou/timeout)")
                                except Exception as err:
                                    logger.error(f"    Erro ao extrair prestação de contas de {mes_ext}: {err}")
                                    pc_consistente, pc_motivo = evaluate_entity_consistency('prestacao_contas', sucesso=False)
                                    save_prestacao_contas(
                                        mes_id, None, None, None, pc_consistente, pc_motivo
                                    )
                            else:
                                logger.warning(f"  Prestação de contas de {mes_ext} não encontrada ou indisponível.")
                                pc_consistente, pc_motivo = evaluate_entity_consistency('prestacao_contas', sucesso=False)
                                save_prestacao_contas(
                                    mes_id, None, None, None, pc_consistente, pc_motivo
                                )
                            
                            # Atualiza auditoria após cada prestação de contas processada e comitada
                            update_current_audit()
                    else:
                        logger.warning("  Aba PRESTAÇÃO DE CONTAS não encontrada no iframe.")
            
            # Salvar dados de auditoria
            update_current_audit()
        except Exception as e:
            logger.error(f"Erro inesperado durante a extração: {e}", exc_info=True)
        finally:
            browser.close()
            # Limpa o diretório temporário de anexos se ele existir
            temp_dir = os.path.join(project_root, "anexos", "temp")
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as err_temp:
                    logger.error(f"Erro ao remover a pasta temporária: {err_temp}")

# ==========================================
# 5. Entrada do Script (CLI)
# ==========================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-file', default='config/dev.config')
    args = parser.parse_args()
    
    config = load_config(args.config_file)
    
    user = config.get("user")
    password = config.get("password")
    wl = config.get("wl", "")
    
    if not user or not password:
        parser.error("O usuário e a senha devem ser fornecidos no arquivo de configuração.")
        
    # Calcula mês atual e mês passado como defaults
    today = datetime.now()
    default_end = today.strftime("%Y-%m")
    
    first_of_this_month = today.replace(day=1)
    last_month_date = first_of_this_month - timedelta(days=1)
    default_start = last_month_date.strftime("%Y-%m")
    
    start_str = config.get("start") or default_start
    end_str = config.get("end") or default_end
    
    s_y, s_m = map(int, start_str.split('-'))
    s_obj = datetime(s_y, s_m, 1)
    e_y, e_m = map(int, end_str.split('-'))
    e_obj = datetime(e_y, e_m, 1)
    
    try:
        extract_winker(user, password, wl, s_obj, e_obj, config.get("headless", False), config.get("portal_index"))
    finally:
        if not config.get("no_wait", False):
            input("\nPressione Enter para continuar...")
