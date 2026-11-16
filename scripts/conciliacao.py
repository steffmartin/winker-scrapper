"""Busca limitada de pagamentos agrupados, sem acessar o banco de dados."""

from bisect import bisect_left, bisect_right
from itertools import combinations
import math
import sys


class LimiteConciliacao(Exception):
    """A conciliação não pôde ser concluída dentro do orçamento de busca."""


def encontrar_combinacao(transacoes, vencimento, valor, desconto, *,
                         limite_estados=1 << 18, limite_operacoes=1_000_000):
    """Retorna os índices da primeira combinação segundo a regra original.

    Cada transação é um par (valor, data). A busca mantém a prioridade por
    quantidade e ordem dos lançamentos, inclusive a comparação de ponto
    flutuante anterior. Em grupos grandes, divide os subconjuntos em duas
    metades; se o orçamento for excedido, interrompe sem declarar a taxa paga
    ou não paga.
    """
    if len(transacoes) < 2:
        return None

    valores = [item[0] for item in transacoes]
    alvo_desconto = valor - (desconto or 0)
    if not all(math.isfinite(v) for v in [*valores, valor, alvo_desconto]):
        raise LimiteConciliacao('Há valores não finitos na conciliação.')

    # O índice só serve para localizar candidatos. A validação final refaz a
    # soma na ordem original, pois o arredondamento pode mudar perto de R$ 0,01.
    margem = (math.fsum(abs(v) for v in valores) + abs(valor) +
              abs(alvo_desconto) + 1) * len(valores) * sys.float_info.epsilon * 8
    alvos = {valor, alvo_desconto}
    candidatos = list(range(len(transacoes)))
    if all(v >= 0 for v in valores):
        teto = max(alvos) + 0.01 + margem
        candidatos = [i for i in candidatos if valores[i] <= teto]

    def confere(indices):
        soma = sum(valores[i] for i in indices)
        datas = [transacoes[i][1] for i in indices if transacoes[i][1] is not None]
        return abs(soma - valor) < 0.01 or (
            datas and max(datas) <= vencimento and abs(soma - alvo_desconto) < 0.01
        )

    # Casos comuns terminam sem construir o índice. A quantidade de trabalho
    # dessas buscas pequenas também é limitada.
    for tamanho in (2, 3):
        if tamanho <= len(candidatos) and math.comb(len(candidatos), tamanho) <= 100_000:
            for indices in combinations(candidatos, tamanho):
                if confere(indices):
                    return indices

    meio = len(candidatos) // 2
    esquerda, direita = candidatos[:meio], candidatos[meio:]
    if (1 << len(esquerda)) > limite_estados or (1 << len(direita)) > limite_estados:
        raise LimiteConciliacao('O grupo de recebimentos excede o limite de conciliação.')

    # Índice de somas da metade direita, preservando todas as alternativas:
    # somas iguais podem produzir arredondamento diferente na soma completa.
    por_soma = {}
    for tamanho in range(len(direita) + 1):
        for indices in combinations(direita, tamanho):
            soma = sum(valores[i] for i in indices)
            por_soma.setdefault(soma, []).append(indices)
    for grupo in por_soma.values():
        grupo.sort(key=lambda indices: (len(indices), indices))
    somas = sorted(por_soma)

    melhor = None
    operacoes = 0
    for tamanho in range(len(esquerda) + 1):
        if melhor is not None and tamanho > len(melhor):
            break
        for indices_esq in combinations(esquerda, tamanho):
            soma_esq = sum(valores[i] for i in indices_esq)
            for alvo in alvos:
                inicio = bisect_left(somas, alvo - soma_esq - 0.01 - margem)
                fim = bisect_right(somas, alvo - soma_esq + 0.01 + margem)
                for pos in range(inicio, fim):
                    operacoes += 1
                    if operacoes > limite_operacoes:
                        raise LimiteConciliacao('A conciliação excedeu o limite de operações.')
                    for indices_dir in por_soma[somas[pos]]:
                        operacoes += 1
                        if operacoes > limite_operacoes:
                            raise LimiteConciliacao('A conciliação excedeu o limite de operações.')
                        indices = indices_esq + indices_dir
                        if len(indices) < 2:
                            continue
                        if melhor is not None and (len(indices), indices) >= (len(melhor), melhor):
                            break
                        if confere(indices):
                            melhor = indices
                            break
    return melhor
