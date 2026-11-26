import sys
import unittest
import types
import ntpath
from urllib.parse import urlparse
from urllib.request import url2pathname
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exportar_relatorio


class TestExportarRelatorio(unittest.TestCase):
    def test_html_temporario_em_outra_unidade_nao_usa_caminho_relativo(self):
        janela = Mock()
        janela.create_file_dialog.return_value = ('D:/relatorios/arquivo.pdf',)
        janela.evaluate_js.return_value = '<html><body>Teste</body></html>'
        auxiliar = Mock()
        auxiliar.events.loaded.wait.return_value = True

        def criar_janela(titulo, *, url, hidden):
            # O servidor global do pywebview chama relpath para caminhos locais,
            # mas trata file:// como uma URL que não precisa ser relativizada.
            if not url.startswith('file://'):
                ntpath.relpath(r'C:\Temp\relatorio.html', r'D:\app\compilados')
            self.assertEqual(urlparse(url).scheme, 'file')
            self.assertTrue(Path(url2pathname(urlparse(url).path)).exists())
            return auxiliar

        with patch.object(exportar_relatorio.webview, 'create_window', side_effect=criar_janela), patch.object(exportar_relatorio, '_gerar_pdf'):
            self.assertEqual(exportar_relatorio.salvar_pdf(janela, 'Relatório')['status'], 'success')

    def test_gera_pdf_com_orientacao_paisagem(self):
        class Func:
            def __class_getitem__(cls, tipo):
                return lambda funcao: funcao

        sistema = types.ModuleType('System')
        sistema.Func, sistema.Object = Func, object
        webview2 = types.ModuleType('Microsoft.Web.WebView2.Core')
        webview2.CoreWebView2PrintOrientation = types.SimpleNamespace(Landscape='paisagem')
        janela = Mock()
        controle = janela.native.webview
        controle.Invoke.side_effect = lambda funcao: funcao()
        configuracao = controle.CoreWebView2.Environment.CreatePrintSettings.return_value
        controle.CoreWebView2.PrintToPdfAsync.return_value.GetAwaiter.return_value.GetResult.return_value = True
        with patch.dict(sys.modules, {'System': sistema, 'Microsoft.Web.WebView2.Core': webview2}):
            exportar_relatorio._gerar_pdf(janela, 'C:/relatorios/extrato.pdf')
        self.assertEqual(configuracao.Orientation, 'paisagem')
        controle.CoreWebView2.PrintToPdfAsync.assert_called_once_with('C:/relatorios/extrato.pdf', configuracao)

    def test_seleciona_caminho_e_gera_pdf(self):
        janela = Mock()
        janela.create_file_dialog.return_value = ('C:/relatorios/extrato.pdf',)
        janela.evaluate_js.return_value = '<html><body>Relatório</body></html>'
        auxiliar = Mock()
        auxiliar.events.loaded.wait.return_value = True
        with patch.object(exportar_relatorio, '_gerar_pdf') as gerar, patch.object(exportar_relatorio.webview, 'create_window', return_value=auxiliar) as criar:
            resposta = exportar_relatorio.salvar_pdf(janela, 'Extrato de recebimentos')
        self.assertEqual(resposta, {'status': 'success', 'path': 'C:/relatorios/extrato.pdf'})
        self.assertEqual(janela.create_file_dialog.call_args.kwargs['save_filename'], 'Extrato de recebimentos.pdf')
        self.assertTrue(criar.call_args.kwargs['hidden'])
        gerar.assert_called_once_with(auxiliar, 'C:/relatorios/extrato.pdf')
        auxiliar.destroy.assert_called_once()

    def test_cancelamento_e_extensao(self):
        janela = Mock()
        janela.create_file_dialog.return_value = None
        auxiliar = Mock()
        auxiliar.events.loaded.wait.return_value = True
        janela.evaluate_js.return_value = '<html></html>'
        with patch.object(exportar_relatorio, '_gerar_pdf') as gerar, patch.object(exportar_relatorio.webview, 'create_window', return_value=auxiliar):
            self.assertEqual(exportar_relatorio.salvar_pdf(janela, 'Relatório'), {'status': 'cancelled'})
            gerar.assert_not_called()
            janela.create_file_dialog.return_value = 'C:/relatorios/arquivo'
            exportar_relatorio.salvar_pdf(janela, 'Relatório')
            gerar.assert_called_once_with(auxiliar, 'C:/relatorios/arquivo.pdf')

    def test_erro_de_geracao_nao_e_silenciado(self):
        janela = Mock()
        janela.create_file_dialog.return_value = ('C:/relatorios/arquivo.pdf',)
        janela.evaluate_js.return_value = '<html></html>'
        auxiliar = Mock()
        auxiliar.events.loaded.wait.return_value = True
        with patch.object(exportar_relatorio, '_gerar_pdf', side_effect=RuntimeError('Falha')), patch.object(exportar_relatorio.webview, 'create_window', return_value=auxiliar):
            with self.assertRaisesRegex(RuntimeError, 'Falha'):
                exportar_relatorio.salvar_pdf(janela, 'Relatório')
        auxiliar.destroy.assert_called_once()

    def test_falha_ao_carregar_fecha_janela_auxiliar(self):
        janela = Mock()
        janela.create_file_dialog.return_value = ('C:/relatorios/arquivo.pdf',)
        janela.evaluate_js.return_value = '<html></html>'
        auxiliar = Mock()
        auxiliar.events.loaded.wait.return_value = False
        with patch.object(exportar_relatorio.webview, 'create_window', return_value=auxiliar), patch.object(exportar_relatorio, '_gerar_pdf') as gerar:
            with self.assertRaisesRegex(RuntimeError, 'carregar'):
                exportar_relatorio.salvar_pdf(janela, 'Relatório')
        gerar.assert_not_called()
        auxiliar.destroy.assert_called_once()
