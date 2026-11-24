import unittest
import sqlite3
import os
import sys
import itertools
from unittest.mock import patch

# Add the project root to sys.path if needed
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from scripts.run_dashboard import Api

class TestRunDashboard(unittest.TestCase):

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
        self.assertNotIn(taxa.id, [t['id'] for t in unidade['taxas']])
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
                unidade = next(item for item in resultado['data'] if item['unidade'] == '101')
                taxa = unidade['taxas'][0]
                self.assertEqual(taxa['dias_vencidos'], 0)
                self.assertEqual(taxa['multa'], 0)
                self.assertEqual(taxa['juros_total'], 0)

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

    def test_inadimplencia_regressao_com_descontos_estornos_e_corte(self):
        # Dados sintéticos: a mesma transação não pode quitar duas taxas.
        self.cursor.execute("UPDATE condominio SET apartamentos = ? WHERE id = ?",
                            ('["101", "102", "103"]', self.condo_id))
        taxa_id = self.cursor.execute("SELECT id FROM taxas WHERE descricao = 'Taxa Condomínio'").fetchone()[0]
        self.cursor.execute("INSERT INTO taxas (condominio_id, taxa_id, apartamento, tipo, valor_original, desconto_vista, multa_percentual, juros_mes_percentual) VALUES (?, ?, '101', 'D', 20, 2, 0.5, 0.2)",
                            (self.condo_id, taxa_id))
        self.cursor.execute("INSERT INTO taxas (condominio_id, competencia, exibicao, vencimento, descricao, valor_original, desconto_vista, multa_percentual, juros_mes_percentual, tipo) VALUES (?, '2023-01', 'JAN/2023', '15/01/2023', 'Taxa adicional', 100, 0, 2, 1, 'C')", (self.condo_id,))
        self.cursor.execute("INSERT INTO renegociacao (id, condominio_id, apartamento, data_renegociacao, quantidade_parcelas, despesas_adicionais, descontos_adicionais) VALUES (1, ?, '103', '18/01/2023', 1, 0, 0)", (self.condo_id,))
        self.cursor.execute("INSERT INTO taxas (condominio_id, renegociacao_id, competencia, exibicao, vencimento, descricao, valor_original, desconto_vista, multa_percentual, juros_mes_percentual, apartamento, tipo) VALUES (?, 1, '2023-01', 'JAN/2023', '10/01/2023', 'Parcela renegociada', 50, 0, 2, 1, '103', 'P')", (self.condo_id,))
        for transacao in [
            (3, '101', 25, '14/01/2023'), (4, '101', 75, '14/01/2023'),
            (5, '103', 150, '14/01/2023'), (6, '103', 160, '14/01/2023'),
            (7, '103', -20, '14/01/2023'), (8, '103', 50, '19/01/2023'),
        ]:
            self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, apartamento, competencia, valor, data, anexos, consistente, revisado_usuario) VALUES (?, 1, 'R', ?, '2023-01', ?, ?, 0, 1, 0)", transacao)
        self.conn.commit()

        def busca_anterior(transacoes, vencimento, valor, desconto):
            for tamanho in range(2, len(transacoes) + 1):
                for indices in itertools.combinations(range(len(transacoes)), tamanho):
                    soma = sum(transacoes[i][0] for i in indices)
                    datas = [transacoes[i][1] for i in indices if transacoes[i][1] is not None]
                    if abs(soma - valor) < 0.01 or (datas and max(datas) <= vencimento and abs(soma - (valor - (desconto or 0))) < 0.01):
                        return indices
            return None

        # A conexão da aplicação é estritamente de leitura durante os cálculos.
        import models
        models.db.execute_sql('PRAGMA query_only = ON')
        for corte in ('2023-01-16', '2023-01-18', '2023-01-20'):
            with self.subTest(corte=corte):
                resultado = self.api.get_inadimplencia(data_corte=corte)
                with patch.dict(Api.get_inadimplencia.__globals__, encontrar_combinacao=busca_anterior):
                    anterior = self.api.get_inadimplencia(data_corte=corte)
                self.assertEqual(resultado, anterior)
                self.assertEqual(resultado['status'], 'success')

        resultado = self.api.get_inadimplencia(data_corte='2023-01-20')
        unidade_101 = next(item for item in resultado['data'] if item['unidade'] == '101')
        self.assertEqual([taxa['descricao'] for taxa in unidade_101['taxas']], ['Taxa Condomínio'])
        self.assertEqual(unidade_101['taxas'][0]['valor'], 280)

    def test_limite_de_conciliacao_retorna_erro_sem_resultado_parcial(self):
        from conciliacao import LimiteConciliacao

        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, apartamento, competencia, valor, data, anexos, consistente, revisado_usuario) VALUES (3, 1, 'R', '101', '2023-01', 20, '14/01/2023', 0, 1, 0)")
        self.cursor.execute("INSERT INTO transacoes (id, subcategoria_id, tipo, apartamento, competencia, valor, data, anexos, consistente, revisado_usuario) VALUES (4, 1, 'R', '101', '2023-01', 30, '14/01/2023', 0, 1, 0)")
        self.conn.commit()
        def excede_limite(*args, **kwargs):
            raise LimiteConciliacao('Limite de teste')
        with patch.dict(Api.get_inadimplencia.__globals__, encontrar_combinacao=excede_limite):
            resultado = self.api.get_inadimplencia(data_corte='2023-01-20')
        self.assertEqual(resultado['status'], 'error')
        self.assertIn('Conciliação pendente', resultado['message'])
        self.assertNotIn('data', resultado)

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
