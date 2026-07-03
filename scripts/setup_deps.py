import sys
import subprocess
from utils import logger

def install_dependencies():
    """
    Verifica e instala as dependências necessárias para o projeto.
    Garante que todos os pacotes existam antes dos imports principais.
    """
    packages = ["playwright", "python-dotenv", "pypdf", "peewee", "pywebview"]
    installed_playwright = False
    
    # Prepara flag para ocultar janela do subprocesso no Windows
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
    
    for package in packages:
        try:
            if package == "playwright":
                import playwright
            elif package == "python-dotenv":
                import dotenv
            elif package == "pypdf":
                import pypdf
            elif package == "peewee":
                import peewee
            elif package == "pywebview":
                import webview
        except ImportError:
            logger.info(f"Instalando pacote: {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"], creationflags=creationflags)
            if package == "playwright":
                installed_playwright = True
    
    if installed_playwright:
        try:
            subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)
        except Exception as e:
            logger.warning(f"Aviso: Erro ao tentar instalar navegadores Playwright: {e}")
