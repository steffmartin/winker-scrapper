"""Consulta independente do extrato de recebimentos."""
import calendar
import json
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

import models


def _data(valor):
    for formato in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(valor, formato).date()
        except (ValueError, TypeError):
            pass
    raise ValueError(f'Data ausente ou inválida: {valor or "não informada"}.')


def _mes(valor):
    try:
        return datetime.strptime(valor, '%Y-%m').date().replace(day=1)
    except (TypeError, ValueError):
        raise ValueError(f'Competência inválida: {valor or "não informada"}.')


def _meses(inicio, fim):
    atual = inicio.replace(day=1)
    while atual <= fim:
        yield atual.strftime('%Y-%m')
        atual = date(atual.year + (atual.month == 12), atual.month % 12 + 1, 1)


def _centavos(valor):
    return int((Decimal(str(valor or 0)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _chave_ordenacao_linha(linha):
    valor = linha['valor']
    return (linha['data'], 0 if valor >= 0 else 1, -valor if valor >= 0 else valor, linha['id'])


def _conciliar_lancamentos(linhas):
    """Gera ajustes apenas na resposta, sem modificar os registros de origem."""
    linhas = [dict(linha) for linha in linhas]
    positivas = [i for i, linha in enumerate(linhas) if not linha['renegociado'] and _centavos(linha['valor']) > 0]
    negativas = [i for i, linha in enumerate(linhas) if not linha['renegociado'] and _centavos(linha['valor']) < 0]
    usadas = set()

    # Esgota combinações com recebimento na mesma data antes de usar outras datas.
    for mesma_data in (True, False):
        def data_compativel(cobranca, outra):
            return (cobranca['data'] == outra['data']) == mesma_data

        for i in positivas:
            if i in usadas:
                continue
            j = next((j for j in negativas if j not in usadas and data_compativel(linhas[i], linhas[j])
                      and _centavos(linhas[i]['valor']) == -_centavos(linhas[j]['valor'])), None)
            if j is not None:
                usadas.update((i, j))

        for i in positivas:
            linha = linhas[i]
            desconto = _centavos(linha['desconto_vista'])
            if i in usadas or desconto <= 0:
                continue
            esperado = _centavos(linha['valor']) - desconto
            if esperado <= 0:
                continue
            j = next((j for j in negativas if j not in usadas and linhas[j]['tipo'] == 'Recebimento'
                      and data_compativel(linha, linhas[j]) and -_centavos(linhas[j]['valor']) == esperado), None)
            if j is None:
                continue
            usadas.update((i, j))
            linha['desconto_vista'] = 0
            linhas.append({'id': -linha['id'], 'data': linhas[j]['data'], 'descricao': linha['descricao'],
                           'tipo': 'Desconto à vista', 'valor': -desconto / 100, 'desconto_vista': 0,
                           'renegociado': False, 'ordem': 0})

        # Um desconto registrado na data da cobrança pode compor o valor exato.
        for i in positivas:
            linha = linhas[i]
            desconto_vista = _centavos(linha['desconto_vista'])
            if i in usadas or desconto_vista <= 0:
                continue
            combinado = next(((j, k, desconto_efetivo) for j in negativas
                              if j not in usadas and linhas[j]['tipo'] == 'Desconto' and linhas[j]['data'] == linha['data']
                              for desconto_efetivo in [desconto_vista - _centavos(linhas[j]['desconto_vista'])]
                              if desconto_efetivo > 0
                              for k in negativas
                              if k not in usadas and linhas[k]['tipo'] == 'Recebimento' and data_compativel(linha, linhas[k])
                              and _centavos(linha['valor']) + _centavos(linhas[j]['valor']) + _centavos(linhas[k]['valor']) == desconto_efetivo), None)
            if combinado is None:
                continue
            j, k, desconto_efetivo = combinado
            usadas.update((i, j, k))
            linha['desconto_vista'] = 0
            linhas.append({'id': -linha['id'], 'data': linhas[k]['data'], 'descricao': linha['descricao'],
                           'tipo': 'Desconto à vista', 'valor': -desconto_efetivo / 100, 'desconto_vista': 0,
                           'renegociado': False, 'ordem': 0})

    cobrancas = [linhas[i] for i in positivas if i not in usadas]
    recebimentos = [linhas[i] for i in negativas if i not in usadas and linhas[i]['tipo'] == 'Recebimento']
    if positivas and recebimentos:
        residual = sum(-_centavos(linha['valor']) for linha in recebimentos) - sum(_centavos(linha['valor']) for linha in cobrancas)
        if residual > 0:
            linhas.append({'id': -1, 'data': max(linha['data'] for linha in recebimentos),
                           'descricao': 'Juros, multas e/ou correções', 'tipo': 'Acréscimo',
                           'valor': residual / 100, 'desconto_vista': 0, 'renegociado': False, 'ordem': 0})
    return linhas


def gerar(condo_id, filtros):
    condo = models.Condominio.get_or_none(id=condo_id)
    if not condo:
        raise ValueError('Condomínio não encontrado.')
    meses = sorted(_mes(m.competencia) for m in models.Meses.select().where(models.Meses.condominio_id == condo_id) if m.competencia)
    if not meses:
        raise ValueError('Não há meses cadastrados para este condomínio.')
    limites = {'inicio': meses[0].isoformat(), 'fim': meses[-1].replace(day=calendar.monthrange(meses[-1].year, meses[-1].month)[1]).isoformat()}
    if filtros.get('limites'):
        return {'limites': limites}

    tipo = filtros.get('tipo')
    if tipo not in ('completo', 'competencia', 'recebimento'):
        raise ValueError('Selecione um tipo de extrato válido.')
    selecionados = filtros.get('apartamentos') or []
    if not isinstance(selecionados, list) or not all(isinstance(a, str) for a in selecionados):
        raise ValueError('Filtro de apartamentos inválido.')
    apartamentos = json.loads(condo.apartamentos) if condo.apartamentos else []
    if not isinstance(apartamentos, list):
        raise ValueError('Cadastro de apartamentos inválido.')
    unidades = list(dict.fromkeys(selecionados or apartamentos))
    if tipo == 'completo':
        corte = date.today()
        inicio, fim = meses[0], min(meses[-1], corte.replace(day=1))
        limites = {**limites, 'fim': fim.replace(day=calendar.monthrange(fim.year, fim.month)[1]).isoformat()}
    else:
        periodo = filtros.get('periodo')
        if not isinstance(periodo, list) or len(periodo) != 2 or not all(periodo):
            raise ValueError('Selecione o início e o fim do período.')
        inicio, fim = (_mes(v) for v in periodo) if tipo == 'competencia' else (_data(v) for v in periodo)
        if inicio > fim:
            raise ValueError('O início do período deve ser anterior ou igual ao fim.')
        corte = fim.replace(day=calendar.monthrange(fim.year, fim.month)[1]) if tipo == 'competencia' else fim

    taxas = list(models.Taxas.select().where(models.Taxas.condominio_id == condo_id))
    renegociadas = set()
    for taxa in taxas:
        if taxa.tipo == 'R' and taxa.taxa_id_id and taxa.renegociacao_id_id:
            if _data(taxa.renegociacao_id.data_renegociacao) <= corte:
                renegociadas.add((taxa.taxa_id_id, taxa.apartamento))

    registros = []
    nomes = {'C': 'Cobrança', 'E': 'Cobrança', 'I': 'Cobrança', 'P': 'Parcela de renegociação', 'D': 'Desconto'}

    def adicionar(apto, competencia, data, item):
        comp = _mes(competencia).strftime('%Y-%m') if competencia else None
        if tipo in ('completo', 'competencia') and comp and not (inicio <= _mes(comp) <= fim):
            return
        if tipo == 'competencia' and not comp:
            return
        if tipo == 'recebimento' and not (inicio <= data <= fim):
            return
        registros.append((apto, comp, data, item))

    for taxa in taxas:
        if taxa.tipo not in nomes:
            continue  # R representa o vínculo de renegociação, não um lançamento adicional.
        destinos = unidades if taxa.tipo in ('C', 'E') else [taxa.apartamento]
        for apto in destinos:
            if selecionados and apto not in selecionados:
                continue
            if not apto:
                continue
            dt = _data(taxa.vencimento)
            item = {'data': dt.isoformat(), 'descricao': taxa.descricao or '', 'tipo': nomes[taxa.tipo],
                    'valor': (-1 if taxa.tipo == 'D' else 1) * abs(taxa.valor_original or 0),
                    'desconto_vista': taxa.desconto_vista or 0,
                    'renegociado': (taxa.id, apto) in renegociadas, 'ordem': 0, 'id': taxa.id}
            adicionar(apto, taxa.competencia, dt, item)

    transacoes = (models.Transacoes.select(models.Transacoes).join(models.Subcategorias).join(models.Categorias).join(models.Meses)
                  .where((models.Meses.condominio_id == condo_id) & (models.Transacoes.tipo == 'R')))
    for transacao in transacoes:
        apto = transacao.apartamento or None
        if selecionados and apto not in selecionados:
            continue
        dt = _data(transacao.data)
        item = {'data': dt.isoformat(), 'descricao': transacao.descricao or '', 'tipo': 'Recebimento',
                'valor': -abs(transacao.valor or 0), 'desconto_vista': 0, 'renegociado': False, 'ordem': 1, 'id': transacao.id}
        adicionar(apto, transacao.competencia, dt, item)
        if apto and apto not in unidades and not selecionados:
            unidades.append(apto)

    if tipo == 'recebimento':
        comps = sorted(comp for _, comp, _, _ in registros if comp)
        competencias = list(_meses(_mes(comps[0]), _mes(comps[-1]))) if comps else []
    else:
        competencias = list(_meses(inicio, fim))
    if any(apto is None for apto, _, _, _ in registros):
        unidades.append(None)
    unidades.sort(key=lambda apto: (apto is None, (apto or '').casefold()))
    grupos = []
    total_geral = 0
    for apto in unidades:
        itens_unidade = [r for r in registros if r[0] == apto]
        grupos_comp = []
        subtotal_unidade = 0
        for comp in competencias + ([None] if any(r[1] is None for r in itens_unidade) else []):
            linhas = [r[3] for r in itens_unidade if r[1] == comp]
            linhas.sort(key=_chave_ordenacao_linha)
            linhas = _conciliar_lancamentos(linhas)
            linhas.sort(key=_chave_ordenacao_linha)
            subtotal = sum(_centavos(linha['valor']) for linha in linhas if not linha['renegociado'])
            subtotal_unidade += subtotal
            grupos_comp.append({'competencia': comp, 'lancamentos': linhas, 'subtotal': subtotal / 100})
        grupos.append({'apartamento': apto, 'competencias': grupos_comp, 'subtotal': subtotal_unidade / 100})
        total_geral += subtotal_unidade
    return {'limites': limites, 'data_corte': corte.isoformat(), 'tipo': tipo, 'apartamentos': grupos, 'total': total_geral / 100}
