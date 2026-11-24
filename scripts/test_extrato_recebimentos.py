import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
with patch('setup_deps.install_dependencies'):
    import models
    from relatorio_recebimentos import gerar, _conciliar_lancamentos
from peewee import SqliteDatabase


class TestExtratoRecebimentos(unittest.TestCase):
    def setUp(self):
        self.db = SqliteDatabase(':memory:')
        self.classes = [models.Condominio, models.Meses, models.Categorias, models.Subcategorias,
                        models.Transacoes, models.Renegociacao, models.Taxas]
        self.ctx = self.db.bind_ctx(self.classes)
        self.ctx.__enter__()
        self.db.create_tables(self.classes)
        self.condo = models.Condominio.create(id='a', apartamentos='["101", "102"]')
        self.mes = models.Meses.create(condominio_id='a', competencia='2023-01')
        models.Meses.create(condominio_id='a', competencia='2023-03')
        categoria = models.Categorias.create(mes_id=self.mes)
        self.sub = models.Subcategorias.create(categoria_id=categoria)

    def tearDown(self):
        self.db.close()
        self.ctx.__exit__(None, None, None)

    def test_agrupamento_filtros_e_renegociacao(self):
        taxa = models.Taxas.create(condominio_id='a', tipo='C', competencia='2023-01', vencimento='10/01/2023', descricao='Mensal', valor_original=100, desconto_vista=5)
        models.Taxas.create(condominio_id='a', tipo='D', apartamento='101', competencia='2023-01', vencimento='10/01/2023', descricao='Desconto', valor_original=10)
        ren = models.Renegociacao.create(condominio_id='a', apartamento='101', data_renegociacao='15/01/2023')
        models.Taxas.create(condominio_id='a', tipo='R', apartamento='101', taxa_id=taxa, renegociacao_id=ren)
        models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='12/01/2023', apartamento='101', competencia='2023-01', descricao='Pagamento', valor=90)
        models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='20/01/2023', descricao='Sem unidade', valor=20)
        dados = gerar('a', {'tipo': 'completo', 'apartamentos': []})
        self.assertEqual([u['apartamento'] for u in dados['apartamentos']], ['101', '102', None])
        grupos = dados['apartamentos'][0]['competencias']
        self.assertEqual([g['competencia'] for g in grupos], ['2023-01', '2023-02', '2023-03'])
        self.assertEqual([g['subtotal'] for g in grupos], [-100, 0, 0])
        self.assertEqual(dados['apartamentos'][0]['subtotal'], -100)
        self.assertEqual(dados['apartamentos'][1]['subtotal'], 100)
        self.assertEqual(dados['total'], -20)
        linhas = grupos[0]['lancamentos']
        self.assertEqual([l['valor'] for l in linhas], [100, -10, -90])
        mensal = next(linha for linha in linhas if linha['tipo'] == 'Cobrança')
        self.assertTrue(mensal['renegociado'])
        self.assertEqual(mensal['desconto_vista'], 5)
        self.assertFalse(dados['apartamentos'][1]['competencias'][0]['lancamentos'][0]['renegociado'])
        filtrado = gerar('a', {'tipo': 'recebimento', 'periodo': ['2023-01-12', '2023-01-12'], 'apartamentos': ['101']})
        self.assertEqual([l['tipo'] for l in filtrado['apartamentos'][0]['competencias'][0]['lancamentos']], ['Recebimento'])
        anterior = gerar('a', {'tipo': 'recebimento', 'periodo': ['2023-01-01', '2023-01-10'], 'apartamentos': ['101']})
        self.assertFalse(anterior['apartamentos'][0]['competencias'][0]['lancamentos'][0]['renegociado'])

    def test_periodo_obrigatorio_e_sem_competencia(self):
        with self.assertRaisesRegex(ValueError, 'início e o fim'):
            gerar('a', {'tipo': 'competencia', 'periodo': ['2023-01', None]})
        dados = gerar('a', {'tipo': 'competencia', 'periodo': ['2023-01', '2023-03']})
        self.assertEqual(dados['data_corte'], '2023-03-31')
        self.assertEqual(len(dados['apartamentos'][0]['competencias']), 3)

    def test_completo_limita_competencias_e_mantem_sem_competencia(self):
        models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='01/01/2020', apartamento='101', competencia='2020-01', valor=10)
        models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='01/01/2020', apartamento='101', competencia=None, valor=20)
        models.Transacoes.create(subcategoria_id=self.sub, tipo='D', data='01/01/2023', apartamento='101', competencia='2023-01', valor=30)
        dados = gerar('a', {'tipo': 'completo'})
        grupos = dados['apartamentos'][0]['competencias']
        self.assertEqual([g['competencia'] for g in grupos], ['2023-01', '2023-02', '2023-03', None])
        self.assertEqual([l['valor'] for l in grupos[-1]['lancamentos']], [-20])

    def test_conciliacao_prioriza_valores_iguais_e_nao_reutiliza_pagamento(self):
        def item(id, tipo, valor, desconto=0):
            return {'id': id, 'data': '2023-01-10', 'descricao': str(id), 'tipo': tipo,
                    'valor': valor, 'desconto_vista': desconto, 'renegociado': False, 'ordem': 1 if tipo == 'Recebimento' else 0}
        linhas = [item(1, 'Cobrança', 100, 10), item(2, 'Cobrança', 90), item(3, 'Recebimento', -90)]
        resultado = _conciliar_lancamentos(linhas)
        self.assertEqual(len(resultado), 3)
        self.assertEqual(resultado[0]['desconto_vista'], 10)
        self.assertEqual(linhas[0]['desconto_vista'], 10)

    def test_prioriza_recebimentos_na_data_da_cobranca_antes_de_valores_integrais_em_outras_datas(self):
        def item(id, tipo, valor, data, desconto=0):
            return {'id': id, 'data': data, 'descricao': str(id), 'tipo': tipo, 'valor': valor,
                    'desconto_vista': desconto, 'renegociado': False, 'ordem': 1 if tipo == 'Recebimento' else 0}
        linhas = [item(1, 'Parcela de renegociação', 452.89, '2025-01-07'),
                  item(2, 'Cobrança', 360.22, '2025-01-10', 36.02), item(3, 'Cobrança', 36.02, '2025-01-10', 3.60),
                  item(4, 'Recebimento', -360.22, '2025-01-07'), item(5, 'Recebimento', -36.02, '2025-01-07'),
                  item(6, 'Recebimento', -41.17, '2025-01-07'), item(7, 'Recebimento', -15.48, '2025-01-07'),
                  item(8, 'Recebimento', -324.20, '2025-01-10'), item(9, 'Recebimento', -32.42, '2025-01-10')]
        resultado = _conciliar_lancamentos(linhas)
        descontos = [linha for linha in resultado if linha['tipo'] == 'Desconto à vista']
        self.assertCountEqual([linha['valor'] for linha in descontos], [-36.02, -3.60])
        self.assertTrue(all(linha['data'] == '2025-01-10' for linha in descontos))
        self.assertFalse(any(linha['tipo'] == 'Acréscimo' for linha in resultado))

    def test_desconto_e_acrescimo_gerados_apenas_no_relatorio(self):
        models.Taxas.create(condominio_id='a', apartamento='101', tipo='I', competencia='2023-01', vencimento='10/01/2023', descricao='Mensal', valor_original=100, desconto_vista=10)
        models.Taxas.create(condominio_id='a', apartamento='101', tipo='I', competencia='2023-01', vencimento='10/01/2023', descricao='Extra', valor_original=50)
        models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='12/01/2023', apartamento='101', competencia='2023-01', descricao='Pagamento', valor=90)
        models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='13/01/2023', apartamento='101', competencia='2023-01', descricao='Outro pagamento', valor=55)
        antes = (models.Taxas.select().count(), models.Transacoes.select().count())
        linhas = gerar('a', {'tipo': 'completo', 'apartamentos': ['101']})['apartamentos'][0]['competencias'][0]['lancamentos']
        self.assertEqual([(l['tipo'], l['valor']) for l in linhas if l['tipo'] in ('Desconto à vista', 'Acréscimo')], [('Desconto à vista', -10), ('Acréscimo', 5)])
        mesmo_dia = [l for l in linhas if l['data'] == '2023-01-10']
        self.assertEqual([l['tipo'] for l in mesmo_dia], ['Cobrança', 'Cobrança'])
        self.assertEqual(next(l['desconto_vista'] for l in linhas if l['descricao'] == 'Mensal' and l['tipo'] == 'Cobrança'), 0)
        self.assertEqual(sum(round(l['valor'] * 100) for l in linhas), 0)
        dados = gerar('a', {'tipo': 'completo', 'apartamentos': ['101']})
        self.assertEqual(dados['apartamentos'][0]['competencias'][0]['subtotal'], 0)
        self.assertEqual(dados['apartamentos'][0]['subtotal'], 0)
        self.assertEqual((models.Taxas.select().count(), models.Transacoes.select().count()), antes)

    def test_ajustes_usam_data_do_recebimento(self):
        def item(id, tipo, valor, data, desconto=0):
            return {'id': id, 'data': data, 'descricao': '', 'tipo': tipo, 'valor': valor,
                    'desconto_vista': desconto, 'renegociado': False, 'ordem': 1 if tipo == 'Recebimento' else 0}
        simples = _conciliar_lancamentos([item(1, 'Cobrança', 100, '2023-01-10', 10), item(2, 'Recebimento', -90, '2023-01-12')])
        self.assertEqual(next(l['data'] for l in simples if l['tipo'] == 'Desconto à vista'), '2023-01-12')
        combinado = _conciliar_lancamentos([item(1, 'Cobrança', 100, '2023-01-10', 10), item(2, 'Desconto', -5, '2023-01-10'), item(3, 'Recebimento', -85, '2023-01-13')])
        self.assertEqual(next(l['data'] for l in combinado if l['tipo'] == 'Desconto à vista'), '2023-01-13')
        acrescimo = _conciliar_lancamentos([item(1, 'Cobrança', 100, '2023-01-10'), item(2, 'Recebimento', -105, '2023-01-15')])
        self.assertEqual(next(l['data'] for l in acrescimo if l['tipo'] == 'Acréscimo'), '2023-01-15')

    def test_nao_cria_acrescimo_sem_os_dois_lados_ou_se_recebido_for_menor(self):
        def item(id, tipo, valor):
            return {'id': id, 'data': '2023-01-10', 'descricao': '', 'tipo': tipo,
                    'valor': valor, 'desconto_vista': 0, 'renegociado': False, 'ordem': 0}
        for linhas in ([item(1, 'Recebimento', -20)], [item(1, 'Cobrança', 100), item(2, 'Recebimento', -80)]):
            self.assertFalse(any(l['tipo'] == 'Acréscimo' for l in _conciliar_lancamentos(linhas)))

    def test_renegociados_nao_participam_de_conciliacao(self):
        def item(id, tipo, valor, desconto=0, renegociado=False):
            return {'id': id, 'data': '2024-05-10', 'descricao': '', 'tipo': tipo,
                    'valor': valor, 'desconto_vista': desconto, 'renegociado': renegociado,
                    'ordem': 1 if tipo == 'Recebimento' else 0}
        # A cobrança renegociada não deve gerar desconto nem acréscimo com o recebimento.
        linhas = [item(1, 'Cobrança', 100, 10, True), item(2, 'Recebimento', -90)]
        resultado = _conciliar_lancamentos(linhas)
        self.assertEqual(len(resultado), 2)
        self.assertTrue(resultado[0]['renegociado'])
        # O desconto renegociado também não pode completar uma combinação de três linhas.
        linhas = [item(1, 'Cobrança', 100, 10), item(2, 'Desconto', -5, renegociado=True), item(3, 'Recebimento', -85)]
        resultado = _conciliar_lancamentos(linhas)
        self.assertFalse(any(linha['tipo'] == 'Desconto à vista' for linha in resultado))

    def test_acrescimo_apos_pares_exatos_como_apartamento_201(self):
        for descricao, valor in [('Taxa ordinária', 360.22), ('Fundo de reserva', 36.02)]:
            models.Taxas.create(condominio_id='a', apartamento='101', tipo='I', competencia='2023-01', vencimento='10/01/2023', descricao=descricao, valor_original=valor)
        for valor in (360.22, 36.02, 10.39):
            models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='01/02/2023', apartamento='101', competencia='2023-01', valor=valor)
        linhas = gerar('a', {'tipo': 'completo', 'apartamentos': ['101']})['apartamentos'][0]['competencias'][0]['lancamentos']
        acrescimos = [linha for linha in linhas if linha['tipo'] == 'Acréscimo']
        self.assertEqual(len(acrescimos), 1)
        self.assertEqual(acrescimos[0]['valor'], 10.39)
        self.assertEqual(acrescimos[0]['descricao'], 'Juros, multas e/ou correções')
        self.assertEqual(models.Taxas.select().count(), 2)

    def test_desconto_mesma_data_composto_com_desconto_vista(self):
        for descricao, valor, desconto_vista, desconto, pago in [
            ('Ordinária', 433.52, 43.35, .18, 389.99), ('Reserva', 43.35, 4.33, .01, 39.01)
        ]:
            taxa = models.Taxas.create(condominio_id='a', apartamento='101', tipo='I', competencia='2023-01', vencimento='10/01/2023', descricao=descricao, valor_original=valor, desconto_vista=desconto_vista)
            models.Taxas.create(condominio_id='a', apartamento='101', tipo='D', taxa_id=taxa, competencia='2023-01', vencimento='10/01/2023', descricao='Desconto', valor_original=desconto)
            models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='10/01/2023', apartamento='101', competencia='2023-01', valor=pago)
        linhas = gerar('a', {'tipo': 'completo', 'apartamentos': ['101']})['apartamentos'][0]['competencias'][0]['lancamentos']
        descontos = [l['valor'] for l in linhas if l['tipo'] == 'Desconto à vista']
        self.assertCountEqual(descontos, [-43.35, -4.33])
        self.assertFalse(any(l['tipo'] == 'Acréscimo' for l in linhas))
        self.assertEqual(sum(round(l['valor'] * 100) for l in linhas), 0)

    def test_desconto_extra_exige_mesma_data_e_valor_exato(self):
        def item(id, tipo, valor, data='2023-01-10', desconto=0):
            return {'id': id, 'data': data, 'descricao': '', 'tipo': tipo, 'valor': valor,
                    'desconto_vista': desconto, 'renegociado': False, 'ordem': 1 if tipo == 'Recebimento' else 0}
        for data, valor in [('2023-01-11', -0.18), ('2023-01-10', -0.17)]:
            linhas = [item(1, 'Cobrança', 433.52, desconto=43.35), item(2, 'Desconto', valor, data), item(3, 'Recebimento', -389.99)]
            resultado = _conciliar_lancamentos(linhas)
            self.assertFalse(any(l['tipo'] == 'Desconto à vista' for l in resultado))

    def test_desconto_vista_considera_abatimento_do_desconto_vinculado(self):
        for descricao, valor, desconto_vista, desconto, abatimento_vista, pago in [
            ('Ordinária', 360.22, 36.02, 180.11, 18.01, 162.10),
            ('Reserva', 36.02, 3.19, 18.01, 1.39, 16.21)
        ]:
            taxa = models.Taxas.create(condominio_id='a', apartamento='101', tipo='I', competencia='2023-01', vencimento='10/01/2023', descricao=descricao, valor_original=valor, desconto_vista=desconto_vista)
            models.Taxas.create(condominio_id='a', apartamento='101', tipo='D', taxa_id=taxa, competencia='2023-01', vencimento='10/01/2023', descricao='Desconto síndico', valor_original=desconto, desconto_vista=abatimento_vista)
            models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='10/01/2023', apartamento='101', competencia='2023-01', valor=pago)
        linhas = gerar('a', {'tipo': 'completo', 'apartamentos': ['101']})['apartamentos'][0]['competencias'][0]['lancamentos']
        self.assertCountEqual([l['valor'] for l in linhas if l['tipo'] == 'Desconto à vista'], [-18.01, -1.80])
        self.assertEqual(sum(round(l['valor'] * 100) for l in linhas), 0)

    def test_ordena_por_data_positivo_desc_e_negativo_asc(self):
        for valor in (20, 50):
            models.Taxas.create(condominio_id='a', apartamento='101', tipo='I', competencia='2023-01', vencimento='10/01/2023', valor_original=valor)
        for valor in (5, 10):
            models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='10/01/2023', apartamento='101', competencia='2023-01', valor=valor)
        models.Transacoes.create(subcategoria_id=self.sub, tipo='R', data='09/01/2023', apartamento='101', competencia='2023-01', valor=2)
        linhas = gerar('a', {'tipo': 'completo', 'apartamentos': ['101']})['apartamentos'][0]['competencias'][0]['lancamentos']
        self.assertEqual([l['valor'] for l in linhas], [-2, 50, 20, -10, -5])

    def test_apartamentos_selecionados_em_ordem_crescente(self):
        dados = gerar('a', {'tipo': 'completo', 'apartamentos': ['102', '101']})
        self.assertEqual([unidade['apartamento'] for unidade in dados['apartamentos']], ['101', '102'])
