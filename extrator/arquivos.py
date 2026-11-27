"""Downloads de documentos e anexos extraídos do portal."""

import os
import re
import time
from urllib.parse import parse_qs, unquote, urlparse

from compartilhado.utils import logger

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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

def download_file_from_button(context, btn, dest_dir, filename_prefix="", default_filename="", confirm_locator=None):
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
            if confirm_locator and confirm_locator.is_visible():
                try:
                    confirm_locator.click()
                    confirm_locator = None
                except Exception:
                    pass

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

def download_anexos(loc, context, raiz_projeto=None):
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
    temp_dir = os.path.join(raiz_projeto or project_root, "anexos", "temp")
    
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
