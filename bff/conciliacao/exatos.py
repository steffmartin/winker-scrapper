"""Busca de quitações exatas por taxas e recebimentos."""
from datetime import date
from itertools import combinations
from bff.conciliacao.valores import (ConciliacaoInconclusiva, _centavos, _data,
    _validar_detalhes_quitacao, calcular_encargos)
from bff.conciliacao.alocacao import distribuir_parciais


def conciliar_exatos(taxas, recebimentos, modalidade, limite_operacoes=3000000, ids_nao_fracionar=frozenset(),
                     margem_encargos_centavos=10):
    """Localiza quitações exatas em um único apartamento e competência.

    O resultado é uma etapa isolada: não processa pagamentos parciais ou
    ajustes. Os valores de entrada devem estar líquidos de descontos manuais.
    Em caso de empate, vence o conjunto com mais taxas, seguido por vencimentos
    mais antigos, valores maiores e, por fim, recebimentos da mesma data,
    menos recebimentos e IDs para estabilidade técnica.
    """
    chaves = {(t['apartamento'], t['competencia']) for t in taxas + recebimentos}
    if len(chaves) > 1:
        raise ValueError('A conciliação deve conter uma única unidade e competência.')
    taxas_restantes = sorted(taxas, key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
    receitas_restantes = sorted((r for r in recebimentos if r['valor_centavos'] > 0),
                               key=lambda r: (r['data'], -r['valor_centavos'], str(r['id'])))
    if len(taxas_restantes) > 18:
        raise ConciliacaoInconclusiva('Grupo excede o limite de taxas.')
    operacoes = 0
    alocacoes = []

    def subconjuntos(itens):
        for tamanho in range(len(itens), 0, -1):
            yield from combinations(itens, tamanho)

    def buscar_somas(candidatos, teto):
        nonlocal operacoes
        # Cada valor alcançável retém a seleção lexicograficamente preferida.
        # O índice na lista ordenada só desempata resultados equivalentes.
        somas = {0: ()}
        for indice, receita in enumerate(candidatos):
            valor = receita['valor_centavos']
            anteriores = list(somas.items())
            operacoes += len(anteriores)
            if operacoes > limite_operacoes:
                raise ConciliacaoInconclusiva('Busca excedeu o limite de operações.')
            for soma, indices in anteriores:
                nova = soma + valor
                if nova > teto:
                    continue
                selecao = indices + (indice,)
                if nova not in somas or (len(selecao), selecao) < (len(somas[nova]), somas[nova]):
                    somas[nova] = selecao
        return somas

    for prioridade in (1, 2, 3):
        while taxas_restantes and receitas_restantes:
            melhor = None
            for grupo_taxas in subconjuntos(taxas_restantes):
                if melhor is not None and len(grupo_taxas) < -melhor[0][0]:
                    continue
                principal = sum(t['valor_centavos'] for t in grupo_taxas)
                primeiro_vencimento = min(t['vencimento'] for t in grupo_taxas)
                inicio_grupo = max((_data(t['data_renegociacao']) for t in grupo_taxas
                                    if t.get('tipo') == 'P' and t.get('data_renegociacao')), default=date.min)
                cenarios = []
                antes = [r for r in receitas_restantes if inicio_grupo <= r['data'] <= primeiro_vencimento]
                desconto_antes = sum(min(t['valor_centavos'], _centavos(t.get('desconto_vista'))) for t in grupo_taxas)
                if antes and (prioridade != 1 or desconto_antes):
                    cenarios.append((antes, desconto_antes if prioridade == 1 else 0, 0))
                for dia in sorted({r['data'] for r in receitas_restantes if r['data'] > primeiro_vencimento and r['data'] >= inicio_grupo}):
                    candidatos = [r for r in receitas_restantes if r['data'] == dia]
                    desconto = sum(min(t['valor_centavos'], _centavos(t.get('desconto_vista')))
                                   for t in grupo_taxas if dia <= t['vencimento']) if prioridade == 1 else 0
                    encargos = sum(calcular_encargos(t['valor_centavos'], t.get('juros_mes_percentual'),
                        t.get('multa_percentual'), (dia - t['vencimento']).days, modalidade)['total_centavos'] - t['valor_centavos']
                        for t in grupo_taxas if dia > t['vencimento'])
                    if (prioridade == 1 and not desconto) or (prioridade == 3 and not encargos):
                        continue
                    cenarios.append((candidatos, desconto, encargos))
                for candidatos, desconto, encargos in cenarios:
                    if prioridade == 3 and not encargos:
                        continue
                    alvo = principal - desconto + encargos
                    if alvo <= 0:
                        continue
                    somas = buscar_somas(candidatos, alvo + (margem_encargos_centavos if prioridade == 3 else 0))
                    valores = (sorted(pago for pago in somas if max(principal, alvo - margem_encargos_centavos) <= pago <= alvo + margem_encargos_centavos)
                               if prioridade == 3 else (alvo,))
                    for pago in valores:
                        if pago not in somas or not somas[pago] or (prioridade == 3 and pago == alvo):
                            continue
                        grupo_receitas = tuple(candidatos[i] for i in somas[pago])
                        diferenca = pago - alvo
                        ordenadas = sorted(grupo_taxas, key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
                        chave = (-len(grupo_taxas), tuple((t['vencimento'], -t['valor_centavos']) for t in ordenadas),
                                 0, len(grupo_receitas), 0, tuple(str(t['id']) for t in ordenadas),
                                 tuple((r['data'], -r['valor_centavos'], str(r['id'])) for r in grupo_receitas))
                        if melhor is None or chave < melhor[0]:
                            detalhes_candidato = distribuir_parciais(
                                list(grupo_taxas), list(grupo_receitas), max(r['data'] for r in grupo_receitas),
                                modalidade, habilitar_desconto=(prioridade == 1), desconto_agrupado=True,
                                priorizar_exatos=True)
                            try:
                                _validar_detalhes_quitacao(detalhes_candidato, desconto, encargos, diferenca)
                            except ConciliacaoInconclusiva:
                                # Um valor agregado pode cobrir os principais, mas a ordem de
                                # alocação pode usar parte dele para encargos de outra taxa.
                                continue
                            melhor = (chave, grupo_taxas, grupo_receitas, desconto, encargos, diferenca)
                    # Um recebimento pode quitar algumas taxas com desconto e
                    # ainda abater outra. A fração remanescente continua no
                    # grupo e nunca é consumida duas vezes.
                    if prioridade == 1 and len(grupo_taxas) < len(taxas_restantes):
                        ids_grupo = {id(t) for t in grupo_taxas}
                        outras = [t for t in taxas_restantes if id(t) not in ids_grupo]
                        for receita in candidatos:
                            if receita['id'] in ids_nao_fracionar:
                                continue
                            restante = receita['valor_centavos'] - alvo
                            disponiveis = [t for t in outras if t.get('tipo') != 'P' or not t.get('data_renegociacao')
                                           or _data(t['data_renegociacao']) <= receita['data']]
                            if restante <= 0 or restante > sum(t['valor_centavos'] for t in disponiveis):
                                continue
                            grupo_receitas = (dict(receita, valor_centavos=alvo),)
                            ordenadas = sorted(grupo_taxas, key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
                            chave = (-len(grupo_taxas), tuple((t['vencimento'], -t['valor_centavos']) for t in ordenadas),
                                     0, 1, 1, tuple(str(t['id']) for t in ordenadas),
                                     ((receita['data'], -alvo, str(receita['id'])),))
                            if melhor is None or chave < melhor[0]:
                                melhor = (chave, grupo_taxas, grupo_receitas, desconto, encargos, 0)
                        # Também permite vários recebimentos integrais e uma
                        # fração final, sem reutilizar nenhum centavo.
                        ordenadas_grupo = sorted(grupo_taxas, key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
                        negocio_grupo = (-len(grupo_taxas), tuple((t['vencimento'], -t['valor_centavos']) for t in ordenadas_grupo))
                        if (melhor is None or negocio_grupo < melhor[0][:2]
                                or (negocio_grupo == melhor[0][:2] and len(melhor[2]) > 1)):
                            for fracionada in candidatos:
                                if fracionada['id'] in ids_nao_fracionar:
                                    continue
                                disponiveis = [t for t in outras if t.get('tipo') != 'P' or not t.get('data_renegociacao')
                                               or _data(t['data_renegociacao']) <= fracionada['data']]
                                capacidade = sum(t['valor_centavos'] for t in disponiveis)
                                if capacidade <= 0:
                                    continue
                                demais = [r for r in candidatos if r['id'] != fracionada['id']]
                                somas_parciais = buscar_somas(demais, alvo - 1)
                                operacoes += len(somas_parciais)
                                if operacoes > limite_operacoes:
                                    raise ConciliacaoInconclusiva('Busca excedeu o limite de operações.')
                                for soma, indices in somas_parciais.items():
                                    parcela = alvo - soma
                                    sobra = fracionada['valor_centavos'] - parcela
                                    if not indices or parcela <= 0 or not 0 < sobra <= capacidade:
                                        continue
                                    grupo_receitas = tuple(sorted(
                                        [demais[i] for i in indices] + [dict(fracionada, valor_centavos=parcela)],
                                        key=lambda r: (r['data'], -r['valor_centavos'], str(r['id']))))
                                    ordenadas = sorted(grupo_taxas, key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
                                    chave = (-len(grupo_taxas), tuple((t['vencimento'], -t['valor_centavos']) for t in ordenadas),
                                             0, len(grupo_receitas), 1, tuple(str(t['id']) for t in ordenadas),
                                             tuple((r['data'], -r['valor_centavos'], str(r['id'])) for r in grupo_receitas))
                                    if melhor is None or chave < melhor[0]:
                                        melhor = (chave, grupo_taxas, grupo_receitas, desconto, encargos, 0)
            # Para pagamentos em datas distintas após algum vencimento, os
            # encargos dependem dos pagamentos parciais anteriores. Simula-se
            # cada subconjunto que possa superar a melhor combinação já achada.
            # Em empate de negócio, a seleção de mesma data é o desempate
            # técnico, evitando a busca exponencial quando já é suficiente.
            if len({r['data'] for r in receitas_restantes}) > 1:
                for grupo_taxas in subconjuntos(taxas_restantes):
                    ordenadas = sorted(grupo_taxas, key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
                    negocio = (-len(grupo_taxas), tuple((t['vencimento'], -t['valor_centavos']) for t in ordenadas))
                    if melhor is not None:
                        if negocio > melhor[0][:2] or (negocio == melhor[0][:2] and melhor[0][2] == 0):
                            continue
                    if (1 << len(receitas_restantes)) > limite_operacoes - operacoes:
                        raise ConciliacaoInconclusiva('Busca de pagamentos em datas distintas excedeu o limite de operações.')
                    for grupo_receitas in subconjuntos(receitas_restantes):
                        operacoes += 1
                        dias = {r['data'] for r in grupo_receitas}
                        if len(dias) < 2 or max(dias) <= min(t['vencimento'] for t in grupo_taxas):
                            continue
                        simulacao = distribuir_parciais(list(grupo_taxas), list(grupo_receitas), max(dias), modalidade,
                                                       habilitar_desconto=(prioridade == 1))
                        if any(s['principal_centavos'] for s in simulacao['saldos']):
                            continue
                        desconto = sum(s['desconto_concedido_centavos'] for s in simulacao['saldos'])
                        pagos = sum(a['juros_centavos'] + a['multa_centavos']
                                    for p in simulacao['recebimentos'] for a in p['alocacoes'])
                        pendentes = sum(s['juros_centavos'] + s['multa_centavos'] for s in simulacao['saldos'])
                        excedente = sum(p['nao_alocado_centavos'] for p in simulacao['recebimentos'])
                        encargos = pagos + pendentes
                        diferenca = excedente - pendentes
                        if prioridade == 1 and (not desconto or diferenca != 0):
                            continue
                        if prioridade == 2 and diferenca != 0:
                            continue
                        if prioridade == 3 and (not encargos or not diferenca or abs(diferenca) > margem_encargos_centavos):
                            continue
                        chave = (*negocio, 1, len(grupo_receitas), 0, tuple(str(t['id']) for t in ordenadas),
                                 tuple((r['data'], -r['valor_centavos'], str(r['id'])) for r in grupo_receitas))
                        if melhor is None or chave < melhor[0]:
                            melhor = (chave, grupo_taxas, grupo_receitas, desconto, encargos, diferenca)
            if melhor is None:
                break
            chave_selecao, grupo_taxas, grupo_receitas, desconto, encargos, diferenca = melhor
            detalhes = distribuir_parciais(list(grupo_taxas), list(grupo_receitas),
                                          max(r['data'] for r in grupo_receitas), modalidade,
                                          habilitar_desconto=(prioridade == 1), desconto_agrupado=(chave_selecao[2] == 0),
                                          priorizar_exatos=(chave_selecao[2] == 0))
            _validar_detalhes_quitacao(detalhes, desconto, encargos, diferenca)
            origens_atuais = {r['id']: r['valor_centavos'] for r in receitas_restantes}
            fracionados = [r['id'] for r in grupo_receitas if r['valor_centavos'] < origens_atuais[r['id']]]
            alocacoes.append({'taxas': [t['id'] for t in grupo_taxas],
                'recebimentos': [r['id'] for r in grupo_receitas], 'prioridade': prioridade,
                'desconto_centavos': desconto, 'encargos_centavos': encargos,
                'diferenca_centavos': diferenca, 'recebimentos_fracionados': fracionados, 'detalhes': detalhes})
            ids_taxas = {id(t) for t in grupo_taxas}
            taxas_restantes = [t for t in taxas_restantes if id(t) not in ids_taxas]
            consumido = {r['id']: r['valor_centavos'] for r in grupo_receitas}
            novas_receitas = []
            for receita in receitas_restantes:
                saldo_receita = receita['valor_centavos'] - consumido.get(receita['id'], 0)
                if saldo_receita > 0:
                    novas_receitas.append(dict(receita, valor_centavos=saldo_receita))
            receitas_restantes = novas_receitas
    return {'alocacoes': alocacoes, 'taxas_pendentes': taxas_restantes,
            'recebimentos_nao_alocados': receitas_restantes}
