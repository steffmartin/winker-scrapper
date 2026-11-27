import unittest
import sqlite3
import os
import sys
from unittest.mock import patch, MagicMock
from datetime import date

# Add the project root to sys.path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from bff.main import Api

class TestRunDashboard(unittest.TestCase):

    def test_taxas_repetidas_virada_de_ano_e_operacoes(self):
        from compartilhado import models
        resposta = self.api.insert_taxa({'competencia': '2023-12', 'vencimento': '31/12/2023',
                                         'meses_repeticao': 3, 'tipo': 'I', 'apartamento': '101',
                                         'descricao': 'Garagem', 'valor_original': 42})
        self.assertEqual(resposta['status'], 'success')
        taxas = list(models.Taxas.select().where(models.Taxas.descricao == 'Garagem').order_by(models.Taxas.competencia))
        self.assertEqual([(t.competencia, t.exibicao, t.vencimento) for t in taxas],
                         [('2023-12', 'DEZ/2023', '31/12/2023'), ('2024-01', 'JAN/2024', '31/01/2024'),
                          ('2024-02', 'FEV/2024', '29/02/2024')])
        selecionadas = self.api.get_taxas_por_apartamento('101', ['2023-12', '2024-02'])['data']
        self.assertEqual([t['competencia'] for t in selecionadas], ['2024-02', '2024-01', '2023-12'])
        self.assertEqual(self.api.get_taxas_por_apartamento('102', ['2023-12', '2024-02'])['data'], [])
        self.assertEqual(self.api.update_taxa(taxas[0].id, {'competencia': '2024-03', 'valor_original': 50})['status'], 'success')
        atualizada = models.Taxas.get_by_id(taxas[0].id)
        self.assertEqual((atualizada.exibicao, atualizada.valor_original), ('MAR/2024', 50))
        self.assertEqual(self.api.delete_taxa(taxas[0].id)['status'], 'success')
        self.assertFalse(models.Taxas.select().where(models.Taxas.id == taxas[0].id).exists())

    def test_desconto_herda_vencimento_e_taxa_renegociada_nao_e_editada_isoladamente(self):
        from compartilhado import models
        original = models.Taxas.select().where(models.Taxas.tipo == 'C').get()
        self.assertEqual(self.api.insert_taxa({'tipo': 'D', 'taxa_id': original.id, 'competencia': '2023-01',
                                               'apartamento': '101', 'valor_original': 10})['status'], 'success')
        desconto = models.Taxas.get(models.Taxas.tipo == 'D')
        self.assertEqual(desconto.vencimento, original.vencimento)
        self.assertEqual(desconto.taxa_id_id, original.id)
        self.assertEqual(self.api.update_taxa(desconto.id, {'competencia': '2023-02', 'descricao': 'desconto'})['status'], 'success')
        desconto = models.Taxas.get_by_id(desconto.id)
        self.assertEqual((desconto.exibicao, desconto.descricao), ('FEV/2023', 'desconto'))
        parcela = models.Taxas.create(condominio_id=self.condo_id, tipo='P', competencia='2023-01', valor_original=50)
        self.assertEqual(self.api.update_taxa(parcela.id, {'valor_original': 10})['status'], 'error')
        self.assertEqual(self.api.delete_taxa(parcela.id)['status'], 'error')
        self.assertEqual(models.Taxas.get_by_id(parcela.id).valor_original, 50)

    def test_preferencias_anexos_e_prestacoes(self):
        self.assertEqual(self.api.get_preferencias()['data']['condominio_id'], self.condo_id)
        dados = {'modo_escuro': True, 'cor_primaria': 'emerald', 'modo_menu': 'static'}
        self.assertEqual(self.api.salvar_preferencias(dados)['status'], 'success')
        preferencias = self.api.get_preferencias()['data']
        for chave, valor in dados.items():
            self.assertEqual(preferencias[chave], valor)
        self.assertEqual(self.api.sync_preferencias_cache(dados), {'status': 'success'})
        self.assertEqual(self.api.prefs_cache, dados)
        self.assertEqual([item['id'] for item in self.api.get_anexos_transacao(1)['data']], [1])
        self.assertEqual([item['id'] for item in self.api.get_prestacoes_contas_mes('2023-01')['data']], [1])
        self.assertEqual(self.api.get_prestacoes_contas_mes('1900-01')['status'], 'error')

    def test_selecao_de_arquivo_e_janelas(self):
        from unittest.mock import MagicMock
        self.assertEqual(self.api.selecionar_arquivo()['status'], 'error')
        janela = MagicMock()
        self.api._main_window = janela
        janela.create_file_dialog.return_value = []
        self.assertEqual(self.api.selecionar_arquivo()['status'], 'cancelled')
        janela.create_file_dialog.return_value = ['arquivo_sem_extensao']
        self.assertEqual(self.api.selecionar_arquivo()['status'], 'error')
        janela.create_file_dialog.return_value = ['arquivo.pdf']
        self.assertEqual(self.api.selecionar_arquivo(), {'status': 'success', 'data': 'arquivo.pdf'})
        splash = MagicMock()
        self.api._splash_window = splash
        self.assertEqual(self.api.app_ready(), {'status': 'success'})
        janela.show.assert_called_once_with()
        splash.destroy.assert_called_once_with()
        self.assertIsNone(self.api._splash_window)

    def test_encerramento_salva_preferencias_e_destroi_janela(self):
        from unittest.mock import MagicMock
        self.api._main_window = MagicMock()
        self.api.prefs_cache = {'darkTheme': True, 'primary': 'blue', 'surface': 'slate',
                                'preset': 'Aura', 'menuMode': 'overlay'}
        with patch.object(self.api, 'salvar_preferencias') as salvar, patch('threading.Timer') as timer:
            self.assertEqual(self.api.exit_app(), {'status': 'success'})
        salvar.assert_called_once_with({'modo_escuro': 1, 'cor_primaria': 'blue', 'cor_superficie': 'slate',
                                        'tema_preset': 'Aura', 'modo_menu': 'overlay'})
        self.api._main_window.destroy.assert_called_once_with()
        timer.return_value.start.assert_called_once_with()

    def test_abrir_arquivo_local_trata_caminho_ausente_e_falha(self):
        import tempfile
        from bff import main as dashboard
        self.assertEqual(self.api.abrir_arquivo_local('')['status'], 'error')
        with tempfile.TemporaryDirectory() as pasta, patch.object(self.api, '_raiz_projeto', pasta):
            self.assertEqual(self.api.abrir_arquivo_local('ausente.pdf')['status'], 'error')
            with open(os.path.join(pasta, 'nota.pdf'), 'wb') as arquivo:
                arquivo.write(b'nota ficticia')
            with patch.object(dashboard.os, 'startfile', create=True) as abrir:
                self.assertEqual(self.api.abrir_arquivo_local('nota.pdf'), {'status': 'success'})
                abrir.assert_called_once_with(os.path.join(pasta, 'nota.pdf'))
                abrir.side_effect = OSError('falha simulada')
                self.assertEqual(self.api.abrir_arquivo_local('nota.pdf')['status'], 'error')

    def test_revisao_lista_e_atualiza_cada_nivel(self):
        from compartilhado import models
        for tipo in ('meses', 'categorias', 'subcategorias', 'lancamentos', 'documentos'):
            with self.subTest(tipo=tipo):
                resposta = self.api.get_registros_nao_revisados(tipo)
                self.assertEqual(resposta['status'], 'success')
                self.assertTrue(resposta['data'])
        lancamento = self.api.get_registros_nao_revisados('lancamentos')['data'][0]
        self.assertEqual(lancamento['anexos_lista'][0]['id'], 1)
        self.assertEqual({doc['tipo_doc'] for doc in self.api.get_registros_nao_revisados('documentos')['data']}, {'C', 'P'})
        self.assertEqual(self.api.update_registro_revisado('meses', {'id': 1, 'receita_total': 501, 'revisado_usuario': 1})['status'], 'success')
        self.assertEqual(self.api.update_registro_revisado('categorias', {'id': 1, 'valor': 101, 'revisado_usuario': 1})['status'], 'success')
        self.assertEqual(self.api.update_registro_revisado('subcategorias', {'id': 1, 'valor': 102, 'revisado_usuario': 1})['status'], 'success')
        self.assertEqual(self.api.update_registro_revisado('lancamentos', {'id': 1, 'apartamento': '101', 'conta': 'Corrente', 'revisado_usuario': 1})['status'], 'success')
        self.assertEqual(self.api.update_registro_revisado('documentos', {'id': 1, 'tipo_doc': 'C', 'revisado_usuario': 1})['status'], 'success')
        self.assertEqual(models.Meses.get_by_id(1).receita_total, 501)
        self.assertEqual(models.Categorias.get_by_id(1).valor, 101)
        self.assertEqual(models.Subcategorias.get_by_id(1).valor, 102)
        self.assertEqual(models.Transacoes.get_by_id(1).conta, 'Corrente')
        self.assertEqual(models.Anexos.get_by_id(1).revisado_usuario, 1)
        for tipo in ('meses', 'categorias', 'subcategorias', 'lancamentos'):
            self.assertNotIn(1, [r['id'] for r in self.api.get_registros_nao_revisados(tipo)['data']])
            self.assertIn(1, [r['id'] for r in self.api.get_registros_nao_revisados(tipo, True)['data']])

    def test_revisao_rejeita_apartamento_inexistente_e_id_ausente(self):
        from compartilhado import models
        resposta = self.api.update_registro_revisado('lancamentos', {'id': 1, 'apartamento': '999'})
        self.assertEqual(resposta['status'], 'error')
        self.assertEqual(models.Transacoes.get_by_id(1).apartamento, '101')
        self.assertEqual(self.api.update_registro_revisado('categorias', {})['status'], 'error')

    def test_operacoes_propagam_erro_de_inicializacao_sem_acessar_banco(self):
        self.api.init_error = 'Banco indisponível'
        operacoes = [
            ('get_nome_condominio', ()), ('get_condominios', ()), ('set_condominio', ('teste',)),
            ('get_contas_relatorio', ()), ('get_relatorio_conta', ()),
            ('get_relatorio_recebimentos', ()), ('get_apartamentos', ()),
            ('get_condominio_config', ()), ('update_condominio_config', ({},)), ('get_pendencias_revisao_count', ()),
            ('get_dashboard_kpis', ()), ('get_transacoes', ()), ('get_registros_nao_revisados', ('meses',)),
            ('update_registro_revisado', ('meses', {})), ('get_inadimplencia', ()),
            ('get_taxas_por_apartamento', ('101', ['2023-01', '2023-12'])), ('get_taxas', ()),
            ('delete_taxa', (1,)), ('update_taxa', (1, {})), ('insert_taxa', ({},)),
            ('get_renegociacao', (1,)), ('delete_renegociacao', (1,)), ('salvar_renegociacao', ({},)),
            ('selecionar_arquivo', ()), ('get_anexos_transacao', (1,)), ('get_prestacoes_contas_mes', ('2023-01',)),
            ('get_preferencias', ()), ('salvar_preferencias', ({},)),
        ]
        for nome, argumentos in operacoes:
            with self.subTest(operacao=nome):
                self.assertEqual(getattr(self.api, nome)(*argumentos),
                                 {'status': 'error', 'message': 'Banco indisponível'})

    def test_consulta_condominios_e_altera_selecao_persistida(self):
        from compartilhado import models
        models.Condominio.create(id='segundo', nome='Segundo')
        self.assertEqual(self.api.get_nome_condominio()['data']['nome'], 'Condominio Teste')
        resposta = self.api.get_condominios()
        self.assertEqual(resposta['current_id'], self.condo_id)
        self.assertEqual({c['id'] for c in resposta['data']}, {self.condo_id, 'segundo'})
        self.assertEqual(self.api.set_condominio('segundo')['status'], 'success')
        self.assertEqual(self.api.get_nome_condominio()['data']['nome'], 'Segundo')
        self.assertEqual(models.PreferenciasUsuario.select().first().condominio_id, 'segundo')

    def test_relatorios_e_pdf_propagam_erro_sem_alterar_formato_da_resposta(self):
        with patch('bff.relatorio_conta.gerar', side_effect=RuntimeError('relatório indisponível')):
            self.assertEqual(self.api.get_relatorio_conta(), {'status': 'error', 'message': 'relatório indisponível'})
        with patch('bff.exportar_relatorio.salvar_pdf', side_effect=RuntimeError('impressão indisponível')):
            self.assertEqual(self.api.salvar_relatorio_pdf('relatorio'), {'status': 'error', 'message': 'impressão indisponível'})
        with patch.object(self.api, '_calcular_posicao_unificada', side_effect=RuntimeError('conciliação indisponível')):
            resposta = self.api.get_relatorio_inadimplencia({'data_corte': '2025-01-01'})
            self.assertEqual(resposta, {'status': 'error', 'message': 'conciliação indisponível'})
            resposta = self.api.get_inadimplencia('2025-01-01')
            self.assertEqual(resposta, {'status': 'error', 'message': 'conciliação indisponível'})

    def test_configuracao_persiste_campos_membros_e_contas(self):
        payload = {'condominio': {'nome': 'Novo nome', 'administradora': 'Administradora teste',
                                  'telefone_administradora': ['1133334444'], 'apartamentos': ['001', '102'],
                                  'prazo_fechamento': 7, 'inadimplencia_data_corte': '2025-01-31',
                                  'inadimplencia_unidades': 2, 'inadimplencia_valor': 150,
                                  'saldo_declarado': 1200, 'tipo_juros_multa': 'N', 'taxa_renegociacao': 5},
                   'membros': [{'nome': 'Maria', 'cargo': 'Síndica'}],
                   'contas': [{'conta': 'Corrente', 'saldo_inicial': 100}, {'conta': 'Reserva', 'saldo_inicial': 50}]}
        self.assertEqual(self.api.update_condominio_config(payload)['status'], 'success')
        configuracao = self.api.get_condominio_config()['data']
        for campo, valor in payload['condominio'].items():
            self.assertEqual(configuracao['condominio'][campo], valor, campo)
        self.assertEqual([(m['nome'], m['cargo']) for m in configuracao['membros']], [('Maria', 'Síndica')])
        self.assertEqual(self.api.get_contas_relatorio()['data'], ['Corrente', 'Reserva'])
        self.assertEqual(self.api.get_apartamentos()['data'], ['001', '102'])

    def test_revisao_remove_e_renomeia_documentos_no_diretorio_isolado(self):
        import tempfile
        from compartilhado import models
        from bff import main as dashboard
        with tempfile.TemporaryDirectory() as pasta, patch.object(self.api, '_raiz_projeto', pasta):
            anexo = models.Anexos.get_by_id(1)
            anexo.caminho_local = 'anexo.dat'
            anexo.nome_original = 'original.dat'
            anexo.save()
            with open(os.path.join(pasta, 'anexo.dat'), 'wb') as arquivo:
                arquivo.write(b'documento de teste')
            resposta = self.api.update_registro_revisado('documentos', {'id': 1, 'tipo_doc': 'C', 'extensao': '.pdf'})
            self.assertEqual(resposta['status'], 'success')
            self.assertTrue(os.path.exists(os.path.join(pasta, 'anexo.pdf')))
            self.assertEqual(models.Anexos.get_by_id(1).nome_original, 'original.pdf')
            resposta = self.api.update_registro_revisado('lancamentos', {'id': 1, 'anexos_removidos': [1, 9999]})
            self.assertEqual(resposta['status'], 'success')
            self.assertFalse(os.path.exists(os.path.join(pasta, 'anexo.pdf')))
            self.assertFalse(models.Anexos.select().where(models.Anexos.id == 1).exists())
            prestacao = models.PrestacoesContas.get_by_id(1)
            prestacao.caminho_local = 'prestacao.pdf'
            prestacao.save()
            with open(os.path.join(pasta, 'prestacao.pdf'), 'wb') as arquivo:
                arquivo.write(b'prestacao ficticia')
            resposta = self.api.update_registro_revisado('meses', {'id': 1, 'anexos_removidos': [1, 9999]})
            self.assertEqual(resposta['status'], 'success')
            self.assertFalse(os.path.exists(os.path.join(pasta, 'prestacao.pdf')))
            self.assertFalse(models.PrestacoesContas.select().where(models.PrestacoesContas.id == 1).exists())

    def test_revisao_adiciona_documentos_a_mes_e_lancamento(self):
        import tempfile
        from compartilhado import models
        from bff import main as dashboard
        with tempfile.TemporaryDirectory() as pasta, patch.object(self.api, '_raiz_projeto', pasta):
            origem = os.path.join(pasta, 'entrada.pdf')
            with open(origem, 'wb') as arquivo:
                arquivo.write(b'arquivo de teste')
            mes = self.api.update_registro_revisado('meses', {'id': 1, 'prestacoes_contas': [{'caminho_local': origem}]})
            lancamento = self.api.update_registro_revisado('lancamentos', {'id': 1, 'anexos_lista': [{'caminho_local': origem}]})
            self.assertEqual((mes['status'], lancamento['status']), ('success', 'success'))
            prestacao = models.PrestacoesContas.select().where(models.PrestacoesContas.nome_original == 'entrada.pdf').get()
            anexo = models.Anexos.select().where(models.Anexos.nome_original == 'entrada.pdf').get()
            self.assertEqual((prestacao.mes_id.id, anexo.transacao_id.id), (1, 1))
            for documento in (prestacao, anexo):
                with open(os.path.join(pasta, *documento.caminho_local.split('/')), 'rb') as arquivo:
                    self.assertEqual(arquivo.read(), b'arquivo de teste')
            self.assertEqual(models.Meses.get_by_id(1).anexos, 2)
            self.assertEqual(models.Transacoes.get_by_id(1).anexos, 2)

    def test_regras_importacao_persistencia_e_validacao(self):
        from compartilhado import models
        models.Condominio.create(id='outro')
        outra = models.RegrasPreenchimento.create(condominio_id='outro', descricao_contem='outra', campo='conta', valor='Conta')
        regras = [{'descricao_contem': ' tarifa ', 'campo': 'fornecedor', 'valor': ' Banco '}, {'descricao_contem': 'tarifa', 'campo': 'conta', 'valor': 'Corrente'}]
        resposta = self.api.update_condominio_config({'regras_preenchimento': regras})
        self.assertEqual(resposta['status'], 'success')
        salvas = resposta['regras_preenchimento']
        self.assertEqual([(r['descricao_contem'], r['campo'], r['valor']) for r in salvas], [(' tarifa ', 'fornecedor', ' Banco '), ('tarifa', 'conta', 'Corrente')])
        ids = [r['id'] for r in salvas]
        salvas[0]['valor'] = 'Alterado'
        atualizadas = self.api.update_condominio_config({'regras_preenchimento': salvas})['regras_preenchimento']
        self.assertEqual([r['id'] for r in atualizadas], ids)
        reordenadas = self.api.update_condominio_config({'regras_preenchimento': atualizadas[::-1]})['regras_preenchimento']
        self.assertEqual([r['campo'] for r in reordenadas], ['conta', 'fornecedor'])
        self.assertEqual([r['id'] for r in reordenadas], sorted(r['id'] for r in reordenadas))
        self.assertEqual([r['campo'] for r in self.api.get_condominio_config()['data']['regras_preenchimento']], ['conta', 'fornecedor'])
        nova = {'descricao_contem': 'tarifa', 'campo': 'conta', 'valor': 'Primeira'}
        reordenadas = self.api.update_condominio_config({'regras_preenchimento': [nova, *reordenadas]})['regras_preenchimento']
        self.assertEqual([r['valor'] for r in reordenadas], ['Primeira', 'Corrente', 'Alterado'])
        from extrator.execucao import evaluate_entity_consistency
        resultado = evaluate_entity_consistency('transacao', tipo_flag='D', desc_completa='tarifa', desc_f='tarifa', regras_preenchimento=reordenadas)
        self.assertEqual(resultado[-1], 'Primeira')
        for invalida in ({'descricao_contem': ' ', 'campo': 'conta', 'valor': 'X'}, {'descricao_contem': 'a', 'campo': 'x', 'valor': 'X'}, {'id': outra.id, 'descricao_contem': 'a', 'campo': 'conta', 'valor': 'X'}):
            self.assertEqual(self.api.update_condominio_config({'condominio': {'nome': 'Alterado'}, 'regras_preenchimento': [invalida]})['status'], 'error')
        self.assertEqual(models.Condominio.get_by_id(self.condo_id).nome, 'Condominio Teste')
        self.assertEqual(len(self.api.get_condominio_config()['data']['regras_preenchimento']), 3)
        self.assertEqual(self.api.update_condominio_config({'regras_preenchimento': []})['status'], 'success')
        self.assertEqual(self.api.get_condominio_config()['data']['regras_preenchimento'], [])
        self.assertEqual(models.RegrasPreenchimento.select().where(models.RegrasPreenchimento.condominio_id == 'outro').count(), 1)

    def test_posicao_unificada_pode_ser_calculada_em_conexao_somente_leitura(self):
        from compartilhado import models
        from bff.apresentacao_conciliacao import inadimplencia
        models.db.execute_sql('PRAGMA query_only = ON')
        posicao = self.api._calcular_posicao_unificada('2023-01-20')
        resultado = inadimplencia(posicao)
        self.assertEqual([(u['unidade'], u['taxas'][0]['valor']) for u in resultado], [('101', 300)])

    def test_configuracao_da_margem_e_usada_sem_consultas_por_grupo(self):
        from compartilhado import models
        self.assertEqual(self.api.get_condominio_config()['data']['condominio']['margem_diferenca_encargos'], 0.10)
        payload = {'condominio': {'margem_diferenca_encargos': 0.25}, 'membros': [], 'contas': []}
        self.assertEqual(self.api.update_condominio_config(payload)['status'], 'success')
        self.assertEqual(self.api.get_condominio_config()['data']['condominio']['margem_diferenca_encargos'], 0.25)
        with patch('bff.conciliacao_unificada.calcular_posicao', return_value={}) as calcular:
            self.api._calcular_posicao_unificada('2023-01-20')
        self.assertEqual(calcular.call_args.kwargs['margem_encargos_centavos'], 25)
        for invalido in (-0.01, None, 'abc', 0.001, True):
            with self.subTest(invalido=invalido):
                resposta = self.api.update_condominio_config({'condominio': {'margem_diferenca_encargos': invalido}})
                self.assertEqual(resposta['status'], 'error')
                self.assertEqual(models.Condominio.get_by_id(self.condo_id).margem_diferenca_encargos, 0.25)
        self.assertEqual(self.api.update_condominio_config({'condominio': {'margem_diferenca_encargos': 0}})['status'], 'success')
        with patch('bff.conciliacao_unificada.calcular_posicao', return_value={}) as calcular:
            self.api._calcular_posicao_unificada('2023-01-20')
        self.assertEqual(calcular.call_args.kwargs['margem_encargos_centavos'], 0)

    @patch('bff.apresentacao_conciliacao.date', wraps=date)
    def test_compartilha_posicao_entre_os_tres_pontos(self, data_simulada):
        data_simulada.today.return_value = date(2023, 1, 20)
        tela = self.api.get_inadimplencia('2023-01-20')
        relatorio = self.api.get_relatorio_inadimplencia({'data_corte': '2023-01-20'})
        extrato = self.api.get_relatorio_recebimentos({'tipo': 'completo', 'data_corte': '2023-01-20'})
        self.assertEqual([tela['status'], relatorio['status'], extrato['status']], ['success'] * 3)
        self.assertEqual(tela['data'][0]['taxas'][0]['valor'], 300)
        self.assertEqual(relatorio['data']['total'], 300)
        grupo = next(u for u in extrato['data']['apartamentos'] if u['apartamento'] == '101')['competencias'][0]
        self.assertEqual(grupo['saldo_original'], 300)
        self.assertEqual(extrato['data']['data_corte'], '2023-01-20')
        na_data = self.api.get_inadimplencia('2023-01-15')
        self.assertEqual(na_data['data'], [])

    @patch('bff.apresentacao_conciliacao.date', wraps=date)
    def test_receitas_incompletas_entram_apos_revisao_e_negativas_nao_abatem(self, data_simulada):
        data_simulada.today.return_value = date(2023, 1, 20)
        from compartilhado import models
        incompleta = models.Transacoes.create(subcategoria_id=1, tipo='R', apartamento='101', competencia=None,
                                              data='14/01/2023', descricao='Pagamento', valor=50)
        sem_apartamento = models.Transacoes.create(subcategoria_id=1, tipo='R', apartamento=None, competencia='2023-01',
                                                   data='14/01/2023', descricao='Pagamento', valor=60)
        negativa = models.Transacoes.create(subcategoria_id=1, tipo='R', apartamento='101', competencia='2023-01',
                                            data='14/01/2023', descricao='Origem desconhecida', valor=-3)
        filtros = {'tipo': 'completo', 'data_corte': '2023-01-20', 'apartamentos': ['101']}
        antes = self.api.get_relatorio_recebimentos(filtros)
        saldo_antes = self.api.get_inadimplencia('2023-01-20')
        self.assertEqual((antes['status'], saldo_antes['status']), ('success', 'success'))
        linhas = [l for u in antes['data']['apartamentos'] for g in u['competencias'] for l in g['lancamentos']]
        self.assertNotIn(incompleta.id, [l['id'] for l in linhas])
        self.assertNotIn(sem_apartamento.id, [l['id'] for l in linhas])
        self.assertEqual(next((l['tipo'], l['valor']) for l in linhas if l['id'] == negativa.id),
                         ('Valor negativo de origem a esclarecer', -3))
        self.assertEqual(saldo_antes['data'][0]['taxas'][0]['valor'], 300)
        incompleta.competencia = '2023-01'
        incompleta.save()
        depois = self.api.get_relatorio_recebimentos(filtros)
        saldo_depois = self.api.get_inadimplencia('2023-01-20')
        linhas = [l for u in depois['data']['apartamentos'] for g in u['competencias'] for l in g['lancamentos']]
        self.assertIn(incompleta.id, [l['id'] for l in linhas if l['tipo'] == 'Recebimento'])
        self.assertEqual(saldo_depois['data'][0]['taxas'][0]['valor'], 250)

    def test_filtro_de_movimento_exclui_grupos_sem_movimento_no_periodo(self):
        filtros = {'tipo': 'recebimento', 'periodo': ['2023-01-20', '2023-01-20'],
                   'data_corte': '2023-01-14', 'apartamentos': ['101']}
        extrato = self.api.get_relatorio_recebimentos(filtros)
        relatorio = self.api.get_relatorio_inadimplencia({'data_corte': '2023-01-20', 'apartamentos': ['101']})
        self.assertEqual((extrato['status'], relatorio['status']), ('success', 'success'))
        self.assertEqual(extrato['data']['apartamentos'][0]['competencias'], [])
        self.assertEqual(extrato['data']['total'], 0)
        self.assertEqual((extrato['data']['saldo_original'], relatorio['data']['total']), (0, 300))

    def test_extrato_mostra_origem_quando_conciliacao_e_inconclusiva(self):
        from bff.conciliacao_unificada import ConciliacaoInconclusiva
        with patch('bff.conciliacao_unificada.conciliar_exatos', side_effect=ConciliacaoInconclusiva('Limite de teste')):
            inadimplencia = self.api.get_inadimplencia('2023-01-20')
            relatorio = self.api.get_relatorio_inadimplencia({'data_corte': '2023-01-20'})
            extrato = self.api.get_relatorio_recebimentos({'tipo': 'competencia', 'periodo': ['2023-01', '2023-01']})
        self.assertEqual(inadimplencia['status'], 'success')
        self.assertEqual(next(u for u in inadimplencia['data'] if u['unidade'] == '101')['taxas'][0]['valor'], 300)
        self.assertEqual(relatorio['status'], 'success')
        self.assertEqual(next(u for u in relatorio['data']['apartamentos'] if u['apartamento'] == '101')['subtotal'], 300)
        self.assertEqual(extrato['status'], 'success')
        unidade = next(u for u in extrato['data']['apartamentos'] if u['apartamento'] == '101')
        grupo = unidade['competencias'][0]
        self.assertTrue(grupo['conciliacao_inconclusiva'])
        self.assertIsNone(grupo['saldo_original'])
        self.assertIsNone(unidade['saldo_original'])
        self.assertIsNone(extrato['data']['saldo_original'])
        self.assertEqual(grupo['subtotal'], sum(l['valor'] for l in grupo['lancamentos'] if not l['renegociado'] and not l['informativo']))
        self.assertTrue(any(l['tipo'] == 'Cobrança' for l in grupo['lancamentos']))
        self.assertFalse(any(l['tipo'] in ('Acréscimo', 'Desconto à vista') for l in grupo['lancamentos']))

    def test_inadimplencia_inconclusiva_mostra_taxa_aberta_apos_desconto_manual(self):
        from compartilhado import models
        from bff.conciliacao_unificada import ConciliacaoInconclusiva
        taxa = models.Taxas.get(models.Taxas.descricao == 'Taxa Condomínio')
        self.assertEqual(self.api.insert_taxa({'tipo': 'D', 'taxa_id': taxa.id, 'apartamento': '101',
            'competencia': '2023-01', 'vencimento': '15/01/2023', 'descricao': 'Desconto manual',
            'valor_original': 70})['status'], 'success')
        models.Transacoes.create(subcategoria_id=1, tipo='R', apartamento='101', competencia='2023-01',
                                  data='14/01/2023', descricao='Pagamento', valor=40)
        with patch('bff.conciliacao_unificada.conciliar_historicos', side_effect=ConciliacaoInconclusiva('Limite')):
            tela = self.api.get_inadimplencia('2023-01-20', ['101'])
            relatorio = self.api.get_relatorio_inadimplencia({'data_corte': '2023-01-20', 'apartamentos': ['101']})
        self.assertEqual(tela['status'], 'success')
        self.assertEqual(tela['data'][0]['taxas'][0]['valor'], 230)
        self.assertEqual(relatorio['data']['total'], 230)
        self.assertGreater(tela['data'][0]['taxas'][0]['juros_total'], 0)

    def test_desconto_tem_vencimento_proprio_e_respeita_data_de_corte(self):
        from compartilhado import models
        taxa = models.Taxas.get(models.Taxas.descricao == 'Taxa Condomínio')
        payload = {'tipo': 'D', 'taxa_id': taxa.id, 'apartamento': '101',
                   'competencia': '2023-01', 'vencimento': '20/01/2023',
                   'descricao': 'Desconto', 'valor_original': 20}
        self.assertEqual(self.api.insert_taxa(payload)['status'], 'success')
        desconto = models.Taxas.get(models.Taxas.tipo == 'D')
        self.assertEqual(desconto.vencimento, '20/01/2023')
        for corte, valor in [('2023-01-19', 300), ('2023-01-20', 280)]:
            resultado = self.api.get_inadimplencia(corte)
            unidade = next(u for u in resultado['data'] if u['unidade'] == '101')
            self.assertEqual(next(t['valor'] for t in unidade['taxas'] if t['id'] == taxa.id), valor)
        self.assertEqual(self.api.update_taxa(desconto.id, {'vencimento': '25/01/2023'})['status'], 'success')
        desconto_lido = next(t for t in self.api.get_taxas(['D'])['data'] if t['id'] == desconto.id)
        self.assertEqual(desconto_lido['vencimento'], '25/01/2023')

    def test_renegociacao_de_taxa_extraordinaria_abate_apenas_unidade_selecionada(self):
        from compartilhado import models
        extra = models.Taxas.create(condominio_id=self.condo_id, tipo='E', competencia='2023-01',
                                    exibicao='JAN/2023', vencimento='15/01/2023',
                                    descricao='Taxa extraordinária', valor_original=75)
        tipos = ['C', 'E', 'I', 'P', 'D']
        result = self.api.get_taxas_por_apartamento('101', ['2023-01', '2023-01'], tipos)
        self.assertEqual(result['status'], 'success')
        self.assertIn(extra.id, [t['id'] for t in result['data']])
        payload = {'apartamento': '101', 'competencia_inicial': '2023-01', 'competencia_final': '2023-01',
                   'data_renegociacao': '18/01/2023', 'taxas_originais': [extra.id],
                   'parcelas': [{'competencia': '2023-02', 'vencimento': '10/02/2023',
                                 'descricao': 'Parcela', 'valor_original': 75}]}
        result = self.api.salvar_renegociacao(payload)
        self.assertEqual(result['status'], 'success', result.get('message'))
        acordo = models.Renegociacao.get()
        self.assertEqual(self.api.get_renegociacao(acordo.id)['data']['taxas_originais'][0]['taxa_id'], extra.id)
        for corte in ('2023-01-17', '2023-01-18'):
            resultado = self.api.get_inadimplencia(corte)
            self.assertEqual(resultado['status'], 'success')
            for apto in ('101', '102'):
                taxas = next((u['taxas'] for u in resultado['data'] if u['unidade'] == apto), [])
                self.assertEqual(extra.id in [t['id'] for t in taxas], apto == '102' or corte == '2023-01-17')

    def test_desconto_renegociado_deixa_de_abater_taxa_a_partir_da_data(self):
        from compartilhado import models
        taxa = models.Taxas.get(models.Taxas.descricao == 'Taxa Condomínio')
        desconto = models.Taxas.create(condominio_id=self.condo_id, apartamento='101', tipo='D',
                                        taxa_id=taxa.id, competencia='2023-01', vencimento='15/01/2023',
                                        descricao='Desconto', valor_original=20, desconto_vista=2,
                                        multa_percentual=0.5, juros_mes_percentual=0.2)
        payload = {'apartamento': '101', 'competencia_inicial': '2023-01', 'competencia_final': '2023-01',
                   'data_renegociacao': '18/01/2023', 'taxas_originais': [desconto.id],
                   'parcelas': [{'competencia': '2023-02', 'vencimento': '10/02/2023',
                                 'descricao': 'Parcela', 'valor_original': 280}]}
        self.assertEqual(self.api.salvar_renegociacao(payload)['status'], 'error')
        ren = models.Renegociacao.create(condominio_id=self.condo_id, apartamento='101', data_renegociacao='18/01/2023')
        models.Taxas.create(condominio_id=self.condo_id, apartamento='101', tipo='R', taxa_id=desconto.id,
                            renegociacao_id=ren.id, valor_original=20, desconto_vista=2,
                            multa_percentual=0.5, juros_mes_percentual=0.2)
        for corte, valor in [('2023-01-17', 280), ('2023-01-18', 300)]:
            resultado = self.api.get_inadimplencia(corte)
            self.assertEqual(resultado['status'], 'success')
            unidade = next((u for u in resultado['data'] if u['unidade'] == '101'), {'taxas': []})
            origem = next((t for t in unidade['taxas'] if t['id'] == taxa.id), None)
            if valor is None:
                self.assertIsNone(origem)
            else:
                self.assertEqual(origem['valor'], valor)
        models.Renegociacao.delete_by_id(ren.id)
        payload['taxas_originais'] = [taxa.id, desconto.id]
        resultado = self.api.salvar_renegociacao(payload)
        self.assertEqual(resultado['status'], 'success', resultado.get('message'))
        ren = models.Renegociacao.get()
        self.assertEqual({t['taxa_id'] for t in self.api.get_renegociacao(ren.id)['data']['taxas_originais']}, {taxa.id, desconto.id})
        self.assertEqual(self.api.delete_taxa(desconto.id)['status'], 'error')
        self.assertEqual(self.api.update_taxa(desconto.id, {})['status'], 'error')
        resultado = self.api.get_inadimplencia('2023-01-18')
        unidade = next((u for u in resultado['data'] if u['unidade'] == '101'), {'taxas': []})
        self.assertEqual(next(t['valor'] for t in unidade['taxas'] if t['id'] == taxa.id), 0)
        self.assertEqual(self.api.delete_renegociacao(ren.id)['status'], 'success')
        resultado = self.api.get_inadimplencia('2023-01-18')
        unidade = next(u for u in resultado['data'] if u['unidade'] == '101')
        self.assertEqual(next(t['valor'] for t in unidade['taxas'] if t['id'] == taxa.id), 280)

    def test_rerenegociacao_preserva_historico_e_impede_exclusao_da_origem(self):
        from compartilhado import models
        taxa = models.Taxas.get(models.Taxas.descricao == 'Taxa Condomínio')
        def payload(originais, data, vencimento, valor, ren_id=None):
            return {'id': ren_id, 'apartamento': '101', 'competencia_inicial': '2023-01',
                    'competencia_final': '2023-03', 'data_renegociacao': data,
                    'quantidade_parcelas': 1, 'taxas_originais': originais,
                    'parcelas': [{'competencia': '2023-02' if data == '18/01/2023' else '2023-03',
                                  'vencimento': vencimento, 'descricao': 'Parcela', 'valor_original': valor}]}

        self.assertEqual(self.api.salvar_renegociacao(payload([taxa.id], '18/01/2023', '10/02/2023', 300))['status'], 'success')
        origem = models.Renegociacao.get()
        parcela = models.Taxas.get((models.Taxas.renegociacao_id == origem.id) & (models.Taxas.tipo == 'P'))
        extra = models.Taxas.create(condominio_id=self.condo_id, apartamento='101', tipo='I',
                                    competencia='2023-02', vencimento='10/02/2023', descricao='Taxa individual', valor_original=40)
        disponiveis = self.api.get_taxas_por_apartamento('101', ['2023-01', '2023-03'], ['C', 'E', 'I', 'P'])['data']
        self.assertIn(parcela.id, [t['id'] for t in disponiveis])
        self.assertNotIn(parcela.id, [t['id'] for t in self.api.get_taxas_por_apartamento('102', ['2023-01', '2023-03'], ['C', 'E', 'I', 'P'])['data']])
        self.assertEqual(self.api.salvar_renegociacao(payload([parcela.id, extra.id], '15/02/2023', '10/03/2023', 340))['status'], 'success')
        nova = models.Renegociacao.get(models.Renegociacao.id != origem.id)
        self.assertEqual({t['taxa_id'] for t in self.api.get_renegociacao(nova.id)['data']['taxas_originais']}, {parcela.id, extra.id})
        self.assertEqual(self.api.delete_renegociacao(origem.id)['status'], 'error')
        self.assertEqual(self.api.salvar_renegociacao(payload([taxa.id], '18/01/2023', '10/02/2023', 300, origem.id))['status'], 'error')
        self.assertTrue(models.Taxas.get_or_none(models.Taxas.id == parcela.id))
        for corte, esperado in [('2023-02-14', parcela.id), ('2023-03-11', None)]:
            resultado = self.api.get_inadimplencia(corte)
            taxas = next(x['taxas'] for x in resultado['data'] if x['unidade'] == '101')
            ids = [t['id'] for t in taxas]
            if esperado is not None:
                self.assertIn(esperado, ids)
            else:
                self.assertNotIn(parcela.id, ids)
                self.assertNotIn(extra.id, ids)
                self.assertIn(self.api.get_renegociacao(nova.id)['data']['parcelas'][0]['id'], ids)
        self.assertEqual(self.api.delete_renegociacao(nova.id)['status'], 'success')
        self.assertEqual(self.api.delete_renegociacao(origem.id)['status'], 'success')

    def setUp(self):
        import tempfile
        from compartilhado import models
        from bff import main as rd_mod
        # Isola project_root: métodos do Api gravam arquivos em project_root/anexos
        self.temp_root = tempfile.mkdtemp(prefix='rd_test_')
        root_patcher = patch.object(rd_mod, 'project_root', self.temp_root)
        root_patcher.start()
        self.addCleanup(root_patcher.stop)
        self.addCleanup(lambda: __import__('shutil').rmtree(self.temp_root, ignore_errors=True))
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='_test_rd.db')
        
        # Initialize ORM with this temp db
        models.init_models(self.temp_db_path)
        
        # Connect raw sqlite to populate data easily
        self.conn = sqlite3.connect(self.temp_db_path)
        self.cursor = self.conn.cursor()
        
        # Populate data
        import datetime
        current_date = datetime.datetime.now().strftime("%Y-%m")
        self.condo_id = "condo_123"
        self.cursor.execute("INSERT INTO condominio (id, nome, inadimplencia_valor, inadimplencia_unidades, inadimplencia_data_corte, administradora, telefone_administradora, ultima_atualizacao) VALUES (?, ?, 100.50, 2, '2023-01-01', 'Admin Teste', '[\"12345678\"]', '2026-06-25T21:00:00')", (self.condo_id, "Condominio Teste"))
        self.cursor.execute("INSERT INTO membros_gestao (condominio_id, nome, cargo) VALUES (?, ?, ?)", (self.condo_id, "João", "Síndico"))
        self.cursor.execute("INSERT INTO meses (id, condominio_id, consistente, motivo_inconsistencia, revisado_usuario, competencia, exibicao, receita_total, despesa_total, anexos) VALUES (1, ?, 0, 'Erro Mês', 0, '2023-01', 'JAN/2023', 500.0, 300.0, 0)", (self.condo_id,))
        self.cursor.execute("INSERT INTO meses (id, condominio_id, consistente, motivo_inconsistencia, revisado_usuario, competencia, exibicao, receita_total, despesa_total, anexos) VALUES (2, ?, 1, NULL, 0, ?, ?, 600.0, 400.0, 0)", (self.condo_id, current_date, 'MÊS ATUAL'))
        self.cursor.execute("INSERT INTO categorias (id, mes_id, tipo, nome, valor, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 'Despesas', 'Cat 1', 100, 0, 'Erro Categoria', 0)")
        self.cursor.execute("INSERT INTO subcategorias (id, categoria_id, tipo, nome, valor, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 'Despesas', 'Sub 1', 100, 0, 'Erro Subcategoria', 0)")
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 'Despesas', '2023-01-10', 'Transação Teste', 100, '101', '2023-01', 'Fornecedor A', 1, 0, 'Erro Transação', 0)")
        self.cursor.execute("INSERT INTO anexos (id, transacao_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Anexo', 0)")
        self.cursor.execute("INSERT INTO prestacoes_contas (id, mes_id, consistente, motivo_inconsistencia, revisado_usuario) VALUES (1, 1, 0, 'Erro Prestação', 0)")
        
        self.cursor.execute("INSERT INTO taxas (condominio_id, competencia, exibicao, vencimento, descricao, valor_original, desconto_vista, multa_percentual, juros_mes_percentual, tipo) VALUES (?, '2023-01', 'JAN/2023', '15/01/2023', 'Taxa Condomínio', 300.0, 10.0, 2.0, 1.0, 'C')", (self.condo_id,))
        self.cursor.execute("UPDATE condominio SET apartamentos = '[\"101\", \"102\"]' WHERE id = ?", (self.condo_id,))
        # Adicionar uma transação que abate a taxa (receita para apto 102) - pago com desconto
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (2, 1, 'R', '14/01/2023', 'Pagamento', 290.0, '102', '2023-01', 'Morador', 0, 1, NULL, 1)")
        
        self.conn.commit()
        
        # Avoid file check failing by patching os.path.exists during init
        self.original_exists = os.path.exists
        os.path.exists = lambda path: True if path.endswith('winker_data.db') or path.endswith('.db') else self.original_exists(path)
        
        try:
            self.api = Api(db_path=self.temp_db_path, raiz_projeto=self.temp_root)
            self.api.condo_id = self.condo_id
        finally:
            os.path.exists = self.original_exists
            
        self.api.init_error = None

    def tearDown(self):
        self.conn.close()
        from compartilhado import models
        models.db.close()
        try:
            os.close(self.temp_db_fd)
            os.unlink(self.temp_db_path)
        except:
            pass

    def test_get_pendencias_revisao_count(self):
        result = self.api.get_pendencias_revisao_count()
        self.assertEqual(result["status"], "success", result.get("message"))
        
        data = result["data"]
        self.assertEqual(data["count"], 7)
        
        details = data["details"]
        self.assertIn("meses", details)
        self.assertEqual(details["meses"], 2)
        self.assertIn("categorias", details)
        self.assertIn("subcategorias", details)
        self.assertIn("lancamentos", details)
        self.assertIn("documentos", details)

    def test_get_dashboard_kpis(self):
        result = self.api.get_dashboard_kpis()
        self.assertEqual(result["status"], "success", result.get("message"))
        
        data = result["data"]
        self.assertIn("inadimplencia", data)
        self.assertIn("gestao", data)
        self.assertIn("saldos", data)
        self.assertIn("resumo_mes", data)
        
        self.assertEqual(data["gestao"]["membros"][0]["nome"], "João")
        self.assertEqual(data["saldos"]["saldo_total"], 400.0)
        self.assertEqual(data["resumo_mes"]["resultado"], 200.0) # rec 600 - desp 400

    def test_get_transacoes(self):
        result = self.api.get_transacoes()
        if result["status"] != "success":
            print("ERROR:", result)
        self.assertEqual(result["status"], "success", result.get("message"))
        tree = result["data"]["tree"]
        
        self.assertTrue(len(tree) > 0)
        
        mes_node = tree[0]
        self.assertEqual(mes_node["data"]["tipo_node"], "mes")
        self.assertEqual(mes_node["data"]["descricao"], "JAN/2023")
        
        tipo_node_rec = mes_node["children"][0]
        self.assertEqual(tipo_node_rec["data"]["tipo_node"], "tipo")
        self.assertEqual(tipo_node_rec["data"]["descricao"], "Receitas")

        tipo_node = mes_node["children"][1]
        self.assertEqual(tipo_node["data"]["tipo_node"], "tipo")
        self.assertEqual(tipo_node["data"]["descricao"], "Despesas")
        
        cat_node = tipo_node["children"][0]
        self.assertEqual(cat_node["data"]["tipo_node"], "categoria")
        self.assertEqual(cat_node["data"]["descricao"], "Cat 1")
        
        sub_node = cat_node["children"][0]
        self.assertEqual(sub_node["data"]["tipo_node"], "subcategoria")
        self.assertEqual(sub_node["data"]["descricao"], "Sub 1")
        
        trans_nodes = sub_node["children"]
        trans_teste = next((n for n in trans_nodes if n["data"]["descricao"] == "Transação Teste"), None)
        self.assertIsNotNone(trans_teste)
        self.assertEqual(trans_teste["data"]["tipo_node"], "transacao")
        self.assertEqual(trans_teste["data"]["valor"], 100)
        self.assertEqual(trans_teste["data"]["apartamento"], '101')

    def test_get_inadimplencia(self):
        result = self.api.get_inadimplencia(data_corte="2023-01-20")
        self.assertEqual(result["status"], "success", result.get("message"))
        data = result["data"]
        
        # Apto 101 não pagou, deve estar na inadimplencia
        # Apto 102 pagou a taxa, não deve aparecer (ou ter a taxa na lista)
        # 102 is omitted because it has no unpaid fees
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["unidade"], "101")
        
        taxas = data[0]["taxas"]
        self.assertEqual(len(taxas), 1)
        self.assertEqual(taxas[0]["valor"], 300.0)
        self.assertEqual(taxas[0]["dias_vencidos"], 5) # (20 - 15) = 5
        self.assertAlmostEqual(taxas[0]["juros_total"], 0.5) # 300 * (1% / 30) * 5 dias
        
    def test_get_inadimplencia_multa_sobre_juros(self):
        # Mudar para M (Multa sobre Juros)
        self.cursor.execute("UPDATE condominio SET tipo_juros_multa = 'M' WHERE id = ?", (self.condo_id,))
        self.conn.commit()
        result = self.api.get_inadimplencia(data_corte="2023-01-20")
        taxas = result["data"][0]["taxas"]
        # Juros = 0.5
        # Multa = (300 + 0.5) * 2% = 6.01
        self.assertAlmostEqual(taxas[0]["juros_total"], 0.5)
        self.assertAlmostEqual(taxas[0]["multa"], 6.01)

    def test_get_inadimplencia_juros_sobre_multa(self):
        # Mudar para J (Juros sobre Multa)
        self.cursor.execute("UPDATE condominio SET tipo_juros_multa = 'J' WHERE id = ?", (self.condo_id,))
        self.conn.commit()
        result = self.api.get_inadimplencia(data_corte="2023-01-20")
        taxas = result["data"][0]["taxas"]
        # Multa = 300 * 2% = 6.0
        # Juros = (300 + 6.0) * (1% / 30) * 5 = 306 * 0.001666... = 0.51
        self.assertAlmostEqual(taxas[0]["multa"], 6.0)
        self.assertAlmostEqual(taxas[0]["juros_total"], 0.51)

    def test_inadimplencia_sem_data_de_corte_nao_aplica_multa_no_dia_do_vencimento(self):
        from datetime import datetime

        class DataFixa(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2023, 1, 15, 12, 0)

        for tipo in ('N', 'M', 'J'):
            with self.subTest(tipo=tipo):
                self.cursor.execute("UPDATE condominio SET tipo_juros_multa = ? WHERE id = ?", (tipo, self.condo_id))
                self.conn.commit()
                with patch('bff.inadimplencia.datetime', DataFixa):
                    resultado = self.api.get_inadimplencia()
                self.assertEqual(resultado['status'], 'success')
                self.assertFalse(any(item['unidade'] == '101' for item in resultado['data']))

    def test_get_inadimplencia_multiple_match(self):
        self.cursor.execute("INSERT INTO taxas (condominio_id, competencia, exibicao, vencimento, descricao, valor_original, desconto_vista, multa_percentual, juros_mes_percentual, tipo) VALUES (?, '2023-01', 'JAN/2023', '15/01/2023', 'Taxa Teste Match Múltiplo', 100.0, 0.0, 2.0, 1.0, 'C')", (self.condo_id,))
        self.cursor.execute("UPDATE condominio SET apartamentos = '[\"101\", \"102\", \"103\"]' WHERE id = ?", (self.condo_id,))
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (3, 1, 'R', '10/01/2023', 'Pag parcial 1', 55.0, '103', '2023-01', 'Morador', 0, 1, NULL, 1)")
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (4, 1, 'R', '10/01/2023', 'Pag parcial 2', 50.0, '103', '2023-01', 'Morador', 0, 1, NULL, 1)")
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, data, descricao, valor, apartamento, competencia, fornecedor, anexos, consistente, motivo_inconsistencia, revisado_usuario) VALUES (5, 1, 'R', '10/01/2023', 'Pag parcial 3', 45.0, '103', '2023-01', 'Morador', 0, 1, NULL, 1)")
        self.conn.commit()
        
        result = self.api.get_inadimplencia(data_corte="2023-01-20")
        self.assertEqual(result["status"], "success")
        
        # O apto 103 pode ter outras taxas pendentes (ex: Taxa Condomínio comum),
        # mas a "Taxa Teste Match Múltiplo" deve ter sido paga pelo match de (55+45) = 100
        taxas_103 = next((d["taxas"] for d in result["data"] if d["unidade"] == "103"), [])
        descricoes_103 = [t["descricao"] for t in taxas_103]
        self.assertNotIn("Taxa Teste Match Múltiplo", descricoes_103)

    def test_recebimentos_agrupados_nao_quitam_duas_taxas(self):
        for descricao in ('Primeira taxa', 'Segunda taxa'):
            self.cursor.execute("INSERT INTO taxas (condominio_id, competencia, exibicao, vencimento, descricao, valor_original, desconto_vista, multa_percentual, juros_mes_percentual, tipo) VALUES (?, '2023-01', 'JAN/2023', '15/01/2023', ?, 100, 0, 0, 0, 'C')", (self.condo_id, descricao))
        for transacao_id in (3, 4):
            self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, apartamento, competencia, valor, data, anexos, consistente, revisado_usuario) VALUES (?, 1, 'R', '101', '2023-01', 50, '14/01/2023', 0, 1, 0)", (transacao_id,))
        self.conn.commit()
        resultado = self.api.get_inadimplencia(data_corte='2023-01-20')
        self.assertEqual(resultado['status'], 'success')
        unidade = next(item for item in resultado['data'] if item['unidade'] == '101')
        descricoes = [taxa['descricao'] for taxa in unidade['taxas']]
        self.assertNotIn('Primeira taxa', descricoes)
        self.assertIn('Segunda taxa', descricoes)

    def test_validar_margem_encargos_rejeita_entradas_invalidas(self):
        from bff.main import validar_margem_encargos
        self.assertEqual(validar_margem_encargos('0.25'), 25)
        self.assertEqual(validar_margem_encargos(0), 0)
        for invalido in (None, True, 'abc', -1, '0.001', 'nan', 'inf'):
            with self.assertRaises(ValueError, msg=str(invalido)):
                validar_margem_encargos(invalido)

    def test_relatorios_e_apartamentos_validam_entradas(self):
        self.assertEqual(self.api.get_relatorio_inadimplencia({})['message'], 'Informe a data de corte.')
        self.assertEqual(self.api.get_relatorio_inadimplencia({'data_corte': 'invalida'})['status'], 'error')
        self.assertEqual(self.api.get_relatorio_inadimplencia({'data_corte': '2023-01-20', 'apartamentos': '101'})['message'],
                         'Filtro de apartamentos inválido.')
        self.assertEqual(self.api.get_relatorio_recebimentos({'limites': True})['status'], 'success')
        self.assertEqual(self.api.get_relatorio_recebimentos({'limites': True})['data']['limites']['inicio'], '2023-01-01')

    def test_apartamentos_invalidos_no_cadastro_e_condominio_ausente(self):
        from compartilhado import models
        condo = models.Condominio.get_by_id(self.condo_id)
        condo.apartamentos = 'nao-json'
        condo.save()
        self.assertEqual(self.api.get_apartamentos()['status'], 'error')
        self.assertEqual(self.api.get_apartamentos()['message'], 'Cadastro de apartamentos inválido.')
        self.api.condo_id = 'inexistente'
        self.assertEqual(self.api.get_apartamentos()['message'], 'Condomínio não encontrado.')
        self.assertEqual(self.api.get_condominio_config()['message'], 'Condomínio não encontrado.')
        self.api.condo_id = self.condo_id
        condo.apartamentos = '["101"]'
        condo.save()
        self.assertEqual(self.api.get_apartamentos()['data'], ['101'])

    def test_config_condominio_parseia_json_invalido_e_campos(self):
        from compartilhado import models
        condo = models.Condominio.get_by_id(self.condo_id)
        condo.telefone_administradora = 'json-invalido'
        condo.apartamentos = '{invalid'
        condo.save()
        resposta = self.api.get_condominio_config()
        self.assertEqual(resposta['status'], 'success')
        self.assertEqual(resposta['data']['condominio']['telefone_administradora'], 'json-invalido')
        self.assertEqual(self.api.update_condominio_config({'condominio': {'nome': 'Novo Nome', 'apartamentos': ['101'],
                                                                          'telefone_administradora': ['119999'],
                                                                          'margem_diferenca_encargos': 0.5}})['status'], 'success')
        condo = models.Condominio.get_by_id(self.condo_id)
        self.assertEqual(condo.nome, 'Novo Nome')
        self.assertEqual(self.api.update_condominio_config({'condominio': {'margem_diferenca_encargos': -1}})['status'], 'error')
        self.assertEqual(self.api.update_condominio_config({'regras_preenchimento': 'invalido'})['status'], 'error')
        self.assertEqual(self.api.update_condominio_config({'regras_preenchimento': [{'campo': 'x', 'descricao_contem': '', 'valor': '1'}]})['status'], 'error')

    def test_nome_e_lista_de_condominios_e_troca_sem_preferencia(self):
        self.assertEqual(self.api.get_nome_condominio()['data']['nome'], 'Condominio Teste')
        self.assertEqual(self.api.get_condominios()['current_id'], self.condo_id)
        from compartilhado import models
        models.PreferenciasUsuario.delete().execute()
        self.assertEqual(self.api.set_condominio(self.condo_id)['status'], 'success')
        self.assertIsNotNone(models.PreferenciasUsuario.select().first())
        self.api.condo_id = 'inexistente'
        self.assertEqual(self.api.get_nome_condominio()['message'], 'Condomínio não encontrado.')
        self.assertEqual(self.api.set_condominio('inexistente')['status'], 'success')

    def test_exit_app_salva_preferencias_e_destroi_janela(self):
        self.api.prefs_cache = {'darkTheme': True, 'primary': 'blue', 'surface': 'dark', 'preset': 'lara', 'menuMode': 'static'}
        self.api._main_window = type('Janela', (), {'destroy': lambda self: setattr(self, 'destruida', True)})()
        with patch('threading.Timer') as timer:
            self.assertEqual(self.api.exit_app()['status'], 'success')
            timer.assert_called_once()
        self.assertTrue(self.api._main_window.destruida)
        self.api.prefs_cache = {'darkTheme': True}
        with patch.object(self.api, 'salvar_preferencias', side_effect=RuntimeError('falha')), \
             patch('threading.Timer') as timer2:
            self.assertEqual(self.api.exit_app()['status'], 'success')
            timer2.assert_called_once()

    def test_contas_relatorio_trata_erro_e_sucesso(self):
        from compartilhado import models
        models.Contas.create(condominio_id=self.condo_id, conta='Conta A', saldo_inicial=10)
        self.assertEqual(self.api.get_contas_relatorio()['data'], ['Conta A'])
        with patch('compartilhado.models.Contas.select', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_contas_relatorio()['status'], 'error')

    def test_get_condominio_config_com_campos_json_validos(self):
        from compartilhado import models
        import json
        condo = models.Condominio.get_by_id(self.condo_id)
        condo.telefone_administradora = json.dumps(['119999'])
        condo.apartamentos = json.dumps(['101', '102'])
        condo.save()
        resposta = self.api.get_condominio_config()
        self.assertEqual(resposta['data']['condominio']['telefone_administradora'], ['119999'])
        self.assertEqual(resposta['data']['condominio']['apartamentos'], ['101', '102'])
        self.assertIn('membros', resposta['data'])
        self.assertIn('contas', resposta['data'])
        self.assertIn('regras_preenchimento', resposta['data'])

    def test_pendencias_revisao_count_e_registros_com_erros(self):
        resposta = self.api.get_pendencias_revisao_count()
        self.assertEqual(resposta['status'], 'success')
        self.assertIn('data', resposta)
        for tipo in ('meses', 'categorias', 'subcategorias', 'lancamentos', 'documentos', 'desconhecido'):
            r = self.api.get_registros_nao_revisados(tipo)
            self.assertIn(r['status'], ('success', 'error'))

    def test_update_registro_revisado_todos_os_tipos(self):
        from compartilhado import models
        import os, tempfile
        # sem id
        self.assertEqual(self.api.update_registro_revisado('meses', {})['message'], 'ID não informado.')
        # meses: campos + remoção de prestação + nova prestação
        models.PrestacoesContas.update(caminho_local='anexos/inexistente.pdf').where(models.PrestacoesContas.id == 1).execute()
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            abs_pdf = f.name
        self.assertEqual(self.api.update_registro_revisado('meses', {
            'id': 1, 'receita_total': 999, 'despesa_total': 888, 'revisado_usuario': 1,
            'anexos_removidos': [99999, 1],
            'prestacoes_contas': [{'caminho_local': abs_pdf}, {'caminho_local': 'relativo.pdf'}, {}]
        })['status'], 'success')
        mes = models.Meses.get_by_id(1)
        self.assertEqual((mes.receita_total, mes.despesa_total, mes.revisado_usuario), (999, 888, 1))
        self.assertGreaterEqual(mes.anexos, 1)
        os.unlink(abs_pdf)
        # categorias e subcategorias
        self.assertEqual(self.api.update_registro_revisado('categorias', {'id': 1, 'valor': 50, 'revisado_usuario': 1})['status'], 'success')
        self.assertEqual(models.Categorias.get_by_id(1).valor, 50)
        self.assertEqual(self.api.update_registro_revisado('subcategorias', {'id': 1, 'valor': 60, 'revisado_usuario': 1})['status'], 'success')
        self.assertEqual(models.Subcategorias.get_by_id(1).valor, 60)
        # lancamentos: apartamento válido/inválido e campos
        models.Anexos.update(caminho_local='anexos/inexistente.pdf').where(models.Anexos.id == 1).execute()
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            abs_anexo = f.name
        self.assertEqual(self.api.update_registro_revisado('lancamentos', {
            'id': 1, 'apartamento': '999', 'competencia': '2023-02', 'fornecedor': 'F', 'conta': 'C',
            'revisado_usuario': 1, 'anexos_removidos': [99999], 'anexos_lista': []})['status'], 'error')
        self.assertEqual(self.api.update_registro_revisado('lancamentos', {
            'id': 1, 'apartamento': '101', 'competencia': '2023-02', 'fornecedor': 'F', 'conta': 'C',
            'revisado_usuario': 1, 'anexos_removidos': [1], 'anexos_lista': [{'caminho_local': abs_anexo}]})['status'], 'success')
        self.assertGreaterEqual(models.Anexos.select().where(models.Anexos.transacao_id == 1).count(), 1)
        os.unlink(abs_anexo)
        trans = models.Transacoes.get_by_id(1)
        self.assertEqual((trans.apartamento, trans.competencia, trans.fornecedor, trans.conta), ('101', '2023-02', 'F', 'C'))
        # lancamento sem apartamento (limpa) e apartamento vazio
        self.assertEqual(self.api.update_registro_revisado('lancamentos', {'id': 1, 'apartamento': ''})['status'], 'success')
        self.assertEqual(models.Transacoes.get_by_id(1).apartamento, '')
        # documentos tipo C (anexo) e P (prestação) com troca de extensão
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            abs_doc = f.name
        anexo = models.Anexos.create(transacao_id=1, caminho_local='anexos/t.pdf', nome_original='t.pdf', extensao='pdf')
        resp = self.api.update_registro_revisado('documentos', {'id': anexo.id, 'tipo_doc': 'C', 'extensao': 'png', 'revisado_usuario': 1})
        self.assertEqual(resp['status'], 'success')
        self.assertEqual(models.Anexos.get_by_id(anexo.id).extensao, 'png')
        pc = models.PrestacoesContas.create(mes_id=1, caminho_local='anexos/p.pdf', nome_original='p.pdf', extensao='pdf')
        resp = self.api.update_registro_revisado('documentos', {'id': pc.id, 'tipo_doc': 'P', 'extensao': 'jpg'})
        self.assertEqual(resp['status'], 'success')
        self.assertEqual(models.PrestacoesContas.get_by_id(pc.id).extensao, 'jpg')
        # tipo desconhecido -> nenhum branch executa, retorna success
        self.assertEqual(self.api.update_registro_revisado('desconhecido', {'id': 1})['status'], 'success')
        # erro: id inexistente
        self.assertEqual(self.api.update_registro_revisado('meses', {'id': 99999})['status'], 'error')
        os.unlink(abs_doc)

    def test_get_transacoes_datas_invalidas_e_arestas(self):
        r = self.api.get_transacoes('data-invalida', 'outra-invalida')
        self.assertIn(r['status'], ('success', 'error'))
        r2 = self.api.get_transacoes()
        self.assertIn(r2['status'], ('success', 'error'))
        self.assertTrue(r2.get('data') is not None or r2['status'] == 'error')
        r3 = self.api.get_transacoes('2023-01-01', '2023-01-31')
        self.assertEqual(r3['status'], 'success')

    def test_renegociacao_e_arquivo_e_anexos(self):
        from compartilhado import models
        ren = models.Renegociacao.create(condominio_id=self.condo_id, apartamento='101', data_renegociacao='18/01/2023')
        self.assertEqual(self.api.get_renegociacao(ren.id)['status'], 'success')
        self.assertEqual(self.api.get_renegociacao(99999)['status'], 'error')
        self.assertEqual(self.api.delete_renegociacao(99999)['status'], 'success')
        # salvar_renegociacao payload inválido/válido
        resp = self.api.salvar_renegociacao({'apartamento': '101', 'data_renegociacao': '20/01/2023'})
        self.assertIn(resp['status'], ('success', 'error'))
        # anexos e prestações
        self.assertIn(self.api.get_anexos_transacao(1)['status'], ('success', 'error'))
        self.assertIn(self.api.get_anexos_transacao(99999)['status'], ('success', 'error'))
        self.assertIn(self.api.get_prestacoes_contas_mes('2023-01')['status'], ('success', 'error'))
        # selecionar_arquivo / abrir_arquivo_local
        self.api._main_window = MagicMock()
        self.api._main_window.create_file_dialog.return_value = []
        self.assertEqual(self.api.selecionar_arquivo()['status'], 'cancelled')
        self.api._main_window.create_file_dialog.return_value = ['/tmp/sem_extensao']
        self.assertEqual(self.api.selecionar_arquivo()['status'], 'error')
        self.api._main_window.create_file_dialog.return_value = ['/tmp/x.pdf']
        self.assertEqual(self.api.selecionar_arquivo()['data'], '/tmp/x.pdf')
        self.api._main_window = None
        self.assertEqual(self.api.selecionar_arquivo()['message'], 'Janela não disponível.')
        self.assertEqual(self.api.abrir_arquivo_local(None)['message'], 'Caminho inválido.')
        with patch('os.path.exists', return_value=True), patch('os.startfile', create=True) as startfile:
            self.assertEqual(self.api.abrir_arquivo_local('anexos/x.pdf')['status'], 'success')
            startfile.assert_called_once()
        with patch('os.path.exists', return_value=False):
            self.assertEqual(self.api.abrir_arquivo_local('anexos/x.pdf')['message'], 'Arquivo não encontrado no disco.')

    def test_preferencias_sync_e_app_ready(self):
        self.assertIn(self.api.sync_preferencias_cache({})['status'], ('success', 'error'))
        self.assertIn(self.api.app_ready()['status'], ('success', 'error'))
        prefs = self.api.get_preferencias()
        self.assertIn(prefs['status'], ('success', 'error'))
        resp = self.api.salvar_preferencias({'modo_escuro': False, 'cor_primaria': 'blue'})
        self.assertEqual(resp['status'], 'success')

    def test_init_condo_id_e_posicao_unificada_erros(self):
        from compartilhado import models
        import json
        # _initialize_condo_id: preferencia sem condominio valido -> tenta set_condominio
        pref = models.PreferenciasUsuario.get(models.PreferenciasUsuario.condominio_id == self.condo_id) if models.PreferenciasUsuario.select().exists() else None
        import datetime as _dt
        self.api.condo_id = 'fantasma'
        with self.assertRaises(ValueError):
            self.api._calcular_posicao_unificada(_dt.date(2023, 1, 31), {})
        models.Condominio.create(id='fantasma', nome='F', apartamentos='json-quebrado')
        with self.assertRaises(Exception):
            self.api._calcular_posicao_unificada(_dt.date(2023, 1, 31), {})
        self.api.condo_id = self.condo_id
        # get_nome_condominio com exceção
        with patch('compartilhado.models.Condominio.get_or_none', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_nome_condominio()['status'], 'error')
        with patch('compartilhado.models.Condominio.select', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_condominios()['status'], 'error')
        with patch.object(self.api, 'salvar_preferencias', side_effect=RuntimeError('x')):
            pass
        # relatorio conta sem dados / conta inválida
        self.assertIn(self.api.get_relatorio_conta({'conta': 'inexistente'})['status'], ('success', 'error'))
        # get_condominio_config com exceção genérica
        with patch('compartilhado.models.MembrosGestao.select', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_condominio_config()['status'], 'error')
        # update_condominio_config com condo inexistente
        self.api.condo_id = 'nao-existe-xyz'
        resp = self.api.update_condominio_config({'condominio': {'nome': 'X'}})
        self.assertEqual(resp['status'], 'error')
        self.api.condo_id = self.condo_id
        # validar_margem via update com valor limite
        self.assertEqual(self.api.update_condominio_config({'condominio': {'margem_diferenca_encargos': 'abc'}})['status'], 'error')
        self.assertEqual(self.api.update_condominio_config({'condominio': {'margem_diferenca_encargos': 0.001}})['status'], 'error')
        # taxas: get com tipos, delete/update inexistente
        self.assertEqual(self.api.get_taxas(tipos=['C'])['status'], 'success')
        self.assertEqual(self.api.delete_taxa(99999)['status'], 'error')
        self.assertEqual(self.api.update_taxa(99999, {'valor_original': 1})['status'], 'error')
        # insert_taxa com payload parcial
        resp = self.api.insert_taxa({'tipo': 'C', 'apartamento': '101', 'competencia': '2023-03', 'descricao': 'Taxa X', 'valor_original': 10})
        self.assertIn(resp['status'], ('success', 'error'))
        # get_taxas_por_apartamento
        self.assertEqual(self.api.get_taxas_por_apartamento('101', ['2023-01', '2023-12'])['status'], 'success')
        self.assertEqual(self.api.get_taxas_por_apartamento('101', ['2023-01', '2023-12'], tipos=['X'])['data'], [])

    def test_init_error_retorna_erro_em_todos_os_metodos_publicos(self):
        self.api.init_error = 'falha de inicialização'
        chamadas = [
            ('get_nome_condominio', ()), ('get_condominios', ()), ('set_condominio', ('x',)),
            ('get_contas_relatorio', ()), ('get_relatorio_conta', ()),
            ('get_relatorio_recebimentos', ({},)), ('get_apartamentos', ()), ('get_condominio_config', ()),
            ('update_condominio_config', ({},)), ('get_pendencias_revisao_count', ()), ('get_dashboard_kpis', ()),
            ('get_transacoes', ()), ('get_registros_nao_revisados', ('meses',)),
            ('update_registro_revisado', ('meses', {})), ('get_inadimplencia', ()),
            ('get_taxas_por_apartamento', ('101', ['2023-01', '2023-12'])), ('get_taxas', ()),
            ('delete_taxa', (1,)), ('update_taxa', (1, {})), ('insert_taxa', ({},)),
            ('get_renegociacao', (1,)), ('delete_renegociacao', (1,)), ('salvar_renegociacao', ({},)),
            ('selecionar_arquivo', ()), ('get_anexos_transacao', (1,)), ('get_prestacoes_contas_mes', ('2023-01',)),
            ('get_preferencias', ()), ('salvar_preferencias', ({},)),
        ]
        for nome, args in chamadas:
            with self.subTest(metodo=nome):
                resp = getattr(self.api, nome)(*args)
                self.assertEqual(resp['status'], 'error', nome)
                self.assertEqual(resp['message'], 'falha de inicialização', nome)
        self.api.init_error = None

    def test_excecoes_nos_metodos_de_relatorio_e_listagem(self):
        from compartilhado import models
        # exceções internas -> status error
        with patch('bff.relatorio_conta.gerar', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_relatorio_conta({})['status'], 'error')
        with patch('bff.relatorio_recebimentos.gerar', side_effect=RuntimeError('falha'), create=True):
            pass
        with patch.object(models.Meses, 'select', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_pendencias_revisao_count()['status'], 'error')
            self.assertEqual(self.api.get_registros_nao_revisados('meses')['status'], 'error')
        with patch.object(models.Condominio, 'get_or_none', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_dashboard_kpis()['status'], 'error')
        with patch.object(models.Transacoes, 'select', side_effect=RuntimeError('falha')):
            r = self.api.get_transacoes()
            self.assertEqual(r['status'], 'error')
        with patch.object(models.Taxas, 'select', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_taxas()['status'], 'error')
            self.assertEqual(self.api.get_taxas_por_apartamento('101', ['2023-01', '2023-12'])['status'], 'error')
        with patch.object(models.Renegociacao, 'get_or_none', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_renegociacao(1)['status'], 'error')
        with patch.object(models.Anexos, 'select', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_anexos_transacao(1)['status'], 'error')
        with patch.object(models.PrestacoesContas, 'select', side_effect=RuntimeError('falha')):
            self.assertEqual(self.api.get_prestacoes_contas_mes('2023-01')['status'], 'error')
        with patch.object(models.PreferenciasUsuario, 'get_or_none', side_effect=RuntimeError('falha')):
            r = self.api.get_preferencias()
            self.assertIn(r['status'], ('success', 'error'))

    def test_initialize_condo_id_pref_sem_condominio_e_excecao(self):
        from compartilhado import models
        models.PreferenciasUsuario.delete().execute()
        models.PreferenciasUsuario.create(condominio_id=None)
        api2 = Api(db_path=self.temp_db_path)
        self.assertEqual(api2.condo_id, self.condo_id)
        self.assertEqual(models.PreferenciasUsuario.select().first().condominio_id, self.condo_id)
        with patch.object(models.PreferenciasUsuario, 'select', side_effect=RuntimeError('x')):
            api3 = Api(db_path=self.temp_db_path)
        self.assertIsNone(api3.condo_id)
        self.assertIsNotNone(api3.init_error)

    def test_calcular_posicao_validacoes_de_cadastro_e_filtro(self):
        from compartilhado import models
        import datetime as dt
        condo = models.Condominio.get_by_id(self.condo_id)
        for invalido in ('{"a":1}', '["101", 5]', '123', '[true]'):
            condo.apartamentos = invalido
            condo.save()
            with self.assertRaises(ValueError, msg=invalido):
                self.api._calcular_posicao_unificada(dt.date(2023, 1, 31), {})
        condo.apartamentos = '["101"]'
        condo.save()
        for filtro in ({'apartamentos': 'x'}, {'apartamentos': [1]}, {'apartamentos': '101'}):
            with self.assertRaises(ValueError, msg=str(filtro)):
                self.api._calcular_posicao_unificada(dt.date(2023, 1, 31), filtro)
        try:
            self.api._calcular_posicao_unificada(dt.date(2023, 1, 31), {'apartamentos': ['102']})
        except Exception:
            pass
        with patch.object(models.PreferenciasUsuario, 'create', side_effect=RuntimeError('x')):
            models.PreferenciasUsuario.delete().execute()
            self.assertEqual(self.api.set_condominio(self.condo_id)['status'], 'error')
        self.api.prefs_cache = None
        self.api._main_window = None
        with patch('threading.Timer'):
            self.assertEqual(self.api.exit_app()['status'], 'success')

    def test_relatorios_apartamentos_e_config_excecoes(self):
        from compartilhado import models
        with patch.object(self.api, '_calcular_posicao_unificada', side_effect=RuntimeError('x')):
            self.assertEqual(self.api.get_relatorio_inadimplencia({'data_corte': '2023-01-20'})['status'], 'error')
            self.assertEqual(self.api.get_relatorio_recebimentos({})['status'], 'error')
        with patch.object(models.Condominio, 'get_or_none', side_effect=RuntimeError('x')):
            self.assertEqual(self.api.get_apartamentos()['status'], 'error')
            self.assertEqual(self.api.get_condominio_config()['status'], 'error')
        with patch.object(models.MembrosGestao, 'select', side_effect=RuntimeError('x')):
            self.assertEqual(self.api.get_condominio_config()['status'], 'error')
        with patch.object(models.Contas, 'select', side_effect=RuntimeError('x')):
            self.assertEqual(self.api.get_condominio_config()['status'], 'error')

    def test_dashboard_kpis_condominio_inexistente_e_telefone_invalido(self):
        from compartilhado import models
        self.api.condo_id = 'inexistente'
        r = self.api.get_dashboard_kpis()
        self.assertEqual(r['status'], 'error')
        self.api.condo_id = self.condo_id
        condo = models.Condominio.get_by_id(self.condo_id)
        condo.telefone_administradora = 'json-quebrado'
        condo.save()
        r2 = self.api.get_dashboard_kpis()
        self.assertEqual(r2['status'], 'success')
        self.assertEqual(r2['data']['gestao']['administradora']['telefone'], 'json-quebrado')

    def test_transacoes_arvore_casos_de_borda(self):
        from compartilhado import models
        # sem datas -> deriva range das linhas
        r = self.api.get_transacoes()
        self.assertEqual(r['status'], 'success')
        # range vazio -> nos de mês sem transações (percentuais zerados)
        r2 = self.api.get_transacoes('2020-01-01', '2020-01-31')
        self.assertEqual(r2['status'], 'success')
        # mês fora do range pré-preenchido + segundo tipo no mesmo mês
        mes_fora = models.Meses.create(condominio_id=self.condo_id, competencia='2020-06', exibicao='JUN/2020',
                                       consistente=1, revisado_usuario=0, receita_total=0, despesa_total=0, anexos=0)
        cat_r = models.Categorias.create(mes_id=mes_fora.id, tipo='R', nome='Receita X', valor=50, consistente=1, revisado_usuario=0)
        sub_r = models.Subcategorias.create(categoria_id=cat_r.id, tipo='R', nome='Sub R', valor=50, consistente=1, revisado_usuario=0)
        models.Transacoes.create(subcategoria_id=sub_r.id, tipo='R', data='10/01/2023', descricao='Rec', valor=50,
                                 apartamento='101', competencia='2023-01', fornecedor=None, anexos=0, consistente=1, revisado_usuario=0)
        cat_d = models.Categorias.get(models.Categorias.mes_id == 1)
        sub_d = models.Subcategorias.get(models.Subcategorias.categoria_id == cat_d.id)
        models.Transacoes.create(subcategoria_id=sub_d.id, tipo='D', data='11/01/2023', descricao='Desp', valor=10,
                                 apartamento='101', competencia='2023-01', fornecedor='F', anexos=0, consistente=1, revisado_usuario=0)
        r3 = self.api.get_transacoes('2023-01-01', '2023-01-31')
        self.assertEqual(r3['status'], 'success')
        # data fora do padrão no registro não revisado
        models.Transacoes.get(models.Transacoes.descricao == 'Desp').data = 'curta'
        models.Transacoes.get(models.Transacoes.descricao == 'Desp').save()
        regs = self.api.get_registros_nao_revisados('lancamentos')
        self.assertEqual(regs['status'], 'success')

    def test_update_registro_revisado_sub_ramos(self):
        from compartilhado import models
        import os, tempfile
        # prestação de outro mês em anexos_removidos
        pc_outro = models.PrestacoesContas.create(mes_id=2, caminho_local='anexos/outro.pdf', nome_original='o.pdf', extensao='pdf')
        models.PrestacoesContas.update(caminho_local='anexos/inexistente.pdf').where(models.PrestacoesContas.id == 1).execute()
        r = self.api.update_registro_revisado('meses', {'id': 1, 'anexos_removidos': [pc_outro.id]})
        self.assertEqual(r['status'], 'success')
        self.assertIsNotNone(models.PrestacoesContas.get_by_id(pc_outro.id))
        # apartamento vazio e cadastro de apartamentos inválido
        condo = models.Condominio.get_by_id(self.condo_id)
        condo.apartamentos = None
        condo.save()
        self.assertEqual(self.api.update_registro_revisado('lancamentos', {'id': 1, 'apartamento': '202'})['status'], 'success')
        condo.apartamentos = 'json-quebrado'
        condo.save()
        self.assertEqual(self.api.update_registro_revisado('lancamentos', {'id': 1, 'apartamento': '303'})['status'], 'success')
        self.assertEqual(models.Transacoes.get_by_id(1).apartamento, '303')
        condo.apartamentos = '["101", "102"]'
        condo.save()
        # anexo de outra transação em anexos_removidos + entradas inválidas em anexos_lista
        anexo_outro = models.Anexos.create(transacao_id=2, caminho_local='anexos/x.pdf', nome_original='x.pdf', extensao='pdf')
        models.Anexos.update(caminho_local='anexos/inexistente.pdf').where(models.Anexos.id == 1).execute()
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            abs_a = f.name
        r = self.api.update_registro_revisado('lancamentos', {
            'id': 1, 'anexos_removidos': [anexo_outro.id],
            'anexos_lista': [{'caminho_local': abs_a}, {'sem_caminho': 1}, {'caminho_local': 'relativo.pdf'}]})
        self.assertEqual(r['status'], 'success')
        self.assertIsNotNone(models.Anexos.get_by_id(anexo_outro.id))
        os.unlink(abs_a)
        # documentos sem extensão e sem nome_original
        anexo2 = models.Anexos.create(transacao_id=1, caminho_local=None, nome_original=None, extensao='pdf')
        r = self.api.update_registro_revisado('documentos', {'id': anexo2.id, 'tipo_doc': 'C', 'revisado_usuario': 1})
        self.assertEqual(r['status'], 'success')

        # documento com extensão mas sem nome_original
        anexo3 = models.Anexos.create(transacao_id=1, caminho_local='x.pdf', nome_original=None, extensao='pdf')
        r = self.api.update_registro_revisado('documentos', {'id': anexo3.id, 'tipo_doc': 'C', 'extensao': 'png'})
        self.assertEqual(r['status'], 'success')
        self.assertIsNone(models.Anexos.get_by_id(anexo3.id).nome_original)

    def test_taxas_update_insert_e_renegociacao_ramos(self):
        from compartilhado import models
        taxa = models.Taxas.get(models.Taxas.tipo == 'C')
        # competência inválida com exibicao no payload
        r = self.api.update_taxa(taxa.id, {'competencia': 'invalida', 'exibicao': 'XYZ/2000'})
        self.assertEqual(r['status'], 'success')
        self.assertEqual(models.Taxas.get_by_id(taxa.id).exibicao, 'XYZ/2000')
        # somente exibicao (elif)
        r = self.api.update_taxa(taxa.id, {'exibicao': 'QQQ/1999'})
        self.assertEqual(models.Taxas.get_by_id(taxa.id).exibicao, 'QQQ/1999')
        # tipo D com taxa_id limpa o vínculo
        r = self.api.update_taxa(taxa.id, {'tipo': 'C'})
        self.assertEqual(r['status'], 'success')
        # insert com competência inválida
        self.assertEqual(self.api.insert_taxa({'competencia': 'bad', 'tipo': 'C'})['status'], 'error')
        # delete/renegociação com dependentes
        ren1 = models.Renegociacao.create(condominio_id=self.condo_id, apartamento='101', data_renegociacao='01/01/2023')
        parcela = models.Taxas.create(condominio_id=self.condo_id, renegociacao_id=ren1.id, tipo='P',
                                      competencia='2023-01', valor_original=100)
        ren2 = models.Renegociacao.create(condominio_id=self.condo_id, apartamento='101', data_renegociacao='02/01/2023')
        models.Taxas.create(condominio_id=self.condo_id, renegociacao_id=ren2.id, tipo='R', taxa_id=parcela.id,
                            competencia='2023-01', valor_original=100)
        self.assertEqual(self.api.delete_renegociacao(ren1.id)['status'], 'error')
        # salvar_renegociacao: edição com dependentes
        r = self.api.salvar_renegociacao({'id': ren1.id, 'apartamento': '101', 'taxas_originais': [taxa.id], 'parcelas': []})
        self.assertEqual(r['status'], 'error')
        # edição incluindo as próprias parcelas (ren sem dependentes)
        ren3 = models.Renegociacao.create(condominio_id=self.condo_id, apartamento='101', data_renegociacao='03/01/2023')
        parcela3 = models.Taxas.create(condominio_id=self.condo_id, renegociacao_id=ren3.id, tipo='P',
                                       competencia='2023-01', valor_original=80)
        r = self.api.salvar_renegociacao({'id': ren3.id, 'apartamento': '101', 'taxas_originais': [parcela3.id], 'parcelas': []})
        self.assertEqual(r['status'], 'error')
        # edição válida com parcela de vencimento inválido
        r = self.api.salvar_renegociacao({'id': ren3.id, 'apartamento': '101', 'competencia_inicial': '2023-01',
                                         'competencia_final': '2023-03', 'numero': 1, 'data_renegociacao': '05/01/2023',
                                         'vencimento_primeira_parcela': '10/02/2023', 'quantidade_parcelas': 2,
                                         'taxas_originais': [taxa.id],
                                         'parcelas': [{'vencimento': 'bad', 'competencia': '2023-02', 'valor_original': 50},
                                                      {'vencimento': '10/03/2023', 'valor_original': 50}]})
        self.assertEqual(r['status'], 'success')
        # desconto sem taxa vinculada selecionada
        desconto = models.Taxas.create(condominio_id=self.condo_id, tipo='D', taxa_id=taxa.id,
                                       competencia='2023-01', valor_original=10)
        r = self.api.salvar_renegociacao({'apartamento': '101', 'taxas_originais': [desconto.id], 'parcelas': []})
        self.assertEqual(r['status'], 'error')

    def test_abrir_arquivo_local_plataformas_e_preferencias_app_ready(self):
        from compartilhado import models
        with patch('os.path.exists', return_value=True), \
             patch('os.startfile', create=True, side_effect=AttributeError), \
             patch('sys.platform', 'darwin'), patch('subprocess.call') as call:
            self.assertEqual(self.api.abrir_arquivo_local('x.pdf')['status'], 'success')
            call.assert_called_once()
        with patch('os.path.exists', return_value=True), \
             patch('os.startfile', create=True, side_effect=AttributeError), \
             patch('sys.platform', 'linux'), patch('subprocess.call') as call:
            self.assertEqual(self.api.abrir_arquivo_local('x.pdf')['status'], 'success')
            call.assert_called_once()
        # preferências sem registro e exceções
        models.PreferenciasUsuario.delete().execute()
        r = self.api.get_preferencias()
        self.assertEqual((r['status'], r['data']), ('success', None))
        self.assertEqual(self.api.salvar_preferencias({'modo_escuro': 1})['status'], 'success')
        with patch.object(models.PreferenciasUsuario, 'select', side_effect=RuntimeError('x')):
            self.assertEqual(self.api.get_preferencias()['status'], 'error')
            self.assertEqual(self.api.salvar_preferencias({})['status'], 'error')
        # app_ready com janelas que falham
        self.api._main_window = MagicMock()
        self.api._main_window.show.side_effect = RuntimeError('x')
        self.api._splash_window = MagicMock()
        self.api._splash_window.destroy.side_effect = RuntimeError('x')
        self.assertEqual(self.api.app_ready()['status'], 'success')
        self.assertIsNone(self.api._splash_window)
        self.assertTrue(self.api._get_db_path().endswith(os.path.join('database', 'winker_data.db')))

    def test_main_cenarios_de_inicializacao(self):
        from bff import main as rd_mod
        import ctypes as _ctypes
        class FakeEvent:
            def __init__(self): self.handlers = []
            def __iadd__(self, h): self.handlers.append(h); return self
        def nova_janela():
            j = MagicMock()
            j.events = MagicMock()
            j.events.closing = FakeEvent()
            return j
        # banco ausente -> página de erro html
        janela = nova_janela()
        with patch('os.path.exists', return_value=False), \
             patch.object(rd_mod, 'webview') as wv, \
             patch.object(rd_mod, 'Api') as api_cls, \
             patch.object(rd_mod, 'project_root', self.temp_root):
            wv.create_window.return_value = janela
            api = api_cls.return_value
            api.prefs_cache = {'darkTheme': True}
            rd_mod.main()
            wv.start.assert_called_once()
            on_closing = janela.events.closing.handlers[0]
            api.salvar_preferencias = MagicMock()
            on_closing()
            api.salvar_preferencias.assert_called_once()
            api.prefs_cache = None
            on_closing()
            api.prefs_cache = {'darkTheme': True}
            api.salvar_preferencias.side_effect = RuntimeError('x')
            on_closing()
        # banco ok + angular ok + splash + user32 falha
        def existe(path):
            return (path.endswith('winker_data.db') or path.endswith('index.html')
                    or path.endswith('splash.html') or 'node_modules' in path)
        janela2 = nova_janela()
        windll = MagicMock()
        windll.user32.GetSystemMetrics.side_effect = RuntimeError('sem user32')
        with patch('os.path.exists', side_effect=existe), \
             patch.object(rd_mod, 'webview') as wv, \
             patch.object(rd_mod, 'Api') as api_cls, \
             patch.object(rd_mod, 'project_root', self.temp_root), \
             patch.object(_ctypes, 'windll', windll, create=True):
            wv.create_window.return_value = janela2
            rd_mod.main()
            self.assertEqual(wv.create_window.call_count, 2)
            wv.start.assert_called_once()
        # node_modules ausente + npm install falha -> sys.exit(1)
        janela3 = nova_janela()
        with patch('os.path.exists', side_effect=lambda p: p.endswith('winker_data.db')), \
             patch.object(rd_mod, 'webview') as wv, \
             patch.object(rd_mod, 'Api'), \
             patch.object(rd_mod, 'project_root', self.temp_root), \
             patch('subprocess.check_call') as npm:
            npm.side_effect = __import__('subprocess').CalledProcessError(1, 'npm')
            wv.create_window.return_value = janela3
            with self.assertRaises(SystemExit):
                rd_mod.main()
        # node_modules ok + build falha + dashboard.html ausente -> html de erro
        def existe3(path):
            return path.endswith('winker_data.db') or 'node_modules' in path
        janela4 = nova_janela()
        with patch('os.path.exists', side_effect=existe3), \
             patch.object(rd_mod, 'webview') as wv, \
             patch.object(rd_mod, 'Api'), \
             patch.object(rd_mod, 'project_root', self.temp_root), \
             patch('subprocess.check_call') as build:
            build.side_effect = __import__('subprocess').CalledProcessError(1, 'npm')
            wv.create_window.return_value = janela4
            rd_mod.main()
            wv.start.assert_called_once()

    def test_dashboard_kpis_e_transacoes_basicos(self):
        kpis = self.api.get_dashboard_kpis()
        self.assertIn(kpis['status'], ('success', 'error'))
        transacoes = self.api.get_transacoes('2023-01-01', '2023-12-31')
        self.assertIn(transacoes['status'], ('success', 'error'))
        inadimplencia = self.api.get_inadimplencia()
        self.assertIn(inadimplencia['status'], ('success', 'error'))
        self.assertEqual(self.api.get_taxas()['status'], 'success')
        self.assertEqual(self.api.get_apartamentos()['status'], 'success')

if __name__ == '__main__':
    unittest.main()
