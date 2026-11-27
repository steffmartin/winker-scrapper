import unittest
import sys
from pathlib import Path
from unittest.mock import patch

with patch('compartilhado.setup_deps.install_dependencies'):
    from bff.main import Api


class TestApartamentosRelatorio(unittest.TestCase):
    def test_lista_do_condominio_ativo_e_cadastro_vazio(self):
        api = Api.__new__(Api)
        api.init_error = None
        api.condo_id = 42
        with patch('compartilhado.models.Condominio.get_or_none') as buscar:
            buscar.return_value.apartamentos = '["101", "202"]'
            self.assertEqual(api.get_apartamentos(), {"status": "success", "data": ["101", "202"]})
            buscar.assert_called_with(id=42)
            buscar.return_value.apartamentos = None
            self.assertEqual(api.get_apartamentos(), {"status": "success", "data": []})
            buscar.return_value.apartamentos = '{"invalido": true}'
            self.assertEqual(api.get_apartamentos()['status'], 'error')

    def test_condominio_ausente_e_falha_inicial(self):
        api = Api.__new__(Api)
        api.condo_id = 42
        api.init_error = 'Banco indisponível'
        self.assertEqual(api.get_apartamentos()['message'], 'Banco indisponível')
        api.init_error = None
        with patch('compartilhado.models.Condominio.get_or_none', return_value=None):
            self.assertEqual(api.get_apartamentos()['status'], 'error')
