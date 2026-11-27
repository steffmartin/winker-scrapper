"""Exercita o entrypoint em cópia temporária, sem configuração ou banco reais."""
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from compartilhado import models
import playwright.sync_api
from compartilhado import utils
from extrator import execucao


class CliExtracaoTest(unittest.TestCase):
    def test_argumentos_configurados_iniciam_extracao_e_encerram_em_falha_de_login(self):
        with tempfile.TemporaryDirectory() as pasta:
            scripts = Path(pasta) / 'extrator'
            scripts.mkdir()
            copia = scripts / 'main.py'
            shutil.copyfile(Path(__file__).resolve().parents[2] / 'extrator' / 'main.py', copia)
            configuracao = {'user': 'usuario-teste', 'password': 'senha-teste', 'wl': 'portal-teste',
                            'start': '2024-12', 'end': '2025-01', 'headless': True, 'no_wait': True}
            navegador_simulado = MagicMock()
            navegador = navegador_simulado.return_value.__enter__.return_value.chromium.launch.return_value
            pagina = navegador.new_context.return_value.new_page.return_value
            pagina.goto.side_effect = RuntimeError('login simulado indisponível')
            with patch.object(sys, 'argv', [str(copia), '--config-file', 'ficticio.json']), \
                 patch.object(utils, 'load_config', return_value=configuracao) as carregar, \
                 patch.object(execucao, 'sync_playwright', navegador_simulado), \
                 patch.object(execucao, 'project_root', pasta), \
                 patch.object(models, 'init_models') as iniciar_banco, \
                 patch.object(models.Auditoria, 'create', return_value=MagicMock(id=None)), \
                 patch('socket.socket', side_effect=OSError('rede desativada')):
                with self.assertRaises(SystemExit) as saida:
                    runpy.run_path(str(copia), run_name='__main__')
                self.assertEqual(saida.exception.code, 1)
            carregar.assert_called_once_with('ficticio.json')
            iniciar_banco.assert_called_once_with(os.path.join(pasta, 'compartilhado', 'database', 'winker_data.db'))
            navegador.close.assert_called_once_with()
            navegador_simulado.return_value.__enter__.return_value.chromium.launch.assert_called_once_with(headless=True)


    def test_configuracao_padrao_e_a_local_ignorada(self):
        from extrator import main
        configuracao = {'user': 'usuario-ficticio', 'password': 'senha-ficticia',
                        'start': '2025-01', 'end': '2025-01', 'no_wait': True}
        with patch.object(sys, 'argv', ['extrator']), \
             patch.object(utils, 'load_config', return_value=configuracao) as carregar, \
             patch.object(execucao, 'extract_winker') as executar:
            main.main()
        carregar.assert_called_once_with('compartilhado/config/meu.config')
        executar.assert_called_once()


if __name__ == '__main__':
    unittest.main()
