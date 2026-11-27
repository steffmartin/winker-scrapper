"""Leitura de condomínio e sessão do portal Winker."""

import re
from urllib.parse import parse_qs, urlparse

from compartilhado import models
from compartilhado.utils import logger


def extract_condominio_and_gestao(page):
    """
    Navega para a página de informações do condomínio, extrai o ID de segurança,
    o nome do condomínio e os membros da gestão.
    """
    condo_url = "https://app.winker.com.br/intra/condominio/sobre/index"
    page.goto(condo_url, wait_until="networkidle")
    
    # Aguarda o elemento chave carregar
    page.wait_for_selector("div.info_cond_codigo_seguranca strong", timeout=10000)
    
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

def capturar_sessao_api(page):
    """Captura o portal ativo antes de navegar e o JWT disponível na página de boletos."""
    page.wait_for_load_state("networkidle")
    portal_id = page.evaluate("() => window.PORTAL_DATA?.id_portal ?? null")
    if not portal_id:
        match = re.search(r'\bPORTAL_DATA\s*=\s*\{[^}]*\bid_portal\s*:\s*[\'"]?(\d+)', page.content())
        portal_id = match.group(1) if match else None
    page.goto("https://app.winker.com.br/intra/meuCondominio/boleto", wait_until="networkidle")
    token = page.evaluate("() => window.TOKEN_API || null")
    if not token:
        match = re.search(r"\bTOKEN_API\s*=\s*['\"]([^'\"]+)['\"]", page.content())
        token = match.group(1) if match else None
    if not token:
        for frame in page.frames:
            url = urlparse(frame.url)
            if url.hostname == "appweb.winker.com.br":
                token = parse_qs(url.query).get("token", [None])[0]
                if token:
                    break
    return portal_id, token

def extrair_condominio_api(context, token, portal_id):
    """Resolve o código de segurança pelo slug do portal ativo e valida sua identidade."""
    if not str(portal_id or '').isdigit():
        raise ValueError("ID do portal da sessão indisponível")
    if not token:
        raise ValueError("JWT da sessão indisponível")
    headers = {"authorization": token, "accept": "application/json"}
    response = context.request.get("https://api.winker.com.br/v1/portal", headers=headers, timeout=10000)
    if not response.ok:
        raise ValueError("Não foi possível consultar os portais da sessão")
    portais = response.json()
    if not isinstance(portais, list):
        raise ValueError("Resposta de portais inválida")
    matches = [p for p in portais if isinstance(p, dict) and str(p.get('id_portal')) == str(portal_id)]
    if len(matches) != 1:
        raise ValueError("Portal da sessão ausente ou duplicado na API")
    url = urlparse(matches[0].get('url') or '')
    slug = url.path.strip('/')
    if url.scheme != 'https' or url.hostname != 'app.winker.com.br' or not slug or '/' in slug:
        raise ValueError("URL do portal ausente ou inválida")
    response = context.request.post(
        "https://app.winker.com.br/novo/findCondominio",
        data={"cepCondominio": None, "numeroCondominio": None, "codigoSeguranca": slug, "criarConta": 0},
        headers={"accept": "application/json"}, timeout=10000)
    if not response.ok:
        raise ValueError("Busca do condomínio falhou")
    resultado = response.json()
    if isinstance(resultado, list):
        if len(resultado) != 1:
            raise ValueError("Busca do condomínio não retornou um resultado único")
        resultado = resultado[0]
    if not isinstance(resultado, dict) or str(resultado.get('id_condominio')) != str(portal_id):
        raise ValueError("ID do condomínio retornado diverge do portal da sessão ou está ausente")
    codigo = resultado.get('codigo_seguranca')
    if not isinstance(codigo, str) or not codigo.strip():
        raise ValueError("Código de segurança do condomínio ausente")
    membros, administradora, telefone = [], None, None
    try:
        about = context.request.get(f"https://api.winker.com.br/v1/portal/{portal_id}/about", headers=headers, timeout=10000)
        if not about.ok:
            raise ValueError("resposta HTTP sem sucesso")
        users = about.json().get('users') or {}
        manager = users.get('manager') or {}
        if manager.get('name'):
            membros.append({'nome': manager['name'], 'cargo': manager.get('title') or 'Síndico'})
        for member in users.get('boardMembers') or []:
            if member.get('name'):
                grupos = member.get('groups') or []
                membros.append({'nome': member['name'], 'cargo': next((g.get('name') for g in grupos if g.get('name')), 'Membro da Gestão')})
        for provider in users.get('providers') or []:
            if any('administradora' in str(a.get('activitie', '')).lower() for a in provider.get('activities') or []):
                administradora = provider.get('name')
                phone = re.sub(r'\D', '', str(provider.get('phone') or ''))
                telefone = [phone] if phone else None
                break
    except Exception as exc:
        logger.warning("Não foi possível obter a gestão pela API: %s", exc)
    return codigo.strip(), resultado.get('nome') or matches[0].get('name') or 'Condomínio', membros, administradora, telefone


def selecionar_condominio_fallback():
    """
    Lista os condomínios cadastrados na tabela 'condominio' do banco de dados
    para seleção interativa do usuário quando a extração automática falhar.
    Retorna uma tupla (condo_id, condo_nome) ou (None, None) se o usuário optar por desistir.
    """
    try:
        condos = list(models.Condominio.select().order_by(models.Condominio.nome))
    except Exception as e:
        logger.error(f"Erro ao consultar condomínios no banco de dados: {e}")
        condos = []

    if not condos:
        logger.error("Nenhum condomínio cadastrado no banco de dados para seleção de fallback.")
        return None, None

    for idx, c in enumerate(condos, start=1):
        nome_str = c.nome or "Nome não identificado"
        print(f"[{idx}] {nome_str} (ID: {c.id})")
    print("[0] Desistir / Cancelar extração")

    while True:
        try:
            escolha = input("\nDigite o número da opção desejada: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExtração cancelada pelo usuário.")
            return None, None

        if escolha == "0":
            logger.info("Usuário optou por cancelar a extração no fallback de condomínio.")
            return None, None

        if escolha.isdigit():
            num = int(escolha)
            if 1 <= num <= len(condos):
                selecionado = condos[num - 1]
                logger.debug(f"Condomínio selecionado manualmente: {selecionado.nome} (ID: {selecionado.id})")
                return selecionado.id, selecionado.nome

        print(f"Opção inválida! Digite um número de 1 a {len(condos)} ou 0 para desistir.")
