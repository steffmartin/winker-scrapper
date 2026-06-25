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
        # Create an in-memory database
        self.conn = sqlite3.connect(':memory:')
        # Note: setting row_factory is handled in the method being tested, but the mock connection will receive it.
        self.cursor = self.conn.cursor()
        
        # Create tables needed for get_inconsistencies_count
        self.cursor.executescript('''
            CREATE TABLE condominio (id TEXT PRIMARY KEY, nome TEXT);
            CREATE TABLE meses (id INTEGER PRIMARY KEY, condominio_id TEXT, consistente INTEGER, motivo_inconsistencia TEXT, revisado_usuario INTEGER);
            CREATE TABLE categorias (id INTEGER PRIMARY KEY, mes_id INTEGER, consistente INTEGER, motivo_inconsistencia TEXT, revisado_usuario INTEGER);
            CREATE TABLE subcategorias (id INTEGER PRIMARY KEY, categoria_id INTEGER, consistente INTEGER, motivo_inconsistencia TEXT, revisado_usuario INTEGER);
            CREATE TABLE transacoes (id INTEGER PRIMARY KEY, subcategoria_id INTEGER, consistente INTEGER, motivo_inconsistencia TEXT, revisado_usuario INTEGER);
            CREATE TABLE anexos (id INTEGER PRIMARY KEY, transacao_id INTEGER, consistente INTEGER, motivo_inconsistencia TEXT, revisado_usuario INTEGER);
            CREATE TABLE prestacoes_contas (id INTEGER PRIMARY KEY, mes_id INTEGER, consistente INTEGER, motivo_inconsistencia TEXT, revisado_usuario INTEGER);
        ''')
        
        # Populate data
        self.condo_id = "condo_123"
        self.cursor.execute("INSERT INTO condominio (id, nome) VALUES (?, ?)", (self.condo_id, "Condominio Teste"))
        self.cursor.execute("INSERT INTO meses (id, condominio_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, ?, 0, 'Erro Mês', 0)", (self.condo_id,))
        self.cursor.execute("INSERT INTO meses (id, condominio_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (2, ?, 1, NULL, 0)", (self.condo_id,))
        self.cursor.execute("INSERT INTO categorias (id, mes_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Categoria', 0)")
        self.cursor.execute("INSERT INTO subcategorias (id, categoria_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Subcategoria', 0)")
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Transação', 0)")
        self.cursor.execute("INSERT INTO anexos (id, transacao_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Anexo', 0)")
        self.cursor.execute("INSERT INTO prestacoes_contas (id, mes_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Prestação', 0)")
        self.conn.commit()
        
        # We need to mock the connect behavior for Api instances
        self.original_connect = sqlite3.connect
        sqlite3.connect = self._mock_connect
        
        # Avoid file check failing by patching os.path.exists during init
        self.original_exists = os.path.exists
        os.path.exists = lambda path: True if path.endswith('winker_data.db') else self.original_exists(path)
        
        try:
            self.api = Api(condo_id=self.condo_id)
        finally:
            os.path.exists = self.original_exists
            
        self.api.init_error = None
        self.api.db_path = ":memory:"

    def _mock_connect(self, *args, **kwargs):
        if args and args[0] == self.api.db_path:
            return self.conn
        return self.original_connect(*args, **kwargs)

    def tearDown(self):
        sqlite3.connect = self.original_connect
        pass

    def test_get_inconsistencies_count(self):
        result = self.api.get_inconsistencies_count()
        self.assertEqual(result["status"], "success")
        
        data = result["data"]
        self.assertEqual(data["count"], 6)
        
        details = data["details"]
        self.assertIn("meses", details)
        self.assertEqual(details["meses"]["Erro Mês"], 1)
        self.assertIn("categorias", details)
        self.assertIn("subcategorias", details)
        self.assertIn("transacoes", details)
        self.assertIn("anexos", details)
        self.assertIn("prestacoes_contas", details)

if __name__ == '__main__':
    unittest.main()
