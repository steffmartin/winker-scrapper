import unittest
import sqlite3
import os
import sys
from unittest.mock import patch
from datetime import date

# Add the project root to sys.path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.run_dashboard import Api

class TestRunDashboard(unittest.TestCase):

    def test_posicao_unificada_pode_ser_calculada_em_conexao_somente_leitura(self):
        import models
        from apresentacao_conciliacao import inadimplencia
        models.db.execute_sql('PRAGMA query_only = ON')
        posicao = self.api._calcular_posicao_unificada('2023-01-20')
        resultado = inadimplencia(posicao)
        self.assertEqual([(u['unidade'], u['taxas'][0]['valor']) for u in resultado], [('101', 300)])

    def test_configuracao_da_margem_e_usada_sem_consultas_por_grupo(self):
        import models
        self.assertEqual(self.api.get_condominio_config()['data']['condominio']['margem_diferenca_encargos'], 0.10)
        payload = {'condominio': {'margem_diferenca_encargos': 0.25}, 'membros': [], 'contas': []}
        self.assertEqual(self.api.update_condominio_config(payload)['status'], 'success')
        self.assertEqual(self.api.get_condominio_config()['data']['condominio']['margem_diferenca_encargos'], 0.25)
        with patch('conciliacao_unificada.calcular_posicao', return_value={}) as calcular:
            self.api._calcular_posicao_unificada('2023-01-20')
        self.assertEqual(calcular.call_args.kwargs['margem_encargos_centavos'], 25)
        for invalido in (-0.01, None, 'abc', 0.001, True):
            with self.subTest(invalido=invalido):
                resposta = self.api.update_condominio_config({'condominio': {'margem_diferenca_encargos': invalido}})
                self.assertEqual(resposta['status'], 'error')
                self.assertEqual(models.Condominio.get_by_id(self.condo_id).margem_diferenca_encargos, 0.25)
        self.assertEqual(self.api.update_condominio_config({'condominio': {'margem_diferenca_encargos': 0}})['status'], 'success')
        with patch('conciliacao_unificada.calcular_posicao', return_value={}) as calcular:
            self.api._calcular_posicao_unificada('2023-01-20')
        self.assertEqual(calcular.call_args.kwargs['margem_encargos_centavos'], 0)

    @patch('apresentacao_conciliacao.date', wraps=date)
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

    @patch('apresentacao_conciliacao.date', wraps=date)
    def test_receitas_incompletas_entram_apos_revisao_e_negativas_nao_abatem(self, data_simulada):
        data_simulada.today.return_value = date(2023, 1, 20)
        import models
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
        from conciliacao_unificada import ConciliacaoInconclusiva
        with patch('conciliacao_unificada.conciliar_exatos', side_effect=ConciliacaoInconclusiva('Limite de teste')):
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
        import models
        from conciliacao_unificada import ConciliacaoInconclusiva
        taxa = models.Taxas.get(models.Taxas.descricao == 'Taxa Condomínio')
        self.assertEqual(self.api.insert_taxa({'tipo': 'D', 'taxa_id': taxa.id, 'apartamento': '101',
            'competencia': '2023-01', 'vencimento': '15/01/2023', 'descricao': 'Desconto manual',
            'valor_original': 70})['status'], 'success')
        models.Transacoes.create(subcategoria_id=1, tipo='R', apartamento='101', competencia='2023-01',
                                  data='14/01/2023', descricao='Pagamento', valor=40)
        with patch('conciliacao_unificada.conciliar_historicos', side_effect=ConciliacaoInconclusiva('Limite')):
            tela = self.api.get_inadimplencia('2023-01-20', ['101'])
            relatorio = self.api.get_relatorio_inadimplencia({'data_corte': '2023-01-20', 'apartamentos': ['101']})
        self.assertEqual(tela['status'], 'success')
        self.assertEqual(tela['data'][0]['taxas'][0]['valor'], 230)
        self.assertEqual(relatorio['data']['total'], 230)
        self.assertGreater(tela['data'][0]['taxas'][0]['juros_total'], 0)

    def test_desconto_tem_vencimento_proprio_e_respeita_data_de_corte(self):
        import models
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
        import models
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
        import models
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
        import models
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
        import models
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
            self.api = Api(db_path=self.temp_db_path)
            self.api.condo_id = self.condo_id
        finally:
            os.path.exists = self.original_exists
            
        self.api.init_error = None

    def tearDown(self):
        self.conn.close()
        import models
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
                with patch.dict(Api.get_inadimplencia.__globals__, datetime=DataFixa):
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

if __name__ == '__main__':
    unittest.main()
