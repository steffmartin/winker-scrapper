import unittest
import sqlite3
import os
import sys

# Add the project root to sys.path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.run_dashboard import Api

class TestRunDashboard(unittest.TestCase):

    def setUp(self):
        import tempfile
        import models
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='_test_rd.db')
        
        # Initialize ORM with this temp db
        models.init_models(self.temp_db_path)
        
        # Connect raw sqlite to populate data easily
        self.conn = sqlite3.connect(self.temp_db_path)
        self.cursor = self.conn.cursor()
        
        # Populate data
        import datetime
        current_date = datetime.datetime.now().strftime("%Y-%m")
        self.condo_id = "condo_123"
        self.cursor.execute("INSERT INTO condominio (id, nome, inadimplencia_valor, inadimplencia_unidades, inadimplencia_data_corte, administradora, telefone_administradora, ultima_atualizacao) VALUES (?, ?, 100.50, 2, '2023-01-01', 'Admin Teste', '12345678', '2026-06-25T21:00:00')", (self.condo_id, "Condominio Teste"))
        self.cursor.execute("INSERT INTO membros_gestao (condominio_id, nome, cargo) VALUES (?, ?, ?)", (self.condo_id, "João", "Síndico"))
        self.cursor.execute("INSERT INTO meses (id, condominio_id, consistente, motivo_inconsistencia, revisado_usuario, competencia, exibicao, receita_total, despesa_total, anexos) VALUES (1, ?, 0, 'Erro Mês', 0, '01/2023', 'JAN/2023', 500.0, 300.0, 0)", (self.condo_id,))
        self.cursor.execute("INSERT INTO meses (id, condominio_id, consistente, motivo_inconsistencia, revisado_usuario, competencia, exibicao, receita_total, despesa_total, anexos) VALUES (2, ?, 1, NULL, 0, ?, ?, 600.0, 400.0, 0)", (self.condo_id, current_date, 'MÊS ATUAL'))
        self.cursor.execute("INSERT INTO categorias (id, mes_id, tipo, nome, valor, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 'Despesas', 'Cat 1', 100, 0, 'Erro Categoria', 0)")
        self.cursor.execute("INSERT INTO subcategorias (id, categoria_id, tipo, nome, valor, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 'Despesas', 'Sub 1', 100, 0, 'Erro Subcategoria', 0)")
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 'Despesas', '2023-01-10', 'Transação Teste', 100, '101', '01/2023', 'Fornecedor A', 1, 0, 'Erro Transação', 0)")
        self.cursor.execute("INSERT INTO anexos (id, transacao_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Anexo', 0)")
        self.cursor.execute("INSERT INTO prestacoes_contas (id, mes_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Prestação', 0)")
        self.conn.commit()
        
        # Avoid file check failing by patching os.path.exists during init
        self.original_exists = os.path.exists
        os.path.exists = lambda path: True if path.endswith('winker_data.db') or path.endswith('.db') else self.original_exists(path)
        
        try:
            self.api = Api(condo_id=self.condo_id, db_path=self.temp_db_path)
        finally:
            os.path.exists = self.original_exists
            
        self.api.init_error = None

    def tearDown(self):
        self.conn.close()
        import models
        models.db.close()
        try:
            os.close(self.temp_db_fd)
            os.unlink(self.temp_db_path)
        except:
            pass

    def test_get_inconsistencies_count(self):
        result = self.api.get_inconsistencies_count()
        self.assertEqual(result["status"], "success", result.get("message"))
        
        data = result["data"]
        self.assertEqual(data["count"], 6)
        
        details = data["details"]
        self.assertIn("meses", details)
        self.assertEqual(details["meses"], 1)
        self.assertIn("categorias", details)
        self.assertIn("subcategorias", details)
        self.assertIn("transacoes", details)
        self.assertIn("anexos", details)
        self.assertIn("prestacoes_contas", details)

    def test_get_dashboard_kpis(self):
        result = self.api.get_dashboard_kpis()
        self.assertEqual(result["status"], "success", result.get("message"))
        
        data = result["data"]
        self.assertIn("inadimplencia", data)
        self.assertIn("gestao", data)
        self.assertIn("saldos", data)
        self.assertIn("resumo_mes", data)
        
        self.assertEqual(data["gestao"]["membros"][0]["nome"], "João")
        self.assertEqual(data["saldos"]["saldo_total"], 400.0)
        self.assertEqual(data["resumo_mes"]["resultado"], 200.0) # rec 600 - desp 400

    def test_get_transacoes(self):
        result = self.api.get_transacoes()
        if result["status"] != "success":
            print("ERROR:", result)
        self.assertEqual(result["status"], "success", result.get("message"))
        tree = result["data"]["tree"]
        
        self.assertTrue(len(tree) > 0)
        
        mes_node = tree[0]
        self.assertEqual(mes_node["data"]["tipo_node"], "mes")
        self.assertEqual(mes_node["data"]["descricao"], "JAN/2023")
        
        tipo_node = mes_node["children"][0]
        self.assertEqual(tipo_node["data"]["tipo_node"], "tipo")
        self.assertEqual(tipo_node["data"]["descricao"], "Despesas")
        
        cat_node = tipo_node["children"][0]
        self.assertEqual(cat_node["data"]["tipo_node"], "categoria")
        self.assertEqual(cat_node["data"]["descricao"], "Cat 1")
        
        sub_node = cat_node["children"][0]
        self.assertEqual(sub_node["data"]["tipo_node"], "subcategoria")
        self.assertEqual(sub_node["data"]["descricao"], "Sub 1")
        
        trans_node = sub_node["children"][0]
        self.assertEqual(trans_node["data"]["tipo_node"], "transacao")
        self.assertEqual(trans_node["data"]["descricao"], "Transação Teste")
        self.assertEqual(trans_node["data"]["valor"], 100)

if __name__ == '__main__':
    unittest.main()
