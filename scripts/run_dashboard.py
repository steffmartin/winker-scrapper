import os
import sys
import sqlite3
import webview
import subprocess
import argparse
from datetime import datetime

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

    def get_inconsistencies_count(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            queries = {
                "meses": """
                    SELECT COUNT(*) as qtd 
                    FROM meses m 
                    WHERE m.consistente = 0 AND m.revisado_usuario = 0 AND m.condominio_id = ? 
                """,
                "categorias": """
                    SELECT COUNT(*) as qtd 
                    FROM categorias c
                    INNER JOIN meses m ON c.mes_id = m.id
                    WHERE c.consistente = 0 AND c.revisado_usuario = 0 AND m.condominio_id = ? 
                """,
                "subcategorias": """
                    SELECT COUNT(*) as qtd 
                    FROM subcategorias s
                    INNER JOIN categorias c ON s.categoria_id = c.id
                    INNER JOIN meses m ON c.mes_id = m.id
                    WHERE s.consistente = 0 AND s.revisado_usuario = 0 AND m.condominio_id = ? 
                """,
                "transacoes": """
                    SELECT COUNT(*) as qtd 
                    FROM transacoes t
                    INNER JOIN subcategorias s ON t.subcategoria_id = s.id
                    INNER JOIN categorias c ON s.categoria_id = c.id
                    INNER JOIN meses m ON c.mes_id = m.id
                    WHERE t.consistente = 0 AND t.revisado_usuario = 0 AND m.condominio_id = ? 
                """,
                "anexos": """
                    SELECT COUNT(*) as qtd 
                    FROM anexos a
                    INNER JOIN transacoes t ON a.transacao_id = t.id
                    INNER JOIN subcategorias s ON t.subcategoria_id = s.id
                    INNER JOIN categorias c ON s.categoria_id = c.id
                    INNER JOIN meses m ON c.mes_id = m.id
                    WHERE a.consistente = 0 AND a.revisado_usuario = 0 AND m.condominio_id = ? 
                """,
                "prestacoes_contas": """
                    SELECT COUNT(*) as qtd 
                    FROM prestacoes_contas p
                    INNER JOIN meses m ON p.mes_id = m.id
                    WHERE p.consistente = 0 AND p.revisado_usuario = 0 AND m.condominio_id = ? 
                """
            }
            
            total_count = 0
            details = {}
            
            for table, query in queries.items():
                cursor.execute(query, (self.condo_id,))
                row = cursor.fetchone()
                if row and row["qtd"] > 0:
                    qtd = row["qtd"]
                    details[table] = qtd
                    total_count += qtd
            
            conn.close()
            
            return {
                "status": "success",
                "data": {
                    "count": total_count,
                    "details": details
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_dashboard_kpis(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # KPI Inadimplencia & Admin (from condominio)
            cursor.execute("SELECT inadimplencia_valor, inadimplencia_unidades, inadimplencia_data_corte, administradora, telefone_administradora, ultima_atualizacao FROM condominio WHERE id = ?", (self.condo_id,))
            condominio_row = cursor.fetchone()
            
            inadimplencia = {}
            administradora = {}
            estatisticas = {
                "ultima_atualizacao": None,
                "transacoes_total": 0,
                "meses_lidos": 0,
                "anexos_baixados": 0
            }
            
            if condominio_row:
                inadimplencia = {
                    "valor": condominio_row["inadimplencia_valor"] or 0,
                    "unidades": condominio_row["inadimplencia_unidades"] or 0,
                    "data_corte": condominio_row["inadimplencia_data_corte"]
                }
                administradora = {
                    "nome": condominio_row["administradora"],
                    "telefone": condominio_row["telefone_administradora"]
                }
                estatisticas["ultima_atualizacao"] = condominio_row["ultima_atualizacao"]
            
            # Estatísticas - total_transacoes
            cursor.execute("""
                SELECT COUNT(t.id) as count
                FROM transacoes t
                JOIN subcategorias s ON t.subcategoria_id = s.id
                JOIN categorias c ON s.categoria_id = c.id
                JOIN meses m ON c.mes_id = m.id
                WHERE m.condominio_id = ?
            """, (self.condo_id,))
            transacoes_row = cursor.fetchone()
            if transacoes_row:
                estatisticas["transacoes_total"] = transacoes_row["count"]
                
            # Estatísticas - meses_lidos
            cursor.execute("SELECT COUNT(id) as count FROM meses WHERE condominio_id = ?", (self.condo_id,))
            meses_row = cursor.fetchone()
            if meses_row:
                estatisticas["meses_lidos"] = meses_row["count"]
                
            # Estatísticas - total_anexos
            cursor.execute("""
                SELECT COUNT(a.id) as count
                FROM anexos a
                JOIN transacoes t ON a.transacao_id = t.id
                JOIN subcategorias s ON t.subcategoria_id = s.id
                JOIN categorias c ON s.categoria_id = c.id
                JOIN meses m ON c.mes_id = m.id
                WHERE m.condominio_id = ?
            """, (self.condo_id,))
            anexos_row = cursor.fetchone()
            anexos_count = anexos_row["count"] if anexos_row else 0
            
            cursor.execute("""
                SELECT COUNT(p.id) as count
                FROM prestacoes_contas p
                JOIN meses m ON p.mes_id = m.id
                WHERE m.condominio_id = ?
            """, (self.condo_id,))
            prestacoes_row = cursor.fetchone()
            prestacoes_count = prestacoes_row["count"] if prestacoes_row else 0
            
            estatisticas["anexos_baixados"] = anexos_count + prestacoes_count
            
            # KPI Gestão (from membros_gestao)
            cursor.execute("SELECT nome, cargo FROM membros_gestao WHERE condominio_id = ?", (self.condo_id,))
            membros_gestao = [dict(row) for row in cursor.fetchall()]
            
            gestao = {
                "membros": membros_gestao,
                "administradora": administradora
            }
            
            # KPI Saldo de Contas (Mock)
            # TODO Implementar cálculo de saldo após criação da coluna 'saldo inicial' e contas
            saldos = {
                "saldo_total": 0,
                "contas": [
                    {"nome": "Conta Corrente Padrão", "saldo": 0},
                    {"nome": "Fundo de Reserva", "saldo": 0}
                ]
            }
            
            # KPI Resumo do Mês Atual (competência mais atual)
            current_date_str = datetime.now().strftime("%Y-%m")
            cursor.execute("SELECT competencia, receita_total, despesa_total FROM meses WHERE condominio_id = ? AND competencia = ?", (self.condo_id, current_date_str))
            mes_row = cursor.fetchone()
            
            if mes_row:
                rec = mes_row["receita_total"] or 0
                desp = mes_row["despesa_total"] or 0
                resumo_mes = {
                    "competencia": mes_row["competencia"],
                    "receita_total": rec,
                    "despesa_total": desp,
                    "resultado": rec - desp
                }
            else:
                resumo_mes = {
                    "competencia": current_date_str,
                    "receita_total": 0,
                    "despesa_total": 0,
                    "resultado": 0
                }
                
            conn.close()
            
            return {
                "status": "success",
                "data": {
                    "inadimplencia": inadimplencia,
                    "gestao": gestao,
                    "saldos": saldos,
                    "resumo_mes": resumo_mes,
                    "estatisticas": estatisticas
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_transacoes(self, start_date=None, end_date=None):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
            
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    m.competencia as mes_competencia,
                    m.exibicao as mes_exibicao,
                    c.nome as categoria_nome,
                    c.tipo as categoria_tipo,
                    s.nome as subcategoria_nome,
                    t.id as transacao_id,
                    t.descricao as transacao_descricao,
                    t.data,
                    t.valor,
                    t.consistente,
                    t.revisado_usuario,
                    t.anexos as anexos_count
                FROM transacoes t
                JOIN subcategorias s ON t.subcategoria_id = s.id
                JOIN categorias c ON s.categoria_id = c.id
                JOIN meses m ON c.mes_id = m.id
                WHERE m.condominio_id = ?
            """
            params = [self.condo_id]
            
            if start_date:
                query += " AND substr(t.data, 7, 4) || '-' || substr(t.data, 4, 2) || '-' || substr(t.data, 1, 2) >= ?"
                params.append(start_date)
            if end_date:
                query += " AND substr(t.data, 7, 4) || '-' || substr(t.data, 4, 2) || '-' || substr(t.data, 1, 2) <= ?"
                params.append(end_date)
                
            query += " ORDER BY t.data ASC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            meses_dict = {}
            for row in rows:
                mes = row["mes_competencia"]
                mes_exibicao = row["mes_exibicao"]
                tipo = "Receitas" if row["categoria_tipo"] == "R" else "Despesas"
                categoria = row["categoria_nome"]
                subcategoria = row["subcategoria_nome"]
                
                if mes not in meses_dict:
                    meses_dict[mes] = {
                        "data": {"descricao": mes_exibicao, "valor_total": 0, "tipo_node": "mes"},
                        "expanded": False,
                        "children_dict": {}
                    }
                
                mes_node = meses_dict[mes]
                if tipo not in mes_node["children_dict"]:
                    mes_node["children_dict"][tipo] = {
                        "data": {"descricao": tipo, "valor_total": 0, "porcentagem": 0.0, "tipo_node": "tipo"},
                        "expanded": False,
                        "children_dict": {}
                    }
                
                tipo_node = mes_node["children_dict"][tipo]
                if categoria not in tipo_node["children_dict"]:
                    tipo_node["children_dict"][categoria] = {
                        "data": {"descricao": categoria, "valor_total": 0, "porcentagem": 0.0, "tipo_node": "categoria"},
                        "expanded": False,
                        "children_dict": {}
                    }
                
                categoria_node = tipo_node["children_dict"][categoria]
                if subcategoria not in categoria_node["children_dict"]:
                    categoria_node["children_dict"][subcategoria] = {
                        "data": {"descricao": subcategoria, "valor_total": 0, "porcentagem": 0.0, "tipo_node": "subcategoria"},
                        "expanded": False,
                        "children": []
                    }
                
                subcategoria_node = categoria_node["children_dict"][subcategoria]
                
                valor = row["valor"] or 0
                
                transacao_data = {
                    "descricao": row["transacao_descricao"],
                    "valor": valor,
                    "data": row["data"],
                    "consistente": row["consistente"],
                    "revisado_usuario": row["revisado_usuario"],
                    "anexos": row["anexos_count"],
                    "tipo_node": "transacao"
                }
                
                subcategoria_node["children"].append({
                    "data": transacao_data
                })
                
                subcategoria_node["data"]["valor_total"] += valor
                categoria_node["data"]["valor_total"] += valor
                tipo_node["data"]["valor_total"] += valor
                mes_node["data"]["valor_total"] += valor
                
            tree = []
            sorted_meses = sorted(meses_dict.keys())
            
            for mes in sorted_meses:
                mes_node = meses_dict[mes]
                mes_node["children"] = []
                
                sorted_tipos = sorted(mes_node["children_dict"].keys(), key=lambda x: (x.lower() != 'receitas', x))
                
                for tipo in sorted_tipos:
                    tipo_node = mes_node["children_dict"][tipo]
                    tipo_node["children"] = []
                    tipo_total = tipo_node["data"]["valor_total"]
                    mes_total = mes_node["data"]["valor_total"]
                    if mes_total > 0:
                        tipo_node["data"]["porcentagem"] = round((tipo_total / mes_total) * 100, 2)
                    
                    sorted_categorias = sorted(tipo_node["children_dict"].values(), key=lambda x: x["data"]["valor_total"], reverse=True)
                    
                    for cat_node in sorted_categorias:
                        cat_node["children"] = []
                        cat_total = cat_node["data"]["valor_total"]
                        if tipo_total > 0:
                            cat_node["data"]["porcentagem"] = round((cat_total / tipo_total) * 100, 2)
                        
                        sorted_subcats = sorted(cat_node["children_dict"].values(), key=lambda x: x["data"]["valor_total"], reverse=True)
                        for sub_node in sorted_subcats:
                            sub_total = sub_node["data"]["valor_total"]
                            if cat_total > 0:
                                sub_node["data"]["porcentagem"] = round((sub_total / cat_total) * 100, 2)
                            
                            for trans_node in sub_node["children"]:
                                if sub_total > 0:
                                    trans_node["data"]["porcentagem"] = round((trans_node["data"]["valor"] / sub_total) * 100, 2)
                                else:
                                    trans_node["data"]["porcentagem"] = 0.0
                            
                            cat_node["children"].append(sub_node)
                            
                        del cat_node["children_dict"]
                        tipo_node["children"].append(cat_node)
                        
                    del tipo_node["children_dict"]
                    mes_node["children"].append(tipo_node)
                    
                del mes_node["children_dict"]
                tree.append(mes_node)
                
            return {
                "status": "success",
                "data": tree
            }
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
