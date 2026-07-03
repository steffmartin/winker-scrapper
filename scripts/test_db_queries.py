import unittest
import os
import sqlite3
import tempfile
from datetime import datetime

# Substitui o caminho do DB padrão para o banco de teste temporário em extract_winker
import extract_winker
import run_dashboard

class TestDBQueries(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_winker.db")
        
        # Override project_root temporariamente para forçar db_path onde for usado
        self.original_project_root = extract_winker.project_root
        extract_winker.project_root = self.temp_dir.name
        
        # Inicializa o BD (criar tabelas)
        extract_winker.init_db(self.db_path)
        
        # Cria uma pasta "database" no temp_dir pois extract_winker.init_db() se não passado o db_path, 
        # e Api() tenta usar project_root + "database" + "winker_data.db".
        os.makedirs(os.path.join(self.temp_dir.name, "database"), exist_ok=True)
        # Vamos renomear self.db_path para combinar com o padrão
        self.default_db_path = os.path.join(self.temp_dir.name, "database", "winker_data.db")
        extract_winker.init_db(self.default_db_path)
        
    def tearDown(self):
        extract_winker.project_root = self.original_project_root
        # Ignore cleanup errors in Windows to avoid PermissionError
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_auditoria_crud(self):
        # Insert Condominio so FK doesn't fail
        conn = sqlite3.connect(self.default_db_path)
        conn.execute("INSERT INTO condominio (id, nome) VALUES ('COND-TEST', 'Teste')")
        conn.commit()
        conn.close()

        # Insert
        auditoria_id = extract_winker.create_auditoria("2024-01-01", "2024-01-31")
        self.assertIsNotNone(auditoria_id)
        
        # Update condominio ID
        extract_winker.update_auditoria_condominio_id(auditoria_id, "COND-TEST")
        
        # Update completo
        user_data = {"id": 1, "name": "Admin", "uuid": "abc", "cpf": "000", "rg": "000", "fone": "000", "apto": "000"}
        extract_winker.update_auditoria(auditoria_id, user_data, 10, 50, 120.5, True, False, True)
        
        conn = sqlite3.connect(self.default_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT condominio_id, downloads_realizados FROM auditoria WHERE id=?", (auditoria_id,))
        row = cursor.fetchone()
        self.assertEqual(row[0], "COND-TEST")
        self.assertEqual(row[1], 10)
        conn.close()

    def test_condominio_e_gestao(self):
        membros = [{"nome": "Síndico Teste", "cargo": "Síndico"}, {"nome": "João", "cargo": "Subsíndico"}]
        extract_winker.save_condominio_and_gestao(
            "COND-123", "Condomínio Teste", "2024-01-01", 5, 1000.50, "AdminCorp", "11999999999", membros
        )
        
        conn = sqlite3.connect(self.default_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM condominio WHERE id='COND-123'")
        self.assertEqual(cursor.fetchone(), ("COND-123", "Condomínio Teste"))
        
        cursor.execute("SELECT count(*) FROM membros_gestao WHERE condominio_id='COND-123'")
        self.assertEqual(cursor.fetchone()[0], 2)
        conn.close()

    def test_dashboard_api(self):
        # Setup dados falsos para a API
        extract_winker.save_condominio_and_gestao(
            "COND-API", "Condominio API", "2024-01-01", 0, 0.0, "", "", []
        )
        conn = sqlite3.connect(self.default_db_path)
        cursor = conn.cursor()
        current_comp = datetime.now().strftime("%Y-%m")
        current_exib = datetime.now().strftime("%m/%Y")
        cursor.execute("INSERT INTO meses (condominio_id, exibicao, competencia, receita_total, despesa_total, consistente, revisado_usuario) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       ("COND-API", current_exib, current_comp, 5000.0, 4000.0, 1, 0))
        mes_id = cursor.lastrowid
        cursor.execute("INSERT INTO categorias (mes_id, tipo, nome, valor, consistente, revisado_usuario) VALUES (?, ?, ?, ?, ?, ?)",
                       (mes_id, 'Despesas', 'Despesas Operacionais', 4000.0, 1, 0))
        cat_id = cursor.lastrowid
        cursor.execute("INSERT INTO subcategorias (categoria_id, tipo, nome, valor, consistente, revisado_usuario) VALUES (?, ?, ?, ?, ?, ?)",
                       (cat_id, 'Despesas', 'Água', 4000.0, 1, 0))
        sub_id = cursor.lastrowid
        cursor.execute("INSERT INTO transacoes (subcategoria_id, tipo, data, descricao, valor, consistente, revisado_usuario, anexos) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (sub_id, 'Despesas', '05/01/2024', 'Conta de água', 4000.0, 1, 0, 0))
        conn.commit()
        conn.close()

        # Injeta projeto_root no run_dashboard para ele ler o mesmo banco
        original_rd_root = run_dashboard.project_root
        run_dashboard.project_root = self.temp_dir.name
        try:
            api = run_dashboard.Api("COND-API", db_path=self.default_db_path)
            kpis = api.get_dashboard_kpis()
            self.assertIn("resumo_mes", kpis["data"])
            self.assertEqual(kpis["data"]["resumo_mes"]["receita_total"], 5000.0)
            
            transacoes = api.get_transacoes()
            self.assertTrue(len(transacoes["data"]) > 0)
            self.assertEqual(transacoes["data"][0]["data"]["valor_total"], 4000.0)
        finally:
            run_dashboard.project_root = original_rd_root

if __name__ == '__main__':
    unittest.main()
