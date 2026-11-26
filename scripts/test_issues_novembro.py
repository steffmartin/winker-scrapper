import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

import extract_winker as e
import models


class TestIssuesNovembro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        e.init_db(os.path.join(self.tmp.name, 'test.db'))
        models.Condominio.create(id='teste')

    def tearDown(self):
        models.db.close()
        self.tmp.cleanup()

    def test_regras_somente_campos_nao_preenchidos(self):
        regras = [{'descricao_contem': 'TARIFA', 'campo': 'conta', 'valor': 'CONTA CORRENTE'},
                  {'descricao_contem': 'tarifa', 'campo': 'fornecedor', 'valor': 'SICOOB'}]
        result = e.evaluate_entity_consistency('transacao', tipo_flag='D', desc_completa='Tarifa', desc_f='Tarifa', regras_preenchimento=regras)
        self.assertEqual(result[-2:], ('SICOOB', 'CONTA CORRENTE'))
        result = e.evaluate_entity_consistency('transacao', tipo_flag='D', desc_completa='Tarifa BANCO', desc_f='Tarifa', contas_list=['BANCO'], regras_preenchimento=regras)
        self.assertEqual(result[-1], 'BANCO')

    def test_reprocessamento_preserva_totais_revisados_em_cada_nivel(self):
        detalhes = {'receitas': [], 'despesas': [{'nome': 'Serviços', 'valor': '90,00', 'subcategorias': [
            {'nome': 'Limpeza', 'valor': '80,00', 'itens': [
                {'nome': 'Serviço (01/11/2026)', 'valor': '70,00', 'anexos': []}]}]}]}
        args = ('202611', 'NOV', 2026, 0, 100, detalhes, self.tmp.name)
        e.save_extraction_data_to_db(*args, condominio_id='teste')
        mes, categoria, subcategoria = models.Meses.get(), models.Categorias.get(), models.Subcategorias.get()
        self.assertEqual((mes.consistente, categoria.consistente, subcategoria.consistente), (0, 0, 0))
        mes.despesa_total, mes.revisado_usuario = 101, 1
        categoria.valor, categoria.revisado_usuario = 91, 1
        subcategoria.valor, subcategoria.revisado_usuario = 81, 1
        for registro in (mes, categoria, subcategoria):
            registro.save()
        e.save_extraction_data_to_db(*args, condominio_id='teste')
        mes, categoria, subcategoria = models.Meses.get(), models.Categorias.get(), models.Subcategorias.get()
        self.assertEqual((mes.despesa_total, categoria.valor, subcategoria.valor), (101, 91, 81))
        self.assertEqual((mes.revisado_usuario, categoria.revisado_usuario, subcategoria.revisado_usuario), (1, 1, 1))

    def test_reprocessamento_preserva_revisao_e_documento(self):
        detalhes = {'receitas': [], 'despesas': [{'nome': 'C', 'valor': '10,00', 'subcategorias': [{'nome': 'S', 'valor': '10,00', 'itens': [{'nome': 'Teste (01/11/2026)', 'valor': '10,00', 'anexos': []}]}]}]}
        args = ('202611', 'NOV', 2026, 0, 10, detalhes, self.tmp.name)
        mes_id, _ = e.save_extraction_data_to_db(*args, condominio_id='teste')
        trans = models.Transacoes.get()
        trans.fornecedor = 'Manual'
        trans.conta = 'Conta manual'
        trans.revisado_usuario = 1
        trans.save()
        diretorio = os.path.join(self.tmp.name, 'anexos', 'teste', '202611')
        os.makedirs(diretorio, exist_ok=True)
        caminho_rel = 'anexos/teste/202611/manual.pdf'
        caminho = os.path.join(diretorio, 'manual.pdf')
        with open(caminho, 'wb') as f:
            f.write(b'documento')
        models.Anexos.create(transacao_id=trans.id, nome_original='manual.pdf', caminho_local=caminho_rel, extensao='pdf')
        with open(os.path.join(diretorio, 'arquivo_sem_registro.pdf'), 'wb') as f:
            f.write(b'obsoleto')
        preservados = []
        mes_id, movimentos = e.save_extraction_data_to_db(*args, condominio_id='teste', anexos_preservados=preservados)
        trans = models.Transacoes.get()
        self.assertEqual((trans.fornecedor, trans.revisado_usuario, trans.consistente), ('Manual', 1, 0))
        self.assertEqual(models.Anexos.get().nome_original, 'manual.pdf')
        e._atualizar_arquivos_mes(self.tmp.name, diretorio, preservados, movimentos)
        self.assertTrue(os.path.isfile(caminho))
        self.assertFalse(os.path.exists(os.path.join(diretorio, 'arquivo_sem_registro.pdf')))
        detalhes['despesas'][0]['subcategorias'][0]['itens'] = [{'nome': 'Nova (02/11/2026)', 'valor': '10,00', 'anexos': []}]
        preservados = []
        _, movimentos = e.save_extraction_data_to_db(*args, condominio_id='teste', anexos_preservados=preservados)
        self.assertEqual(models.Transacoes.get().descricao, 'Nova')
        self.assertEqual(models.Anexos.select().count(), 0)
        e._atualizar_arquivos_mes(self.tmp.name, diretorio, preservados, movimentos)
        self.assertFalse(os.path.exists(caminho))

    def test_documento_antigo_descartado_quando_falta_de_comprovante_nao_persiste(self):
        item = {'nome': 'Tarifa (01/11/2026)', 'valor': '10,00', 'anexos': []}
        detalhes = {'receitas': [], 'despesas': [{'nome': 'C', 'valor': '10,00', 'subcategorias': [{'nome': 'S', 'valor': '10,00', 'itens': [item]}]}]}
        args = ('202611', 'NOV', 2026, 0, 10, detalhes, self.tmp.name)
        e.save_extraction_data_to_db(*args, condominio_id='teste')
        trans = models.Transacoes.get()
        trans.revisado_usuario = 1
        trans.save()
        diretorio = os.path.join(self.tmp.name, 'anexos', 'teste', '202611')
        os.makedirs(diretorio, exist_ok=True)
        antigo = os.path.join(diretorio, 'manual.pdf')
        with open(antigo, 'wb') as f:
            f.write(b'antigo')
        models.Anexos.create(transacao_id=trans.id, nome_original='manual.pdf', caminho_local='anexos/teste/202611/manual.pdf', extensao='pdf')
        baixado = os.path.join(self.tmp.name, 'novo.pdf')
        with open(baixado, 'wb') as f:
            f.write(b'novo')
        item['anexos_count'] = 1
        item['anexos'] = [{'nome_original': 'novo.pdf', 'temp_path': baixado}]
        preservados = []
        _, movimentos = e.save_extraction_data_to_db(*args, condominio_id='teste', anexos_preservados=preservados)
        self.assertEqual(preservados, [])
        self.assertEqual([a.nome_original for a in models.Anexos.select()], ['novo.pdf'])
        e._atualizar_arquivos_mes(self.tmp.name, diretorio, preservados, movimentos)
        self.assertFalse(os.path.exists(antigo))
        self.assertTrue(os.path.isfile(movimentos[0]['caminho_final']))

    def test_falha_apos_limpeza_recupera_anexo_preservado(self):
        diretorio = os.path.join(self.tmp.name, 'anexos', 'teste', '202611')
        os.makedirs(diretorio, exist_ok=True)
        caminho_rel = 'anexos/teste/202611/manual.pdf'
        caminho = os.path.join(diretorio, 'manual.pdf')
        with open(caminho, 'wb') as f:
            f.write(b'preservar')
        novo = os.path.join(self.tmp.name, 'novo.pdf')
        with open(novo, 'wb') as f:
            f.write(b'novo')
        copiar = e.shutil.copy2
        def falhar_novo(origem, destino):
            if origem == novo:
                raise OSError('falha simulada')
            return copiar(origem, destino)
        with patch.object(e.shutil, 'copy2', side_effect=falhar_novo):
            with self.assertRaises(OSError):
                e._atualizar_arquivos_mes(self.tmp.name, diretorio, [caminho_rel], [{'temp_path': novo, 'caminho_final': os.path.join(diretorio, 'novo.pdf')}])
        with open(caminho, 'rb') as f:
            self.assertEqual(f.read(), b'preservar')

    def test_reaplica_somente_motivo_ainda_presente(self):
        detalhes = {'receitas': [], 'despesas': [{'nome': 'C', 'valor': '10,00', 'subcategorias': [{'nome': 'S', 'valor': '10,00', 'itens': [{'nome': 'Tarifa (01/11/2026)', 'valor': '10,00', 'anexos': []}]}]}]}
        args = ('202611', 'NOV', 2026, 0, 10, detalhes, self.tmp.name)
        e.save_extraction_data_to_db(*args, condominio_id='teste')
        trans = models.Transacoes.get()
        trans.fornecedor, trans.conta, trans.revisado_usuario = 'Fornecedor antigo', 'Conta revista', 1
        trans.save()
        caminho = os.path.join(self.tmp.name, 'manual.pdf')
        with open(caminho, 'wb') as f:
            f.write(b'doc')
        models.Anexos.create(transacao_id=trans.id, nome_original='manual.pdf', caminho_local='manual.pdf', extensao='pdf')
        regras = [{'descricao_contem': 'tarifa', 'campo': 'fornecedor', 'valor': 'Fornecedor importado'}]
        e.save_extraction_data_to_db(*args, condominio_id='teste', regras_preenchimento=regras)
        trans = models.Transacoes.get()
        self.assertEqual((trans.fornecedor, trans.conta, trans.revisado_usuario), ('Fornecedor importado', 'Conta revista', 1))

    def test_motivo_novo_exige_nova_revisao(self):
        detalhes = {'receitas': [], 'despesas': [{'nome': 'C', 'valor': '10,00', 'subcategorias': [{'nome': 'S', 'valor': '10,00', 'itens': [{'nome': 'Tarifa (01/11/2026)', 'valor': '10,00', 'anexos': []}]}]}]}
        args = ('202611', 'NOV', 2026, 0, 10, detalhes, self.tmp.name)
        antigas = [{'descricao_contem': 'tarifa', 'campo': 'conta', 'valor': 'Conta original'}]
        e.save_extraction_data_to_db(*args, condominio_id='teste', regras_preenchimento=antigas)
        trans = models.Transacoes.get()
        trans.fornecedor, trans.revisado_usuario = 'Fornecedor manual', 1
        trans.save()
        novas = [{'descricao_contem': 'tarifa', 'campo': 'fornecedor', 'valor': 'Fornecedor novo'}]
        e.save_extraction_data_to_db(*args, condominio_id='teste', regras_preenchimento=novas)
        trans = models.Transacoes.get()
        self.assertEqual((trans.fornecedor, trans.conta, trans.revisado_usuario), ('Fornecedor novo', None, 0))

    def test_valor_antigo_nao_sobrescreve_valor_importado_consistente(self):
        detalhes = {'receitas': [], 'despesas': [{'nome': 'C', 'valor': '10,00', 'subcategorias': [{'nome': 'S', 'valor': '10,00', 'itens': [{'nome': 'Tarifa (01/11/2026)', 'valor': '10,00', 'anexos': []}]}]}]}
        args = ('202611', 'NOV', 2026, 0, 10, detalhes, self.tmp.name)
        e.save_extraction_data_to_db(*args, condominio_id='teste')
        trans = models.Transacoes.get()
        trans.fornecedor, trans.conta, trans.revisado_usuario = 'Antigo', 'Antiga', 1
        trans.save()
        regras = [{'descricao_contem': 'tarifa', 'campo': 'fornecedor', 'valor': 'Novo'},
                  {'descricao_contem': 'tarifa', 'campo': 'conta', 'valor': 'Nova'}]
        e.save_extraction_data_to_db(*args, condominio_id='teste', regras_preenchimento=regras)
        trans = models.Transacoes.get()
        self.assertEqual((trans.fornecedor, trans.conta), ('Novo', 'Nova'))
        self.assertEqual(trans.revisado_usuario, 0)  # falta de comprovante ainda não corrigida

    def test_regra_tarifa_match_case_insensitive_contains(self):
        regras = [{'descricao_contem': 'TARIFA COBRANÇA', 'campo': 'fornecedor', 'valor': 'SICOOB ARACOOP'},
                  {'descricao_contem': 'TARIFA COBRANÇA', 'campo': 'conta', 'valor': 'CONTA CORRENTE'}]
        resultado = e.evaluate_entity_consistency('transacao', tipo_flag='D', desc_completa='Lançamento tarifa cobrança boleto', desc_f='Lançamento tarifa cobrança boleto', regras_preenchimento=regras)
        self.assertEqual(resultado[-2:], ('SICOOB ARACOOP', 'CONTA CORRENTE'))

    @patch('extract_winker._get_ip_address', return_value=None)
    @patch('extract_winker.socket.socket', side_effect=OSError())
    def test_ip_indisponivel_tem_fallback_explicito(self, *_):
        self.assertEqual(e.get_ip_address(), 'indisponível')

    @patch('extract_winker.get_mac_address', return_value=None)
    @patch('extract_winker.get_ip_address', return_value='indisponível')
    @patch('extract_winker.init_db')
    @patch('extract_winker.sync_playwright')
    def test_falha_login_finaliza_auditoria(self, playwright, init_db, *_):
        p = playwright.return_value.__enter__.return_value
        browser = p.chromium.launch.return_value
        page = MagicMock()
        browser.new_context.return_value.new_page.return_value = page
        page.goto.side_effect = TimeoutError('login indisponível')
        with patch.object(e, 'project_root', self.tmp.name):
            e.extract_winker('u', 'p', '', datetime(2026, 11, 1), datetime(2026, 11, 1), True)
        audit = models.Auditoria.get()
        self.assertEqual((audit.status, audit.erro, audit.ip), ('falha', 'login indisponível', 'indisponível'))
        self.assertIsNotNone(audit.tempo_duracao)

if __name__ == '__main__':
    unittest.main()
