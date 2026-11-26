"""Testes de verificação de dependências sem instalação ou acesso à rede."""
import builtins
import unittest
from unittest.mock import patch

import setup_deps


class DependenciasTest(unittest.TestCase):
    def test_instala_playwright_e_navegador_quando_pacote_ausente(self):
        importar_real = builtins.__import__
        def importar(nome, *args, **kwargs):
            if nome == 'playwright':
                raise ImportError('dependência simulada ausente')
            return importar_real(nome, *args, **kwargs)
        with patch('builtins.__import__', side_effect=importar), \
             patch.object(setup_deps.subprocess, 'check_call') as executar:
            setup_deps.install_dependencies()
        comandos = [chamada.args[0] for chamada in executar.call_args_list]
        self.assertEqual(comandos, [[setup_deps.sys.executable, '-m', 'pip', 'install', 'playwright', '--quiet'],
                                    [setup_deps.sys.executable, '-m', 'playwright', 'install', 'chromium']])

    def test_falha_na_instalacao_do_navegador_nao_aborta_inicializacao(self):
        importar_real = builtins.__import__
        def importar(nome, *args, **kwargs):
            if nome == 'playwright':
                raise ImportError('dependência simulada ausente')
            return importar_real(nome, *args, **kwargs)
        with patch('builtins.__import__', side_effect=importar), \
             patch.object(setup_deps.subprocess, 'check_call', side_effect=[None, RuntimeError('falha simulada')]), \
             patch.object(setup_deps.logger, 'warning') as aviso:
            setup_deps.install_dependencies()
        self.assertIn('falha simulada', aviso.call_args.args[0])
