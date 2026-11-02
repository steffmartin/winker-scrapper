"""Synthetic configuration and condominium-scope regressions."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import local_config
import generate_sql
import validate_sql


class LocalConfigTests(unittest.TestCase):
    def test_missing_default_does_not_select_a_condominium(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(local_config, 'DEFAULT_CONFIG', Path(directory) / 'missing.json'):
                self.assertEqual(local_config.load_config(), {})
                with self.assertRaises(ValueError):
                    local_config.condominium_id(local_config.load_config())

    def test_explicit_missing_configuration_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                local_config.load_config(Path(directory) / 'missing.json')

    def test_explicit_scope_overrides_local_scope(self):
        self.assertEqual(local_config.condominium_id({'condominium': {'id': 'local-example'}}, 'other-example'), 'other-example')
        db = sqlite3.connect(':memory:')
        db.executescript('''
            CREATE TABLE meses (id INTEGER, condominio_id TEXT, competencia TEXT);
            CREATE TABLE categorias (id INTEGER, mes_id INTEGER);
            CREATE TABLE subcategorias (id INTEGER, categoria_id INTEGER);
            CREATE TABLE transacoes (id INTEGER, subcategoria_id INTEGER);
            CREATE TABLE prestacoes_contas (id INTEGER, mes_id INTEGER);
            INSERT INTO meses VALUES (1, 'local-example', '2099-01'), (2, 'other-example', '2099-01');
            INSERT INTO categorias VALUES (10, 1), (20, 2);
            INSERT INTO subcategorias VALUES (100, 10), (200, 20);
            INSERT INTO transacoes VALUES (1000, 100), (2000, 200);
        ''')
        self.assertEqual(validate_sql.target_ids(db, '2099-01', 'other-example')['transacoes'], {2000})
        db.close()

    def test_generator_uses_explicit_configuration_without_private_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            records = {
                'config.json': {'condominium': {'id': "example'quoted", 'name': 'Synthetic building'}},
                'review.json': {'approved_for_generation': True, 'month': '2099-01'},
                'controls.json': [{'tipo': 'R', 'categoria': 'Example', 'classe': 'Example class', 'valor_centavos': 123}],
                'ledger.json': [{'tipo': 'R', 'categoria': 'Example', 'classe': 'Example class', 'valor_centavos': 123,
                                 'data': '01/01/2099', 'descricao': 'Synthetic payment', 'conta': 'Example account',
                                 'competencia': '2099-01', 'apartamento': 'Example unit', 'fornecedor': None, 'pagina': 1}],
            }
            for name, value in records.items():
                (folder / name).write_text(json.dumps(value), encoding='utf8')
            generate_sql.generate(folder, folder / 'result.sql', folder / 'config.json')
            result = (folder / 'result.sql').read_text(encoding='utf8')
            self.assertIn('Synthetic building', result)
            self.assertIn("condominio_id = 'example''quoted'", result)
            self.assertIn('1.23', result)


if __name__ == '__main__':
    unittest.main()
