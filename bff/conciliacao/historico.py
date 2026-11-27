"""Quitações e simulações para históricos com ajustes temporais."""
from collections import defaultdict
from itertools import combinations, permutations
from math import factorial

from bff.conciliacao.valores import (ConciliacaoInconclusiva, _data, _centavos,
    _validar_detalhes_quitacao)
from bff.conciliacao.alocacao import distribuir_parciais


def conciliar_historicos(taxas, recebimentos, ajustes, modalidade, limite_operacoes=150000, data_corte=None,
                         ids_nao_fracionar=frozenset(), margem_encargos_centavos=10):
    """Busca quitações em grupos que tenham ajustes durante o histórico.

    Cada candidato é simulado na sequência de datas, considerando somente os
    ajustes vinculados às cobranças do candidato. Ajustes posteriores são
    simulados; quando houver outras taxas, uma quitação só é separada se não
    gerar crédito novo que possa precisar ser aplicado a elas.
    """
    chaves = {(t['apartamento'], t['competencia']) for t in taxas + recebimentos}
    if len(chaves) > 1:
        raise ValueError('A conciliação deve conter uma única unidade e competência.')
    taxas_restantes = sorted(taxas, key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
    receitas_restantes = sorted((r for r in recebimentos if r['valor_centavos'] > 0),
                               key=lambda r: (r['data'], -r['valor_centavos'], str(r['id'])))
    operacoes = 0
    quitacoes = []
    rejeitada = None

    def grupos(itens):
        for tamanho in range(1, len(itens) + 1):
            yield from combinations(itens, tamanho)

    for prioridade in (1, 2, 3):
        while taxas_restantes and receitas_restantes:
            melhor = None
            for selecionadas in grupos(taxas_restantes):
                ids = {t['id'] for t in selecionadas}
                descontos_ids = {a['id'] for a in ajustes if a['tipo'] == 'D' and a.get('taxa_id') in ids}
                relacionados = [a for a in ajustes if a.get('taxa_id') in ids or a.get('taxa_id') in descontos_ids]
                ordenadas = sorted(selecionadas, key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
                negocio = (-len(selecionadas), tuple((t['vencimento'], -t['valor_centavos']) for t in ordenadas))
                if melhor is not None and negocio > melhor[0][:2]:
                    continue
                for usados in grupos(receitas_restantes):
                    operacoes += 1
                    if operacoes > limite_operacoes:
                        raise ConciliacaoInconclusiva('Busca histórica excedeu o limite de operações.')
                    ultima = max(r['data'] for r in usados)
                    futuros = any(_data(data_ajuste) > ultima for a in relacionados
                                  for data_ajuste in [a.get('vencimento') if a['tipo'] == 'D' else a.get('data_renegociacao')]
                                  if data_ajuste)
                    corte_final = (_data(data_corte) if data_corte else max(
                        [ultima] + [_data(data_ajuste) for a in relacionados
                                    for data_ajuste in [a.get('vencimento') if a['tipo'] == 'D' else a.get('data_renegociacao')]
                                    if data_ajuste]))
                    sim = distribuir_parciais(list(selecionadas), list(usados), ultima, modalidade, relacionados,
                                              habilitar_desconto=(prioridade == 1), desconto_agrupado=True)
                    if any(s['principal_centavos'] for s in sim['saldos']):
                        continue
                    desconto = sum(s['desconto_concedido_centavos'] for s in sim['saldos'])
                    pago_encargos = sum(a['juros_centavos'] + a['multa_centavos']
                                        for p in sim['recebimentos'] for a in p['alocacoes'])
                    pendente_encargos = sum(s['juros_centavos'] + s['multa_centavos'] for s in sim['saldos'])
                    excedente = sum(p['nao_alocado_centavos'] for p in sim['recebimentos'])
                    if prioridade == 1 and desconto and not pendente_encargos and excedente > 0 and len(selecionadas) < len(taxas_restantes):
                        com_sobra = [p for p in sim['recebimentos'] if p['nao_alocado_centavos'] > 0]
                        if len(com_sobra) == 1 and com_sobra[0]['recebimento_id'] not in ids_nao_fracionar:
                            pagamento_sobra = com_sobra[0]
                            outras = [t for t in taxas_restantes if t['id'] not in ids]
                            original = next(r for r in usados if r['id'] == pagamento_sobra['recebimento_id'])
                            disponiveis = [t for t in outras if t.get('tipo') != 'P' or not t.get('data_renegociacao')
                                           or _data(t['data_renegociacao']) <= original['data']]
                            if (excedente < original['valor_centavos'] and
                                    excedente <= sum(t['valor_centavos'] for t in disponiveis)):
                                usados = tuple(dict(r, valor_centavos=r['valor_centavos'] - excedente)
                                               if r['id'] == original['id'] else r for r in usados)
                                sim = distribuir_parciais(list(selecionadas), list(usados), ultima, modalidade, relacionados,
                                                          habilitar_desconto=True, desconto_agrupado=True)
                                desconto = sum(s['desconto_concedido_centavos'] for s in sim['saldos'])
                                pago_encargos = sum(a['juros_centavos'] + a['multa_centavos']
                                                    for p in sim['recebimentos'] for a in p['alocacoes'])
                                pendente_encargos = sum(s['juros_centavos'] + s['multa_centavos'] for s in sim['saldos'])
                                excedente = sum(p['nao_alocado_centavos'] for p in sim['recebimentos'])
                                if any(s['principal_centavos'] for s in sim['saldos']):
                                    continue
                    encargos = pago_encargos + pendente_encargos
                    diferenca = excedente - pendente_encargos
                    if prioridade == 1 and (not desconto or diferenca != 0):
                        continue
                    if prioridade == 2 and diferenca != 0:
                        continue
                    if prioridade == 3 and (not encargos or not diferenca or abs(diferenca) > margem_encargos_centavos):
                        continue
                    if futuros:
                        final = distribuir_parciais(list(selecionadas), list(usados), corte_final,
                                                    modalidade, relacionados, habilitar_desconto=(prioridade == 1),
                                                    desconto_agrupado=True)
                        if any(s['total_centavos'] for s in final['saldos']):
                            continue
                        credito_novo = (sum(p['nao_alocado_centavos'] for p in final['recebimentos'])
                                        - sum(p['nao_alocado_centavos'] for p in sim['recebimentos']))
                        if len(selecionadas) != len(taxas_restantes) and credito_novo > 0:
                            chave_rejeitada = (*negocio, len(usados), tuple(str(t['id']) for t in ordenadas),
                                               tuple((r['data'], -r['valor_centavos'], str(r['id'])) for r in usados))
                            if prioridade == 2 and (rejeitada is None or chave_rejeitada < rejeitada['chave']):
                                rejeitada = {'negocio': negocio, 'chave': chave_rejeitada, 'taxas': [t['id'] for t in selecionadas],
                                             'recebimentos': [r['id'] for r in usados],
                                             'data': ultima, 'detalhes': sim}
                            continue
                    chave = (*negocio, len(usados), tuple(str(t['id']) for t in ordenadas),
                             tuple((r['data'], -r['valor_centavos'], str(r['id'])) for r in usados))
                    if melhor is None or chave < melhor[0]:
                        melhor = (chave, selecionadas, usados, desconto, encargos, diferenca, futuros)
            if melhor is None:
                break
            _, selecionadas, usados, desconto, encargos, diferenca, futuros = melhor
            ids = {t['id'] for t in selecionadas}
            descontos_ids = {a['id'] for a in ajustes if a['tipo'] == 'D' and a.get('taxa_id') in ids}
            relacionados = [a for a in ajustes if a.get('taxa_id') in ids or a.get('taxa_id') in descontos_ids]
            detalhes = distribuir_parciais(list(selecionadas), list(usados), max(r['data'] for r in usados),
                                          modalidade, relacionados, habilitar_desconto=(prioridade == 1),
                                          desconto_agrupado=True)
            _validar_detalhes_quitacao(detalhes, desconto, encargos, diferenca)
            origens_atuais = {r['id']: r['valor_centavos'] for r in receitas_restantes}
            fracionados = [r['id'] for r in usados if r['valor_centavos'] < origens_atuais[r['id']]]
            quitacao = {'taxas': [t['id'] for t in selecionadas], 'recebimentos': [r['id'] for r in usados],
                              'prioridade': prioridade, 'desconto_centavos': desconto,
                              'encargos_centavos': encargos, 'diferenca_centavos': diferenca,
                              'recebimentos_fracionados': fracionados, 'detalhes': detalhes}
            if futuros:
                corte_final = (_data(data_corte) if data_corte else max(
                    [max(r['data'] for r in usados)] + [_data(data_ajuste) for a in relacionados
                        for data_ajuste in [a.get('vencimento') if a['tipo'] == 'D' else a.get('data_renegociacao')]
                        if data_ajuste]))
                quitacao['historico_final'] = distribuir_parciais(list(selecionadas), list(usados), corte_final,
                                                                 modalidade, relacionados, habilitar_desconto=(prioridade == 1),
                                                                 desconto_agrupado=True)
            quitacoes.append(quitacao)
            usados_t = {id(t) for t in selecionadas}
            taxas_restantes = [t for t in taxas_restantes if id(t) not in usados_t]
            consumido = {r['id']: r['valor_centavos'] for r in usados}
            receitas_restantes = [dict(r, valor_centavos=r['valor_centavos'] - consumido.get(r['id'], 0))
                                  for r in receitas_restantes if r['valor_centavos'] - consumido.get(r['id'], 0) > 0]
    return {'alocacoes': quitacoes, 'taxas_pendentes': taxas_restantes,
            'recebimentos_nao_alocados': receitas_restantes, 'rejeitada_credito': rejeitada}

def simular_descontos_temporais(taxas, recebimentos, ajustes, data_corte, modalidade, limite_ordens=5040):
    """Busca distribuições com desconto quando ajustes dividem o histórico.

    Cada ordem de cobranças é simulada com os mesmos recebimentos de origem.
    Descontos que dependam de deixar parte do próprio recebimento sem aplicação
    são rejeitados, salvo crédito criado posteriormente por um ajuste.
    """
    if not taxas or not recebimentos or not any(_centavos(t.get('desconto_vista')) > 0 for t in taxas):
        return None
    if factorial(len(taxas)) > limite_ordens:
        raise ConciliacaoInconclusiva('Busca de distribuição histórica excedeu o limite de ordens.')
    por_id = {t['id']: t for t in taxas}
    melhor = None
    for ordem in permutations(sorted(por_id, key=str)):
        try:
            sim = distribuir_parciais(taxas, recebimentos, data_corte, modalidade, ajustes,
                                      habilitar_desconto=True, desconto_agrupado=True, ordem_taxas=ordem)
        except ConciliacaoInconclusiva:
            continue
        descontadas = [s for s in sim['saldos'] if s['desconto_concedido_centavos'] > 0]
        if not descontadas:
            continue
        ids = {s['taxa']['id'] for s in descontadas}
        if any(p['nao_alocado_centavos'] > p['credito_ajuste_centavos'] and
               any(a['principal_centavos'] > 0 for a in p['alocacoes'])
               for p in sim['recebimentos']):
            continue
        ordenadas = sorted((por_id[i] for i in ids), key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
        chave = (-len(ordenadas), tuple((t['vencimento'], -t['valor_centavos']) for t in ordenadas),
                 tuple(str(t['id']) for t in ordenadas), tuple(str(i) for i in ordem))
        if melhor is None or chave < melhor[0]:
            melhor = (chave, sim)
    return melhor

def simular_quitacao_com_credito(taxas, recebimentos, ajustes, data_corte, modalidade, rejeitada):
    """Reconstitui quitação que libera crédito a outras taxas posteriormente."""
    selecionadas = set(rejeitada['taxas'])
    selecionadas_ordenadas = sorted((t for t in taxas if t['id'] in selecionadas),
                                    key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
    outras = sorted((t for t in taxas if t['id'] not in selecionadas),
                    key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
    if factorial(len(outras)) > 5040:
        raise ConciliacaoInconclusiva('Busca de crédito entre taxas excedeu o limite de ordens.')

    def movimentos(resultado):
        agrupados = defaultdict(int)
        for pagamento in resultado['recebimentos']:
            for movimento in pagamento['movimentacoes']:
                if movimento['data'] <= rejeitada['data'] and movimento['taxa_id'] in selecionadas:
                    for campo in ('principal_centavos', 'juros_centavos', 'multa_centavos'):
                        agrupados[(movimento['recebimento_id'], movimento['taxa_id'], campo)] += movimento[campo]
        return {chave: valor for chave, valor in agrupados.items() if valor}

    melhor = None
    por_id = {t['id']: t for t in taxas}
    for ordem_outras in permutations(outras):
        ordem = selecionadas_ordenadas + list(ordem_outras)
        sim = distribuir_parciais(taxas, recebimentos, data_corte, modalidade, ajustes,
                                  ordem_taxas=[t['id'] for t in ordem],
                                  reservas={i: set(rejeitada['recebimentos']) for i in selecionadas},
                                  data_reserva=rejeitada['data'])
        if movimentos(sim) != movimentos(rejeitada['detalhes']):
            continue
        outros = [s for s in sim['saldos'] if s['taxa']['id'] not in selecionadas]
        pendentes = [s for s in outros if s['total_centavos'] > 0]
        ids_pendentes = {s['taxa']['id'] for s in pendentes}
        aplicado_pendentes = sum(a['principal_centavos'] + a['juros_centavos'] + a['multa_centavos']
                                 for p in sim['recebimentos'] for a in p['alocacoes'] if a['taxa_id'] in ids_pendentes)
        minimo = min((s['taxa']['valor_centavos'] for s in pendentes if s['taxa']['valor_centavos'] > 0), default=0)
        if minimo and aplicado_pendentes >= minimo:
            continue
        quitadas = sorted((por_id[s['taxa']['id']] for s in outros
                           if s['total_centavos'] == 0 and s['principal_pago_centavos'] > 0),
                          key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
        chave = (-len(quitadas), tuple((t['vencimento'], -t['valor_centavos']) for t in quitadas),
                 tuple(str(t['id']) for t in quitadas), tuple(str(t['id']) for t in ordem_outras))
        if melhor is None or chave < melhor[0]:
            melhor = (chave, sim)
    return melhor[1] if melhor else None
