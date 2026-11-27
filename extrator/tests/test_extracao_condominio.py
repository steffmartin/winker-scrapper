"""Contratos de leitura do portal, usando apenas respostas simuladas."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from extrator import execucao as extrator
class ExtracaoCondominioTest(unittest.TestCase):
    def test_leitura_de_pdf_agrega_paginas_e_extrai_inadimplencia(self):
        paginas = [MagicMock(), MagicMock()]
        paginas[0].extract_text.return_value = 'Inadimplência do condomínio em 31/01/2025\nUnidades inadimplentes: 3\n'
        paginas[1].extract_text.return_value = 'Valor Total: 1.234,56'
        with patch.object(extrator.pypdf, 'PdfReader', return_value=MagicMock(pages=paginas)) as leitor:
            self.assertEqual(extrator.extract_inadimplencia_from_pdf('arquivo-ficticio.pdf'), ('31/01/2025', 3, 1234.56))
        leitor.assert_called_once_with('arquivo-ficticio.pdf')

    def test_leitura_de_pdf_invalido_retorna_campos_ausentes(self):
        with patch.object(extrator.pypdf, 'PdfReader', side_effect=ValueError('PDF inválido')):
            self.assertEqual(extrator.extract_inadimplencia_from_pdf('ficticio.pdf'), (None, None, None))

    def test_pagina_de_condominio_extrai_sindico_e_membros(self):
        pagina = MagicMock()
        codigo, breadcrumb, sindico, linhas = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        codigo.inner_text.return_value = ' COD-1 '
        breadcrumb.first.count.return_value = 1
        breadcrumb.first.inner_text.return_value = ' Condomínio Teste '
        sindico.first.count.return_value = 1
        sindico.first.inner_text.return_value = ' Ana - Síndica '
        membro = MagicMock()
        membro.locator.return_value.count.return_value = 1
        membro.locator.return_value.first.inner_text.return_value = ' Bruno '
        membro.inner_text.return_value = 'Bruno - Conselheiro Fiscal'
        linhas.all.return_value = [membro]
        seletores = {'div.info_cond_codigo_seguranca strong': codigo, '#breadcrumb a': breadcrumb,
                     'div.panel.panel-info label.label-success': sindico, '#lista_corpo_diretivo .row': linhas}
        pagina.locator.side_effect = lambda seletor: seletores[seletor]
        self.assertEqual(extrator.extract_condominio_and_gestao(pagina),
                         ('COD-1', 'Condomínio Teste', [{'nome': 'Ana', 'cargo': 'Síndico'},
                                                       {'nome': 'Bruno', 'cargo': 'Conselheiro Fiscal'}]))
        pagina.wait_for_selector.assert_called_once_with('div.info_cond_codigo_seguranca strong', timeout=10000)

    def test_sessao_usa_token_do_iframe_quando_pagina_nao_disponibiliza(self):
        pagina = MagicMock()
        pagina.evaluate.side_effect = [11, None]
        pagina.content.return_value = '<html></html>'
        pagina.frames = [MagicMock(url='https://outro.test/?token=ignorar'),
                         MagicMock(url='https://appweb.winker.com.br/?token=ficticio')]
        self.assertEqual(extrator.capturar_sessao_api(pagina), (11, 'ficticio'))

    def test_boleto_extrai_administradora_pdf_e_apaga_temporario(self):
        pagina, contexto = MagicMock(), MagicMock()
        info = MagicMock()
        info.inner_text.return_value = 'Contato - Administradora Exemplo (11) 99999-8888'
        cabecalho = MagicMock()
        cabecalho.all.return_value = [info]
        filtro = MagicMock()
        filtro.first.count.return_value = 1
        filtro.first.is_visible.return_value = True
        item = MagicMock()
        item.last.count.return_value = 1
        botao = item.last.locator.return_value.first
        botao.count.return_value = 1
        confirmacao = MagicMock()
        seletores = {'strong, .panel-heading, div.alert.alert-info': cabecalho,
                     "#boletos button:has-text('Filtrar')": filtro,
                     '.list-group-item': item, 'button.swal2-confirm': confirmacao}
        pagina.locator.side_effect = lambda seletor: seletores[seletor]
        with tempfile.TemporaryDirectory() as pasta, patch('extrator.inadimplencia.project_root', pasta):
            def baixar(contexto, botao, destino, **kwargs):
                caminho = os.path.join(destino, 'boleto.pdf')
                with open(caminho, 'wb') as arquivo:
                    arquivo.write(b'%PDF-ficticio')
                return caminho, 'boleto.pdf'
            with patch('extrator.inadimplencia.download_file_from_button', side_effect=baixar), \
                 patch('extrator.inadimplencia.extract_inadimplencia_from_pdf', return_value=('2025-01-31', 3, 500)):
                resultado = extrator.extract_inadimplencia_boleto(pagina, contexto)
            self.assertEqual(resultado, ('2025-01-31', 3, 500, 'Administradora Exemplo', ['11999998888']))
            self.assertEqual(os.listdir(os.path.join(pasta, 'anexos', 'temp')), [])
        filtro.first.click.assert_called_once_with()

    def test_boleto_ausente_preserva_dados_da_administradora(self):
        pagina = MagicMock()
        pagina.locator.return_value.all.return_value = []
        pagina.locator.return_value.first.count.return_value = 0
        pagina.wait_for_selector.side_effect = TimeoutError('sem boleto')
        self.assertEqual(extrator.extract_inadimplencia_boleto(pagina, MagicMock()), (None, None, None, None, []))


if __name__ == '__main__':
    unittest.main()
