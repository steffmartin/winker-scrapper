"""Conciliação de cobranças e recebimentos sem escrita no banco.

Os registros de origem e as alocações são preservados. Valores são convertidos
a centavos com arredondamento decimal HALF_DOWN; buscas limitadas sinalizam
resultado inconclusivo em vez de retornar quitações parciais como completas.
"""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_DOWN
from itertools import combinations, permutations, groupby
from math import factorial
from collections import defaultdict
from bff.conciliacao.valores import (ConciliacaoInconclusiva, _data, _centavos,
    calcular_encargos, _validar_detalhes_quitacao)
from bff.conciliacao.dados import consultar, normalizar, aplicar_ajustes, filtrar_grupos
from bff.conciliacao.alocacao import distribuir_parciais
from bff.conciliacao.exatos import conciliar_exatos
from bff.conciliacao.historico import (conciliar_historicos, simular_descontos_temporais,
    simular_quitacao_com_credito)






























def calcular_posicao(condominio_id, data_corte, apartamentos, taxas, recebimentos, modalidade, margem_encargos_centavos=10, filtros=None, permitir_inconclusivo=False):
    """Produz uma posição por unidade e competência a partir dos dados de origem.

    O histórico é carregado até o corte, sem filtros de período de apresentação.
    Ajustes posteriores aos pagamentos são aplicados em ordem cronológica.
    A busca histórica é limitada; se não puder determinar uma quitação sem
    retroagir um ajuste, a posição é sinalizada como inconclusiva.
    """
    if isinstance(margem_encargos_centavos, bool) or not isinstance(margem_encargos_centavos, int) or margem_encargos_centavos < 0:
        raise ValueError('Margem de diferença de encargos inválida.')
    corte = _data(data_corte)
    selecionados = (filtros or {}).get('apartamentos') or []
    dados = normalizar(condominio_id, corte, apartamentos, taxas, recebimentos, apartamentos_filtro=selecionados)
    if filtros:
        dados = filtrar_grupos(dados, filtros, corte)
    grupos = defaultdict(lambda: {'taxas': [], 'recebimentos': [], 'ajustes': []})
    originais = {(t['apartamento'], t['id']): t for t in dados['taxas']}
    for taxa in aplicar_ajustes(dados):
        grupos[(taxa['apartamento'], taxa['competencia'])]['taxas'].append(taxa)
    for receita in dados['recebimentos']:
        grupos[(receita['apartamento'], receita['competencia'])]['recebimentos'].append(receita)
    ajustes_por_id = {(a['apartamento'], a['id']): a for a in dados['ajustes']}
    for ajuste in dados['ajustes']:
        vinculo = ajuste.get('taxa_id')
        alvo = originais.get((ajuste['apartamento'], vinculo))
        if alvo is None:
            desconto = ajustes_por_id.get((ajuste['apartamento'], vinculo))
            if desconto:
                alvo = originais.get((ajuste['apartamento'], desconto.get('taxa_id')))
        if alvo:
            grupos[(alvo['apartamento'], alvo['competencia'])]['ajustes'].append(ajuste)
    resultado = []
    for (apartamento, competencia), grupo in sorted(grupos.items()):
        try:
            positivas = [r for r in grupo['recebimentos'] if r['valor_centavos'] > 0]
            primeiro_pagamento = min((r['data'] for r in positivas), default=None)
            primeiro_vencimento = min((t['vencimento'] for t in grupo['taxas']), default=None)
            ajuste_temporal = False
            for ajuste in grupo['ajustes']:
                data_ajuste = ajuste.get('vencimento') if ajuste['tipo'] == 'D' else ajuste.get('data_renegociacao')
                if data_ajuste:
                    data_ajuste = _data(data_ajuste)
                    if ((primeiro_pagamento and data_ajuste > primeiro_pagamento) or
                            (primeiro_vencimento and data_ajuste > primeiro_vencimento)):
                        ajuste_temporal = True
                        break
            if ajuste_temporal:
                taxas_historicas = [originais[(t['apartamento'], t['id'])] for t in grupo['taxas']]
                proibidos = set()
                while True:
                    exatos = conciliar_historicos(taxas_historicas, positivas, grupo['ajustes'], modalidade,
                                                  data_corte=corte, ids_nao_fracionar=proibidos,
                                                  margem_encargos_centavos=margem_encargos_centavos)
                    rejeitada = exatos.get('rejeitada_credito')
                    if rejeitada and not any(_centavos(t.get('desconto_vista')) > 0 for t in taxas_historicas):
                        origens_por_id = {t['id']: t for t in taxas_historicas}
                        receitas_por_id = {r['id']: r for r in positivas}
                        chaves_exatas = []
                        for quitacao in exatos['alocacoes']:
                            if quitacao['prioridade'] != 2:
                                continue
                            itens = sorted((origens_por_id[i] for i in quitacao['taxas']),
                                           key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
                            fontes = [receitas_por_id[i] for i in quitacao['recebimentos']]
                            chaves_exatas.append((-len(itens), tuple((t['vencimento'], -t['valor_centavos']) for t in itens),
                                                  len(fontes), tuple(str(t['id']) for t in itens),
                                                  tuple((r['data'], -r['valor_centavos'], str(r['id'])) for r in fontes)))
                        if not chaves_exatas or rejeitada['chave'] < min(chaves_exatas):
                            sim = simular_quitacao_com_credito(taxas_historicas, positivas, grupo['ajustes'], corte,
                                                               modalidade, rejeitada)
                            if sim is None:
                                raise ConciliacaoInconclusiva(
                                    f'Crédito de ajuste exige busca adicional: unidade {apartamento}, competência {competencia}.')
                            exatos = {'alocacoes': []}
                            parciais = sim
                            break
                    ids_descontados = {s['taxa']['id'] for q in exatos['alocacoes'] if q['prioridade'] == 1
                                       for s in q['detalhes']['saldos'] if s['desconto_concedido_centavos'] > 0}
                    por_id = {t['id']: t for t in taxas_historicas}
                    ordenadas = sorted((por_id[i] for i in ids_descontados),
                                       key=lambda t: (t['vencimento'], -t['valor_centavos'], str(t['id'])))
                    chave_exatos = (-len(ordenadas), tuple((t['vencimento'], -t['valor_centavos']) for t in ordenadas),
                                    tuple(str(t['id']) for t in ordenadas))
                    futuras = any(primeiro_pagamento and _data(data_ajuste) > primeiro_pagamento
                                  for a in grupo['ajustes']
                                  for data_ajuste in [a.get('vencimento') if a['tipo'] == 'D' else a.get('data_renegociacao')]
                                  if data_ajuste)
                    quantidade_descontavel = sum(_centavos(t.get('desconto_vista')) > 0 for t in taxas_historicas)
                    if futuras and len(ids_descontados) < quantidade_descontavel:
                        simulada = simular_descontos_temporais(taxas_historicas, positivas, grupo['ajustes'], corte, modalidade)
                        if simulada and simulada[0][:3] < chave_exatos:
                            sim = simulada[1]
                            outros = [s for s in sim['saldos'] if not s['desconto_concedido_centavos']]
                            ids_outros = {s['taxa']['id'] for s in outros}
                            aplicado_outros = sum(a['principal_centavos'] + a['juros_centavos'] + a['multa_centavos']
                                                 for p in sim['recebimentos'] for a in p['alocacoes'] if a['taxa_id'] in ids_outros)
                            min_outros = min((s['taxa']['valor_centavos'] for s in outros if s['taxa']['valor_centavos'] > 0), default=0)
                            if outros and any(s['total_centavos'] for s in outros) and min_outros and aplicado_outros >= min_outros:
                                raise ConciliacaoInconclusiva(
                                    f'Distribuição histórica exige busca adicional: unidade {apartamento}, competência {competencia}.')
                            exatos = {'alocacoes': []}
                            parciais = sim
                            break
                    posteriores = any(_data(data_ajuste) > max((r['data'] for r in exatos['recebimentos_nao_alocados']), default=corte)
                                      for a in grupo['ajustes']
                                      for data_ajuste in [a.get('vencimento') if a['tipo'] == 'D' else a.get('data_renegociacao')]
                                      if data_ajuste)
                    if (posteriores and len(exatos['taxas_pendentes']) > 1 and exatos['recebimentos_nao_alocados']
                            and any(_centavos(t.get('desconto_vista')) > 0 for t in exatos['taxas_pendentes'])):
                        possivel = False
                        for taxa in exatos['taxas_pendentes']:
                            desconto_maximo = _centavos(taxa.get('desconto_vista'))
                            if desconto_maximo <= 0:
                                continue
                            abatimentos_maximos = sum(max(0, _centavos(a.get('valor_original'))) for a in grupo['ajustes']
                                                      if a.get('taxa_id') == taxa['id'] and a['tipo'] in ('D', 'R'))
                            minimo = max(0, taxa['valor_centavos'] - abatimentos_maximos - desconto_maximo)
                            pago_no_prazo = sum(r['valor_centavos'] for r in exatos['recebimentos_nao_alocados']
                                                if r['data'] <= taxa['vencimento'])
                            if minimo <= pago_no_prazo:
                                possivel = True
                                break
                        if possivel:
                            raise ConciliacaoInconclusiva(
                                f'Desconto à vista e ajuste posterior exigem conciliação histórica: unidade {apartamento}, competência {competencia}.')
                    parciais = distribuir_parciais(exatos['taxas_pendentes'], exatos['recebimentos_nao_alocados'], corte,
                                                   modalidade, grupo['ajustes'], habilitar_desconto=True)
                    fracionados = {i for q in exatos['alocacoes'] for i in q['recebimentos_fracionados']}
                    invalidos = {p['recebimento_id'] for p in parciais['recebimentos']
                                 if p['recebimento_id'] in fracionados and p['nao_alocado_centavos'] > 0}
                    novos = invalidos - proibidos
                    if not novos:
                        break
                    proibidos.update(novos)
                    if len(proibidos) > 20:
                        raise ConciliacaoInconclusiva('Busca histórica fracionada excedeu o limite de tentativas.')
                for quitacao in exatos['alocacoes']:
                    for pagamento in quitacao.get('historico_final', {}).get('recebimentos', []):
                        if pagamento['credito_ajuste_centavos']:
                            parciais['recebimentos'].append(dict(pagamento, quitacao_exata=True,
                                nao_alocado_centavos=pagamento['credito_ajuste_centavos']))
            else:
                ativas = [t for t in grupo['taxas'] if t['valor_centavos'] > 0]
                proibidos = set()
                while True:
                    exatos = conciliar_exatos(ativas, positivas, modalidade, ids_nao_fracionar=proibidos,
                                              margem_encargos_centavos=margem_encargos_centavos)
                    parciais = distribuir_parciais(exatos['taxas_pendentes'], exatos['recebimentos_nao_alocados'], corte, modalidade)
                    fracionados = {i for q in exatos['alocacoes'] for i in q['recebimentos_fracionados']}
                    invalidos = {p['recebimento_id'] for p in parciais['recebimentos']
                                 if p['recebimento_id'] in fracionados and p['nao_alocado_centavos'] > 0}
                    novos = invalidos - proibidos
                    if not novos:
                        break
                    proibidos.update(novos)
                    if len(proibidos) > 20:
                        raise ConciliacaoInconclusiva('Busca de alocações fracionadas excedeu o limite de tentativas.')
            for quitacao in exatos['alocacoes']:
                quitacao['ajuste_automatico'] = bool(quitacao['diferenca_centavos'])
            for pagamento in parciais['recebimentos']:
                pagamento['ajuste_automatico'] = pagamento['nao_alocado_centavos'] > 0
            resultado.append({'apartamento': apartamento, 'competencia': competencia,
                              'taxas_origem': grupo['taxas'], 'ajustes_origem': grupo['ajustes'],
                              'recebimentos_origem': grupo['recebimentos'],
                              'quitacoes_exatas': exatos['alocacoes'], 'saldos': parciais['saldos'],
                              'pagamentos_parciais': parciais['recebimentos']})
        except ConciliacaoInconclusiva as erro:
            if not permitir_inconclusivo:
                raise
            saldos_abertos = []
            for taxa in grupo['taxas']:
                dias = max(0, (corte - taxa['vencimento']).days)
                encargos = calcular_encargos(taxa['valor_centavos'], taxa.get('juros_mes_percentual'),
                                             taxa.get('multa_percentual'), dias, modalidade)
                saldos_abertos.append({'taxa': taxa, **encargos})
            resultado.append({'apartamento': apartamento, 'competencia': competencia,
                              'taxas_origem': grupo['taxas'], 'ajustes_origem': grupo['ajustes'],
                              'recebimentos_origem': grupo['recebimentos'],
                              'quitacoes_exatas': [], 'saldos': [], 'saldos_abertos': saldos_abertos,
                              'pagamentos_parciais': [], 'conciliacao_inconclusiva': str(erro)})
    return {'condominio_id': condominio_id, 'data_corte': corte,
            'apartamentos': list(dict.fromkeys(selecionados or apartamentos)), 'grupos': resultado}
