"""Entrada de linha de comando do extrator Winker."""
import argparse
import os
import sys
from datetime import datetime, timedelta

_raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _raiz not in sys.path:
    sys.path.insert(0, _raiz)

from extrator import execucao as _extrator

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config-file', default='compartilhado/config/meu.config')
    args = parser.parse_args()
    
    from compartilhado.utils import load_config
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
        if _extrator.extract_winker(user, password, wl, s_obj, e_obj, config.get("headless", False), config.get("portal_index")) is False:
            raise SystemExit(1)
    finally:
        if not config.get("no_wait", False):
            input("\nPressione Enter para continuar...")


if __name__ == "__main__":
    main()
