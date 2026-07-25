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
        self.cursor.execute("INSERT INTO condominio (id, nome, inadimplencia_valor, inadimplencia_unidades, inadimplencia_data_corte, administradora, telefone_administradora, ultima_atualizacao) VALUES (?, ?, 100.50, 2, '2023-01-01', 'Admin Teste', '[\"12345678\"]', '2026-06-25T21:00:00')", (self.condo_id, "Condominio Teste"))
        self.cursor.execute("INSERT INTO membros_gestao (condominio_id, nome, cargo) VALUES (?, ?, ?)", (self.condo_id, "João", "Síndico"))
        self.cursor.execute("INSERT INTO meses (id, condominio_id, consistente, motivo_inconsistencia, revisado_usuario, competencia, exibicao, receita_total, despesa_total, anexos) VALUES (1, ?, 0, 'Erro Mês', 0, '2023-01', 'JAN/2023', 500.0, 300.0, 0)", (self.condo_id,))
        self.cursor.execute("INSERT INTO meses (id, condominio_id, consistente, motivo_inconsistencia, revisado_usuario, competencia, exibicao, receita_total, despesa_total, anexos) VALUES (2, ?, 1, NULL, 0, ?, ?, 600.0, 400.0, 0)", (self.condo_id, current_date, 'MÊS ATUAL'))
        self.cursor.execute("INSERT INTO categorias (id, mes_id, tipo, nome, valor, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 'Despesas', 'Cat 1', 100, 0, 'Erro Categoria', 0)")
        self.cursor.execute("INSERT INTO subcategorias (id, categoria_id, tipo, nome, valor, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 'Despesas', 'Sub 1', 100, 0, 'Erro Subcategoria', 0)")
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 'Despesas', '2023-01-10', 'Transação Teste', 100, '101', '2023-01', 'Fornecedor A', 1, 0, 'Erro Transação', 0)")
        self.cursor.execute("INSERT INTO anexos (id, transacao_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Anexo', 0)")
        self.cursor.execute("INSERT INTO prestacoes_contas (id, mes_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Prestação', 0)")
        
        self.cursor.execute("INSERT INTO taxas (condominio_id, competencia, exibicao, vencimento, descricao, valor_original, desconto_vista, multa_percentual, juros_mes_percentual, tipo) VALUES (?, '2023-01', 'JAN/2023', '15/01/2023', 'Taxa Condomínio', 300.0, 10.0, 2.0, 1.0, 'C')", (self.condo_id,))
        self.cursor.execute("UPDATE condominio SET apartamentos = '[\"101\", \"102\"]' WHERE id = ?", (self.condo_id,))
        # Adicionar uma transação que abate a taxa (receita para apto 102) - pago com desconto
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (2, 1, 'R', '14/01/2023', 'Pagamento', 290.0, '102', '2023-01', 'Morador', 0, 1, NULL, 1)")
        
        self.conn.commit()
        
        # Avoid file check failing by patching os.path.exists during init
        self.original_exists = os.path.exists
        os.path.exists = lambda path: True if path.endswith('winker_data.db') or path.endswith('.db') else self.original_exists(path)
        
        try:
            self.api = Api(db_path=self.temp_db_path)
            self.api.condo_id = self.condo_id
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

    def test_get_pendencias_revisao_count(self):
        result = self.api.get_pendencias_revisao_count()
        self.assertEqual(result["status"], "success", result.get("message"))
        
        data = result["data"]
        self.assertEqual(data["count"], 7)
        
        details = data["details"]
        self.assertIn("meses", details)
        self.assertEqual(details["meses"], 2)
        self.assertIn("categorias", details)
        self.assertIn("subcategorias", details)
        self.assertIn("lancamentos", details)
        self.assertIn("documentos", details)

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
        
        tipo_node_rec = mes_node["children"][0]
        self.assertEqual(tipo_node_rec["data"]["tipo_node"], "tipo")
        self.assertEqual(tipo_node_rec["data"]["descricao"], "Receitas")

        tipo_node = mes_node["children"][1]
        self.assertEqual(tipo_node["data"]["tipo_node"], "tipo")
        self.assertEqual(tipo_node["data"]["descricao"], "Despesas")
        
        cat_node = tipo_node["children"][0]
        self.assertEqual(cat_node["data"]["tipo_node"], "categoria")
        self.assertEqual(cat_node["data"]["descricao"], "Cat 1")
        
        sub_node = cat_node["children"][0]
        self.assertEqual(sub_node["data"]["tipo_node"], "subcategoria")
        self.assertEqual(sub_node["data"]["descricao"], "Sub 1")
        
        trans_nodes = sub_node["children"]
        trans_teste = next((n for n in trans_nodes if n["data"]["descricao"] == "Transação Teste"), None)
        self.assertIsNotNone(trans_teste)
        self.assertEqual(trans_teste["data"]["tipo_node"], "transacao")
        self.assertEqual(trans_teste["data"]["valor"], 100)

    def test_get_inadimplencia(self):
        result = self.api.get_inadimplencia(data_corte="2023-01-20")
        self.assertEqual(result["status"], "success", result.get("message"))
        data = result["data"]
        
        # Apto 101 não pagou, deve estar na inadimplencia
        # Apto 102 pagou a taxa, não deve aparecer (ou ter a taxa na lista)
        # 102 is omitted because it has no unpaid fees
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["unidade"], "101")
        
        taxas = data[0]["taxas"]
        self.assertEqual(len(taxas), 1)
        self.assertEqual(taxas[0]["valor"], 300.0)
        self.assertEqual(taxas[0]["dias_vencidos"], 5) # (20 - 15) = 5
        self.assertAlmostEqual(taxas[0]["juros_total"], 0.5) # 300 * (1% / 30) * 5 dias
        
    def test_get_inadimplencia_multa_sobre_juros(self):
        # Mudar para M (Multa sobre Juros)
        self.cursor.execute("UPDATE condominio SET tipo_juros_multa = 'M' WHERE id = ?", (self.condo_id,))
        self.conn.commit()
        result = self.api.get_inadimplencia(data_corte="2023-01-20")
        taxas = result["data"][0]["taxas"]
        # Juros = 0.5
        # Multa = (300 + 0.5) * 2% = 6.01
        self.assertAlmostEqual(taxas[0]["juros_total"], 0.5)
        self.assertAlmostEqual(taxas[0]["multa"], 6.01)

    def test_get_inadimplencia_juros_sobre_multa(self):
        # Mudar para J (Juros sobre Multa)
        self.cursor.execute("UPDATE condominio SET tipo_juros_multa = 'J' WHERE id = ?", (self.condo_id,))
        self.conn.commit()
        result = self.api.get_inadimplencia(data_corte="2023-01-20")
        taxas = result["data"][0]["taxas"]
        # Multa = 300 * 2% = 6.0
        # Juros = (300 + 6.0) * (1% / 30) * 5 = 306 * 0.001666... = 0.51
        self.assertAlmostEqual(taxas[0]["multa"], 6.0)
        self.assertAlmostEqual(taxas[0]["juros_total"], 0.51)

    def test_get_inadimplencia_multiple_match(self):
        self.cursor.execute("INSERT INTO taxas (condominio_id, competencia, exibicao, vencimento, descricao, valor_original, desconto_vista, multa_percentual, juros_mes_percentual, tipo) VALUES (?, '2023-01', 'JAN/2023', '15/01/2023', 'Taxa Teste Match Múltiplo', 100.0, 0.0, 2.0, 1.0, 'C')", (self.condo_id,))
        self.cursor.execute("UPDATE condominio SET apartamentos = '[\"101\", \"102\", \"103\"]' WHERE id = ?", (self.condo_id,))
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (3, 1, 'R', '10/01/2023', 'Pag parcial 1', 55.0, '103', '2023-01', 'Morador', 0, 1, NULL, 1)")
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (4, 1, 'R', '10/01/2023', 'Pag parcial 2', 50.0, '103', '2023-01', 'Morador', 0, 1, NULL, 1)")
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (5, 1, 'R', '10/01/2023', 'Pag parcial 3', 45.0, '103', '2023-01', 'Morador', 0, 1, NULL, 1)")
        self.conn.commit()
        
        result = self.api.get_inadimplencia(data_corte="2023-01-20")
        self.assertEqual(result["status"], "success")
        
        # O apto 103 pode ter outras taxas pendentes (ex: Taxa Condomínio comum),
        # mas a "Taxa Teste Match Múltiplo" deve ter sido paga pelo match de (55+45) = 100
        taxas_103 = next((d["taxas"] for d in result["data"] if d["unidade"] == "103"), [])
        descricoes_103 = [t["descricao"] for t in taxas_103]
        self.assertNotIn("Taxa Teste Match Múltiplo", descricoes_103)

if __name__ == '__main__':
    unittest.main()
