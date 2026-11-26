"""Exercita o entrypoint em cópia temporária, sem configuração ou banco reais."""
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import models
import playwright.sync_api
import utils


class CliExtracaoTest(unittest.TestCase):
    def test_argumentos_configurados_iniciam_extracao_e_encerram_em_falha_de_login(self):
        with tempfile.TemporaryDirectory() as pasta:
            scripts = Path(pasta) / 'scripts'
            scripts.mkdir()
            copia = scripts / 'extract_winker.py'
            shutil.copyfile(Path(__file__).with_name('extract_winker.py'), copia)
            configuracao = {'user': 'usuario-teste', 'password': 'senha-teste', 'wl': 'portal-teste',
                            'start': '2024-12', 'end': '2025-01', 'headless': True, 'no_wait': True}
            navegador_simulado = MagicMock()
            navegador = navegador_simulado.return_value.__enter__.return_value.chromium.launch.return_value
            pagina = navegador.new_context.return_value.new_page.return_value
            pagina.goto.side_effect = RuntimeError('login simulado indisponível')
            with patch.object(sys, 'argv', [str(copia), '--config-file', 'ficticio.json']), \
                 patch.object(utils, 'load_config', return_value=configuracao) as carregar, \
                 patch.object(playwright.sync_api, 'sync_playwright', navegador_simulado), \
                 patch.object(models, 'init_models') as iniciar_banco, \
                 patch.object(models.Auditoria, 'create', return_value=MagicMock(id=None)), \
                 patch('socket.socket', side_effect=OSError('rede desativada')):
                runpy.run_path(str(copia), run_name='__main__')
            carregar.assert_called_once_with('ficticio.json')
            iniciar_banco.assert_called_once_with(os.path.join(pasta, 'database', 'winker_data.db'))
            navegador.close.assert_called_once_with()
            navegador_simulado.return_value.__enter__.return_value.chromium.launch.assert_called_once_with(headless=True)


if __name__ == '__main__':
    unittest.main()
