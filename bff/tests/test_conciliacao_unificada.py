import unittest
import sqlite3
import random
from decimal import Decimal
from collections import Counter
from datetime import date
from unittest.mock import patch
from bff.apresentacao_conciliacao import data_corte_extrato, extrato, inadimplencia

from bff.conciliacao_unificada import (ConciliacaoInconclusiva, _centavos, aplicar_ajustes, calcular_encargos, calcular_posicao,
                                    conciliar_exatos, conciliar_historicos, consultar, distribuir_parciais, normalizar, simular_descontos_temporais)


class TestNormalizacao(unittest.TestCase):
    def test_isola_condominio_unidade_competencia_e_corte(self):
        taxas = [
            {'id': 1, 'condominio_id': 'a', 'tipo': 'C', 'competencia': '2022-05', 'vencimento': '10/06/2022', 'valor_original': 100},
            {'id': 2, 'condominio_id': 'b', 'tipo': 'C', 'competencia': '2022-05', 'vencimento': '10/06/2022', 'valor_original': 500},
            {'id': 3, 'condominio_id': 'a', 'tipo': 'I', 'apartamento': '102', 'competencia': '2022-05', 'vencimento': '10/06/2022', 'valor_original': 20},
        ]
        recebimentos = [
            {'id': 1, 'condominio_id': 'a', 'tipo': 'R', 'apartamento': '101', 'competencia': '2022-05', 'data': '01/06/2022', 'valor': 100},
            {'id': 2, 'condominio_id': 'b', 'tipo': 'R', 'apartamento': '101', 'competencia': '2022-05', 'data': '01/06/2022', 'valor': 50},
            {'id': 3, 'condominio_id': 'a', 'tipo': 'R', 'apartamento': '', 'competencia': '2022-05', 'data': '01/06/2022', 'valor': 10},
            {'id': 4, 'condominio_id': 'a', 'tipo': 'R', 'apartamento': '101', 'competencia': None, 'data': '01/06/2022', 'valor': 10},
            {'id': 5, 'condominio_id': 'a', 'tipo': 'R', 'apartamento': '101', 'competencia': '2022-05', 'data': '03/06/2022', 'valor': 10},
            {'id': 6, 'condominio_id': 'a', 'tipo': 'R', 'apartamento': '101', 'competencia': '2022-05', 'data': '02/06/2022', 'valor': -3},
        ]
        resultado = normalizar('a', date(2022, 6, 2), ['101', '102'], taxas, recebimentos)
        self.assertEqual([(t['id'], t['apartamento']) for t in resultado['taxas']], [(1, '101'), (1, '102'), (3, '102')])
        self.assertEqual([r['id'] for r in resultado['recebimentos']], [1, 6])
        self.assertEqual(resultado['recebimentos'][1]['valor_centavos'], -300)
        self.assertEqual(resultado['recebimentos'][0]['competencia'], '2022-05')
        self.assertEqual(resultado['taxas'][0]['vencimento'], date(2022, 6, 10))

    def test_extrato_completo_exclui_competencia_futura_mesmo_com_pagamento_antecipado(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-04', vencimento='10/04/2023', valor_original=100)]
        receitas = [dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-04', data='10/03/2023', valor=50)]
        posicao = calcular_posicao('a', date(2023, 3, 15), ['101'], taxas, receitas, 'N')
        limites = {'inicio': '2023-01-01', 'fim': '2023-04-30'}
        completo = extrato(posicao, {'tipo': 'completo'}, limites)
        self.assertEqual(completo['limites']['fim'], '2023-03-31')
        self.assertEqual(completo['apartamentos'][0]['competencias'], [])
        self.assertEqual(completo['total'], 0)
        por_recebimento = extrato(posicao, {'tipo': 'recebimento', 'periodo': ['2023-03-01', '2023-03-15']}, limites)
        self.assertEqual(por_recebimento['apartamentos'][0]['competencias'][0]['competencia'], '2023-04')

    def test_filtros_selecionam_grupos_antes_da_conciliacao_e_preservam_historico(self):
        taxas = [dict(id=i, condominio_id='a', tipo='I', apartamento=apt, competencia=comp,
                      vencimento=vencimento, descricao='Taxa', valor_original=100)
                 for i, apt, comp, vencimento in [(1, '101', '2023-01', '10/01/2023'),
                                                   (2, '101', '2023-02', '10/02/2023'),
                                                   (3, '102', '2023-01', '10/01/2023')]]
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data=dia, valor=valor)
                    for i, dia, valor in [(1, '05/01/2023', 40), (2, '20/01/2023', 20)]]
        filtros = {'tipo': 'recebimento', 'periodo': ['2023-01-20', '2023-01-20'], 'apartamentos': ['101']}
        with patch('bff.conciliacao_unificada.conciliar_exatos', wraps=conciliar_exatos) as conciliar:
            posicao = calcular_posicao('a', date(2023, 1, 20), ['101', '102'], taxas, receitas, 'N', filtros=filtros)
        self.assertEqual([(g['apartamento'], g['competencia']) for g in posicao['grupos']], [('101', '2023-01')])
        self.assertEqual(conciliar.call_count, 1)
        self.assertEqual(posicao['grupos'][0]['saldos'][0]['principal_centavos'], 4000)
        relatorio = extrato(posicao, filtros, {})
        self.assertEqual(relatorio['total'], -20)
        self.assertEqual(relatorio['saldo_original'], 40)
        competencia = calcular_posicao('a', date(2023, 2, 28), ['101', '102'], taxas, receitas, 'N',
                                       filtros={'tipo': 'competencia', 'periodo': ['2023-02', '2023-02'], 'apartamentos': ['101']})
        self.assertEqual([(g['apartamento'], g['competencia']) for g in competencia['grupos']], [('101', '2023-02')])

    def test_respeita_data_dos_acordos_e_preserva_vinculos(self):
        taxas = [
            {'id': 10, 'condominio_id': 'a', 'tipo': 'P', 'apartamento': '101', 'competencia': '2023-02', 'vencimento': '10/02/2023', 'valor_original': 100, 'data_renegociacao': '18/01/2023'},
            {'id': 11, 'condominio_id': 'a', 'tipo': 'R', 'apartamento': '101', 'taxa_id': 10, 'data_renegociacao': '15/02/2023', 'valor_original': 100},
            {'id': 12, 'condominio_id': 'a', 'tipo': 'D', 'apartamento': '101', 'taxa_id': 10, 'vencimento': '20/02/2023', 'valor_original': 10},
        ]
        antes = normalizar('a', date(2023, 1, 17), ['101'], taxas, [])
        self.assertEqual(antes['taxas'], [])
        depois = normalizar('a', date(2023, 2, 20), ['101'], taxas, [])
        self.assertEqual(depois['taxas'][0]['id'], 10)
        self.assertEqual([(t['id'], t['taxa_id']) for t in depois['ajustes']], [(11, 10), (12, 10)])

    def test_receita_com_unidade_informada_nao_e_descartada_por_falta_no_cadastro(self):
        taxas = [dict(id=1, condominio_id='a', tipo='C', competencia='2023-01', vencimento='10/01/2023', valor_original=100),
                 dict(id=2, condominio_id='a', tipo='I', apartamento='999', competencia='2023-01', vencimento='10/01/2023', valor_original=20)]
        receitas = [dict(id=1, condominio_id='a', tipo='R', apartamento='999', competencia='2023-01', data='10/01/2023', valor=20)]
        dados = normalizar('a', date(2023, 1, 20), ['101'], taxas, receitas)
        self.assertEqual([(t['id'], t['apartamento']) for t in dados['taxas']], [(1, '101'), (2, '999')])
        self.assertEqual([r['id'] for r in dados['recebimentos']], [1])
        posicao = calcular_posicao('a', date(2023, 1, 20), ['101'], taxas, receitas, 'N')
        self.assertIn('999', [u['apartamento'] for u in extrato(posicao, {'tipo': 'completo'}, {})['apartamentos']])

    def test_marcador_que_aponta_desconto_nao_abate_duas_vezes(self):
        taxas = [
            dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='10/01/2023', valor_original=100),
            dict(id=2, condominio_id='a', tipo='D', apartamento='101', taxa_id=1, vencimento='12/01/2023', valor_original=20),
            dict(id=3, condominio_id='a', tipo='R', apartamento='101', taxa_id=2, data_renegociacao='18/01/2023', valor_original=20),
        ]
        for corte, esperado in [(date(2023, 1, 11), 10000), (date(2023, 1, 12), 8000), (date(2023, 1, 18), 10000)]:
            dados = normalizar('a', corte, ['101'], taxas, [])
            self.assertEqual(aplicar_ajustes(dados)[0]['valor_centavos'], esperado)


class TestEncargos(unittest.TestCase):
    def test_arredondamento_no_meio_para_baixo(self):
        self.assertEqual(_centavos(Decimal('5.0049')), 500)
        self.assertEqual(_centavos(Decimal('5.005')), 500)
        self.assertEqual(_centavos(Decimal('5.0051')), 501)
        resultado = calcular_encargos(25000, '1', '2', 3, 'M')
        self.assertEqual((resultado['total_centavos'], resultado['multa_centavos'], resultado['juros_centavos']), (25525, 500, 25))

    def test_exemplo_juros_e_multa_arredondados_no_total(self):
        resultado = calcular_encargos(930, '1', '2', 2, 'M')
        self.assertEqual(resultado['total_centavos'], 949)
        self.assertEqual(resultado['multa_centavos'], 19)
        self.assertEqual(resultado['juros_centavos'], 0)
        self.assertEqual(resultado['ajuste_arredondamento_centavos'], -1)

    def test_modalidades_e_sem_atraso(self):
        self.assertEqual(calcular_encargos(10000, '1', '2', 30, 'N')['total_centavos'], 10300)
        self.assertEqual(calcular_encargos(10000, '1', '2', 30, 'M')['total_centavos'], 10302)
        self.assertEqual(calcular_encargos(10000, '1', '2', 30, 'J')['total_centavos'], 10302)
        self.assertEqual(calcular_encargos(10000, '1', '2', 0, 'M')['total_centavos'], 10000)
        with self.assertRaises(ValueError):
            calcular_encargos(10000, '1', '2', 30, '?')


class TestConsulta(unittest.TestCase):
    def test_consulta_isola_condominio_e_preserva_competencia_da_transacao(self):
        conexao = sqlite3.connect(':memory:')
        self.addCleanup(conexao.close)
        conexao.executescript('''
            CREATE TABLE taxas (id INTEGER, condominio_id TEXT, renegociacao_id INTEGER);
            CREATE TABLE renegociacao (id INTEGER, condominio_id TEXT, data_renegociacao TEXT);
            CREATE TABLE meses (id INTEGER, condominio_id TEXT, competencia TEXT);
            CREATE TABLE categorias (id INTEGER, mes_id INTEGER);
            CREATE TABLE subcategorias (id INTEGER, categoria_id INTEGER);
            CREATE TABLE transacoes (id INTEGER, subcategoria_id INTEGER, tipo TEXT, competencia TEXT);
            INSERT INTO taxas VALUES (1, 'a', 1), (2, 'b', NULL);
            INSERT INTO renegociacao VALUES (1, 'a', '18/01/2023');
            INSERT INTO meses VALUES (1, 'a', '2022-09'), (2, 'b', '2022-09');
            INSERT INTO categorias VALUES (1, 1), (2, 2);
            INSERT INTO subcategorias VALUES (1, 1), (2, 2);
            INSERT INTO transacoes VALUES (1, 1, 'R', '2022-06'), (2, 2, 'R', '2022-06'), (3, 1, 'D', '2022-06');
        ''')
        conexao.execute('PRAGMA query_only = ON')
        taxas, receitas = consultar(conexao, 'a')
        self.assertEqual([(t['id'], t['data_renegociacao']) for t in taxas], [(1, '18/01/2023')])
        self.assertEqual([(t['id'], t['competencia']) for t in receitas], [(1, '2022-06')])


class TestCorrespondenciasExatas(unittest.TestCase):
    def test_distribuicao_do_grupo_prioriza_pagamentos_individuais_exatos(self):
        comum = dict(apartamento='201', competencia='2022-04')
        taxas = [dict(comum, id=333, vencimento=date(2022, 4, 1), valor_centavos=20000, desconto_vista=0),
                 dict(comum, id=221, vencimento=date(2022, 4, 11), valor_centavos=25000, desconto_vista=25),
                 dict(comum, id=211, vencimento=date(2022, 4, 11), valor_centavos=1000, desconto_vista=0),
                 dict(comum, id=205, vencimento=date(2022, 4, 11), valor_centavos=930, desconto_vista=0)]
        receitas = [dict(comum, id=i, data=date(2022, 4, 1), valor_centavos=valor)
                    for i, valor in [(20330, 22500), (20327, 20000), (20329, 1000), (20328, 930)]]
        resultado = conciliar_exatos(taxas, receitas, 'M')
        quitacao = resultado['alocacoes'][0]
        pagamentos = quitacao['detalhes']['recebimentos']
        self.assertEqual({p['recebimento_id']: [(a['taxa_id'], a['principal_centavos']) for a in p['alocacoes']]
                          for p in pagamentos},
                         {20330: [(221, 22500)], 20327: [(333, 20000)],
                          20329: [(211, 1000)], 20328: [(205, 930)]})
        self.assertEqual(sum(p['valor_centavos'] for p in pagamentos), 44430)

    def test_reserva_encaixe_exato_antes_de_fracionar_pagamento_maior(self):
        comum = dict(apartamento='201', competencia='2022-04')
        taxas = [dict(comum, id=1, vencimento=date(2022, 4, 1), valor_centavos=5000, desconto_vista=0),
                 dict(comum, id=2, vencimento=date(2022, 4, 11), valor_centavos=10000, desconto_vista=10),
                 dict(comum, id=3, vencimento=date(2022, 4, 11), valor_centavos=3000, desconto_vista=0)]
        receitas = [dict(comum, id=i, data=date(2022, 4, 1), valor_centavos=valor)
                    for i, valor in [(1, 12000), (2, 5000)]]
        pagamentos = conciliar_exatos(taxas, receitas, 'M')['alocacoes'][0]['detalhes']['recebimentos']
        alocacoes = {p['recebimento_id']: [(a['taxa_id'], a['principal_centavos']) for a in p['alocacoes']]
                     for p in pagamentos}
        self.assertEqual(alocacoes[2], [(1, 5000)])
        self.assertEqual(alocacoes[1], [(2, 9000), (3, 3000)])

    def test_concilia_grupo_de_taxas_e_pagamentos_sem_consumir_duas_vezes(self):
        taxas = [dict(id=i, apartamento='101', competencia='2022-05', vencimento=date(2022, 5, 10),
                      valor_centavos=valor, desconto_vista=desconto)
                 for i, valor, desconto in [(1, 10000, 10), (2, 5000, 5)]]
        receitas = [dict(id=i, apartamento='101', competencia='2022-05', data=date(2022, 5, dia), valor_centavos=valor)
                    for i, dia, valor in [(1, 8, 7000), (2, 9, 6500)]]
        resultado = conciliar_exatos(taxas, receitas, 'N')
        self.assertEqual(len(resultado['alocacoes']), 1)
        self.assertCountEqual(resultado['alocacoes'][0]['taxas'], [1, 2])
        self.assertCountEqual(resultado['alocacoes'][0]['recebimentos'], [1, 2])
        self.assertEqual(resultado['taxas_pendentes'], [])
        self.assertEqual(resultado['recebimentos_nao_alocados'], [])
        detalhes = resultado['alocacoes'][0]['detalhes']
        self.assertEqual(sum(a['principal_centavos'] for p in detalhes['recebimentos'] for a in p['alocacoes']), 13500)
        self.assertEqual(sum(s['desconto_concedido_centavos'] for s in detalhes['saldos']), 1500)

    def test_limite_nao_retorna_resultado_parcial_e_mistura_e_rejeitada(self):
        taxa = dict(id=1, apartamento='101', competencia='2022-05', vencimento=date(2022, 5, 10), valor_centavos=10000)
        receita = dict(id=1, apartamento='101', competencia='2022-05', data=date(2022, 5, 10), valor_centavos=10000)
        with self.assertRaises(ConciliacaoInconclusiva):
            conciliar_exatos([taxa], [receita], 'N', limite_operacoes=0)
        with self.assertRaises(ValueError):
            conciliar_exatos([taxa], [dict(receita, apartamento='102')], 'N')

    def test_pagamento_agrupado_avalia_vencimento_de_cada_taxa(self):
        comum = dict(apartamento='101', competencia='2023-01', valor_centavos=10000,
                     juros_mes_percentual=0, multa_percentual=2)
        taxas = [dict(comum, id=1, vencimento=date(2023, 1, 1), desconto_vista=0),
                 dict(comum, id=2, vencimento=date(2023, 1, 20), desconto_vista=10)]
        receita = dict(id=1, apartamento='101', competencia='2023-01', data=date(2023, 1, 10), valor_centavos=19200)
        grupo = conciliar_exatos(taxas, [receita], 'N')['alocacoes'][0]
        self.assertEqual((grupo['prioridade'], grupo['desconto_centavos'], grupo['encargos_centavos']), (1, 1000, 200))
        self.assertCountEqual(grupo['taxas'], [1, 2])

    def test_tolerancia_e_restrita_aos_encargos_com_principal_integral(self):
        taxa = dict(id=1, apartamento='101', competencia='2023-01', vencimento=date(2023, 1, 1),
                    valor_centavos=10000, juros_mes_percentual=0, multa_percentual=2)
        def receita(valor):
            return dict(id=1, apartamento='101', competencia='2023-01', data=date(2023, 1, 2), valor_centavos=valor)
        self.assertEqual(conciliar_exatos([taxa], [receita(10195)], 'N')['alocacoes'][0]['diferenca_centavos'], -5)
        self.assertFalse(conciliar_exatos([taxa], [receita(9995)], 'N')['alocacoes'])
        self.assertFalse(conciliar_exatos([taxa], [receita(10189)], 'N')['alocacoes'])

    def test_margem_nao_quita_principal_na_distribuicao_de_pagamentos_agrupados(self):
        taxas = [dict(id=i, apartamento='204', competencia='2022-04', vencimento=date(2022, 4, 11),
                      valor_centavos=valor, juros_mes_percentual=1, multa_percentual=2)
                 for i, valor in [(211, 1000), (205, 930)]]
        receitas = [dict(id=i, apartamento='204', competencia='2022-04', data=date(2022, 4, 13), valor_centavos=valor)
                    for i, valor in [(20339, 1000), (20338, 930)]]
        resultado = conciliar_exatos(taxas, receitas, 'M', margem_encargos_centavos=50)
        for quitacao in resultado['alocacoes']:
            self.assertTrue(all(s['principal_centavos'] == 0 for s in quitacao['detalhes']['saldos']))
        usados = [i for q in resultado['alocacoes'] for i in q['recebimentos']]
        self.assertEqual(len(usados), len(set(usados)))

    def test_margem_configuravel_nas_buscas_simples_e_historica(self):
        taxa = dict(id=1, apartamento='101', competencia='2023-01', vencimento=date(2023, 1, 1),
                    valor_centavos=10000, juros_mes_percentual=0, multa_percentual=2)
        for diferenca in (-11, -10, -5, 5, 10, 11):
            receita = dict(id=1, apartamento='101', competencia='2023-01', data=date(2023, 1, 2), valor_centavos=10200 + diferenca)
            for margem in (0, 5, 10, 11):
                with self.subTest(diferenca=diferenca, margem=margem):
                    simples = conciliar_exatos([taxa], [receita], 'N', margem_encargos_centavos=margem)
                    historico = conciliar_historicos([taxa], [receita], [], 'N', margem_encargos_centavos=margem)
                    self.assertEqual(bool(simples['alocacoes']), abs(diferenca) <= margem)
                    self.assertEqual(bool(historico['alocacoes']), abs(diferenca) <= margem)

    def test_muitos_recebimentos_sao_conciliados_com_limite_de_estados(self):
        taxa = dict(id=1, apartamento='101', competencia='2023-01', vencimento=date(2023, 1, 10), valor_centavos=2500)
        receitas = [dict(id=i, apartamento='101', competencia='2023-01', data=date(2023, 1, 9), valor_centavos=100) for i in range(25)]
        resultado = conciliar_exatos([taxa], receitas, 'N')
        self.assertEqual(len(resultado['alocacoes'][0]['recebimentos']), 25)
        self.assertEqual(resultado['recebimentos_nao_alocados'], [])

    def test_desempate_tecnico_prefere_menos_recebimentos(self):
        taxa = dict(id=1, apartamento='101', competencia='2023-01', vencimento=date(2023, 1, 10), valor_centavos=10000)
        receitas = [dict(id=i, apartamento='101', competencia='2023-01', data=date(2023, 1, 9), valor_centavos=valor)
                    for i, valor in [(1, 6000), (2, 4000), (3, 10000)]]
        resultado = conciliar_exatos([taxa], receitas, 'N')
        self.assertEqual(resultado['alocacoes'][0]['recebimentos'], [3])

    def test_pagamento_dividido_em_datas_tardias_considera_amortizacao(self):
        taxa = dict(id=1, apartamento='101', competencia='2023-01', vencimento=date(2023, 1, 1),
                    valor_centavos=10000, juros_mes_percentual=1, multa_percentual=2)
        receitas = [dict(id=1, apartamento='101', competencia='2023-01', data=date(2023, 1, 11), valor_centavos=4000),
                    dict(id=2, apartamento='101', competencia='2023-01', data=date(2023, 1, 21), valor_centavos=6253)]
        quitacao = conciliar_exatos([taxa], receitas, 'N')['alocacoes'][0]
        self.assertEqual(quitacao['prioridade'], 2)
        self.assertEqual(quitacao['encargos_centavos'], 253)
        self.assertEqual(quitacao['recebimentos'], [1, 2])

    def test_desempate_prioriza_vencimento_e_valor_antes_do_id(self):
        base = dict(apartamento='101', competencia='2023-01')
        receita = dict(base, id=1, data=date(2023, 1, 1), valor_centavos=9000)
        antiga = dict(base, id=99, vencimento=date(2023, 1, 10), valor_centavos=10000, desconto_vista=10)
        recente = dict(base, id=1, vencimento=date(2023, 1, 11), valor_centavos=12000, desconto_vista=30)
        for taxas in ([antiga, recente], [recente, antiga]):
            self.assertEqual(conciliar_exatos(taxas, [receita], 'N')['alocacoes'][0]['taxas'], [99])
        maior = dict(recente, vencimento=date(2023, 1, 10))
        for taxas in ([antiga, maior], [maior, antiga]):
            self.assertEqual(conciliar_exatos(taxas, [receita], 'N')['alocacoes'][0]['taxas'], [1])


class TestPagamentosParciais(unittest.TestCase):
    def taxa(self, **alteracoes):
        return dict(dict(id=1, apartamento='101', competencia='2023-01', vencimento=date(2023, 1, 1),
                         valor_centavos=10000, juros_mes_percentual=1, multa_percentual=2), **alteracoes)

    def receita(self, id, dia, valor):
        return dict(id=id, apartamento='101', competencia='2023-01', data=date(2023, 1, dia), valor_centavos=valor)

    def test_pagamento_parcial_reduz_principal_e_nao_repete_multa(self):
        resultado = distribuir_parciais([self.taxa()], [self.receita(1, 11, 4000)], date(2023, 1, 21), 'N')
        saldo = resultado['saldos'][0]
        self.assertEqual(saldo['principal_centavos'], 6000)
        self.assertEqual(saldo['multa_centavos'], 200)
        self.assertEqual(saldo['juros_centavos'], 53)  # 33 antes + 20 após o pagamento
        self.assertEqual(saldo['total_centavos'], 6253)
        self.assertEqual(resultado['recebimentos'][0]['alocacoes'][0]['principal_centavos'], 4000)

    def test_receita_negativa_e_excedente_nao_abatem_ou_inventam_encargos(self):
        taxa = self.taxa(juros_mes_percentual=0, multa_percentual=0)
        resultado = distribuir_parciais([taxa], [self.receita(1, 1, -500), self.receita(2, 2, 10200)], date(2023, 1, 3), 'N')
        self.assertEqual(resultado['saldos'][0]['total_centavos'], 0)
        self.assertEqual([r['nao_alocado_centavos'] for r in resultado['recebimentos']], [-500, 200])

    def test_vencimentos_diferentes_e_pagamento_no_corte(self):
        taxas = [self.taxa(id=1, valor_centavos=10000), self.taxa(id=2, vencimento=date(2023, 1, 20), valor_centavos=5000)]
        resultado = distribuir_parciais(taxas, [self.receita(1, 10, 12000)], date(2023, 1, 10), 'N')
        self.assertEqual([s['principal_centavos'] for s in resultado['saldos']], [0, 3230])
        self.assertEqual(resultado['saldos'][1]['multa_centavos'], 0)

    def test_modalidade_j_mantem_multa_na_base_dos_juros_posteriores(self):
        saldo = distribuir_parciais([self.taxa()], [self.receita(1, 11, 4000)], date(2023, 1, 21), 'J')['saldos'][0]
        self.assertEqual((saldo['principal_centavos'], saldo['multa_centavos'], saldo['juros_centavos']), (6000, 200, 55))

    def test_ajustes_apos_pagamento_nao_retroagem_e_cancelamento_restaura_saldo(self):
        taxa = self.taxa(valor_original=100, juros_mes_percentual=0, multa_percentual=0)
        ajustes = [dict(id=2, apartamento='101', tipo='D', taxa_id=1, vencimento=date(2023, 1, 15), valor_original=20),
                   dict(id=3, apartamento='101', tipo='R', taxa_id=2, data_renegociacao='20/01/2023', valor_original=20)]
        receita = self.receita(1, 10, 4000)
        antes = distribuir_parciais([taxa], [receita], date(2023, 1, 14), 'N', ajustes)['saldos'][0]
        durante = distribuir_parciais([taxa], [receita], date(2023, 1, 15), 'N', ajustes)['saldos'][0]
        depois = distribuir_parciais([taxa], [receita], date(2023, 1, 20), 'N', ajustes)['saldos'][0]
        self.assertEqual([antes['principal_centavos'], durante['principal_centavos'], depois['principal_centavos']], [6000, 4000, 6000])

    def test_cancelamento_de_desconto_nao_cria_principal_pago_duas_vezes(self):
        taxa = self.taxa(valor_original=100, juros_mes_percentual=0, multa_percentual=0)
        ajustes = [dict(id=2, apartamento='101', tipo='D', taxa_id=1, vencimento=date(2023, 1, 15), valor_original=20),
                   dict(id=3, apartamento='101', tipo='R', taxa_id=2, data_renegociacao='20/01/2023', valor_original=20)]
        saldo = distribuir_parciais([taxa], [self.receita(1, 10, 9000)], date(2023, 1, 20), 'N', ajustes)['saldos'][0]
        self.assertEqual(saldo['principal_centavos'], 1000)

    def test_desconto_tardio_nao_retroage_aos_juros_anteriores(self):
        taxa = self.taxa(valor_original=100)
        ajuste = dict(id=2, apartamento='101', tipo='D', taxa_id=1, vencimento=date(2023, 1, 11), valor_original=20)
        saldo = distribuir_parciais([taxa], [], date(2023, 1, 21), 'N', [ajuste])['saldos'][0]
        self.assertEqual((saldo['principal_centavos'], saldo['juros_centavos'], saldo['multa_centavos']), (8000, 60, 200))

    def test_desconto_posterior_libera_parte_do_pagamento_para_outra_taxa(self):
        taxas = [self.taxa(id=1, valor_original=100, juros_mes_percentual=0, multa_percentual=0),
                 self.taxa(id=2, valor_original=100, juros_mes_percentual=0, multa_percentual=0)]
        ajuste = dict(id=3, apartamento='101', tipo='D', taxa_id=1, vencimento=date(2023, 1, 15), valor_original=20)
        resultado = distribuir_parciais(taxas, [self.receita(1, 10, 10000)], date(2023, 1, 16), 'N', [ajuste])
        self.assertEqual([s['principal_centavos'] for s in resultado['saldos']], [0, 8000])
        pagamento = resultado['recebimentos'][0]
        self.assertEqual(pagamento['nao_alocado_centavos'], 0)
        self.assertEqual(sum(a['principal_centavos'] for a in pagamento['alocacoes']), 10000)
        self.assertEqual([(m['taxa_id'], m['principal_centavos'], m['motivo']) for m in pagamento['movimentacoes']],
                         [(1, 10000, 'alocacao'), (1, -2000, 'ajuste_posterior'), (2, 2000, 'alocacao')])

    def test_credito_liberado_e_reaplicado_se_desconto_posteriormente_for_cancelado(self):
        taxa = self.taxa(valor_original=100, juros_mes_percentual=0, multa_percentual=0)
        ajustes = [dict(id=2, apartamento='101', tipo='D', taxa_id=1, vencimento=date(2023, 1, 15), valor_original=20),
                   dict(id=3, apartamento='101', tipo='R', taxa_id=2, data_renegociacao='20/01/2023', valor_original=20)]
        resultado = distribuir_parciais([taxa], [self.receita(1, 10, 9000)], date(2023, 1, 20), 'N', ajustes)
        pagamento = resultado['recebimentos'][0]
        self.assertEqual(resultado['saldos'][0]['principal_centavos'], 1000)
        self.assertEqual(pagamento['nao_alocado_centavos'], 0)
        self.assertEqual(sum(a['principal_centavos'] + a['juros_centavos'] + a['multa_centavos'] for a in pagamento['alocacoes']), 9000)
        self.assertEqual([m['principal_centavos'] for m in pagamento['movimentacoes']], [9000, -1000, 1000])

    def test_ajuste_de_outra_taxa_nao_altera_encargos_da_primeira(self):
        taxas = [self.taxa(id=1, valor_original=100), self.taxa(id=2, valor_original=100)]
        ajuste = dict(id=3, apartamento='101', tipo='D', taxa_id=2, vencimento=date(2023, 1, 11), valor_original=20)
        resultado = distribuir_parciais(taxas, [], date(2023, 1, 21), 'M', [ajuste])
        saldo = next(s for s in resultado['saldos'] if s['taxa']['id'] == 1)
        self.assertEqual(saldo['total_centavos'], calcular_encargos(10000, 1, 2, 20, 'M')['total_centavos'])


class TestPosicao(unittest.TestCase):
    def test_conservacao_em_combinacoes_de_pagamentos_e_descontos(self):
        rng = random.Random(122)
        for caso in range(300):
            taxas = [dict(id=i + 1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                          vencimento='20/01/2023', valor_original=rng.choice([20, 30, 50, 100]),
                          desconto_vista=rng.choice([0, 5, 10])) for i in range(rng.randint(1, 4))]
            receitas = [dict(id=i + 1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                             data=f'{rng.randint(1, 19):02d}/01/2023', valor=rng.choice([5, 10, 15, 20, 25, 30, 50, 75, 100]))
                        for i in range(rng.randint(0, 5))]
            with self.subTest(caso=caso):
                grupo = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')['grupos'][0]
                consumos = Counter()
                for quitacao in grupo['quitacoes_exatas']:
                    for pagamento in quitacao['detalhes']['recebimentos']:
                        consumos[pagamento['recebimento_id']] += pagamento['valor_centavos']
                for pagamento in grupo['pagamentos_parciais']:
                    consumos[pagamento['recebimento_id']] += pagamento['valor_centavos']
                self.assertEqual(dict(consumos), {r['id']: round(r['valor'] * 100) for r in receitas})
                saldos = grupo['saldos'] + [s for q in grupo['quitacoes_exatas'] for s in q['detalhes']['saldos']]
                principal = sum(s['principal_pago_centavos'] + s['desconto_concedido_centavos'] + s['principal_centavos'] for s in saldos)
                self.assertEqual(principal, sum(round(t['valor_original'] * 100) for t in taxas))

    def test_conservacao_em_ajustes_manuais_e_pagamentos_em_datas_distintas(self):
        rng = random.Random(123)
        for caso in range(300):
            quantidade = rng.randint(1, 3)
            qtd_receitas = rng.randint(0, 4)
            taxas = [dict(id=i + 1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                          vencimento=f'{i + 1:02d}/01/2023', valor_original=rng.choice([20, 30, 50, 100]))
                     for i in range(quantidade)]
            alvo, desconto = rng.randrange(quantidade), rng.choice([5, 10, 15])
            taxas.append(dict(id=99, condominio_id='a', tipo='D', apartamento='101', taxa_id=alvo + 1,
                              vencimento=f'{rng.randint(5, 18):02d}/01/2023', valor_original=desconto))
            receitas = [dict(id=i + 1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                             data=f'{rng.randint(1, 19):02d}/01/2023', valor=rng.choice([5, 10, 15, 20, 25, 30, 50, 75, 100]))
                        for i in range(qtd_receitas)]
            with self.subTest(caso=caso):
                posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')
                grupo = posicao['grupos'][0]
                devido = sum(t['valor_original'] for t in taxas[:-1]) - min(taxas[alvo]['valor_original'], desconto)
                esperado = max(0, devido - sum(r['valor'] for r in receitas)) * 100
                self.assertEqual(sum(s['principal_centavos'] for s in grupo['saldos']), esperado)
                self.assertEqual(extrato(posicao, {'tipo': 'completo'}, {})['total'], devido - sum(r['valor'] for r in receitas))
                consumos = Counter()
                for quitacao in grupo['quitacoes_exatas']:
                    for pagamento in quitacao['detalhes']['recebimentos']:
                        consumos[pagamento['recebimento_id']] += pagamento['valor_centavos']
                for pagamento in grupo['pagamentos_parciais']:
                    if not pagamento.get('quitacao_exata'):
                        consumos[pagamento['recebimento_id']] += pagamento['valor_centavos']
                self.assertEqual(dict(consumos), {r['id']: r['valor'] * 100 for r in receitas})

    def test_data_corte_segue_tipo_e_periodo(self):
        hoje = date(2024, 3, 15)
        self.assertEqual(data_corte_extrato({'tipo': 'completo', 'data_corte': '2022-05-12'}, hoje), hoje)
        self.assertEqual(data_corte_extrato({'tipo': 'competencia', 'periodo': ['2024-01', '2024-02'], 'data_corte': '2024-03-10'}), date(2024, 2, 29))
        self.assertEqual(data_corte_extrato({'tipo': 'recebimento', 'periodo': ['2023-01-01', '2023-01-31'], 'data_corte': '2023-02-10'}), date(2023, 1, 31))
        with self.assertRaises(ValueError):
            data_corte_extrato({'tipo': 'recebimento', 'periodo': ['2023-02-01', '2023-01-01']})

    def test_caso_118_quitacao_e_total_apresentado_sao_coerentes(self):
        taxa = dict(id=206, condominio_id='a', tipo='I', apartamento='803', competencia='2022-05',
                    vencimento='10/05/2022', valor_original=9.30, juros_mes_percentual=1, multa_percentual=2)
        receita = dict(id=20546, condominio_id='a', tipo='R', apartamento='803', competencia='2022-05',
                       data='12/05/2022', valor=9.49)
        posicao = calcular_posicao('a', date(2022, 5, 12), ['803'], [taxa], [receita], 'M')
        quitacao = posicao['grupos'][0]['quitacoes_exatas'][0]
        self.assertEqual((quitacao['taxas'], quitacao['recebimentos'], quitacao['encargos_centavos']), ([206], [20546], 19))
        relatorio = extrato(posicao, {'tipo': 'completo'}, {'inicio': '2022-05-01', 'fim': '2022-05-31'})
        self.assertEqual((relatorio['total'], relatorio['saldo_original']), (0, 0))
        self.assertEqual(inadimplencia(posicao), [])

    def test_extrato_alinha_encargos_e_diferenca_positivos_com_pagamento(self):
        taxa = dict(id=206, condominio_id='a', tipo='I', apartamento='803', competencia='2022-05',
                    vencimento='10/05/2022', descricao='Seguro', valor_original=9.30,
                    juros_mes_percentual=1, multa_percentual=2)
        receita = dict(id=20546, condominio_id='a', tipo='R', apartamento='803', competencia='2022-05',
                       data='12/05/2022', valor=9.50)
        posicao = calcular_posicao('a', date(2022, 5, 12), ['803'], [taxa], [receita], 'M', 10)
        grupo = extrato(posicao, {'tipo': 'completo'}, {})['apartamentos'][0]['competencias'][0]
        pares = grupo['pares']
        self.assertEqual([(p['taxa']['tipo'] if p['taxa'] else None,
                           p['movimento']['tipo'] if p['movimento'] else None) for p in pares],
                         [('Cobrança', 'Recebimento'), ('Acréscimo', None), ('Diferença', None)])
        self.assertEqual(pares[2]['taxa']['valor'], 0.01)
        self.assertTrue(pares[2]['taxa']['ajuste_automatico'])
        self.assertEqual(grupo['subtotal'], 0)

    def test_posicao_calcula_cada_unidade_e_competencia_sem_reaproveitar(self):
        taxas = [dict(id=1, condominio_id='a', tipo='C', competencia='2023-01', vencimento='10/01/2023', valor_original=100),
                 dict(id=2, condominio_id='a', tipo='C', competencia='2023-02', vencimento='10/02/2023', valor_original=100)]
        receitas = [dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='10/01/2023', valor=100),
                    dict(id=2, condominio_id='a', tipo='R', apartamento='102', competencia='2023-01', data='11/01/2023', valor=40)]
        resultado = calcular_posicao('a', date(2023, 2, 1), ['101', '102'], taxas, receitas, 'N')
        grupos = {(g['apartamento'], g['competencia']): g for g in resultado['grupos']}
        self.assertEqual(grupos['101', '2023-01']['quitacoes_exatas'][0]['recebimentos'], [1])
        self.assertEqual(grupos['102', '2023-01']['saldos'][0]['principal_centavos'], 6000)
        self.assertEqual(grupos['101', '2023-02']['saldos'][0]['principal_centavos'], 10000)
        self.assertEqual(grupos['102', '2023-02']['saldos'][0]['principal_centavos'], 10000)
        exibido = inadimplencia(resultado)
        self.assertEqual([(u['unidade'], [t['valor'] for t in u['taxas']]) for u in exibido], [('102', [60])])

    def test_pagamento_no_corte_respeita_competencia_em_mes_diferente(self):
        taxa = dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2022-05',
                    vencimento='10/06/2022', valor_original=100)
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2022-05',
                       data='02/07/2022', valor=100)
        antes = calcular_posicao('a', date(2022, 7, 1), ['101'], [taxa], [receita], 'N')
        no_corte = calcular_posicao('a', date(2022, 7, 2), ['101'], [taxa], [receita], 'N')
        self.assertEqual(inadimplencia(antes)[0]['taxas'][0]['valor'], 100)
        self.assertEqual(inadimplencia(no_corte), [])

    def test_recebimento_unico_quita_com_desconto_e_abate_outra_taxa(self):
        comum = dict(condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='20/01/2023')
        taxas = [dict(comum, id=1, valor_original=100, desconto_vista=10), dict(comum, id=2, valor_original=100)]
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='10/01/2023', valor=100)
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, [receita], 'N')
        grupo = posicao['grupos'][0]
        self.assertEqual((grupo['quitacoes_exatas'][0]['taxas'], grupo['quitacoes_exatas'][0]['prioridade']), ([1], 1))
        self.assertEqual(grupo['saldos'][0]['principal_centavos'], 9000)
        self.assertEqual(sum(p['valor_centavos'] for p in grupo['quitacoes_exatas'][0]['detalhes']['recebimentos']) +
                         sum(p['valor_centavos'] for p in grupo['pagamentos_parciais']), 10000)
        relatorio = extrato(posicao, {'tipo': 'completo'}, {})
        self.assertEqual((relatorio['total'], relatorio['saldo_original']), (90, 90))
        linhas = relatorio['apartamentos'][0]['competencias'][0]['lancamentos']
        self.assertEqual([l['valor'] for l in linhas if l['tipo'] == 'Recebimento'], [-100])

    def test_extrato_vincula_parcelas_do_mesmo_recebimento_as_taxas(self):
        comum = dict(condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='20/01/2023')
        taxas = [dict(comum, id=1, descricao='Ordinária', valor_original=100, desconto_vista=10),
                 dict(comum, id=2, descricao='Fundo', valor_original=50)]
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                       data='10/01/2023', descricao='Pagamento', valor=110)
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, [receita], 'N')
        grupo = extrato(posicao, {'tipo': 'completo'}, {})['apartamentos'][0]['competencias'][0]
        pares = grupo['pares']
        self.assertEqual([(p['taxa']['id'] if p['taxa'] else None,
                           p['movimento']['tipo'] if p['movimento'] else None,
                           p['movimento']['valor'] if p['movimento'] else None) for p in pares],
                         [(1, 'Recebimento', -90), (None, 'Desconto à vista', -10), (2, 'Recebimento', -20)])
        self.assertEqual(grupo['subtotal'], 30)
        filtrado = extrato(posicao, {'tipo': 'recebimento', 'periodo': ['2023-01-10', '2023-01-10']}, {})
        pares_filtrados = filtrado['apartamentos'][0]['competencias'][0]['pares']
        self.assertTrue(all(p['taxa'] is None for p in pares_filtrados))
        self.assertEqual(sum(p['movimento']['valor'] for p in pares_filtrados), -120)

    def test_extrato_ordena_taxas_e_movimentos_por_data_e_valor(self):
        comum = dict(condominio_id='a', tipo='I', apartamento='101', competencia='2023-01')
        taxas = [dict(comum, id=1, descricao='Menor', vencimento='20/01/2023', valor_original=100),
                 dict(comum, id=2, descricao='Maior', vencimento='20/01/2023', valor_original=200),
                 dict(comum, id=3, descricao='Anterior', vencimento='19/01/2023', valor_original=10)]
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                         data=data, descricao=f'Pagamento {i}', valor=valor)
                    for i, data, valor in [(1, '10/01/2023', 20), (2, '10/01/2023', 60), (3, '09/01/2023', 10)]]
        posicao = calcular_posicao('a', date(2023, 1, 20), ['101'], taxas, receitas, 'N')
        pares = extrato(posicao, {'tipo': 'completo'}, {})['apartamentos'][0]['competencias'][0]['pares']
        self.assertEqual([p['taxa']['id'] for p in pares if p['taxa']], [3, 2, 1])
        inicio = next(i for i, p in enumerate(pares) if p['taxa'] and p['taxa']['id'] == 2)
        fim = next(i for i, p in enumerate(pares) if p['taxa'] and p['taxa']['id'] == 1)
        self.assertEqual([p['movimento']['valor'] for p in pares[inicio:fim]], [-60, -20])

    def test_extrato_aglutina_movimentos_da_mesma_taxa_data_e_descricao(self):
        taxa = dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                    vencimento='20/01/2023', descricao='Ordinária', valor_original=200)
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                         data=data, descricao=descricao, valor=valor)
                    for i, data, descricao, valor in [(1, '10/01/2023', 'Pagamento', 60),
                                                     (2, '10/01/2023', 'Pagamento', 20),
                                                     (3, '11/01/2023', 'Pagamento', 10),
                                                     (4, '10/01/2023', 'Outro pagamento', 5)]]
        posicao = calcular_posicao('a', date(2023, 1, 20), ['101'], [taxa], receitas, 'N')
        grupo = extrato(posicao, {'tipo': 'completo'}, {})['apartamentos'][0]['competencias'][0]
        self.assertEqual([(p['movimento']['data'], p['movimento']['descricao'], p['movimento']['valor'])
                          for p in grupo['pares'] if p['movimento']],
                         [('2023-01-10', 'Pagamento', -80), ('2023-01-10', 'Outro pagamento', -5),
                          ('2023-01-11', 'Pagamento', -10)])
        self.assertEqual(len([l for l in grupo['lancamentos'] if l['tipo'] == 'Recebimento']), 4)
        self.assertEqual(grupo['subtotal'], 105)

    def test_recebimentos_agrupados_podem_consumir_apenas_parte_do_ultimo(self):
        comum = dict(condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='20/01/2023')
        taxas = [dict(comum, id=1, valor_original=100, desconto_vista=10), dict(comum, id=2, valor_original=100)]
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data=dia, valor=valor)
                    for i, dia, valor in [(1, '10/01/2023', 60), (2, '11/01/2023', 50)]]
        grupo = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')['grupos'][0]
        self.assertEqual((grupo['quitacoes_exatas'][0]['taxas'], grupo['quitacoes_exatas'][0]['prioridade']), ([1], 1))
        self.assertEqual(grupo['saldos'][0]['principal_centavos'], 8000)
        consumos = grupo['quitacoes_exatas'][0]['detalhes']['recebimentos'] + grupo['pagamentos_parciais']
        self.assertEqual(sum(p['valor_centavos'] for p in consumos), 11000)

    def test_recebimento_fracionado_com_ajuste_posterior_em_outra_taxa(self):
        comum = dict(condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='20/01/2023')
        taxas = [dict(comum, id=1, valor_original=100, desconto_vista=10), dict(comum, id=2, valor_original=100),
                 dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=2, vencimento='15/01/2023', valor_original=10)]
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='10/01/2023', valor=100)
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, [receita], 'N')
        grupo = posicao['grupos'][0]
        self.assertEqual((grupo['quitacoes_exatas'][0]['taxas'], grupo['quitacoes_exatas'][0]['prioridade']), ([1], 1))
        self.assertEqual(grupo['saldos'][0]['principal_centavos'], 8000)
        self.assertEqual(extrato(posicao, {'tipo': 'completo'}, {})['total'], 80)

    def test_nao_inventa_desconto_so_para_gerar_excedente(self):
        taxa = dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                    vencimento='20/01/2023', valor_original=100, desconto_vista=10)
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='10/01/2023', valor=100)
        grupo = calcular_posicao('a', date(2023, 1, 21), ['101'], [taxa], [receita], 'N')['grupos'][0]
        self.assertEqual((grupo['quitacoes_exatas'][0]['prioridade'], grupo['quitacoes_exatas'][0]['desconto_centavos']), (2, 0))
        self.assertEqual(grupo['pagamentos_parciais'], [])

    def test_nao_inventa_desconto_quando_sobra_de_fracionamento_nao_e_utilizada(self):
        comum = dict(condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='20/01/2023')
        taxas = [dict(comum, id=1, valor_original=100, desconto_vista=10), dict(comum, id=2, valor_original=100)]
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                         data='10/01/2023', valor=100) for i in (1, 2)]
        grupo = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')['grupos'][0]
        self.assertEqual(sum(q['desconto_centavos'] for q in grupo['quitacoes_exatas']), 0)
        self.assertEqual(grupo['saldos'], [])
        self.assertEqual(grupo['pagamentos_parciais'], [])

    def test_nao_inventa_desconto_no_historico_com_ajuste_posterior(self):
        comum = dict(condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='20/01/2023')
        taxas = [dict(comum, id=1, valor_original=100, desconto_vista=10), dict(comum, id=2, valor_original=100, multa_percentual=2),
                 dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=2, vencimento='15/01/2023', valor_original=0, multa_percentual=1)]
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                         data='10/01/2023', valor=100) for i in (1, 2)]
        grupo = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')['grupos'][0]
        self.assertEqual(sum(q['desconto_centavos'] for q in grupo['quitacoes_exatas']), 0)
        self.assertEqual(grupo['saldos'], [])

    def test_ajuste_posterior_a_pagamento_e_aplicado_na_data(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='10/01/2023', valor_original=100),
                 dict(id=2, condominio_id='a', tipo='D', apartamento='101', taxa_id=1, vencimento='15/01/2023', valor_original=20)]
        receitas = [dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='11/01/2023', valor=50)]
        posicao = calcular_posicao('a', date(2023, 1, 20), ['101'], taxas, receitas, 'N')
        self.assertEqual(posicao['grupos'][0]['saldos'][0]['principal_centavos'], 3000)

    def test_encargos_antes_de_desconto_tardio_nao_retroagem(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='01/01/2023', valor_original=100, juros_mes_percentual=1, multa_percentual=2),
                 dict(id=2, condominio_id='a', tipo='D', apartamento='101', taxa_id=1, vencimento='11/01/2023', valor_original=20)]
        saldo = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, [], 'N')['grupos'][0]['saldos'][0]
        self.assertEqual((saldo['principal_centavos'], saldo['juros_centavos'], saldo['multa_centavos']), (8000, 60, 200))

    def test_desconto_vista_e_pagamentos_divididos_entre_ajustes(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='20/01/2023', valor_original=100, desconto_vista=10),
                 dict(id=2, condominio_id='a', tipo='D', apartamento='101', taxa_id=1, vencimento='15/01/2023', valor_original=20)]
        receitas = [dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='10/01/2023', valor=50),
                    dict(id=2, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='16/01/2023', valor=20)]
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')
        quitacao = posicao['grupos'][0]['quitacoes_exatas'][0]
        self.assertEqual((quitacao['prioridade'], quitacao['desconto_centavos']), (1, 1000))
        relatorio = extrato(posicao, {'tipo': 'completo'}, {'inicio': '2023-01-01', 'fim': '2023-01-31'})
        self.assertIn(('Desconto à vista', -10), [(l['tipo'], l['valor']) for l in relatorio['apartamentos'][0]['competencias'][0]['lancamentos']])

        receitas[1]['data'] = '21/01/2023'
        saldo_tardio = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')['grupos'][0]['saldos'][0]
        self.assertEqual((saldo_tardio['principal_centavos'], saldo_tardio['desconto_concedido_centavos']), (1000, 0))

    def test_pagamento_anterior_ao_acordo_nao_quita_parcela_futura(self):
        taxas = [dict(id=1, condominio_id='a', tipo='P', apartamento='101', competencia='2023-01',
                      vencimento='25/01/2023', data_renegociacao='18/01/2023', valor_original=100)]
        receitas = [dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                         data='10/01/2023', valor=100)]
        posicao = calcular_posicao('a', date(2023, 1, 30), ['101'], taxas, receitas, 'N')
        grupo = posicao['grupos'][0]
        self.assertEqual(grupo['quitacoes_exatas'], [])
        self.assertEqual(grupo['saldos'][0]['principal_centavos'], 10000)
        self.assertEqual(grupo['pagamentos_parciais'][0]['nao_alocado_centavos'], 10000)

    def test_pagamentos_agrupados_quitam_taxas_com_ajuste_intermediario(self):
        taxas = [dict(id=i, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                      vencimento='20/01/2023', valor_original=100, desconto_vista=10) for i in (1, 2)]
        taxas.append(dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=1,
                          vencimento='15/01/2023', valor_original=20))
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data=dia, valor=valor)
                    for i, dia, valor in [(1, '10/01/2023', 50), (2, '16/01/2023', 110)]]
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')
        quitacao = posicao['grupos'][0]['quitacoes_exatas'][0]
        self.assertCountEqual(quitacao['taxas'], [1, 2])
        self.assertEqual((quitacao['prioridade'], quitacao['desconto_centavos']), (1, 2000))
        self.assertEqual(inadimplencia(posicao), [])

    def test_ajuste_posterior_a_quitacao_agrupada_preserva_credito(self):
        taxas = [dict(id=i, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                      vencimento='20/01/2023', valor_original=100, desconto_vista=10) for i in (1, 2)]
        taxas.append(dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=1,
                          vencimento='15/01/2023', valor_original=10))
        receitas = [dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='10/01/2023', valor=180)]
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')
        grupo = posicao['grupos'][0]
        self.assertEqual(grupo['quitacoes_exatas'][0]['desconto_centavos'], 2000)
        self.assertEqual(grupo['pagamentos_parciais'][0]['nao_alocado_centavos'], 1000)
        self.assertEqual(inadimplencia(posicao), [])
        relatorio = extrato(posicao, {'tipo': 'completo'}, {})
        linhas = relatorio['apartamentos'][0]['competencias'][0]['lancamentos']
        credito = next(l for l in linhas if l['tipo'] == 'Excedente de origem não identificada')
        self.assertEqual((credito['data'], credito['valor'], credito['informativo']), ('2023-01-15', -10, True))
        self.assertEqual(relatorio['total'], -10)

    def test_ajuste_posterior_a_grupo_quitado_preserva_recebimento_extra(self):
        taxas = [dict(id=i, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                      vencimento='20/01/2023', valor_original=100, desconto_vista=10) for i in (1, 2)]
        taxas.append(dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=1,
                          vencimento='15/01/2023', valor_original=10))
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data=dia, valor=valor)
                    for i, dia, valor in [(1, '10/01/2023', 180), (2, '11/01/2023', 5)]]
        grupo = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')['grupos'][0]
        self.assertEqual(grupo['quitacoes_exatas'][0]['recebimentos'], [1])
        self.assertEqual({p['recebimento_id']: p['nao_alocado_centavos'] for p in grupo['pagamentos_parciais']},
                         {1: 1000, 2: 500})

    def test_quitacao_parcial_do_grupo_com_ajuste_que_nao_gera_credito(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                      vencimento='20/01/2023', valor_original=100, desconto_vista=10, multa_percentual=2),
                 dict(id=2, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                      vencimento='20/01/2023', valor_original=200),
                 dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=1,
                      vencimento='15/01/2023', valor_original=0, multa_percentual=1)]
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='10/01/2023', valor=90)
        grupo = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, [receita], 'N')['grupos'][0]
        self.assertEqual(grupo['quitacoes_exatas'][0]['taxas'], [1])
        self.assertEqual([(s['taxa']['id'], s['principal_centavos']) for s in grupo['saldos']], [(2, 20000)])

    def test_ajuste_posterior_com_pagamento_insuficiente_para_desconto(self):
        taxas = [dict(id=i, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                      vencimento='20/01/2023', valor_original=100, desconto_vista=10) for i in (1, 2)]
        taxas.append(dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=1,
                          vencimento='15/01/2023', valor_original=10))
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='10/01/2023', valor=40)
        grupo = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, [receita], 'N')['grupos'][0]
        self.assertEqual([(s['taxa']['id'], s['principal_centavos']) for s in grupo['saldos']], [(1, 5000), (2, 10000)])

    def test_ajuste_posterior_preserva_prioridade_da_taxa_mais_antiga(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='10/01/2023', valor_original=100),
                 dict(id=2, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='11/01/2023', valor_original=100),
                 dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=1, vencimento='15/01/2023', valor_original=10)]
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='12/01/2023', valor=100)
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, [receita], 'N')
        resultado = inadimplencia(posicao)
        self.assertEqual([(t['id'], t['valor']) for u in resultado for t in u['taxas']], [(2, 90)])
        relatorio = extrato(posicao, {'tipo': 'completo'}, {})
        self.assertEqual((relatorio['total'], relatorio['saldo_original']), (90, 90))

    def test_quitacao_exata_reserva_recebimento_apesar_de_parcial_anterior(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='01/01/2023', valor_original=20),
                 dict(id=2, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='02/01/2023', valor_original=30),
                 dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=1, vencimento='13/01/2023', valor_original=10)]
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data=dia, valor=valor)
                    for i, dia, valor in [(1, '11/01/2023', 20), (2, '06/01/2023', 5)]]
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')
        self.assertEqual([(t['id'], t['valor']) for u in inadimplencia(posicao) for t in u['taxas']], [(2, 15)])

    def test_credito_posterior_favorece_quitar_mais_taxas(self):
        taxas = [dict(id=i, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento=v, valor_original=valor)
                 for i, v, valor in [(1, '01/01/2023', 50), (2, '02/01/2023', 100), (3, '03/01/2023', 20)]]
        taxas.append(dict(id=99, condominio_id='a', tipo='D', apartamento='101', taxa_id=1, vencimento='06/01/2023', valor_original=10))
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data=dia, valor=valor)
                    for i, dia, valor in [(1, '03/01/2023', 50), (2, '15/01/2023', 15)]]
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')
        self.assertEqual([(t['id'], t['valor']) for u in inadimplencia(posicao) for t in u['taxas']], [(2, 95)])

    def test_desempate_tecnico_historico_nao_depende_da_ordem_de_entrada(self):
        comum = dict(condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='10/01/2023', valor_original=100)
        taxas = [dict(comum, id=1), dict(comum, id=2),
                 dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=1, vencimento='15/01/2023', valor_original=10)]
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='12/01/2023', valor=100)
        for itens in (taxas, list(reversed(taxas))):
            posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], itens, [receita], 'N')
            self.assertEqual([(t['id'], t['valor']) for u in inadimplencia(posicao) for t in u['taxas']], [(2, 90)])

    def test_credito_de_ajuste_nao_e_transferido_entre_competencias(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='10/01/2023', valor_original=100),
                 dict(id=2, condominio_id='a', tipo='I', apartamento='101', competencia='2023-02', vencimento='10/02/2023', valor_original=100),
                 dict(id=3, condominio_id='a', tipo='D', apartamento='101', taxa_id=1, vencimento='15/01/2023', valor_original=10)]
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='12/01/2023', valor=100)
        posicao = calcular_posicao('a', date(2023, 2, 20), ['101'], taxas, [receita], 'N')
        grupos = {g['competencia']: g for g in posicao['grupos']}
        self.assertEqual(grupos['2023-02']['saldos'][0]['principal_centavos'], 10000)
        self.assertEqual(grupos['2023-01']['pagamentos_parciais'][0]['nao_alocado_centavos'], 1000)

    def test_busca_temporal_prefere_desconto_da_taxa_mais_antiga(self):
        taxas = [dict(id=1, apartamento='101', competencia='2023-01', tipo='I', vencimento=date(2023, 1, 19),
                      valor_original=100, valor_centavos=10000, desconto_vista=10),
                 dict(id=2, apartamento='101', competencia='2023-01', tipo='I', vencimento=date(2023, 1, 20),
                      valor_original=100, valor_centavos=10000, desconto_vista=10)]
        receitas = [dict(id=1, apartamento='101', competencia='2023-01', data=date(2023, 1, 10), valor_centavos=10000)]
        ajustes = [dict(id=3, apartamento='101', tipo='D', taxa_id=1, vencimento=date(2023, 1, 15), valor_original=10)]
        _, resultado = simular_descontos_temporais(taxas, receitas, ajustes, date(2023, 1, 21), 'N')
        saldos = {s['taxa']['id']: s for s in resultado['saldos']}
        self.assertEqual((saldos[1]['desconto_concedido_centavos'], saldos[1]['principal_centavos']), (1000, 0))
        self.assertEqual(saldos[2]['principal_centavos'], 8000)

        originais = [dict(t, condominio_id='a', vencimento=t['vencimento'].strftime('%d/%m/%Y')) for t in taxas]
        entrada = [dict(receitas[0], condominio_id='a', tipo='R', data='10/01/2023', valor=100)]
        ajustes_originais = [dict(ajustes[0], condominio_id='a', vencimento='15/01/2023')]
        grupo = calcular_posicao('a', date(2023, 1, 21), ['101'], originais + ajustes_originais, entrada, 'N')['grupos'][0]
        saldos = {s['taxa']['id']: s for s in grupo['saldos']}
        self.assertEqual((saldos[1]['desconto_concedido_centavos'], saldos[1]['principal_centavos']), (1000, 0))
        self.assertEqual(saldos[2]['principal_centavos'], 8000)

    def test_busca_temporal_nao_excede_limite_de_ordens(self):
        taxas = [dict(id=i, apartamento='101', competencia='2023-01', tipo='I', vencimento=date(2023, 1, 20),
                      valor_original=100, valor_centavos=10000, desconto_vista=10) for i in range(8)]
        receitas = [dict(id=1, apartamento='101', competencia='2023-01', data=date(2023, 1, 10), valor_centavos=10000)]
        with self.assertRaises(ConciliacaoInconclusiva):
            simular_descontos_temporais(taxas, receitas, [], date(2023, 1, 21), 'N')

    def test_acordos_encadeados_e_marcador_de_desconto_respeitam_cortes(self):
        comum = dict(condominio_id='a', apartamento='101')
        taxas = [
            dict(comum, id=1, tipo='I', competencia='2023-01', vencimento='10/01/2023', valor_original=100),
            dict(comum, id=2, tipo='D', taxa_id=1, vencimento='10/01/2023', valor_original=20),
            dict(comum, id=3, tipo='R', taxa_id=1, data_renegociacao='18/01/2023', valor_original=100),
            dict(comum, id=4, tipo='R', taxa_id=2, data_renegociacao='18/01/2023', valor_original=20),
            dict(comum, id=5, tipo='P', competencia='2023-02', vencimento='10/02/2023', data_renegociacao='18/01/2023', valor_original=80),
            dict(comum, id=6, tipo='R', taxa_id=5, data_renegociacao='15/02/2023', valor_original=80),
            dict(comum, id=7, tipo='P', competencia='2023-03', vencimento='10/03/2023', data_renegociacao='15/02/2023', valor_original=80),
        ]
        for corte, esperado in [(date(2023, 1, 17), [(1, 80)]), (date(2023, 1, 18), []),
                                (date(2023, 2, 14), [(5, 80)]), (date(2023, 2, 15), []),
                                (date(2023, 3, 11), [(7, 80)])]:
            posicao = calcular_posicao('a', corte, ['101'], taxas, [], 'N')
            resultado = inadimplencia(posicao)
            encontrados = [(t['id'], t['valor']) for u in resultado for t in u['taxas']]
            self.assertEqual(encontrados, esperado)

    def test_extrato_preserva_valor_negativo_e_posicao_apos_filtro_de_data(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='01/01/2023', valor_original=100)]
        receitas = [dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='05/01/2023', valor=40),
                    dict(id=2, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='06/01/2023', valor=-3),
                    dict(id=3, condominio_id='a', tipo='R', apartamento=None, competencia='2023-01', data='06/01/2023', valor=100)]
        posicao = calcular_posicao('a', date(2023, 1, 10), ['101'], taxas, receitas, 'N')
        resultado = extrato(posicao, {'tipo': 'recebimento', 'periodo': ['2023-01-06', '2023-01-10']},
                            {'inicio': '2023-01-01', 'fim': '2023-01-31'})
        grupo = resultado['apartamentos'][0]['competencias'][0]
        self.assertEqual(grupo['saldo_original'], 60)
        self.assertEqual([(l['tipo'], l['valor']) for l in grupo['lancamentos']], [('Valor negativo de origem a esclarecer', -3)])
        self.assertEqual(inadimplencia(posicao)[0]['taxas'][0]['valor'], grupo['saldo_original'])

    def test_filtro_de_movimento_nao_esconde_saldo_historico(self):
        taxas = [dict(id=i, condominio_id='a', tipo='I', apartamento='101', competencia=comp,
                      vencimento=vencimento, valor_original=100) for i, comp, vencimento in
                 [(1, '2022-12', '10/12/2022'), (2, '2023-01', '10/01/2023')]]
        receitas = [dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                         data='15/01/2023', valor=50)]
        posicao = calcular_posicao('a', date(2023, 1, 20), ['101'], taxas, receitas, 'N')
        resultado = extrato(posicao, {'tipo': 'recebimento', 'periodo': ['2023-01-15', '2023-01-15']}, {})
        unidade = resultado['apartamentos'][0]
        self.assertEqual([g['competencia'] for g in unidade['competencias']], ['2023-01'])
        self.assertEqual((unidade['competencias'][0]['saldo_original'], unidade['saldo_original'], resultado['saldo_original']), (50, 150, 150))
        self.assertEqual(resultado['total'], -50)

    def test_extrato_registra_encargos_nas_datas_dos_pagamentos(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='01/01/2023',
                      valor_original=100, juros_mes_percentual=1, multa_percentual=2)]
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data=dia, valor=valor)
                    for i, dia, valor in [(1, '11/01/2023', 101), (2, '21/01/2023', 1.33)]]
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')
        resultado = extrato(posicao, {'tipo': 'recebimento', 'periodo': ['2023-01-11', '2023-01-11']},
                            {'inicio': '2023-01-01', 'fim': '2023-01-31'})
        linhas = resultado['apartamentos'][0]['competencias'][0]['lancamentos']
        self.assertEqual([(l['tipo'], l['valor']) for l in linhas], [('Acréscimo', 1), ('Recebimento', -101)])

    def test_extrato_soma_encargos_da_mesma_taxa_apos_filtro_por_data(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                      vencimento='01/01/2023', descricao='Taxa', valor_original=100,
                      juros_mes_percentual=1, multa_percentual=2)]
        receitas = [dict(id=i, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data=dia, valor=valor)
                    for i, dia, valor in [(1, '11/01/2023', 101), (2, '21/01/2023', 1.33)]]
        posicao = calcular_posicao('a', date(2023, 1, 21), ['101'], taxas, receitas, 'N')
        completo = extrato(posicao, {'tipo': 'completo'}, {})
        encargos = [l for l in completo['apartamentos'][0]['competencias'][0]['lancamentos'] if l['tipo'] == 'Acréscimo']
        self.assertEqual([(l['descricao'], l['data'], l['valor']) for l in encargos],
                         [('Encargos calculados - Taxa', '2023-01-21', 2.33)])
        self.assertEqual(completo['total'], 0)
        filtrado = extrato(posicao, {'tipo': 'recebimento', 'periodo': ['2023-01-11', '2023-01-11']}, {})
        encargos_filtrados = [l for l in filtrado['apartamentos'][0]['competencias'][0]['lancamentos'] if l['tipo'] == 'Acréscimo']
        self.assertEqual([(l['data'], l['valor']) for l in encargos_filtrados], [('2023-01-11', 1)])

    def test_conciliacao_sinaliza_apenas_ajustes_automaticos_no_extrato(self):
        taxa = dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                    vencimento='01/01/2023', descricao='Taxa', valor_original=100, multa_percentual=2)
        for valor in (101.95, 102.05):
            receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                           data='02/01/2023', valor=valor)
            posicao = calcular_posicao('a', date(2023, 1, 10), ['101'], [taxa], [receita], 'N')
            self.assertTrue(posicao['grupos'][0]['quitacoes_exatas'][0]['ajuste_automatico'])
            resultado = extrato(posicao, {'tipo': 'completo'}, {})
            linhas = resultado['apartamentos'][0]['competencias'][0]['lancamentos']
            self.assertTrue(next(l for l in linhas if l['tipo'] == 'Diferença')['ajuste_automatico'])
            self.assertFalse(next(l for l in linhas if l['tipo'] == 'Acréscimo')['ajuste_automatico'])
            self.assertFalse(next(l for l in linhas if l['tipo'] == 'Cobrança')['ajuste_automatico'])

    def test_extrato_identifica_taxa_dos_encargos_em_pagamento_agrupado(self):
        taxas = [dict(id=i, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                      vencimento='01/01/2023', descricao=descricao, valor_original=valor,
                      juros_mes_percentual=0, multa_percentual=2)
                 for i, descricao, valor in [(1, 'Ordinária', 100), (2, 'Fundo', 50)]]
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                       data='02/01/2023', valor=153)
        posicao = calcular_posicao('a', date(2023, 1, 10), ['101'], taxas, [receita], 'N')
        resultado = extrato(posicao, {'tipo': 'completo'}, {})
        linhas = resultado['apartamentos'][0]['competencias'][0]['lancamentos']
        self.assertCountEqual([(l['descricao'], l['valor']) for l in linhas if l['tipo'] == 'Acréscimo'],
                              [('Encargos calculados - Ordinária', 2), ('Encargos calculados - Fundo', 1)])
        self.assertEqual(resultado['total'], 0)

    def test_extrato_exibe_credito_de_ajuste_sem_contar_recebimento_duas_vezes(self):
        taxas = [dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01', vencimento='01/01/2023', valor_original=100),
                 dict(id=2, condominio_id='a', tipo='D', apartamento='101', taxa_id=1, vencimento='15/01/2023', valor_original=20)]
        receitas = [dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01', data='10/01/2023', valor=100)]
        posicao = calcular_posicao('a', date(2023, 1, 20), ['101'], taxas, receitas, 'N')
        relatorio = extrato(posicao, {'tipo': 'completo'}, {'inicio': '2023-01-01', 'fim': '2023-01-31'})
        grupo = relatorio['apartamentos'][0]['competencias'][0]
        recebimento = next(l for l in grupo['lancamentos'] if l['tipo'] == 'Recebimento')
        credito = next(l for l in grupo['lancamentos'] if l['tipo'] == 'Excedente de origem não identificada')
        self.assertEqual((recebimento['data'], recebimento['valor']), ('2023-01-10', -100))
        self.assertEqual((credito['data'], credito['valor'], credito['informativo']), ('2023-01-15', -20, True))
        self.assertEqual((grupo['subtotal'], grupo['saldo_original']), (-20, 0))

    def test_excedente_nao_e_convertido_em_encargo_nem_somado_duas_vezes(self):
        taxa = dict(id=1, condominio_id='a', tipo='I', apartamento='101', competencia='2023-01',
                    vencimento='01/01/2023', valor_original=100)
        receita = dict(id=1, condominio_id='a', tipo='R', apartamento='101', competencia='2023-01',
                       data='10/01/2023', valor=105)
        posicao = calcular_posicao('a', date(2023, 1, 20), ['101'], [taxa], [receita], 'N')
        resultado = extrato(posicao, {'tipo': 'completo'}, {})
        linhas = resultado['apartamentos'][0]['competencias'][0]['lancamentos']
        self.assertEqual(next(l['valor'] for l in linhas if l['tipo'] == 'Recebimento'), -105)
        excedente = next(l for l in linhas if l['tipo'] == 'Excedente de origem não identificada')
        self.assertEqual((excedente['valor'], excedente['informativo'], excedente['ajuste_automatico']), (-5, True, True))
        self.assertFalse(any(l['tipo'] == 'Acréscimo' for l in linhas))
        self.assertEqual((resultado['total'], resultado['saldo_original']), (-5, 0))


class TestValidacoes(unittest.TestCase):
    def test_data_e_centavos_rejeitam_entradas_invalidas(self):
        from bff.conciliacao_unificada import _data, _centavos
        from datetime import datetime
        self.assertEqual(_data(datetime(2023, 1, 2, 3, 4)), date(2023, 1, 2))
        with self.assertRaises(ValueError):
            _data('31/02/2023')
        with self.assertRaisesRegex(ValueError, 'não finito'):
            _centavos('nan')
        with self.assertRaisesRegex(ValueError, 'não finito'):
            _centavos(float('inf'))

    def test_encargos_rejeitam_percentual_nao_finito_ou_negativo(self):
        with self.assertRaisesRegex(ValueError, 'Percentual de encargos'):
            calcular_encargos(10000, 'nan', 1, 10, 'N')
        with self.assertRaisesRegex(ValueError, 'Percentual de encargos'):
            calcular_encargos(10000, 1, -5, 10, 'N')
        with self.assertRaisesRegex(ValueError, 'Parâmetros de encargos'):
            calcular_encargos(-1, 1, 1, 10, 'N')

    def test_normalizar_rejeita_registros_incompletos_e_filtra(self):
        base = {'condominio_id': 'a', 'tipo': 'I', 'apartamento': '101', 'competencia': '2023-01',
                'vencimento': '10/01/2023', 'valor_original': 100}
        with self.assertRaisesRegex(ValueError, 'sem data de renegociação'):
            normalizar('a', date(2023, 1, 20), ['101'],
                       [dict(base, id=1, tipo='P')], [])
        with self.assertRaisesRegex(ValueError, 'sem competência ou vencimento'):
            normalizar('a', date(2023, 1, 20), ['101'],
                       [dict(base, id=1, competencia=None)], [])
        dados = normalizar('a', date(2023, 1, 20), ['101', '102'],
                           [dict(base, id=1, tipo='X')],
                           [dict(id=1, condominio_id='a', tipo='R', apartamento='999', competencia='2023-01',
                                 data='10/01/2023', valor=10)],
                           apartamentos_filtro=['101'])
        self.assertEqual(dados['taxas'], [])
        self.assertEqual(dados['recebimentos'], [])

    def test_conciliar_exatos_rejeita_grupo_acima_do_limite(self):
        taxas = [dict(id=i, apartamento='101', competencia='2023-01', vencimento=date(2023, 1, 10),
                      valor_centavos=100) for i in range(19)]
        with self.assertRaises(ConciliacaoInconclusiva):
            conciliar_exatos(taxas, [], 'N')


class TestApresentacaoErros(unittest.TestCase):
    def test_data_corte_e_extrato_validam_tipo_periodo_e_filtros(self):
        with self.assertRaisesRegex(ValueError, 'tipo de extrato'):
            data_corte_extrato({'tipo': 'invalido'})
        with self.assertRaisesRegex(ValueError, 'início e o fim'):
            data_corte_extrato({'tipo': 'recebimento', 'periodo': ['2023-01-01']})
        with self.assertRaisesRegex(ValueError, 'Competência inválida'):
            data_corte_extrato({'tipo': 'competencia', 'periodo': ['2023-13', '2023-01']})
        posicao = {'data_corte': date(2023, 2, 1), 'grupos': []}
        with self.assertRaisesRegex(ValueError, 'tipo de extrato'):
            extrato(posicao, {'tipo': 'invalido'}, {})
        with self.assertRaisesRegex(ValueError, 'Filtro de apartamentos'):
            extrato(posicao, {'tipo': 'completo', 'apartamentos': '101'}, {})
        with self.assertRaisesRegex(ValueError, 'início e o fim'):
            extrato(posicao, {'tipo': 'recebimento', 'periodo': []}, {})
        with self.assertRaisesRegex(ValueError, 'Competência inválida'):
            extrato(posicao, {'tipo': 'competencia', 'periodo': ['2023-13', '2023-01']}, {})
        with self.assertRaisesRegex(ValueError, 'anterior ou igual'):
            extrato(posicao, {'tipo': 'recebimento', 'periodo': ['2023-02-01', '2023-01-01']}, {})

    def _posicao_minima(self):
        taxa = {'id': 1, 'tipo': 'I', 'vencimento': date(2023, 1, 10), 'descricao': 'Taxa',
                'valor_original': 100, 'origem': {'valor_original': 100}}
        grupo = {
            'apartamento': '101', 'competencia': '2023-01',
            'saldos': [{'taxa': {'id': 1, 'competencia': '2023-01', 'vencimento': date(2023, 1, 10), 'descricao': 'Taxa'},
                        'principal_centavos': 10000, 'juros_centavos': 0, 'multa_centavos': 0,
                        'total_centavos': 10000, 'desconto_concedido_centavos': 500,
                        'desconto_data': date(2023, 1, 5)}],
            'taxas_origem': [taxa],
            'ajustes_origem': [{'id': 8, 'tipo': 'D', 'taxa_id': 999, 'valor_original': 5, 'descricao': 'Desc sem vínculo'},
                               {'id': 9, 'tipo': 'R', 'taxa_id': 1}],
            'recebimentos_origem': [], 'pagamentos_parciais': [], 'quitacoes_exatas': [],
        }
        return {'data_corte': date(2023, 2, 1), 'grupos': [grupo]}

    def test_extrato_filtra_apartamento_e_competencia_fora_do_periodo(self):
        posicao = self._posicao_minima()
        filtrado = extrato(posicao, {'tipo': 'completo', 'apartamentos': ['999']}, {})
        self.assertEqual([a['apartamento'] for a in filtrado['apartamentos']], ['999'])
        self.assertEqual(filtrado['apartamentos'][0]['competencias'], [])
        fora = extrato(posicao, {'tipo': 'competencia', 'periodo': ['2023-02', '2023-02']}, {})
        self.assertEqual(fora['apartamentos'], [])
        dentro = extrato(posicao, {'tipo': 'competencia', 'periodo': ['2023-01', '2023-01']}, {})
        lancamentos = dentro['apartamentos'][0]['competencias'][0]['lancamentos']
        self.assertIn('Desconto à vista', [l['tipo'] for l in lancamentos])


if __name__ == '__main__':
    unittest.main()
