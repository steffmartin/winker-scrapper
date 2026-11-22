import sys
import unittest
import types
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exportar_relatorio


class TestExportarRelatorio(unittest.TestCase):
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
        with patch.object(exportar_relatorio, '_gerar_pdf') as gerar:
            resposta = exportar_relatorio.salvar_pdf(janela, 'Extrato de recebimentos')
        self.assertEqual(resposta, {'status': 'success', 'path': 'C:/relatorios/extrato.pdf'})
        self.assertEqual(janela.create_file_dialog.call_args.kwargs['save_filename'], 'Extrato de recebimentos.pdf')
        gerar.assert_called_once_with(janela, 'C:/relatorios/extrato.pdf')

    def test_cancelamento_e_extensao(self):
        janela = Mock()
        janela.create_file_dialog.return_value = None
        with patch.object(exportar_relatorio, '_gerar_pdf') as gerar:
            self.assertEqual(exportar_relatorio.salvar_pdf(janela, 'Relatório'), {'status': 'cancelled'})
            gerar.assert_not_called()
            janela.create_file_dialog.return_value = 'C:/relatorios/arquivo'
            exportar_relatorio.salvar_pdf(janela, 'Relatório')
            gerar.assert_called_once_with(janela, 'C:/relatorios/arquivo.pdf')

    def test_erro_de_geracao_nao_e_silenciado(self):
        janela = Mock()
        janela.create_file_dialog.return_value = ('C:/relatorios/arquivo.pdf',)
        with patch.object(exportar_relatorio, '_gerar_pdf', side_effect=RuntimeError('Falha')):
            with self.assertRaisesRegex(RuntimeError, 'Falha'):
                exportar_relatorio.salvar_pdf(janela, 'Relatório')
