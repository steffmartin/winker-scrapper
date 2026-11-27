"""Leitura dos dados de inadimplência e do boleto."""

import os
import re
import time

import pypdf
from compartilhado.utils import logger
from extrator.arquivos import download_file_from_button
from extrator.interpretacao import parse_currency

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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

def extract_inadimplencia_boleto(page, context, raiz_projeto=None):
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
        
    # Tenta localizar e clicar no botão de filtro se existir
    try:
        btn_filtro = page.locator("#boletos button:has-text('Filtrar')").first
        if btn_filtro.count() > 0 and btn_filtro.is_visible():
            btn_filtro.click()
    except Exception as e:
        logger.debug(f"Botão de filtro não encontrado ou erro ao clicar: {e}")

    try:
        page.wait_for_selector(".list-group-item", timeout=15000)
    except Exception:
        logger.warning("Aviso: Nenhum boleto listado na página de boletos.")
        return None, None, None, administradora, telefone
        
    badge_btn = None

    # Pegar o ÚLTIMO boleto da lista sempre, independente de tags ('Pago', 'Ver boleto', etc).
    loc_ultimo_item = page.locator(".list-group-item").last
    if loc_ultimo_item.count() > 0:
        # Procura por botões/links conhecidos dentro do último item ou fallback para qualquer âncora
        loc_botao = loc_ultimo_item.locator("a.badge, a:has-text('Ver boleto'), a:has-text('Pago'), a").first
        if loc_botao.count() > 0:
            badge_btn = loc_botao
    
    if not badge_btn or badge_btn.count() == 0:
        logger.warning("Aviso: Botão de download/visualização do boleto não encontrado.")
        return None, None, None, administradora, telefone
        
    temp_dir = os.path.join(raiz_projeto or project_root, "anexos", "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # Registra o localizador de confirmação opcional (SweetAlert)
        confirm_btn = page.locator("button.swal2-confirm")
            
        # Chama a função principal de download passando o badge_btn como botão inicial.
        # Ele será clicado e monitorado, e se a confirmação surgir, será automaticamente clicada.
        prefix = f"boleto_{int(time.time())}_"
        temp_path, nome_orig_final = download_file_from_button(
            context, badge_btn, temp_dir,
            filename_prefix=prefix, default_filename="boleto_recente.pdf",
            confirm_locator=confirm_btn
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
