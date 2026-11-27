"""Adaptadores de apresentação para os resultados da conciliação unificada."""
from collections import defaultdict
from datetime import date, datetime
from itertools import zip_longest
import calendar
from bff.conciliacao_unificada import _centavos, _data


def data_corte_extrato(filtros, hoje=None):
    """Resolve a data da posição antes de aplicar filtros de apresentação."""
    tipo = filtros.get('tipo')
    if tipo not in ('completo', 'competencia', 'recebimento'):
        raise ValueError('Selecione um tipo de extrato válido.')
    if tipo == 'completo':
        return hoje or date.today()
    periodo = filtros.get('periodo')
    if not isinstance(periodo, list) or len(periodo) != 2 or not all(periodo):
        raise ValueError('Selecione o início e o fim do período.')
    if tipo == 'competencia':
        try:
            inicio, fim = (datetime.strptime(item, '%Y-%m').date() for item in periodo)
        except (TypeError, ValueError):
            raise ValueError('Competência inválida.')
        calculada = fim.replace(day=calendar.monthrange(fim.year, fim.month)[1])
    else:
        inicio, fim = (_data(item) for item in periodo)
        calculada = fim
    if inicio > fim:
        raise ValueError('O início do período deve ser anterior ou igual ao fim.')
    return calculada


def inadimplencia(posicao):
    """Adapta saldos ao contrato existente da tela de inadimplência."""
    corte = posicao['data_corte']
    unidades = defaultdict(list)
    for grupo in posicao['grupos']:
        for saldo in grupo.get('saldos_abertos', grupo['saldos']):
            taxa = saldo['taxa']
            if taxa['vencimento'] >= corte or saldo['total_centavos'] <= 0:
                continue
            unidades[grupo['apartamento']].append({
                'id': taxa['id'], 'competencia': taxa['competencia'],
                'exibicao': taxa.get('exibicao'), 'descricao': taxa.get('descricao'),
                'vencimento': taxa['vencimento'].strftime('%d/%m/%Y'),
                'valor': saldo['principal_centavos'] / 100,
                'juros_total': saldo['juros_centavos'] / 100,
                'multa': saldo['multa_centavos'] / 100,
                'dias_vencidos': (corte - taxa['vencimento']).days,
            })
    resultado = []
    for apartamento, taxas in sorted(unidades.items()):
        taxas.sort(key=lambda t: (t['vencimento'][6:10], t['vencimento'][3:5], t['vencimento'][:2], -t['valor'], str(t['id'])))
        resultado.append({'unidade': apartamento, 'taxas': taxas})
    return resultado


def extrato(posicao, filtros, limites):
    """Formata a movimentação calculada; filtra somente após a conciliação."""
    tipo = filtros.get('tipo')
    if tipo not in ('completo', 'competencia', 'recebimento'):
        raise ValueError('Selecione um tipo de extrato válido.')
    escolhidos = filtros.get('apartamentos') or []
    if not isinstance(escolhidos, list) or not all(isinstance(a, str) for a in escolhidos):
        raise ValueError('Filtro de apartamentos inválido.')
    inicio = fim = None
    if tipo != 'completo':
        periodo = filtros.get('periodo')
        if not isinstance(periodo, list) or len(periodo) != 2 or not all(periodo):
            raise ValueError('Selecione o início e o fim do período.')
        if tipo == 'competencia':
            try:
                inicio, fim = (datetime.strptime(v, '%Y-%m').strftime('%Y-%m') for v in periodo)
            except (TypeError, ValueError):
                raise ValueError('Competência inválida.')
        else:
            inicio, fim = (_data(v) for v in periodo)
        if inicio > fim:
            raise ValueError('O início do período deve ser anterior ou igual ao fim.')
    corte = posicao['data_corte']
    if tipo == 'completo' and limites.get('fim'):
        fim_corte = corte.replace(day=calendar.monthrange(corte.year, corte.month)[1]).isoformat()
        limites = {**limites, 'fim': min(limites['fim'], fim_corte)}
    unidades = defaultdict(list)
    saldos_unidades = defaultdict(int)
    unidades_inconclusivas = set()
    for grupo in posicao['grupos']:
        apartamento, competencia = grupo['apartamento'], grupo['competencia']
        if escolhidos and apartamento not in escolhidos:
            continue
        if tipo == 'competencia' and not inicio <= competencia <= fim:
            continue
        if tipo == 'completo' and competencia > corte.strftime('%Y-%m'):
            continue
        if grupo.get('conciliacao_inconclusiva'):
            unidades_inconclusivas.add(apartamento)
        saldo_original = sum(s['principal_centavos'] for s in grupo['saldos']
                             if s['taxa']['vencimento'] < corte)
        saldos_unidades[apartamento] += saldo_original
        linhas = []
        marcados = {a.get('taxa_id') for a in grupo['ajustes_origem'] if a['tipo'] == 'R'}

        def incluir(id, data, descricao, nome, centavos, renegociado=False, desconto=0, informativo=False, ajuste_automatico=False, taxa_id=None):
            if data > corte or (tipo == 'recebimento' and not inicio <= data <= fim):
                return
            linhas.append({'id': id, 'data': data.isoformat(), 'descricao': descricao or '', 'tipo': nome,
                           'valor': centavos / 100, 'desconto_vista': desconto / 100,
                           'renegociado': renegociado, 'informativo': informativo, 'ajuste_automatico': ajuste_automatico,
                           'taxa_id': taxa_id})

        originais = {t['id']: t for t in grupo['taxas_origem']}
        encargos_agrupados = {}

        def acumular_encargo(taxa_id, data, centavos):
            if not centavos or data > corte or (tipo == 'recebimento' and not inicio <= data <= fim):
                return
            anterior = encargos_agrupados.get(taxa_id)
            encargos_agrupados[taxa_id] = (max(data, anterior[0]), anterior[1] + centavos) if anterior else (data, centavos)

        def descricao_encargos(taxa_id):
            descricao = originais[taxa_id].get('descricao')
            return f'Encargos calculados - {descricao}' if descricao else 'Encargos calculados - Taxa sem descrição'
        for taxa in grupo['taxas_origem']:
            origem = taxa.get('origem', taxa)
            nome = 'Parcela de renegociação' if taxa['tipo'] == 'P' else 'Cobrança'
            incluir(taxa['id'], taxa['vencimento'], taxa.get('descricao'), nome,
                    _centavos(origem.get('valor_original')), taxa['id'] in marcados,
                    _centavos(origem.get('desconto_vista')))
        for ajuste in grupo['ajustes_origem']:
            if ajuste['tipo'] != 'D':
                continue
            vinculada = originais.get(ajuste.get('taxa_id'))
            vencimento = ajuste.get('vencimento') or (vinculada and vinculada['vencimento'])
            if vencimento:
                incluir(ajuste['id'], _data(vencimento), ajuste.get('descricao'), 'Desconto',
                        -_centavos(ajuste.get('valor_original')), ajuste['id'] in marcados, taxa_id=ajuste.get('taxa_id'))
        recebimentos = {r['id']: r for r in grupo['recebimentos_origem']}
        parciais = {p['recebimento_id']: p for p in grupo['pagamentos_parciais']}
        for receita in grupo['recebimentos_origem']:
            valor = receita['valor_centavos']
            if valor < 0:
                incluir(receita['id'], receita['data'], receita.get('descricao'),
                        'Valor negativo de origem a esclarecer', valor)
            elif valor >= 0:
                parcial = parciais.get(receita['id'])
                excedente = parcial['nao_alocado_centavos'] if parcial else 0
                incluir(receita['id'], receita['data'], receita.get('descricao'), 'Recebimento', -valor)
                credito_ajuste = parcial['credito_ajuste_centavos'] if parcial else 0
                if excedente > credito_ajuste:
                    incluir(receita['id'], receita['data'], receita.get('descricao'),
                            'Excedente de origem não identificada', -(excedente - credito_ajuste), informativo=True,
                            ajuste_automatico=parcial['ajuste_automatico'])
                if parcial:
                    creditos_por_data = defaultdict(int)
                    for credito in parcial['creditos_ajuste']:
                        creditos_por_data[credito['data']] += credito['valor_centavos']
                    for data_credito, valor_credito in creditos_por_data.items():
                        if valor_credito:
                            incluir(receita['id'], data_credito, receita.get('descricao'),
                                    'Excedente de origem não identificada', -valor_credito, informativo=True,
                                    ajuste_automatico=parcial['ajuste_automatico'])
                    if not parcial.get('quitacao_exata'):
                        for alocacao in parcial['alocacoes']:
                            acumular_encargo(alocacao['taxa_id'], alocacao['data'],
                                             alocacao['juros_centavos'] + alocacao['multa_centavos'])
        for numero, quitacao in enumerate(grupo['quitacoes_exatas'], 1):
            data = max(recebimentos[i]['data'] for i in quitacao['recebimentos'])
            detalhes = quitacao['detalhes']
            for saldo in detalhes['saldos']:
                if saldo['desconto_concedido_centavos']:
                    incluir(-saldo['taxa']['id'], saldo['desconto_data'], saldo['taxa'].get('descricao'),
                            'Desconto à vista', -saldo['desconto_concedido_centavos'], taxa_id=saldo['taxa']['id'])
            for pagamento in detalhes['recebimentos']:
                for alocacao in pagamento['alocacoes']:
                    acumular_encargo(alocacao['taxa_id'], recebimentos[pagamento['recebimento_id']]['data'],
                                     alocacao['juros_centavos'] + alocacao['multa_centavos'])
            for saldo in detalhes['saldos']:
                acumular_encargo(saldo['taxa']['id'], data, saldo['juros_centavos'] + saldo['multa_centavos'])
            if quitacao['diferenca_centavos']:
                incluir(-numero, data, 'Diferença de encargos', 'Diferença', quitacao['diferenca_centavos'],
                        ajuste_automatico=quitacao['ajuste_automatico'],
                        taxa_id=quitacao['taxas'][0] if len(quitacao['taxas']) == 1 else None)
        for saldo in grupo['saldos']:
            if saldo.get('desconto_concedido_centavos'):
                incluir(-saldo['taxa']['id'], saldo['desconto_data'], saldo['taxa'].get('descricao'),
                        'Desconto à vista', -saldo['desconto_concedido_centavos'], taxa_id=saldo['taxa']['id'])
        for taxa_id, (data_encargo, encargos) in encargos_agrupados.items():
            incluir(-taxa_id, data_encargo, descricao_encargos(taxa_id), 'Acréscimo', encargos, taxa_id=taxa_id)
        linhas.sort(key=lambda l: (l['data'], 0 if l['valor'] >= 0 else 1,
                                  -l['valor'] if l['valor'] >= 0 else l['valor'], l['tipo'], str(l['id'])))
        subtotal = sum(_centavos(l['valor']) for l in linhas if not l['renegociado'] and not l['informativo'])
        # A visualização reparte recebimentos conforme as alocações reais,
        # mantendo a lista e os totais originais para os demais consumidores.
        alocacoes = defaultdict(lambda: defaultdict(int))
        pagamentos = [p for q in grupo['quitacoes_exatas'] for p in q['detalhes']['recebimentos']]
        pagamentos += [p for p in grupo['pagamentos_parciais'] if not p.get('quitacao_exata')]
        for pagamento in pagamentos:
            for alocacao in pagamento['alocacoes']:
                alocacoes[pagamento['recebimento_id']][alocacao['taxa_id']] += sum(
                    alocacao[campo] for campo in ('principal_centavos', 'juros_centavos', 'multa_centavos'))
        for quitacao in grupo['quitacoes_exatas']:
            if quitacao['diferenca_centavos'] > 0 and len(quitacao['taxas']) == 1:
                for pagamento in quitacao['detalhes']['recebimentos']:
                    alocacoes[pagamento['recebimento_id']][quitacao['taxas'][0]] += pagamento['nao_alocado_centavos']
        vinculados = defaultdict(list)
        avulsos = []

        def aglutinar(itens):
            grupos = {}
            for item in itens:
                chave = (item.get('taxa_id'), item['data'], item['descricao'], item['tipo'],
                         item['renegociado'], item['informativo'], item['ajuste_automatico'], item['valor'] < 0)
                if chave not in grupos:
                    grupos[chave] = dict(item)
                else:
                    grupos[chave]['valor'] = (_centavos(grupos[chave]['valor']) + _centavos(item['valor'])) / 100
            return list(grupos.values())

        cobrancas = sorted((l for l in linhas if l['tipo'] in ('Cobrança', 'Parcela de renegociação')),
                           key=lambda l: (l['data'], -_centavos(l['valor']), str(l['id'])))
        for linha in linhas:
            if linha in cobrancas:
                continue
            if linha['tipo'] == 'Recebimento':
                repartido = 0
                for taxa_id, valor in alocacoes[linha['id']].items():
                    if valor:
                        vinculados[taxa_id].append({**linha, 'valor': -valor / 100, 'taxa_id': taxa_id})
                        repartido += valor
                restante = -_centavos(linha['valor']) - repartido
                if restante:
                    avulsos.append({**linha, 'valor': -restante / 100})
            elif linha.get('taxa_id') in originais:
                vinculados[linha['taxa_id']].append(linha)
            else:
                avulsos.append(linha)
        pares = []
        for cobranca in cobrancas:
            relacionados = aglutinar(vinculados.pop(cobranca['id'], []))
            acrescimos = sorted((l for l in relacionados if l['valor'] >= 0),
                                key=lambda l: (-_centavos(l['valor']), l['tipo'], str(l['id'])))
            movimentos = sorted((l for l in relacionados if l['valor'] < 0),
                                key=lambda l: (l['data'], _centavos(l['valor']), l['tipo'], str(l['id'])))
            pares.extend({'taxa': taxa, 'movimento': movimento}
                         for taxa, movimento in zip_longest([cobranca, *acrescimos], movimentos))
        avulsos += [linha for relacionados in vinculados.values() for linha in relacionados]
        avulsos = aglutinar(avulsos)
        pares += [{'taxa': linha if linha['valor'] >= 0 else None,
                   'movimento': linha if linha['valor'] < 0 else None} for linha in sorted(
            avulsos, key=lambda l: (l['data'], _centavos(l['valor']), l['tipo'], str(l['id'])))]
        if tipo == 'recebimento' and not linhas:
            continue
        unidades[apartamento].append({'competencia': competencia, 'lancamentos': linhas, 'pares': pares,
                                      'subtotal': subtotal / 100, 'saldo_original': None if grupo.get('conciliacao_inconclusiva') else saldo_original / 100,
                                      'conciliacao_inconclusiva': bool(grupo.get('conciliacao_inconclusiva'))})
    resultado = []
    apartamentos = escolhidos or posicao.get('apartamentos', [])
    for apartamento in sorted(set(unidades) | set(apartamentos) | set(saldos_unidades)):
        competencias = sorted(unidades[apartamento], key=lambda g: g['competencia'])
        subtotal = sum(_centavos(g['subtotal']) for g in competencias)
        resultado.append({'apartamento': apartamento, 'competencias': competencias, 'subtotal': subtotal / 100,
                          'saldo_original': None if apartamento in unidades_inconclusivas else saldos_unidades[apartamento] / 100})
    total = sum(_centavos(u['subtotal']) for u in resultado)
    saldo_original = None if unidades_inconclusivas else sum(_centavos(u['saldo_original']) for u in resultado)
    return {'limites': limites, 'data_corte': corte.isoformat(), 'tipo': tipo,
            'apartamentos': resultado, 'total': total / 100, 'saldo_original': None if saldo_original is None else saldo_original / 100}
