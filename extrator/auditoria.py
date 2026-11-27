"""Registro de auditoria e identificação da execução."""
import re
import socket
import subprocess
import sys
import threading
import urllib.request
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger


def get_ip_address():
    result = []
    def lookup():
        result.append(_get_ip_address())
    worker = threading.Thread(target=lookup, daemon=True)
    worker.start()
    worker.join(timeout=2)
    if result and result[0]:
        return result[0]
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(1)
            sock.connect(('8.8.8.8', 80))
            return sock.getsockname()[0] or 'indisponível'
    except OSError:
        return 'indisponível'

def _get_ip_address():
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
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=2, creationflags=creationflags)
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
            data_hora_captura=datetime.now().isoformat(),
            ip=get_ip_address(), mac=get_mac_address(), status='ativa'
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
            downloads_realizados=downloads_realizados,
            transacoes_lidas=transacoes_lidas,
            tempo_duracao=tempo_duracao,
            capturou_condominio=int(capturou_condominio),
            capturou_inadimplencia=int(capturou_inadimplencia),
            capturou_membros=int(capturou_membros)
        ).where(models.Auditoria.id == auditoria_id).execute()
    except Exception as e:
        logger.error(f"Erro ao finalizar auditoria: {e}")
