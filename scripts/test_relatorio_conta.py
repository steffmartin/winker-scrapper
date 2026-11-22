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
        self.assertEqual((a['saldo_anterior'], a['subtotal'], a['saldo_final']), (120, 15, 135))
        self.assertEqual((b['saldo_anterior'], b['subtotal'], b['saldo_final']), (50, 0, 50))
        dias = a['meses'][0]['dias']
        self.assertEqual([t['valor'] for t in dias[0]['transacoes']], [30, -10])
        self.assertEqual((dias[0]['subtotal'], dias[0]['saldo_final'], a['meses'][0]['subtotal']), (20, 140, 15))
        self.assertFalse(a['provisorio'])

    def test_erro_de_filtros_e_dados_inconsistentes(self):
        for filtros in ({'periodo': None}, {'periodo': ['2024-02-01', '2024-01-01']}, {'periodo': ['2024-01-01', '2024-01-31'], 'contas': ['Inválida']}):
            with self.assertRaises(ValueError): gerar('a', filtros)
        models.Transacoes.create(subcategoria_id=self.sub, conta='Conta A', data='01/01/2024', tipo='R', valor=1, consistente=0, revisado_usuario=0)
        dados = gerar('a', {'periodo': ['2024-01-01', '2024-01-31'], 'contas': ['Conta A']})
        self.assertTrue(dados['contas'][0]['provisorio'])
