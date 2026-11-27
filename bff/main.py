import ctypes
import os
import subprocess
import sys
import json
import calendar
from decimal import Decimal, InvalidOperation
from datetime import datetime

# Mantém os pacotes do projeto acessíveis ao executar o entrypoint legado.
_raiz_importacao = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _raiz_importacao not in sys.path:
    sys.path.insert(0, _raiz_importacao)

# Módulos internos independentes
from compartilhado.utils import logger

# Garantir dependências antes de importar libs externas
from compartilhado.setup_deps import install_dependencies
install_dependencies()

# Dependências externas e modelos
import webview

from compartilhado import models
from bff.api import Api
from bff.validacao import validar_margem_encargos
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)





def main():
    html_content = None
    html_path = None
    
    # 1. Verifica se a base de dados SQLite existe
    db_path = os.path.join(project_root, "compartilhado", "database", "winker_data.db")
    if not os.path.exists(db_path):
        logger.warning("AVISO: Banco de dados não encontrado em compartilhado/database/winker_data.db!")
        html_content = "<html><head><meta charset='utf-8'/><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;padding:40px;background:#1e293b;color:#f8fafc;}h2{color:#eab308;}code{background:#334155;padding:2px 6px;border-radius:4px;font-family:monospace;}ol{line-height:1.6;}</style></head><body><h2>Banco de Dados Não Encontrado</h2><p>Não foi possível localizar o banco de dados local em <code>compartilhado/database/winker_data.db</code>.</p><p><b>Como resolver:</b> Você precisa realizar a extração inicial de dados para criar e popular o banco de dados antes de abrir o painel. Por favor:</p><ol><li>Dê um duplo clique no atalho <b><code>Extrair_Dados.lnk</code></b> (ou <b><code>Extrair_Dados_Headless.lnk</code></b>) na raiz do projeto.</li><li>Aguarde o extrator concluir o processamento de pelo menos um período de transações.</li><li>Após o término da extração com sucesso, abra novamente o dashboard.</li></ol></body></html>"
        logger.info("Carregando aviso de banco de dados ausente...")
    else:
        # 2. Se o banco de dados existe, verifica a existência do frontend compilado
        angular_dist_dir = os.path.join(project_root, "dashboard", "compilados", "browser")
        angular_index = os.path.join(angular_dist_dir, "index.html")
        angular_src_dir = os.path.join(project_root, "dashboard")
        
        if not os.path.exists(angular_index):
            logger.warning("Compilados do frontend não encontrados na pasta 'dashboard/compilados/'.")
            logger.info("Iniciando montagem automática do frontend...")
            
            node_modules_dir = os.path.join(angular_src_dir, "node_modules")
            
            # 1. Verifica se node_modules existe, senão instala
            if not os.path.exists(node_modules_dir):
                logger.info("Pasta node_modules não encontrada. Executando 'npm install'...")
                try:
                    subprocess.check_call(["npm", "install"], cwd=angular_src_dir, shell=True)
                    logger.info("Instalação das dependências concluída com sucesso!")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Erro ao instalar dependências via npm install: {e}")
                    sys.exit(1)
                    
            # 2. Executa a compilação de produção
            logger.info("Executando compilação do Angular ('npm run build')...")
            try:
                subprocess.check_call(["npm", "run", "build"], cwd=angular_src_dir, shell=True)
                logger.info("Compilação concluída com sucesso!")
            except subprocess.CalledProcessError as e:
                logger.error(f"Erro ao compilar o frontend: {e}")
                
        # Verifica novamente se o build foi criado
        if os.path.exists(angular_index):
            html_path = angular_index
            logger.info(f"Carregando interface Angular compilada de: {html_path}")
        else:
            html_path = os.path.join(project_root, "dashboard.html")
            if not os.path.exists(html_path):
                html_content = "<html><head><meta charset='utf-8'/><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;padding:40px;background:#1e293b;color:#f8fafc;}h2{color:#f43f5e;}code{background:#334155;padding:2px 6px;border-radius:4px;font-family:monospace;}</style></head><body><h2>Erro de Inicialização do Dashboard</h2><p>Não foi possível encontrar ou compilar a interface do dashboard.</p><p><b>Possível Solução:</b> O sistema precisa do <b>Node.js</b> instalado para compilar o frontend Angular pela primeira vez. Por favor:</p><ol><li>Instale o Node.js (recomendado v18 ou superior).</li><li>Abra um terminal na pasta <code>dashboard/</code> do projeto e execute:</li><pre><code>npm install<br/>npm run build</code></pre><li>Após a compilação, reinicie este aplicativo.</li></ol></body></html>"
            logger.warning(f"Interface Angular não disponível. Carregando fallback: {html_path}")
        


    api = Api()

    # Cria a splash screen como janela separada (banner de carregamento)
    splash_window = None
    if html_content is None:
        splash_html_path = None
        candidates = [
            os.path.join(project_root, "dashboard", "compilados", "browser", "splash.html"),
            os.path.join(project_root, "dashboard", "public", "splash.html")
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                splash_html_path = candidate
                break
        
        if splash_html_path:
            # Calcula posição centralizada na tela
            splash_w, splash_h = 480, 350
            scr_w, scr_h = 1920, 1080
            try:
                user32 = ctypes.windll.user32
                scr_w = user32.GetSystemMetrics(0)
                scr_h = user32.GetSystemMetrics(1)
            except Exception:
                pass
            splash_x = (scr_w - splash_w) // 2
            splash_y = (scr_h - splash_h) // 2
            
            splash_window = webview.create_window(
                title="",
                url=splash_html_path,
                width=splash_w,
                height=splash_h,
                x=splash_x,
                y=splash_y,
                resizable=False,
                frameless=True,
                on_top=True,
                background_color='#E9F2FC'
            )
            api._splash_window = splash_window
            logger.info("Splash screen criada.")
    
    # Cria a janela desktop nativa provida pelo PyWebView
    if html_content is not None:
        # Janela de erro — exibe imediatamente, sem splash
        window = webview.create_window(
            title="Dashboard",
            html=html_content,
            js_api=api,
            width=1280,
            height=800,
            resizable=True,
            maximized=True
        )
    else:
        # Janela Angular — inicia oculta até o tema ser aplicado
        window = webview.create_window(
            title="Dashboard",
            url=html_path,
            js_api=api,
            width=1280,
            height=800,
            resizable=True,
            maximized=True,
            hidden=True
        )
    
    api._main_window = window

    def on_closing():
        try:
            if api.prefs_cache:
                api.salvar_preferencias({
                    'modo_escuro': 1 if api.prefs_cache.get('darkTheme') else 0,
                    'cor_primaria': api.prefs_cache.get('primary'),
                    'cor_superficie': api.prefs_cache.get('surface'),
                    'tema_preset': api.prefs_cache.get('preset'),
                    'modo_menu': api.prefs_cache.get('menuMode')
                })
        except Exception as e:
            logger.error(f"Erro ao salvar preferências no encerramento: {e}")

    window.events.closing += on_closing
    
    # Inicia o loop de eventos
    webview.start()

if __name__ == "__main__":
    main()
