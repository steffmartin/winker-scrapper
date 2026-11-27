"""A autenticação usa somente o navegador fornecido."""
import unittest
from unittest.mock import MagicMock

from extrator.autenticacao import autenticar


class AutenticacaoTest(unittest.TestCase):
    def test_seleciona_portal_configurado_apos_login(self):
        pagina = MagicMock(url='https://site/escolherPortal')
        autenticar(pagina, 'usuario-ficticio', 'senha-ficticia', 'portal', 2)
        pagina.goto.assert_called_once_with('https://app.winker.com.br/intra/default/login?wl=portal', wait_until='networkidle')
        pagina.fill.assert_any_call('#LoginForm_username', 'usuario-ficticio')
        pagina.fill.assert_any_call('#LoginForm_password', 'senha-ficticia')
        pagina.locator.return_value.nth.assert_called_once_with(1)
        pagina.wait_for_url.assert_any_call('**/intra', timeout=60000)
