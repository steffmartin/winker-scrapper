import sys
import os
import logging
import json

def setup_logging(level_name="INFO"):
    """
    Configura o logger global do projeto, garantindo consistência no formato 
    e nível de log em todos os scripts.
    """
    level = getattr(logging, level_name.upper(), logging.INFO)
    log = logging.getLogger("winker")
    log.setLevel(level)
    for h in list(log.handlers):
        log.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(message)s'))
    log.addHandler(handler)
    return log

# Instância global para ser importada pelos outros módulos
logger = setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

def load_config(config_path):
    """
    Carrega o arquivo de configuração JSON.
    Aceita caminhos relativos ou absolutos. Se for relativo, considera
    a raiz do projeto como base.
    """
    if not os.path.isabs(config_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        config_path = os.path.join(project_root, config_path)
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")
        
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
        
    # Reconfigura o logger com base no nível do config
    log_level = config.get("log_level", "INFO")
    setup_logging(log_level)
    return config
