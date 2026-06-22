import os
import sys
import sqlite3
import webview
import subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

class Api:
    def test_db_connection(self):
        """
        Testa a conexão com o banco de dados.
        """
        try:
            db_path = self._get_db_path()
            if not os.path.exists(db_path):
                return {"status": "error", "message": f"Erro de conexão: Banco de dados '{db_path}' não encontrado."}
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM meses")
            count = cursor.fetchone()[0]
            conn.close()
            return {"status": "success", "message": f"Conectado com sucesso! Encontrados {count} meses no banco de dados."}
        except Exception as e:
            return {"status": "error", "message": f"Erro de conexão: {str(e)}"}

    def get_condominio_info(self):
        """
        Retorna informações do condomínio.
        """
        try:
            db_path = self._get_db_path()
            if not os.path.exists(db_path):
                return {"status": "error", "message": "Banco de dados não encontrado."}
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM condominio LIMIT 1")
            row = cursor.fetchone()
            conn.close()
            if row:
                return {"status": "success", "data": dict(row)}
            else:
                return {"status": "success", "data": None}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_monthly_tree(self, mes_id):
        """
        Retorna a árvore hierárquica completa para um determinado mês (mes_id).
        """
        try:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 1. Buscar o mês
            cursor.execute("SELECT * FROM meses WHERE id = ?", (mes_id,))
            mes_row = cursor.fetchone()
            if not mes_row:
                conn.close()
                return {"status": "error", "message": f"Mês {mes_id} não encontrado."}
            mes_dict = dict(mes_row)
            
            # 2. Buscar categorias do mês
            cursor.execute("SELECT * FROM categorias WHERE mes_id = ? order by tipo desc, nome", (mes_id,))
            cat_rows = cursor.fetchall()
            
            # Estrutura para consolidação por nome para evitar duplicados visuais caso o scraper tenha rodado múltiplas vezes
            cat_by_name = {}
            
            for cat_row in cat_rows:
                cat = dict(cat_row)
                cat_key = (cat["nome"].upper().strip(), cat["tipo"])
                
                if cat_key not in cat_by_name:
                    cat_by_name[cat_key] = {
                        "nome": cat["nome"].upper().strip(),
                        "tipo": cat["tipo"],
                        "valor": cat["valor"],
                        "consistente": 1,
                        "motivo_inconsistencia": None,
                        "sub_by_name": {}
                    }
                
                if cat["consistente"] == 0:
                    cat_by_name[cat_key]["consistente"] = 0
                    cat_by_name[cat_key]["motivo_inconsistencia"] = cat["motivo_inconsistencia"]
                
                # 3. Buscar subcategorias para esta categoria usando o ID dela
                cursor.execute("SELECT * FROM subcategorias WHERE categoria_id = ? order by nome", (cat["id"],))
                sub_rows = cursor.fetchall()
                
                for sub_row in sub_rows:
                    sub = dict(sub_row)
                    sub_key = sub["nome"].upper().strip()
                    
                    if sub_key not in cat_by_name[cat_key]["sub_by_name"]:
                        cat_by_name[cat_key]["sub_by_name"][sub_key] = {
                            "nome": sub["nome"].upper().strip(),
                            "tipo": sub["tipo"],
                            "valor": sub["valor"],
                            "consistente": 1,
                            "motivo_inconsistencia": None,
                            "transactions": []
                        }
                    
                    if sub["consistente"] == 0:
                        cat_by_name[cat_key]["sub_by_name"][sub_key]["consistente"] = 0
                        cat_by_name[cat_key]["sub_by_name"][sub_key]["motivo_inconsistencia"] = sub["motivo_inconsistencia"]
                    
                    # 4. Buscar transações para esta subcategoria usando o ID dela
                    cursor.execute("SELECT * FROM transacoes WHERE subcategoria_id = ? ORDER BY data", (sub["id"],))
                    tx_rows = cursor.fetchall()
                    
                    for tx_row in tx_rows:
                        tx = dict(tx_row)
                        
                        if "processed_tx_keys" not in cat_by_name[cat_key]["sub_by_name"][sub_key]:
                            cat_by_name[cat_key]["sub_by_name"][sub_key]["processed_tx_keys"] = set()
                        
                        # Chave composta baseada nos dados da transação para desduplicação de clones físicos do banco
                        tx_key = (tx["data"], tx["descricao"], tx["valor"], tx["apartamento"], tx["tipo"])
                        
                        if tx_key not in cat_by_name[cat_key]["sub_by_name"][sub_key]["processed_tx_keys"]:
                            cat_by_name[cat_key]["sub_by_name"][sub_key]["processed_tx_keys"].add(tx_key)
                            
                            tx_node = {
                                "data": {
                                    "id": f"tx_{tx['id']}",
                                    "nome": tx["descricao"],
                                    "valor": tx["valor"],
                                    "tipo": tx["tipo"],
                                    "consistente": tx["consistente"],
                                    "motivo_inconsistencia": tx["motivo_inconsistencia"],
                                    "detalhe": f"Apto {tx['apartamento']}" if tx['apartamento'] else "",
                                    "data": tx["data"],
                                    "anexos": tx["anexos"],
                                    "nivel": 4
                                }
                            }
                            
                            cat_by_name[cat_key]["sub_by_name"][sub_key]["transactions"].append(tx_node)
            
            conn.close()
            
            # Montar a árvore final a partir do dicionário consolidado ordenando tipo 'R' antes de 'D', e por valor decrescente
            cat_nodes = []
            sorted_cat_keys = sorted(cat_by_name.keys(), key=lambda x: (x[1] != 'R', -cat_by_name[x]["valor"]))
            for cat_key in sorted_cat_keys:
                cat_data = cat_by_name[cat_key]
                sub_nodes = []
                # Ordenar subcategorias por valor decrescente
                sorted_sub_items = sorted(cat_data["sub_by_name"].items(), key=lambda item: -item[1]["valor"])
                for sub_key, sub_data in sorted_sub_items:
                    # Ordenar transações por data crescente
                    def parse_tx_date(t_node):
                        date_str = t_node["data"].get("data") or ""
                        try:
                            parts = date_str.split('/')
                            if len(parts) == 3:
                                return (int(parts[2]), int(parts[1]), int(parts[0]))
                        except:
                            pass
                        return (0, 0, 0)
                    
                    sub_data["transactions"].sort(key=parse_tx_date)
                    
                    sub_node = {
                        "data": {
                            "id": f"sub_{cat_data['nome']}_{sub_data['nome']}",
                            "nome": sub_data["nome"],
                            "valor": sub_data["valor"],
                            "tipo": sub_data["tipo"],
                            "consistente": sub_data["consistente"],
                            "motivo_inconsistencia": sub_data["motivo_inconsistencia"],
                            "nivel": 3
                        },
                        "children": sub_data["transactions"]
                    }
                    sub_nodes.append(sub_node)
                
                cat_node = {
                    "data": {
                        "id": f"cat_{cat_data['nome']}",
                        "nome": cat_data["nome"],
                        "valor": cat_data["valor"],
                        "tipo": cat_data["tipo"],
                        "consistente": cat_data["consistente"],
                        "motivo_inconsistencia": cat_data["motivo_inconsistencia"],
                        "nivel": 2
                    },
                    "expanded": True,
                    "children": sub_nodes
                }
                cat_nodes.append(cat_node)
            
            # Nó raiz do mês
            root_node = {
                "data": {
                    "id": f"mes_{mes_dict['id']}",
                    "nome": mes_dict["exibicao"],
                    "receita_total": mes_dict["receita_total"],
                    "despesa_total": mes_dict["despesa_total"],
                    "consistente": mes_dict["consistente"],
                    "motivo_inconsistencia": mes_dict["motivo_inconsistencia"],
                    "nivel": 1
                },
                "expanded": True,
                "children": cat_nodes
            }
            
            return {"status": "success", "data": root_node}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_dashboard_stats(self):
        """
        Retorna estatísticas consolidadas para os cards do topo.
        """
        try:
            db_path = self._get_db_path()
            if not os.path.exists(db_path):
                return {"status": "error", "message": "Banco de dados não encontrado."}
                
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Totais de receita e despesa
            cursor.execute("SELECT SUM(receita_total) as total_rec, SUM(despesa_total) as total_desp, COUNT(*) as total_meses FROM meses")
            row = cursor.fetchone()
            total_rec = row["total_rec"] or 0
            total_desp = row["total_desp"] or 0
            total_meses = row["total_meses"] or 0
            
            # Quantidade total de transações
            cursor.execute("SELECT COUNT(*) FROM transacoes")
            total_trans = cursor.fetchone()[0]
            
            # Transações inconsistentes
            cursor.execute("SELECT COUNT(*) FROM transacoes WHERE consistente = 0")
            total_inc_trans = cursor.fetchone()[0]
            
            # Quantidade de anexos
            cursor.execute("SELECT COUNT(*) FROM anexos")
            total_anexos = cursor.fetchone()[0]
            
            # Prestações de contas
            cursor.execute("SELECT COUNT(*) FROM prestacoes_contas")
            total_pcs = cursor.fetchone()[0]
            
            conn.close()
            return {
                "status": "success",
                "stats": {
                    "total_receitas": total_rec,
                    "total_despesas": total_desp,
                    "total_meses": total_meses,
                    "total_transacoes": total_trans,
                    "total_inconsistencias": total_inc_trans,
                    "total_anexos": total_anexos,
                    "total_prestacoes": total_pcs
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_all_months(self):
        """
        Retorna todos os meses.
        """
        try:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM meses ORDER BY id DESC")
            rows = cursor.fetchall()
            months = [dict(row) for row in rows]
            conn.close()
            return {"status": "success", "data": months}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_all_transactions(self):
        """
        Retorna todas as transações cadastradas com as categorias e meses.
        """
        try:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    t.id as transacao_id,
                    t.tipo,
                    t.data,
                    t.descricao,
                    t.valor,
                    t.apartamento,
                    t.competencia,
                    t.fornecedor,
                    t.conta,
                    t.anexos as qtde_anexos_original,
                    t.consistente,
                    t.motivo_inconsistencia,
                    s.nome as subcategoria_nome,
                    c.nome as categoria_nome,
                    m.exibicao as mes_exibicao,
                    m.id as mes_id
                FROM transacoes t
                JOIN subcategorias s ON t.subcategoria_id = s.id
                JOIN categorias c ON s.categoria_id = c.id
                JOIN meses m ON c.mes_id = m.id
                ORDER BY m.id DESC, t.id DESC
            """)
            rows = cursor.fetchall()
            seen_keys = set()
            transactions = []
            for row in rows:
                row_dict = dict(row)
                # Chave composta para desduplicar transações no retorno geral
                tx_key = (
                    row_dict["mes_id"],
                    row_dict["data"],
                    row_dict["descricao"],
                    row_dict["valor"],
                    row_dict["apartamento"],
                    row_dict["tipo"]
                )
                if tx_key not in seen_keys:
                    seen_keys.add(tx_key)
                    transactions.append(row_dict)
            conn.close()
            return {"status": "success", "data": transactions}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_revisado_usuario(self, tabela, registro_id, valor):
        """
        Atualiza o campo 'revisado_usuario' de um registro específico de uma tabela.
        tabela: nome da tabela SQLite (ex: 'meses', 'categorias', 'subcategorias', 'transacoes', 'anexos', 'prestacoes_contas')
        registro_id: valor da chave primária (id) do registro
        valor: novo valor (0 ou 1) para a coluna 'revisado_usuario'
        """
        tabelas_validas = ["meses", "categorias", "subcategorias", "transacoes", "anexos", "prestacoes_contas"]
        if tabela not in tabelas_validas:
            return {"status": "error", "message": f"Tabela inválida: {tabela}"}
            
        try:
            db_path = self._get_db_path()
            if not os.path.exists(db_path):
                return {"status": "error", "message": "Banco de dados não encontrado."}
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Utiliza parametrização segura para os valores e validação restrita da tabela
            cursor.execute(f"UPDATE {tabela} SET revisado_usuario = ? WHERE id = ?", (int(valor), registro_id))
            conn.commit()
            conn.close()
            return {"status": "success", "message": f"Registro {registro_id} da tabela {tabela} atualizado com revisado_usuario={valor}."}
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
        
    api = Api()
    
    # Cria a janela desktop nativa provida pelo PyWebView
    if html_content is not None:
        webview.create_window(
            title="Winker Scraper Dashboard - Visualização Financeira",
            html=html_content,
            js_api=api,
            width=1280,
            height=800,
            resizable=True,
            maximized=True
        )
    else:
        webview.create_window(
            title="Winker Scraper Dashboard - Visualização Financeira",
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
