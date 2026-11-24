"""Extrato de conta: movimentos, saldos e subtotais por data."""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import models


def _centavos(valor):
    return int((Decimal(str(valor)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _data(valor):
    for formato in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(valor, formato).date()
        except (TypeError, ValueError):
            pass
    raise ValueError(f'Data de transação inválida: {valor or "não informada"}.')


def gerar(condo_id, filtros):
    periodo = filtros.get('periodo')
    if not isinstance(periodo, list) or len(periodo) != 2 or not all(periodo):
        raise ValueError('Selecione o início e o fim do período.')
    inicio, fim = map(_data, periodo)
    if inicio > fim:
        raise ValueError('O início do período deve ser anterior ou igual ao fim.')
    competencias = [mes.competencia for mes in models.Meses.select(models.Meses.competencia)
                    .where(models.Meses.condominio_id == condo_id) if mes.competencia]
    if not competencias:
        raise ValueError('Não há meses cadastrados para este condomínio.')
    try:
        inicio_historico = min(datetime.strptime(comp, '%Y-%m').date() for comp in competencias)
    except ValueError:
        raise ValueError('Há competência inválida nos meses cadastrados.')
    if inicio < inicio_historico:
        raise ValueError(f'O período não pode começar antes do primeiro mês cadastrado ({inicio_historico:%m/%Y}).')
    selecionadas = filtros.get('contas') or []
    if not isinstance(selecionadas, list) or not all(isinstance(c, str) for c in selecionadas):
        raise ValueError('Filtro de contas inválido.')
    cadastradas = list(models.Contas.select().where(models.Contas.condominio_id == condo_id))
    contas = {}
    for conta in cadastradas:
        if not conta.conta or conta.conta in contas:
            raise ValueError('Há contas sem nome ou com nomes duplicados no cadastro.')
        contas[conta.conta] = conta
    if any(nome not in contas for nome in selecionadas):
        raise ValueError('Uma das contas selecionadas não foi encontrada.')
    nomes = sorted(selecionadas or contas.keys(), key=str.casefold)
    for nome in nomes:
        if contas[nome].saldo_inicial is None:
            raise ValueError(f'Saldo inicial não informado para a conta {nome}.')
    movimentos = {nome: [] for nome in nomes}
    filtro_conta = models.Transacoes.conta.in_(nomes)
    if not selecionadas:
        filtro_conta = filtro_conta | models.Transacoes.conta.is_null(True) | (models.fn.TRIM(models.Transacoes.conta) == '')
    consulta = (models.Transacoes.select(models.Transacoes).join(models.Subcategorias).join(models.Categorias).join(models.Meses)
                .where((models.Meses.condominio_id == condo_id) & filtro_conta))
    for t in consulta:
        if t.tipo not in ('R', 'D') or t.valor is None:
            raise ValueError(f'Transação {t.id} possui tipo ou valor inválido.')
        data = _data(t.data)
        if data < inicio_historico:
            continue
        valor = _centavos(t.valor) * (1 if t.tipo == 'R' else -1)
        conta_movimento = t.conta if t.conta and t.conta.strip() else None
        if conta_movimento is None:
            if data > fim:
                continue
            if None not in movimentos:
                movimentos[None] = []
                nomes.append(None)
        movimentos[conta_movimento].append({'id': t.id, 'data': data.isoformat(), 'descricao': t.descricao or '',
                                   'tipo': 'Receita' if t.tipo == 'R' else 'Despesa', 'centavos': valor,
                                   'pendente_revisao': not t.consistente and not t.revisado_usuario})
    if not nomes:
        raise ValueError('Não há contas cadastradas ou lançamentos sem conta para este condomínio.')
    resultado = []
    saldo_global = 0
    for nome in nomes:
        todos = sorted(movimentos[nome], key=lambda t: (t['data'], -t['centavos'], t['id']))
        saldo = (_centavos(contas[nome].saldo_inicial) if nome is not None else 0) + sum(t['centavos'] for t in todos if t['data'] < inicio.isoformat())
        anterior = saldo
        meses = {}
        total_conta = 0
        for t in todos:
            if not inicio.isoformat() <= t['data'] <= fim.isoformat():
                continue
            mes, dia = t['data'][:7], t['data']
            mes_obj = meses.setdefault(mes, {'mes': mes, 'dias': {}, '_subtotal': 0})
            dia_obj = mes_obj['dias'].setdefault(dia, {'data': dia, 'transacoes': [], '_subtotal': 0})
            valor = t['centavos']
            saldo += valor
            total_conta += valor
            mes_obj['_subtotal'] += valor
            dia_obj['_subtotal'] += valor
            dia_obj['transacoes'].append({'id': t['id'], 'data': dia, 'descricao': t['descricao'], 'tipo': t['tipo'], 'valor': valor / 100, 'saldo': saldo / 100})
            dia_obj['saldo_final'] = saldo / 100
        grupos = []
        for mes_obj in meses.values():
            dias = []
            for dia_obj in mes_obj['dias'].values():
                dia_obj['subtotal'] = dia_obj.pop('_subtotal') / 100
                dias.append(dia_obj)
            grupos.append({'mes': mes_obj['mes'], 'dias': dias, 'subtotal': mes_obj['_subtotal'] / 100})
        resultado.append({'conta': nome if nome is not None else 'CONTA NÃO IDENTIFICADA', 'saldo_anterior': anterior / 100, 'meses': grupos,
                          'subtotal': total_conta / 100, 'saldo_final': saldo / 100,
                          'provisorio': any(t['pendente_revisao'] for t in todos if t['data'] <= fim.isoformat())})
        saldo_global += saldo
    return {'periodo': [inicio.isoformat(), fim.isoformat()], 'contas': resultado, 'saldo_global': saldo_global / 100}
