"""Contratos de inicialização desktop sem abrir janelas nem dados reais."""
import os
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from bff import main as run_dashboard
class InicializacaoDashboardTest(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.raiz = self.pasta.name
        self.patch_raiz = patch.object(run_dashboard, 'project_root', self.raiz)
        self.patch_raiz.start()
        self.addCleanup(self.patch_raiz.stop)
        self.patch_api = patch.object(run_dashboard, 'Api')
        self.api = self.patch_api.start().return_value
        self.addCleanup(self.patch_api.stop)
        self.patch_webview = patch.object(run_dashboard, 'webview')
        self.webview = self.patch_webview.start()
        self.addCleanup(self.patch_webview.stop)
        self.patch_npm = patch.object(run_dashboard.subprocess, 'check_call')
        self.npm = self.patch_npm.start()
        self.addCleanup(self.patch_npm.stop)

    def criar(self, *partes):
        caminho = os.path.join(self.raiz, *partes)
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, 'w', encoding='utf-8') as arquivo:
            arquivo.write('teste')
        return caminho

    def test_sem_banco_mostra_aviso_sem_tentar_compilar(self):
        run_dashboard.main()
        chamada = self.webview.create_window.call_args.kwargs
        self.assertIn('Banco de Dados Não Encontrado', chamada['html'])
        self.assertIs(chamada['js_api'], self.api)
        self.npm.assert_not_called()
        self.webview.start.assert_called_once_with()

    def test_build_existente_abre_splash_e_janela_oculta(self):
        self.criar('compartilhado', 'database', 'winker_data.db')
        index = self.criar('dashboard', 'compilados', 'browser', 'index.html')
        splash = self.criar('dashboard', 'public', 'splash.html')
        run_dashboard.main()
        self.assertEqual(self.webview.create_window.call_count, 2)
        splash_args, janela_args = [c.kwargs for c in self.webview.create_window.call_args_list]
        self.assertEqual(splash_args['url'], splash)
        self.assertEqual(janela_args['url'], index)
        self.assertTrue(janela_args['hidden'])
        self.npm.assert_not_called()

    def test_fechamento_salva_preferencias_do_cache(self):
        self.criar('compartilhado', 'database', 'winker_data.db')
        self.criar('dashboard', 'compilados', 'browser', 'index.html')
        self.api.prefs_cache = {'darkTheme': True, 'primary': 'blue', 'surface': 'slate',
                                'preset': 'Aura', 'menuMode': 'overlay'}
        evento_fechamento = self.webview.create_window.return_value.events.closing
        run_dashboard.main()
        callback = evento_fechamento.__iadd__.call_args.args[0]
        callback()
        self.api.salvar_preferencias.assert_called_once_with({
            'modo_escuro': 1, 'cor_primaria': 'blue', 'cor_superficie': 'slate',
            'tema_preset': 'Aura', 'modo_menu': 'overlay'
        })

    def test_build_ausente_instala_dependencias_e_compila(self):
        self.criar('compartilhado', 'database', 'winker_data.db')
        def compilar(comando, **kwargs):
            if comando == ['npm', 'run', 'build']:
                self.criar('dashboard', 'compilados', 'browser', 'index.html')
        self.npm.side_effect = compilar
        run_dashboard.main()
        self.assertEqual([c.args[0] for c in self.npm.call_args_list], [['npm', 'install'], ['npm', 'run', 'build']])
        self.assertEqual(self.webview.create_window.call_args.kwargs['url'],
                         os.path.join(self.raiz, 'dashboard', 'compilados', 'browser', 'index.html'))

    def test_falha_instalacao_interrompe_sem_abrir_janela(self):
        self.criar('compartilhado', 'database', 'winker_data.db')
        self.npm.side_effect = subprocess.CalledProcessError(1, 'npm')
        with self.assertRaises(SystemExit):
            run_dashboard.main()
        self.webview.create_window.assert_not_called()

    def test_falha_compilacao_mostra_erro_quando_nao_ha_fallback(self):
        self.criar('compartilhado', 'database', 'winker_data.db')
        os.makedirs(os.path.join(self.raiz, 'dashboard', 'node_modules'))
        self.npm.side_effect = subprocess.CalledProcessError(1, 'npm')
        run_dashboard.main()
        self.assertIn('Erro de Inicialização do Dashboard', self.webview.create_window.call_args.kwargs['html'])
        self.assertEqual(self.npm.call_count, 1)


if __name__ == '__main__':
    unittest.main()
