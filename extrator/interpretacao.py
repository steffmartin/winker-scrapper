"""Interpretação dos dados e períodos lidos no Winker."""

import re
from datetime import datetime


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

def parse_conta(descricao, contas_list=None):
    """
    Extrai a conta da descrição da transação verificando a lista de contas.
    """
    if not descricao or not contas_list:
        return None
        
    desc_upper = descricao.upper()
    for conta in contas_list:
        if conta.upper() in desc_upper:
            return conta
            
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
