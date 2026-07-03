import sys
import os
import logging

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
