"""Caracterização do fluxo mensal com navegador simulado e SQLite descartável."""
from contextlib import ExitStack
from datetime import datetime
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from extrator import execucao as extrator
from compartilhado import models
class FluxoExtracaoTest(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.banco = os.path.join(self.pasta.name, 'dados-teste.db')
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(extrator, 'project_root', self.pasta.name))
        self.patches.enter_context(patch.object(extrator, 'init_db', side_effect=lambda: models.init_models(self.banco)))
        self.patches.enter_context(patch('extrator.auditoria.get_ip_address', return_value='127.0.0.1'))
        self.patches.enter_context(patch('extrator.auditoria.get_mac_address', return_value=None))
        self.patches.enter_context(patch.object(extrator.time, 'sleep'))
        self.patches.enter_context(patch.object(extrator, 'capturar_sessao_api', return_value=('1', 'token-ficticio')))
        self.patches.enter_context(patch.object(extrator, 'extract_condominio_and_gestao',
                                              return_value=('teste', 'Condomínio teste', [{'nome': 'Ana', 'cargo': 'Síndica'}])))
        self.patches.enter_context(patch.object(extrator, 'extract_inadimplencia_boleto',
                                              return_value=('2025-01-31', 2, 100.0, 'Admin', ['11999999999'])))
        self.patches.enter_context(patch.object(extrator, 'set_ion_datetime', return_value=True))
        self.patches.enter_context(patch.object(extrator, 'wait_for_new_list_and_items', return_value=True))
        self.patches.enter_context(patch.object(extrator, 'close_last_modal'))
        self.playwright = self.patches.enter_context(patch.object(extrator, 'sync_playwright'))
        self.browser = self.playwright.return_value.__enter__.return_value.chromium.launch.return_value
        self.contexto = self.browser.new_context.return_value
        self.pagina, self.pc, self.documentos, self.demonstrativos = [MagicMock() for _ in range(4)]
        self.contexto.new_page.side_effect = [self.pagina, self.pc, self.documentos, self.demonstrativos]
        self.pagina.url = 'https://app.winker.com.br/intra'
        self.iframe = self.pagina.frame.return_value
        self.iframe_pc = self.pc.frame.return_value
        self.iframe_pc.locator.return_value.get_attribute.return_value = 'selected'
        self.iframe.locator.return_value.get_attribute.return_value = 'selected'
        self.mes = MagicMock()
        self.mes.inner_text.return_value = 'JAN/2025\nR$ 100,00\nR$ 0,00'
        self.botoes_mes = MagicMock()
        self.botoes_mes.all.return_value = [self.mes]
        self.botoes_mes.nth.return_value = self.mes
        self.listas = MagicMock()
        self.listas.count.return_value = 1
        self.saldo = MagicMock()
        self.saldo.locator.return_value.first.inner_text.return_value = 'R$ 500,00'
        self.iframe.locator.side_effect = lambda seletor, **kw: (
            self.botoes_mes if seletor == 'button.item.item-block.item-md' else
            self.listas if seletor == 'ion-list' else
            self.saldo if seletor == 'ion-card-content' else MagicMock())
        self.pc_coluna = self.iframe_pc.locator.return_value.filter.return_value.first
        self.pc_coluna.count.return_value = 0
        self.demonstrativos.locator.return_value.filter.return_value.first.count.return_value = 0
        self.documentos.locator.return_value.filter.return_value.first.count.return_value = 0
        self.ler_modal = self.patches.enter_context(patch.object(extrator, 'extract_list_from_modal'))
        self.ler_modal.side_effect = [
            [{'nome': 'Taxas', 'valor': 'R$ 100,00', 'index': 0}],
            [{'nome': 'Ordinária', 'valor': 'R$ 100,00', 'index': 0}],
            [{'nome': 'Taxa Apto - 101 JAN 2025 (10/01/2025)', 'valor': 'R$ 100,00',
              'anexos': [], 'anexos_count': 0}],
        ]
        self.addCleanup(self.fechar_banco)

    @staticmethod
    def fechar_banco():
        if not models.db.is_closed():
            models.db.close()

    def executar(self):
        extrator.extract_winker('usuario-ficticio', 'senha-ficticia', 'portal',
                                datetime(2025, 1, 1), datetime(2025, 1, 31), True)

    def test_mes_com_receita_grava_hierarquia_e_auditoria(self):
        self.executar()
        mes = models.Meses.get()
        transacao = models.Transacoes.get()
        auditoria = models.Auditoria.get()
        self.assertEqual((mes.competencia, mes.receita_total, mes.despesa_total), ('2025-01', 100, 0))
        self.assertEqual((transacao.tipo, transacao.apartamento, transacao.competencia, transacao.valor),
                         ('R', '101', '2025-01', 100))
        self.assertEqual((auditoria.status, auditoria.transacoes_lidas, auditoria.capturou_condominio,
                          auditoria.capturou_inadimplencia, auditoria.capturou_membros), ('concluida', 1, 1, 1, 1))
        self.assertEqual(models.Condominio.get_by_id('teste').saldo_declarado, 500)
        self.browser.close.assert_called_once_with()
        self.assertEqual(self.ler_modal.call_count, 3)

    def test_identifica_condominio_pela_api_quando_pagina_falha(self):
        extrator.extract_condominio_and_gestao.side_effect = RuntimeError('página indisponível')
        extrator.extract_inadimplencia_boleto.return_value = (None, None, None, None, None)
        with patch.object(extrator, 'extrair_condominio_api', return_value=(
                'teste', 'Condomínio da API', [{'nome': 'Bia', 'cargo': 'Síndica'}], 'Admin API', ['1133334444'])) as api:
            self.executar()
        api.assert_called_once_with(self.contexto, 'token-ficticio', '1')
        condominio = models.Condominio.get_by_id('teste')
        self.assertEqual((condominio.nome, condominio.administradora), ('Condomínio da API', 'Admin API'))
        self.assertEqual(models.MembrosGestao.get().nome, 'Bia')
        self.assertEqual((models.Auditoria.get().status, models.Auditoria.get().capturou_condominio), ('concluida', 1))

    def preparar_download(self):
        def baixar(contexto, url, pasta, filename_prefix='', default_filename=''):
            os.makedirs(pasta, exist_ok=True)
            caminho = os.path.join(pasta, 'prestacao.pdf')
            with open(caminho, 'wb') as arquivo:
                arquivo.write(b'%PDF-dados-ficticios')
            return caminho, 'prestacao.pdf'
        return self.patches.enter_context(patch.object(extrator, 'download_http_file', side_effect=baixar))

    def test_prestacao_da_aba_principal_e_movida_para_o_mes(self):
        self.pc_coluna.count.return_value = 1
        self.pc_coluna.locator.return_value.count.return_value = 1
        self.contexto.pages = []
        resposta = self.pc.expect_response.return_value.__enter__.return_value.value
        resposta.json.return_value = {'return': {'document_link': 'https://exemplo.test/documento.pdf'}}
        baixar = self.preparar_download()
        self.executar()
        prestacao = models.PrestacoesContas.get()
        caminho = os.path.join(self.pasta.name, *prestacao.caminho_local.split('/'))
        with open(caminho, 'rb') as arquivo:
            self.assertEqual(arquivo.read(), b'%PDF-dados-ficticios')
        self.assertEqual((prestacao.nome_original, prestacao.extensao), ('prestacao.pdf', 'pdf'))
        self.assertEqual(baixar.call_args.args[1], 'https://exemplo.test/documento.pdf')
        self.assertEqual(models.Auditoria.get().status, 'concluida')

    def test_prestacao_no_fallback_de_demonstrativos(self):
        celula = self.demonstrativos.locator.return_value.filter.return_value.first
        celula.count.return_value = 1
        botao = celula.locator.return_value.locator.return_value.first
        botao.count.return_value = 1
        botao.get_attribute.return_value = '/download/id/123'
        baixar = self.preparar_download()
        self.executar()
        self.assertEqual(baixar.call_args.args[1], 'https://app.winker.com.br/download/id/123')
        self.assertEqual(models.PrestacoesContas.select().count(), 1)
        self.assertEqual(models.Auditoria.get().status, 'concluida')

    def test_prestacao_no_fallback_de_balancetes(self):
        celula = self.documentos.locator.return_value.filter.return_value.first
        celula.count.return_value = 1
        botao = celula.locator.return_value.locator.return_value.first
        botao.count.return_value = 1
        botao.get_attribute.return_value = '/download/id/456'
        baixar = self.preparar_download()
        self.executar()
        self.assertEqual(baixar.call_args.args[1], 'https://app.winker.com.br/download/id/456')
        self.assertEqual(models.PrestacoesContas.select().count(), 1)
        self.assertEqual(models.Auditoria.get().status, 'concluida')

    def test_mes_com_receita_e_despesa_mantem_tipos_e_totais(self):
        self.mes.inner_text.return_value = 'JAN/2025\nR$ 100,00\nR$ 50,00'
        self.ler_modal.side_effect = [
            [{'nome': 'Taxas', 'valor': 'R$ 100,00', 'index': 0}],
            [{'nome': 'Ordinária', 'valor': 'R$ 100,00', 'index': 0}],
            [{'nome': 'Taxa Apto - 101 JAN 2025 (10/01/2025)', 'valor': 'R$ 100,00', 'anexos': [], 'anexos_count': 0}],
            [{'nome': 'Despesas', 'valor': 'R$ 50,00', 'index': 0}],
            [{'nome': 'Manutenção', 'valor': 'R$ 50,00', 'index': 0}],
            [{'nome': 'Pagamento Prestador - NF: 123 (20/01/2025)', 'valor': 'R$ 50,00', 'anexos': [], 'anexos_count': 0}],
        ]
        self.executar()
        self.assertEqual((models.Meses.get().receita_total, models.Meses.get().despesa_total), (100, 50))
        self.assertEqual([(t.tipo, t.valor) for t in models.Transacoes.select().order_by(models.Transacoes.tipo)],
                         [('D', 50), ('R', 100)])
        self.assertEqual(models.Auditoria.get().transacoes_lidas, 2)

    def test_anexo_baixado_e_vinculado_a_transacao_e_movido_apos_gravacao(self):
        pasta_temporaria = os.path.join(self.pasta.name, 'anexos', 'temp')
        os.makedirs(pasta_temporaria)
        temporario = os.path.join(pasta_temporaria, 'nota-baixada.pdf')
        with open(temporario, 'wb') as arquivo:
            arquivo.write(b'comprovante ficticio')
        self.ler_modal.side_effect = [
            [{'nome': 'Taxas', 'valor': 'R$ 100,00', 'index': 0}],
            [{'nome': 'Ordinária', 'valor': 'R$ 100,00', 'index': 0}],
            [{'nome': 'Taxa Apto - 101 JAN 2025 (10/01/2025)', 'valor': 'R$ 100,00', 'anexos_count': 1,
              'anexos': [{'temp_path': temporario, 'nome_original': 'nota.pdf'}]}],
        ]
        self.executar()
        anexo = models.Anexos.get()
        self.assertEqual(anexo.transacao_id.id, models.Transacoes.get().id)
        self.assertEqual((anexo.nome_original, anexo.extensao), ('nota.pdf', 'pdf'))
        self.assertFalse(os.path.exists(temporario))
        destino = os.path.join(self.pasta.name, *anexo.caminho_local.split('/'))
        with open(destino, 'rb') as arquivo:
            self.assertEqual(arquivo.read(), b'comprovante ficticio')
        self.assertEqual(models.Auditoria.get().status, 'concluida')

    def test_falha_na_gravacao_e_registrada_na_auditoria_e_fecha_browser(self):
        with patch.object(extrator, 'save_extraction_data_to_db', side_effect=RuntimeError('erro simulado')):
            self.executar()
        auditoria = models.Auditoria.get()
        self.assertEqual((auditoria.status, auditoria.erro), ('falha', 'erro simulado'))
        self.assertEqual(models.Meses.select().count(), 0)
        self.browser.close.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
