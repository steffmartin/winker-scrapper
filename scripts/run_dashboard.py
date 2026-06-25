import os
import sys
import sqlite3
import webview
import subprocess
import argparse

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

class Api:
    def __init__(self, condo_id=None):
        self.condo_id = condo_id
        self.db_path = self._get_db_path()
        self.init_error = None
        
        if not os.path.exists(self.db_path):
            self.init_error = "Banco de dados não encontrado."
        else:
            if not self.condo_id:
                self._initialize_default_condo_id()
                
            if not self.condo_id:
                self.init_error = "Nenhum condomínio definido ou encontrado no banco."

    def _initialize_default_condo_id(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM condominio LIMIT 1")
            row = cursor.fetchone()
            if row:
                self.condo_id = row[0]
            conn.close()
        except Exception:
            pass

    def get_condominio(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
            
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM condominio WHERE id = ?", (self.condo_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {"status": "success", "data": dict(row)}
            else:
                return {"status": "error", "message": "Condomínio não encontrado."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _get_db_path(self):
        return os.path.join(project_root, "database", "winker_data.db")

def main():
    html_content = None
    html_path = None
    
    # 1. Verifica se a base de dados SQLite existe
    db_path = os.path.join(project_root, "database", "winker_data.db")
    if not os.path.exists(db_path):
        print("AVISO: Banco de dados não encontrado em database/winker_data.db!")
        html_content = "<html><head><meta charset='utf-8'/><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;padding:40px;background:#1e293b;color:#f8fafc;}h2{color:#eab308;}code{background:#334155;padding:2px 6px;border-radius:4px;font-family:monospace;}ol{line-height:1.6;}</style></head><body><h2>Banco de Dados Não Encontrado</h2><p>Não foi possível localizar o banco de dados local em <code>database/winker_data.db</code>.</p><p><b>Como resolver:</b> Você precisa realizar a extração inicial de dados para criar e popular o banco de dados antes de abrir o painel. Por favor:</p><ol><li>Dê um duplo clique no atalho <b><code>Extrair_Dados.lnk</code></b> (ou <b><code>Extrair_Dados_Headless.lnk</code></b>) na raiz do projeto.</li><li>Aguarde o extrator concluir o processamento de pelo menos um período de transações.</li><li>Após o término da extração com sucesso, abra novamente o dashboard.</li></ol></body></html>"
        print("Carregando aviso de banco de dados ausente...")
    else:
        # 2. Se o banco de dados existe, verifica a existência do frontend compilado
        angular_index = os.path.join(project_root, "compilados", "browser", "index.html")
        if not os.path.exists(angular_index):
            print("Compilados do frontend não encontrados na pasta 'compilados/'.")
            print("Iniciando montagem automática do frontend...")
            
            dashboard_dir = os.path.join(project_root, "dashboard")
            node_modules_dir = os.path.join(dashboard_dir, "node_modules")
            
            # 1. Verifica se node_modules existe, senão instala
            if not os.path.exists(node_modules_dir):
                print("Pasta node_modules não encontrada. Executando 'npm install'...")
                try:
                    subprocess.run("npm install", cwd=dashboard_dir, shell=True, check=True)
                    print("Instalação das dependências concluída com sucesso!")
                except Exception as e:
                    print(f"Erro ao instalar dependências via npm install: {e}")
                    
            # 2. Executa a compilação de produção
            print("Executando compilação do Angular ('npm run build')...")
            try:
                subprocess.run("npm run build", cwd=dashboard_dir, shell=True, check=True)
                print("Compilação concluída com sucesso!")
            except Exception as e:
                print(f"Erro ao compilar o frontend: {e}")
                
        # Verifica novamente se o build foi criado
        if os.path.exists(angular_index):
            html_path = angular_index
            print(f"Carregando interface Angular compilada de: {html_path}")
        else:
            html_path = os.path.join(project_root, "dashboard.html")
            if not os.path.exists(html_path):
                # Fallback inline amigável em HTML para exibir instruções se o Node.js não estiver no PATH
                html_content = "<html><head><meta charset='utf-8'/><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;padding:40px;background:#1e293b;color:#f8fafc;}h2{color:#f43f5e;}code{background:#334155;padding:2px 6px;border-radius:4px;font-family:monospace;}</style></head><body><h2>Erro de Inicialização do Dashboard</h2><p>Não foi possível encontrar ou compilar a interface do dashboard.</p><p><b>Possível Solução:</b> O sistema precisa do <b>Node.js</b> instalado para compilar o frontend Angular pela primeira vez. Por favor:</p><ol><li>Instale o Node.js (recomendado v18 ou superior).</li><li>Abra um terminal na pasta <code>dashboard/</code> do projeto e execute:</li><pre><code>npm install<br/>npm run build</code></pre><li>Após a compilação, reinicie este aplicativo.</li></ol></body></html>"
            print(f"Interface Angular não disponível. Carregando fallback: {html_path}")
        
    parser = argparse.ArgumentParser()
    parser.add_argument('--condo-id', help='ID do condomínio a ser carregado', default=None)
    args = parser.parse_args()

    api = Api(condo_id=args.condo_id)
    
    # Cria a janela desktop nativa provida pelo PyWebView
    if html_content is not None:
        webview.create_window(
            title="Dashboard",
            html=html_content,
            js_api=api,
            width=1280,
            height=800,
            resizable=True,
            maximized=True
        )
    else:
        webview.create_window(
            title="Dashboard",
            url=html_path,
            js_api=api,
            width=1280,
            height=800,
            resizable=True,
            maximized=True
        )
    
    # Inicia o loop de eventos
    webview.start()

if __name__ == "__main__":
    main()
