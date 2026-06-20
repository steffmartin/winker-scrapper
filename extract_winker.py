import os
import sys
import subprocess
import argparse
import time
from datetime import datetime, timedelta
import sqlite3
import re
import shutil
import json

def install_dependencies():
    """
    Verifica e instala as dependências necessárias (playwright, python-dotenv).
    Também garante que os binários do navegador Playwright estejam instalados.
    """
    print("Verificando dependências...")
    
    packages = ["playwright", "python-dotenv"]
    
    for package in packages:
        try:
            if package == "playwright":
                import playwright
            elif package == "python-dotenv":
                import dotenv
        except ImportError:
            print(f"Instalando pacote: {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])
    
    try:
        print("Garantindo que o Chromium do Playwright está instalado...")
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        print(f"Aviso: Erro ao tentar instalar navegadores Playwright: {e}")

# Instala as dependências antes de realizar os imports principais
install_dependencies()

from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Carrega variáveis de ambiente do .env localizado na pasta do script
script_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(script_dir, '.env'))

def parse_currency(val_str):
    """
    Converte uma string de moeda (ex: 'R$ 1.234,56' ou '- R$ 10,00') para float.
    """
    if not val_str: return 0.0
    # Remove R$, espaços, pontos de milhar e troca vírgula por ponto
    # Trata também o sinal de negativo que às vezes vem separado por espaço
    clean_val = val_str.replace("R$", "").replace(".", "").replace(",", ".").replace(" ", "").strip()
    try:
        return float(clean_val)
    except:
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

def parse_fornecedor(descricao):
    """
    Extrai o fornecedor da descrição de uma despesa.
    """
    if not descricao:
        return None
    
    desc_upper = descricao.upper()
    if "TARIFA COBRANÇA" in desc_upper or "TARIFA COBRANCA" in desc_upper:
        return "SICOOB"
        
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

def download_anexos(loc, context):
    """
    Identifica todos os botões de anexo de uma transação, realiza o download
    de cada arquivo (PDF, imagem, etc.), garante o fechamento de todas as abas
    e retorna uma tupla (downloaded_files, count) com os arquivos baixados e o total.
    """
    from urllib.parse import urlparse, parse_qs
    
    attach_buttons = loc.locator("button.button-docs:has(ion-icon[name='attach'])")
    count = attach_buttons.count()
    if count == 0:
        return [], 0
        
    downloaded_files = []
    
    for idx in range(count):
        btn = attach_buttons.nth(idx)
        btn_text = btn.inner_text().strip()
        
        # Extrai o nome do arquivo de dentro dos parênteses
        match_name = re.search(r"\(([^)]+)\)", btn_text)
        nome_original = match_name.group(1).strip() if match_name else btn_text
        
        # Corta query string residual (como ? ou &) do texto do botão
        nome_original = re.split(r'[?&]', nome_original)[0]
        
        # Higieniza o nome de arquivo para o Windows (remove caracteres inválidos e comerciais)
        nome_original = re.sub(r'[\\/*?:"<>|&]', "", nome_original)
        if not nome_original:
            nome_original = f"documento_{int(time.time())}"
            
        new_page = None
        try:
            # Clicar e esperar abertura da nova aba (timeout de 10s)
            with context.expect_page(timeout=10000) as new_page_info:
                btn.click()
            new_page = new_page_info.value
            
            # Aguarda a URL mudar de about:blank para a URL real (timeout de 10s)
            target_url = ""
            start_time = time.time()
            while time.time() - start_time < 10.0:
                target_url = new_page.url
                if target_url and target_url.startswith("http"):
                    break
                time.sleep(0.05)
            
            if target_url and target_url.startswith("http"):
                # Se for o visualizador PDF.js, extrai a URL real do PDF do parâmetro 'file'
                if "viewer.html" in target_url and "file=" in target_url:
                    parsed = urlparse(target_url)
                    query_params = parse_qs(parsed.query)
                    file_param = query_params.get("file", [None])[0]
                    if file_param:
                        target_url = file_param
                
                # Efetua o download usando a mesma sessão do navegador
                response = context.request.get(target_url)
                if response.status == 200:
                    # Determina a extensão correta
                    ext = ""
                    parsed_path = urlparse(target_url).path
                    # Limpa qualquer query parameter residual que tenha ficado no path (ex: &H...)
                    parsed_path_clean = re.split(r'[?&]', parsed_path)[0]
                    _, url_ext = os.path.splitext(parsed_path_clean)
                    if url_ext and len(url_ext) <= 5 and url_ext.startswith("."):
                        ext = url_ext.lower()
                    
                    if not ext:
                        content_type = response.headers.get("content-type", "").lower()
                        if "application/pdf" in content_type:
                            ext = ".pdf"
                        elif "image/jpeg" in content_type or "image/jpg" in content_type:
                            ext = ".jpg"
                        elif "image/png" in content_type:
                            ext = ".png"
                        elif "image/gif" in content_type:
                            ext = ".gif"
                    
                    if not ext:
                        ext = ".pdf" # Default
                        
                    # Remove extensões quebradas ou truncadas do nome_original antes de fixar
                    nome_original_limpo = nome_original
                    name_base, current_ext = os.path.splitext(nome_original)
                    if current_ext and 2 <= len(current_ext) <= 5:
                        nome_original_limpo = name_base
                            
                    nome_original = nome_original_limpo + ext
                    
                    script_dir = os.path.dirname(os.path.abspath(__file__))
                    temp_dir = os.path.join(script_dir, "anexos", "temp")
                    os.makedirs(temp_dir, exist_ok=True)
                    
                    temp_filename = f"temp_{int(time.time() * 1000)}_{idx}_{nome_original}"
                    temp_path = os.path.join(temp_dir, temp_filename)
                    
                    with open(temp_path, "wb") as f:
                        f.write(response.body())
                        
                    downloaded_files.append({
                        "temp_path": temp_path,
                        "nome_original": nome_original
                    })
        except Exception as e:
            print(f"Erro ao baixar anexo {nome_original}: {e}")
        finally:
            if new_page:
                try:
                    new_page.close()
                except:
                    pass
                    
    return downloaded_files, count

def init_db(db_path="winker_data.db"):
    """
    Inicializa o banco de dados SQLite com a estrutura hierárquica e tipos reais.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meses (
            id TEXT PRIMARY KEY, 
            exibicao TEXT,
            receita_total REAL,
            despesa_total REAL,
            consistente INTEGER DEFAULT 1,
            motivo_inconsistencia TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mes_id TEXT,
            tipo TEXT, 
            nome TEXT,
            valor REAL,
            consistente INTEGER DEFAULT 1,
            motivo_inconsistencia TEXT,
            FOREIGN KEY (mes_id) REFERENCES meses(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subcategorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria_id INTEGER,
            tipo TEXT, 
            nome TEXT,
            valor REAL,
            consistente INTEGER DEFAULT 1,
            motivo_inconsistencia TEXT,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subcategoria_id INTEGER,
            tipo TEXT, 
            data TEXT,
            descricao TEXT,
            valor REAL,
            apartamento TEXT,
            competencia TEXT,
            fornecedor TEXT,
            anexos INTEGER DEFAULT 0,
            consistente INTEGER DEFAULT 1,
            motivo_inconsistencia TEXT,
            FOREIGN KEY (subcategoria_id) REFERENCES subcategorias(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS anexos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transacao_id INTEGER,
            caminho_local TEXT,
            nome_original TEXT,
            consistente INTEGER DEFAULT 1,
            motivo_inconsistencia TEXT,
            FOREIGN KEY (transacao_id) REFERENCES transacoes(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    return conn

def set_ion_datetime(iframe, selector_index, target_month, target_year):
    """
    Interage com o componente ion-datetime selecionando mês e ano.
    """
    datetime_elements = iframe.locator("ion-datetime").all()
    if len(datetime_elements) <= selector_index:
        return False

    print(f"Abrindo seletor de data {'inicial' if selector_index == 0 else 'final'} ({target_month}/{target_year})...")
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

def get_date_chunks(start_date_obj, end_date_obj):
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

def extract_list_from_modal(iframe, context=None):
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
            if label_el.count() == 0: continue
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
            import traceback
            print(f"Erro em extract_list_from_modal no item {i}: {e}")
            traceback.print_exc()
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

def extract_winker(username, password, condo, start_date_obj, end_date_obj, headless):
    print(f"Iniciando extração Winker (Condo: {condo})...")
    all_data = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        try:
            login_url = f"https://app.winker.com.br/intra/default/login?wl={condo}"
            page.goto(login_url, wait_until="networkidle")
            page.fill("#LoginForm_username", username)
            page.fill("#LoginForm_password", password)
            page.click("#loginform > div.input-group.login-entrar > input")
            page.wait_for_url("**/intra", timeout=60000)
            
            balancete_url = "https://app.winker.com.br/intra/meuCondominio/balancete"
            page.goto(balancete_url, wait_until="networkidle")
            page.wait_for_selector("iframe[name='pageIframe']", timeout=20000)
            
            iframe = page.frame(name="pageIframe") or page.frame(url=lambda u: "financial-summary" in u)
            if not iframe: return
            iframe.wait_for_load_state("domcontentloaded")
            
            tab_apresentacao = iframe.locator("super-tab-button:has-text('APRESENTAÇÃO')")
            if "selected" not in (tab_apresentacao.get_attribute("class") or ""):
                tab_apresentacao.click()
                iframe.locator("ion-datetime").first.wait_for(state="visible", timeout=15000)
                
            chunks = get_date_chunks(start_date_obj, end_date_obj)
            for i, (chunk_start, chunk_end) in enumerate(chunks):
                set_ion_datetime(iframe, 0, chunk_start.strftime("%m"), chunk_start.strftime("%Y"))
                set_ion_datetime(iframe, 1, chunk_end.strftime("%m"), chunk_end.strftime("%Y"))
                time.sleep(5) # Ajustado: Atualização chunk data
                
                month_buttons = iframe.locator("button.item.item-block.item-md").all()
                for btn_index, btn in enumerate(month_buttons):
                    current_btn = iframe.locator("button.item.item-block.item-md").nth(btn_index)
                    text = current_btn.inner_text().strip()
                    lines = text.split("\n")
                    if len(lines) >= 3:
                        nome_mes_abbr = lines[0].strip()
                        meses_map_reverso = {"JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6, "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12}
                        mes_num = meses_map_reverso.get(nome_mes_abbr)
                        if not mes_num: continue
                        ano_item = chunk_start.year if mes_num >= chunk_start.month else chunk_end.year
                        chave_unica = f"{ano_item}{mes_num:02d}"
                        
                        rec_total_mes = parse_currency(lines[1].strip())
                        des_total_mes = parse_currency(lines[2].strip())
                        if abs(rec_total_mes) < 0.01 and abs(des_total_mes) < 0.01:
                            print(f"  Pulo {nome_mes_abbr}/{ano_item} (Vazio).")
                            continue

                        print(f"  Processando {nome_mes_abbr}/{ano_item}...")
                        lists_before_month = iframe.locator("ion-list").count()
                        current_btn.click()
                        wait_for_new_list_and_items(iframe, lists_before_month, expected_non_zero=(abs(rec_total_mes) > 0.01 or abs(des_total_mes) > 0.01))
                        
                        detalhes_mes = {"receitas": [], "despesas": []}
                        for tipo in ["Receita", "Despesa"]:
                            val_lado = rec_total_mes if tipo == "Receita" else des_total_mes
                            if val_lado == 0: continue
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
                                    
                                    lists_before_close = iframe.locator("ion-list").count()
                                    iframe.get_by_role("button", name="close").last.click()
                                    wait_for_list_close(iframe, lists_before_close)
                                    
                                detalhes_mes[tipo.lower() + "s"].append({"nome": cat['nome'], "valor": cat['valor'], "subcategorias": sub_data_list})
                                lists_before_close = iframe.locator("ion-list").count()
                                iframe.get_by_role("button", name="close").last.click()
                                wait_for_list_close(iframe, lists_before_close)
                                
                        db_conn = init_db()
                        db_cursor = db_conn.cursor()
                        anexos_para_mover = []
                        try:
                            db_cursor.execute("BEGIN")
                            db_cursor.execute("DELETE FROM meses WHERE id = ?", (chave_unica,))
                            
                            # Realiza a análise de consistência em memória do mês
                            soma_cat_rec = sum(parse_currency(cat['valor']) for cat in detalhes_mes["receitas"])
                            soma_cat_desp = sum(parse_currency(cat['valor']) for cat in detalhes_mes["despesas"])
                            
                            mes_rec_ok = abs(rec_total_mes - soma_cat_rec) < 0.01
                            mes_desp_ok = abs(des_total_mes - soma_cat_desp) < 0.01
                            mes_consistente = 1 if (mes_rec_ok and mes_desp_ok) else 0
                            
                            mes_motivo = None
                            if not mes_consistente:
                                print(f"  [AVISO CONSISTÊNCIA] Inconsistência no Mês {nome_mes_abbr}/{ano_item}:")
                                print(f"    - Receitas: Total informado = R$ {rec_total_mes:.2f} | Soma categorias = R$ {soma_cat_rec:.2f}")
                                print(f"    - Despesas: Total informado = R$ {des_total_mes:.2f} | Soma categorias = R$ {soma_cat_desp:.2f}")
                                mes_reasons = []
                                if not mes_rec_ok:
                                    mes_reasons.append("Divergência em receitas")
                                if not mes_desp_ok:
                                    mes_reasons.append("Divergência em despesas")
                                if not mes_reasons:
                                    mes_reasons.append("Divergência em receitas ou despesas")
                                mes_motivo = json.dumps(mes_reasons, ensure_ascii=False)
                            
                            db_cursor.execute("INSERT INTO meses (id, exibicao, receita_total, despesa_total, consistente, motivo_inconsistencia) VALUES (?, ?, ?, ?, ?, ?)", (chave_unica, f"{nome_mes_abbr}/{ano_item}", rec_total_mes, des_total_mes, mes_consistente, mes_motivo))
                            
                            for t_key in ["receitas", "despesas"]:
                                tipo_flag = "R" if t_key == "receitas" else "D"
                                for cat in detalhes_mes[t_key]:
                                    cat_val_num = parse_currency(cat['valor'])
                                    soma_sub = sum(parse_currency(sub['valor']) for sub in cat['subcategorias'])
                                    cat_consistente = 1 if abs(cat_val_num - soma_sub) < 0.01 else 0
                                    
                                    cat_motivo = None
                                    if not cat_consistente:
                                        print(f"  [AVISO CONSISTÊNCIA] Categoria '{cat['nome']}': Valor informado = R$ {cat_val_num:.2f} | Soma subcategorias = R$ {soma_sub:.2f}")
                                        cat_motivo = json.dumps(["Soma das subcategorias difere do total da categoria"], ensure_ascii=False)
                                        
                                    db_cursor.execute("INSERT INTO categorias (mes_id, tipo, nome, valor, consistente, motivo_inconsistencia) VALUES (?, ?, ?, ?, ?, ?)", (chave_unica, tipo_flag, cat['nome'], cat_val_num, cat_consistente, cat_motivo))
                                    cat_id = db_cursor.lastrowid
                                    
                                    for sub in cat['subcategorias']:
                                        sub_val_num = parse_currency(sub['valor'])
                                        soma_itens = sum(parse_currency(item['valor']) for item in sub['itens'])
                                        sub_consistente = 1 if abs(sub_val_num - soma_itens) < 0.01 else 0
                                        
                                        sub_motivo = None
                                        if not sub_consistente:
                                            print(f"  [AVISO CONSISTÊNCIA] Subcategoria '{sub['nome']}': Valor informado = R$ {sub_val_num:.2f} | Soma transações = R$ {soma_itens:.2f}")
                                            sub_motivo = json.dumps(["Soma das transações difere do total da subcategoria"], ensure_ascii=False)
                                            
                                        db_cursor.execute("INSERT INTO subcategorias (categoria_id, tipo, nome, valor, consistente, motivo_inconsistencia) VALUES (?, ?, ?, ?, ?, ?)", (cat_id, tipo_flag, sub['nome'], sub_val_num, sub_consistente, sub_motivo))
                                        sub_id = db_cursor.lastrowid
                                        
                                        for item in sub['itens']:
                                            desc_completa = item['nome']
                                            apto, comp = (None, None)
                                            fornecedor = None
                                            data_t = None
                                            if "(" in desc_completa and ")" in desc_completa:
                                                partes = desc_completa.rsplit(" (", 1)
                                                desc_f, data_t = partes[0], partes[1].replace(")", "")
                                            else: desc_f = desc_completa
                                            
                                            trans_consistente = 1
                                            fields_ok = True
                                            if tipo_flag == "R":
                                                apto, comp = parse_receita_info(desc_completa)
                                                if not (apto and apto.strip() and comp and comp.strip()):
                                                    fields_ok = False
                                            elif tipo_flag == "D":
                                                fornecedor = parse_fornecedor(desc_f)
                                                if not (fornecedor and fornecedor.strip()):
                                                    fields_ok = False
                                                
                                            anexos_esperados = item.get("anexos_count", 0)
                                            anexos_baixados = len(item.get("anexos", []))
                                            anexos_ok = (anexos_esperados == anexos_baixados)
                                            
                                            if not (fields_ok and anexos_ok):
                                                trans_consistente = 0
                                                
                                            trans_motivo = None
                                            if not trans_consistente:
                                                reasons = []
                                                if tipo_flag == "R":
                                                    if not (apto and apto.strip()):
                                                        reasons.append("Apartamento não identificado")
                                                    if not (comp and comp.strip()):
                                                        reasons.append("Competência não identificada")
                                                elif tipo_flag == "D":
                                                    if not (fornecedor and fornecedor.strip()):
                                                        reasons.append("Fornecedor não identificado")
                                                if not anexos_ok:
                                                    reasons.append("Quantidade de anexos divergente")
                                                if not reasons:
                                                    reasons.append("Dados da transação inconsistentes")
                                                trans_motivo = json.dumps(reasons, ensure_ascii=False)
                                                print(f"  [AVISO CONSISTÊNCIA] Transação '{desc_f}' [{tipo_flag}]: Inconsistente ({' | '.join(reasons)})")
                                                
                                            db_cursor.execute("INSERT INTO transacoes (subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (sub_id, tipo_flag, data_t, desc_f, parse_currency(item['valor']), apto, comp, fornecedor, anexos_esperados, trans_consistente, trans_motivo))
                                            transacao_id = db_cursor.lastrowid
                                            
                                            for anexo in item.get("anexos", []):
                                                temp_path = anexo["temp_path"]
                                                nome_orig = anexo["nome_original"]
                                                
                                                if os.path.exists(temp_path):
                                                    # Anexo consistente se contiver extensão (2 a 5 caracteres alfanuméricos)
                                                    anexo_consistente = 1 if re.search(r"\.[a-zA-Z0-9]{2,5}$", nome_orig) else 0
                                                    
                                                    anexo_motivo = None
                                                    if not anexo_consistente:
                                                        anexo_motivo = json.dumps(["Extensão de arquivo inválida ou ausente"], ensure_ascii=False)
                                                        
                                                    db_cursor.execute(
                                                        "INSERT INTO anexos (transacao_id, caminho_local, nome_original, consistente, motivo_inconsistencia) VALUES (?, ?, ?, ?, ?)",
                                                        (transacao_id, "", nome_orig, anexo_consistente, anexo_motivo)
                                                    )
                                                    anexo_id = db_cursor.lastrowid
                                                    
                                                    nome_final = f"{chave_unica}_{cat_id}_{sub_id}_{transacao_id}_{anexo_id}_{nome_orig}"
                                                    caminho_relativo = f"anexos/{chave_unica}/{nome_final}"
                                                    
                                                    db_cursor.execute(
                                                        "UPDATE anexos SET caminho_local = ? WHERE id = ?",
                                                        (caminho_relativo, anexo_id)
                                                    )
                                                    
                                                    script_dir = os.path.dirname(os.path.abspath(__file__))
                                                    mes_dir = os.path.join(script_dir, "anexos", chave_unica)
                                                    caminho_final = os.path.join(mes_dir, nome_final)
                                                    
                                                    anexos_para_mover.append({
                                                        "temp_path": temp_path,
                                                        "caminho_final": caminho_final
                                                    })
                            db_conn.commit()
                            
                            # Após o commit com sucesso, remove a pasta antiga e move os novos anexos
                            script_dir = os.path.dirname(os.path.abspath(__file__))
                            mes_dir = os.path.join(script_dir, "anexos", chave_unica)
                            if os.path.exists(mes_dir):
                                print(f"  Removendo diretório de anexos antigo: {mes_dir}")
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
                                            print(f"  Erro ao mover anexo {t_path} para {f_path}: {err_move}")
                        except Exception as e:
                            db_conn.rollback()
                            print(f"Erro DB {chave_unica}: {e}")
                        finally: db_conn.close()
                        lists_before_close = iframe.locator("ion-list").count()
                        iframe.get_by_role("button", name="close").last.click()
                        wait_for_list_close(iframe, lists_before_close)
        except Exception as e: print(f"Erro: {e}")
        finally: browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--user', default=None)
    parser.add_argument('--password', default=None)
    parser.add_argument('--condo', default=None)
    parser.add_argument('--start', default=None)
    parser.add_argument('--end', default=None)
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--no-wait', action='store_true')
    args = parser.parse_args()
    
    # Prioridade para os argumentos de linha de comando, caindo para as env vars
    user = args.user or os.environ.get("WINKER_USER")
    password = args.password or os.environ.get("WINKER_PASSWORD")
    condo = args.condo or os.environ.get("WINKER_CONDO") or "gosuen"
    
    if not user or not password:
        parser.error("O usuário e a senha devem ser fornecidos via argumentos (--user/--password) ou variáveis de ambiente (WINKER_USER/WINKER_PASSWORD) no arquivo .env.")
        
    # Calcula mês atual e mês passado como defaults
    today = datetime.now()
    default_end = today.strftime("%Y-%m")
    
    first_of_this_month = today.replace(day=1)
    last_month_date = first_of_this_month - timedelta(days=1)
    default_start = last_month_date.strftime("%Y-%m")
    
    start_str = args.start if args.start else default_start
    end_str = args.end if args.end else default_end
    
    s_y, s_m = map(int, start_str.split('-'))
    s_obj = datetime(s_y, s_m, 1)
    e_y, e_m = map(int, end_str.split('-'))
    e_obj = datetime(e_y, e_m, 1)
    
    try:
        extract_winker(user, password, condo, s_obj, e_obj, args.headless)
    finally:
        if not args.no_wait:
            input("\nPressione Enter para continuar...")
