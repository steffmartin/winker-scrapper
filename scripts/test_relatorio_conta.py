import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent))
with patch('setup_deps.install_dependencies'):
    import models
    from relatorio_conta import gerar
from peewee import SqliteDatabase


class TestRelatorioConta(unittest.TestCase):
    def setUp(self):
        self.db = SqliteDatabase(':memory:')
        self.tabelas = [models.Condominio, models.Contas, models.Meses, models.Categorias, models.Subcategorias, models.Transacoes]
        self.ctx = self.db.bind_ctx(self.tabelas); self.ctx.__enter__(); self.db.create_tables(self.tabelas)
        models.Condominio.create(id='a'); models.Condominio.create(id='b')
        models.Contas.create(condominio_id='a', conta='Conta A', saldo_inicial=100)
        models.Contas.create(condominio_id='a', conta='Conta B', saldo_inicial=50)
        models.Contas.create(condominio_id='b', conta='Conta A', saldo_inicial=999)
        mes = models.Meses.create(condominio_id='a', competencia='2024-01')
        cat = models.Categorias.create(mes_id=mes)
        self.sub = models.Subcategorias.create(categoria_id=cat)

    def tearDown(self):
        self.db.close(); self.ctx.__exit__(None, None, None)

    def test_saldos_subtotais_limites_e_ordenacao(self):
        for data, tipo, valor in [('31/12/2023','R',20), ('01/01/2024','D',10), ('01/01/2024','R',30), ('31/01/2024','D',5), ('01/02/2024','R',200)]:
            models.Transacoes.create(subcategoria_id=self.sub, conta='Conta A', data=data, tipo=tipo, valor=valor)
        dados = gerar('a', {'periodo': ['2024-01-01', '2024-01-31'], 'contas': ['Conta B', 'Conta A']})
        self.assertEqual([c['conta'] for c in dados['contas']], ['Conta A', 'Conta B'])
        a, b = dados['contas']
        self.assertEqual((a['saldo_anterior'], a['subtotal'], a['saldo_final']), (100, 15, 115))
        self.assertEqual((b['saldo_anterior'], b['subtotal'], b['saldo_final']), (50, 0, 50))
        self.assertEqual(dados['saldo_global'], 165)
        dias = a['meses'][0]['dias']
        self.assertEqual([t['valor'] for t in dias[0]['transacoes']], [30, -10])
        self.assertEqual((dias[0]['subtotal'], dias[0]['saldo_final'], a['meses'][0]['subtotal']), (20, 120, 15))
        self.assertFalse(a['provisorio'])
        apenas_a = gerar('a', {'periodo': ['2024-01-01', '2024-01-31'], 'contas': ['Conta A']})
        self.assertEqual(apenas_a['saldo_global'], 115)
        fevereiro = gerar('a', {'periodo': ['2024-02-01', '2024-02-29'], 'contas': ['Conta A']})
        self.assertEqual(fevereiro['contas'][0]['saldo_anterior'], 115)
        self.assertEqual(fevereiro['saldo_global'], 315)

    def test_transacoes_sem_conta_apenas_no_filtro_todas(self):
        for conta, data, tipo, valor in [(None, '05/01/2024', 'R', 25), (' ', '06/01/2024', 'D', 5), (None, '05/02/2024', 'R', 7)]:
            models.Transacoes.create(subcategoria_id=self.sub, conta=conta, data=data, tipo=tipo, valor=valor)
        dados = gerar('a', {'periodo': ['2024-02-01', '2024-02-29'], 'contas': []})
        sem_conta = dados['contas'][-1]
        self.assertEqual(sem_conta['conta'], 'CONTA NÃO IDENTIFICADA')
        self.assertEqual((sem_conta['saldo_anterior'], sem_conta['subtotal'], sem_conta['saldo_final']), (20, 7, 27))
        self.assertEqual(dados['saldo_global'], 177)
        filtrado = gerar('a', {'periodo': ['2024-02-01', '2024-02-29'], 'contas': ['Conta A']})
        self.assertEqual([conta['conta'] for conta in filtrado['contas']], ['Conta A'])
        self.assertEqual(filtrado['saldo_global'], 100)

    def test_periodo_antes_do_primeiro_mes_nao_tem_saldo_confiavel(self):
        with self.assertRaisesRegex(ValueError, 'primeiro mês cadastrado'):
            gerar('a', {'periodo': ['2023-12-01', '2024-01-31']})

    def test_data_invalida_no_periodo_e_condominio_sem_meses(self):
        with self.assertRaisesRegex(ValueError, 'Data de transação inválida'):
            gerar('a', {'periodo': ['data-invalida', '2024-01-31']})
        with self.assertRaisesRegex(ValueError, 'meses cadastrados'):
            gerar('b', {'periodo': ['2024-01-01', '2024-01-31']})

    def test_filtro_contas_invalido_saldo_ausente_e_nome_duplicado(self):
        with self.assertRaisesRegex(ValueError, 'Filtro de contas inválido'):
            gerar('a', {'periodo': ['2024-01-01', '2024-01-31'], 'contas': 'Conta A'})
        models.Contas.create(condominio_id='a', conta='Conta C', saldo_inicial=None)
        with self.assertRaisesRegex(ValueError, 'Saldo inicial não informado'):
            gerar('a', {'periodo': ['2024-01-01', '2024-01-31'], 'contas': ['Conta C']})
        models.Contas.create(condominio_id='a', conta='Conta A', saldo_inicial=10)
        with self.assertRaisesRegex(ValueError, 'nomes duplicados'):
            gerar('a', {'periodo': ['2024-01-01', '2024-01-31'], 'contas': ['Conta A']})

    def test_transacao_com_tipo_ou_valor_invalido(self):
        models.Transacoes.create(subcategoria_id=self.sub, conta='Conta A', data='01/01/2024', tipo='X', valor=10)
        with self.assertRaisesRegex(ValueError, 'tipo ou valor inválido'):
            gerar('a', {'periodo': ['2024-01-01', '2024-01-31'], 'contas': ['Conta A']})

    def test_preserva_sinal_dos_valores_inclusive_estornos(self):
        for data, tipo, valor in [
            ('01/01/2024', 'R', 50), ('02/01/2024', 'R', -10),
            ('03/01/2024', 'D', 30), ('04/01/2024', 'D', -5),
        ]:
            models.Transacoes.create(subcategoria_id=self.sub, conta='Conta A', data=data, tipo=tipo, valor=valor)
        resultado = gerar('a', {'periodo': ['2024-01-01', '2024-01-31'], 'contas': ['Conta A']})
        conta = resultado['contas'][0]
        valores = [t['valor'] for dia in conta['meses'][0]['dias'] for t in dia['transacoes']]
        self.assertEqual(valores, [50, -10, -30, 5])
        self.assertEqual(conta['saldo_final'], 115)
        self.assertEqual(resultado['saldo_global'], 115)

    def test_erro_de_filtros_e_dados_inconsistentes(self):
        for filtros in ({'periodo': None}, {'periodo': ['2024-02-01', '2024-01-01']}, {'periodo': ['2024-01-01', '2024-01-31'], 'contas': ['Inválida']}):
            with self.assertRaises(ValueError): gerar('a', filtros)
        models.Transacoes.create(subcategoria_id=self.sub, conta='Conta A', data='01/01/2024', tipo='R', valor=1, consistente=0, revisado_usuario=0)
        dados = gerar('a', {'periodo': ['2024-01-01', '2024-01-31'], 'contas': ['Conta A']})
        self.assertTrue(dados['contas'][0]['provisorio'])
