import os
import sys
import sqlite3
import webview

class Api:
    def test_db_connection(self):
        """
        Método chamado pelo Javascript do Frontend para testar a conexão com o SQLite.
        """
        try:
            # Caminho absoluto para o banco de dados
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, "winker_data.db")
            
            if not os.path.exists(db_path):
                return {"status": "error", "message": f"Erro de conexão: Banco de dados '{db_path}' não encontrado."}
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Testa consulta básica na tabela meses
            cursor.execute("SELECT COUNT(*) FROM meses")
            count = cursor.fetchone()[0]
            conn.close()
            
            return {"status": "success", "message": f"Conectado com sucesso! Encontrados {count} meses no banco de dados."}
        except Exception as e:
            return {"status": "error", "message": f"Erro de conexão: {str(e)}"}

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(script_dir, "dashboard.html")
    
    if not os.path.exists(html_path):
        print(f"Erro: Arquivo HTML '{html_path}' não encontrado!")
        sys.exit(1)
        
    api = Api()
    
    # Cria a janela desktop nativa provida pelo PyWebView
    # Carrega o HTML local e injeta a API Python no objeto window.pywebview.api do Javascript
    webview.create_window(
        title="Winker Scraper Dashboard - Teste de Conexão",
        url=html_path,
        js_api=api,
        width=600,
        height=500,
        resizable=False
    )
    
    # Inicia o loop de eventos da janela do Webview.
    # Ao fechar a janela, o processo de execução do Python é finalizado de forma limpa.
    webview.start()

if __name__ == "__main__":
    main()
