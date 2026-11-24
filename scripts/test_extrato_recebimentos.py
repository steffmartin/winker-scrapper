import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
with patch('setup_deps.install_dependencies'):
    import models
    from relatorio_recebimentos import obter_limites
from peewee import SqliteDatabase


class TestLimitesExtratoRecebimentos(unittest.TestCase):
    def setUp(self):
        self.db = SqliteDatabase(':memory:')
        self.ctx = self.db.bind_ctx([models.Condominio, models.Meses])
        self.ctx.__enter__()
        self.db.create_tables([models.Condominio, models.Meses])
        models.Condominio.create(id='a')
        models.Condominio.create(id='b')

    def tearDown(self):
        self.db.close()
        self.ctx.__exit__(None, None, None)

    def test_limites_ordenam_meses_e_isolam_condominio(self):
        models.Meses.create(condominio_id='a', competencia='2024-02')
        models.Meses.create(condominio_id='a', competencia='2023-01')
        models.Meses.create(condominio_id='b', competencia='2030-01')
        self.assertEqual(obter_limites('a'), {'inicio': '2023-01-01', 'fim': '2024-02-29'})

    def test_condominio_e_meses_obrigatorios(self):
        with self.assertRaisesRegex(ValueError, 'Condomínio não encontrado'):
            obter_limites('inexistente')
        with self.assertRaisesRegex(ValueError, 'Não há meses cadastrados'):
            obter_limites('a')

    def test_competencia_invalida(self):
        models.Meses.create(condominio_id='a', competencia='invalida')
        with self.assertRaisesRegex(ValueError, 'Competência inválida'):
            obter_limites('a')
