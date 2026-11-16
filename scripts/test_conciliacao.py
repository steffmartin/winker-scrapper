import itertools
import random
import unittest
from datetime import date

from conciliacao import LimiteConciliacao, encontrar_combinacao


VENCIMENTO = date(2023, 4, 15)
ANTES = date(2023, 4, 14)
DEPOIS = date(2023, 4, 16)


def referencia(transacoes, valor, desconto):
    """Regra anterior: menor quantidade e primeira combinação na ordem original."""
    for tamanho in range(2, len(transacoes) + 1):
        for combinacao in itertools.combinations(range(len(transacoes)), tamanho):
            soma = sum(transacoes[i][0] for i in combinacao)
            datas = [transacoes[i][1] for i in combinacao if transacoes[i][1] is not None]
            desconto_valido = datas and max(datas) <= VENCIMENTO
            if abs(soma - valor) < 0.01 or (
                desconto_valido and abs(soma - (valor - desconto)) < 0.01
            ):
                return combinacao
    return None


class TestConciliacao(unittest.TestCase):
    def assert_equivalente(self, transacoes, valor, desconto=0):
        self.assertEqual(
            encontrar_combinacao(transacoes, VENCIMENTO, valor, desconto),
            referencia(transacoes, valor, desconto),
        )

    def test_ordem_quantidade_e_primeira_combinacao(self):
        for transacoes, valor in [
            ([(30.0, ANTES), (20.0, ANTES), (10.0, ANTES), (40.0, ANTES)], 50.0),
            ([(3.0, ANTES)] * 5, 12.0),
            ([(1.0, ANTES), (2.0, ANTES), (3.0, ANTES)], 5.0),
        ]:
            with self.subTest(transacoes=transacoes):
                self.assert_equivalente(transacoes, valor)

    def test_desconto_e_datas(self):
        for datas in [(ANTES, ANTES), (ANTES, DEPOIS), (None, ANTES), (None, None)]:
            with self.subTest(datas=datas):
                self.assert_equivalente([(45.0, datas[0]), (45.0, datas[1])], 100.0, 10.0)

    def test_estornos_valores_repetidos_e_sem_solucao(self):
        for valores, alvo in [
            ([120.0, -30.0, 10.0], 100.0),
            ([100.0, -40.0, -30.0, 20.0], 50.0),
            ([9.3, 9.3, 27.27, 27.27, 6.6], 32.42),
            ([3.0, -4.0, 8.0], 123.0),
            ([0.0, 0.0, 0.0, 0.0], 1.0),
        ]:
            with self.subTest(valores=valores):
                self.assert_equivalente([(v, ANTES) for v in valores], alvo)

    def test_limite_de_centavo_e_valores_fracionarios(self):
        for valores, alvo in [
            ([240.0, 34.31, 49.90], 324.20),
            ([0.1, 0.2, 0.3, 0.4], 0.61),
            ([1.005, 2.005, -0.001], 3.0),
            ([99999.99, -99999.98, 0.02, 0.03], 0.06),
        ]:
            with self.subTest(valores=valores, alvo=alvo):
                self.assert_equivalente([(v, ANTES) for v in valores], alvo)

    def test_casos_aleatorios_comparados_a_regra_anterior(self):
        rng = random.Random(103)
        for _ in range(500):
            transacoes = [
                (rng.randrange(-300, 1001) / 100, rng.choice([ANTES, DEPOIS, None]))
                for _ in range(rng.randrange(0, 11))
            ]
            valor = rng.randrange(-200, 2201) / 100
            desconto = rng.choice([0, 0.01, 0.1, 1, 3.25])
            with self.subTest(transacoes=transacoes, valor=valor, desconto=desconto):
                self.assert_equivalente(transacoes, valor, desconto)

    def test_grupo_grande_sem_combinacao(self):
        transacoes = [(2.0 if i % 2 else -2.0, ANTES) for i in range(32)]
        self.assertIsNone(encontrar_combinacao(transacoes, VENCIMENTO, 1.0, 0))

    def test_limite_explicito_nao_retorna_falso_nao_pago(self):
        transacoes = [(2.0 if i % 2 else -2.0, ANTES) for i in range(16)]
        with self.assertRaises(LimiteConciliacao):
            encontrar_combinacao(transacoes, VENCIMENTO, 1.0, 0, limite_estados=8)


if __name__ == '__main__':
    unittest.main()
