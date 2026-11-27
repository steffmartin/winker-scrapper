"""Busca de quitações e distribuição de pagamentos."""

from datetime import date
from decimal import Decimal, ROUND_HALF_DOWN
from itertools import combinations, groupby
from bff.conciliacao.valores import (ConciliacaoInconclusiva, _centavos, _data,
    _validar_detalhes_quitacao, calcular_encargos)
from bff.conciliacao.dados import aplicar_ajustes



def distribuir_parciais(taxas, recebimentos, data_corte, modalidade, ajustes=None, habilitar_desconto=False,
                         desconto_agrupado=False, ordem_taxas=None, reservas=None, data_reserva=None,
                         priorizar_exatos=False):
    """Distribui recebimentos remanescentes sem alterar os registros de origem.

    O principal é amortizado primeiro, seguido de juros e multa. A multa é
    fixada na primeira movimentação após o vencimento (ou na data de corte);
    não é cobrada de novo. Os juros de cada intervalo são arredondados em
    centavos ao fechar o intervalo, antes do pagamento. Na modalidade J,
    juros posteriores incidem também sobre a multa ainda em aberto.

    Esta etapa recebe somente valores ainda não usados nas correspondências
    exatas. Valores negativos são devolvidos sem aplicação.
    """
    corte = _data(data_corte)
    if modalidade not in ('N', 'M', 'J'):
        raise ValueError('Modalidade de encargos inválida.')
    chaves = {(t['apartamento'], t['competencia']) for t in taxas + recebimentos}
    if len(chaves) > 1:
        raise ValueError('A distribuição deve conter uma única unidade e competência.')
    ajustes = ajustes or []
    eventos = []
    vigentes = []
    for ajuste in ajustes:
        valor_data = ajuste.get('vencimento') if ajuste['tipo'] == 'D' else ajuste.get('data_renegociacao')
        if valor_data:
            eventos.append((_data(valor_data), ajuste))
        else:
            vigentes.append(ajuste)
    eventos.sort(key=lambda evento: (evento[0], str(evento[1]['id'])))
    taxas_iniciais = aplicar_ajustes({'taxas': taxas, 'ajustes': vigentes}) if ajustes else taxas
    saldos = []
    for taxa in taxas_iniciais:
        principal = taxa['valor_centavos']
        if not isinstance(principal, int) or principal < 0:
            raise ValueError('Principal inválido.')
        saldos.append({'taxa': taxa, 'principal_centavos': principal,
                       'juros_centavos': 0, 'multa_centavos': 0,
                       'ultima_data': taxa['vencimento'], 'multa_aplicada': False, 'principal_pago_centavos': 0,
                       'desconto_concedido_centavos': 0, 'desconto_data': None,
                       'alocacoes': []})
    saldos.sort(key=lambda s: (s['taxa']['vencimento'], -s['taxa']['valor_centavos'], str(s['taxa']['id'])))
    if ordem_taxas is not None:
        ordem = {taxa_id: indice for indice, taxa_id in enumerate(ordem_taxas)}
        if len(ordem) != len(saldos) or any(s['taxa']['id'] not in ordem for s in saldos):
            raise ValueError('Ordem de taxas inválida.')
        saldos.sort(key=lambda s: ordem[s['taxa']['id']])

    def atualizar(saldo, data):
        taxa = saldo['taxa']
        if data <= taxa['vencimento'] or data <= saldo['ultima_data']:
            return
        dias = (data - saldo['ultima_data']).days
        if not saldo['multa_aplicada']:
            encargos = calcular_encargos(saldo['principal_centavos'], taxa.get('juros_mes_percentual'),
                                         taxa.get('multa_percentual'), dias, modalidade)
            saldo['juros_centavos'] += encargos['juros_centavos']
            saldo['multa_centavos'] += encargos['multa_centavos']
            saldo['multa_aplicada'] = True
        else:
            base = saldo['principal_centavos']
            if modalidade == 'J':
                base += saldo['multa_centavos']
            juros = (Decimal(base) * Decimal(str(taxa.get('juros_mes_percentual') or 0))
                     * dias / Decimal(3000))
            saldo['juros_centavos'] += int(juros.quantize(Decimal('1'), rounding=ROUND_HALF_DOWN))
        saldo['ultima_data'] = data

    indice_evento = 0
    pagamentos = []
    pagamentos_por_id = {}
    reservas = reservas or {}
    recebimentos_reservados = {item for grupo in reservas.values() for item in grupo}

    def saldo_exato(recebimento_id, valor, data):
        if not priorizar_exatos or valor <= 0:
            return None
        for saldo in saldos:
            taxa = saldo['taxa']
            if (taxa['id'] in reservas and recebimento_id not in reservas[taxa['id']]
                    and data_reserva is not None and data <= data_reserva):
                continue
            if taxa.get('tipo') == 'P' and taxa.get('data_renegociacao') and data < _data(taxa['data_renegociacao']):
                continue
            atualizar(saldo, data)
            desconto = (min(saldo['principal_centavos'], _centavos(taxa.get('desconto_vista')))
                        if habilitar_desconto and data <= taxa['vencimento']
                        and not saldo['desconto_concedido_centavos'] else 0)
            devido = saldo['principal_centavos'] - desconto + saldo['juros_centavos'] + saldo['multa_centavos']
            if devido == valor:
                return saldo
        return None

    def alocar(pagamento, disponivel, data):
        exato = saldo_exato(pagamento['recebimento_id'], disponivel, data)
        ordem_saldos = ([exato] + [s for s in saldos if s is not exato]) if exato else saldos
        for saldo in ordem_saldos:
            if (saldo['taxa']['id'] in reservas and pagamento['recebimento_id'] not in reservas[saldo['taxa']['id']]
                    and data_reserva is not None and data <= data_reserva):
                continue
            if (saldo['taxa'].get('tipo') == 'P' and saldo['taxa'].get('data_renegociacao')
                    and data < _data(saldo['taxa']['data_renegociacao'])):
                continue
            atualizar(saldo, data)
            desconto = min(saldo['principal_centavos'], _centavos(saldo['taxa'].get('desconto_vista')))
            necessario = saldo['principal_centavos'] - desconto
            valor_suficiente = disponivel >= necessario if desconto_agrupado else disponivel == necessario
            if (habilitar_desconto and desconto > 0 and necessario > 0 and valor_suficiente
                    and not saldo['desconto_concedido_centavos'] and data <= saldo['taxa']['vencimento']):
                saldo['principal_centavos'] -= desconto
                saldo['desconto_concedido_centavos'] = desconto
                saldo['desconto_data'] = data
            componentes = {}
            for nome in ('principal_centavos', 'juros_centavos', 'multa_centavos'):
                valor = min(disponivel, saldo[nome])
                saldo[nome] -= valor
                disponivel -= valor
                componentes[nome] = valor
                if nome == 'principal_centavos':
                    saldo['principal_pago_centavos'] += valor
            if any(componentes.values()):
                alocacao = {'taxa_id': saldo['taxa']['id'], 'recebimento_id': pagamento['recebimento_id'],
                            'data': data, **componentes}
                saldo['alocacoes'].append(alocacao)
                pagamento['alocacoes'].append(alocacao)
                pagamento['movimentacoes'].append(dict(alocacao, motivo='alocacao'))
            if disponivel == 0:
                break
        return disponivel

    def aplicar_eventos_ate(data):
        nonlocal indice_evento
        while indice_evento < len(eventos) and eventos[indice_evento][0] <= data:
            data_evento = eventos[indice_evento][0]
            while indice_evento < len(eventos) and eventos[indice_evento][0] == data_evento:
                vigentes.append(eventos[indice_evento][1])
                indice_evento += 1
            taxas_ajustadas = aplicar_ajustes({'taxas': taxas, 'ajustes': vigentes})
            por_id = {(t['apartamento'], t['id']): t for t in taxas_ajustadas}
            for saldo in saldos:
                anterior = saldo['taxa']
                atual = por_id[(anterior['apartamento'], anterior['id'])]
                if any(Decimal(str(anterior.get(campo) or 0)) != Decimal(str(atual.get(campo) or 0))
                       for campo in ('valor_centavos', 'multa_percentual', 'juros_mes_percentual')):
                    atualizar(saldo, data_evento)
                saldo['taxa'] = atual
                if saldo['desconto_concedido_centavos'] > atual['valor_centavos']:
                    raise ConciliacaoInconclusiva('Ajuste posterior excede o valor da cobrança com desconto concedido.')
                excesso = max(0, saldo['principal_pago_centavos'] + saldo['desconto_concedido_centavos'] - atual['valor_centavos'])
                for alocacao in reversed(saldo['alocacoes']):
                    if not excesso:
                        break
                    liberado = min(excesso, alocacao['principal_centavos'])
                    if not liberado:
                        continue
                    alocacao['principal_centavos'] -= liberado
                    saldo['principal_pago_centavos'] -= liberado
                    excesso -= liberado
                    pagamento = pagamentos_por_id[alocacao['recebimento_id']]
                    pagamento['nao_alocado_centavos'] += liberado
                    pagamento['credito_ajuste_centavos'] += liberado
                    pagamento['creditos_ajuste'].append({'data': data_evento, 'valor_centavos': liberado})
                    pagamento['movimentacoes'].append({'taxa_id': atual['id'], 'recebimento_id': pagamento['recebimento_id'],
                        'data': data_evento, 'principal_centavos': -liberado, 'juros_centavos': 0,
                        'multa_centavos': 0, 'motivo': 'ajuste_posterior'})
                saldo['principal_centavos'] = max(0, atual['valor_centavos'] - saldo['principal_pago_centavos'] - saldo['desconto_concedido_centavos'])
                desconto = min(saldo['principal_centavos'], _centavos(atual.get('desconto_vista')))
                if (habilitar_desconto and desconto > 0 and saldo['principal_pago_centavos'] > 0
                        and not saldo['desconto_concedido_centavos'] and data_evento <= atual['vencimento']
                        and saldo['principal_centavos'] == desconto):
                    saldo['principal_centavos'] -= desconto
                    saldo['desconto_concedido_centavos'] = desconto
                    saldo['desconto_data'] = data_evento
            for pagamento in pagamentos:
                credito = pagamento['credito_ajuste_centavos']
                if credito > 0:
                    restante = alocar(pagamento, credito, data_evento)
                    usado = credito - restante
                    pagamento['credito_ajuste_centavos'] = restante
                    pagamento['nao_alocado_centavos'] -= usado
                    for item in pagamento['creditos_ajuste']:
                        consumido = min(usado, item['valor_centavos'])
                        item['valor_centavos'] -= consumido
                        usado -= consumido
                        if not usado:
                            break

    receitas_ordenadas = sorted(recebimentos, key=lambda r: (r['data'], r['id'] not in recebimentos_reservados,
                                                             -r['valor_centavos'], str(r['id'])))
    receitas_por_data = groupby(receitas_ordenadas, key=lambda r: _data(r['data']))
    for data, receitas_dia in receitas_por_data:
        if data > corte:
            continue
        aplicar_eventos_ate(data)
        pendentes = list(receitas_dia)
        while pendentes:
            indice = next((i for i, r in enumerate(pendentes)
                           if saldo_exato(r['id'], r['valor_centavos'], data)), 0)
            receita = pendentes.pop(indice)
            disponivel = receita['valor_centavos']
            pagamentos.append({'recebimento_id': receita['id'], 'valor_centavos': disponivel,
                               'alocacoes': [], 'movimentacoes': [], 'credito_ajuste_centavos': 0, 'creditos_ajuste': [],
                               'nao_alocado_centavos': disponivel})
            pagamento = pagamentos[-1]
            pagamentos_por_id[receita['id']] = pagamento
            if disponivel <= 0:
                continue
            pagamento['nao_alocado_centavos'] = alocar(pagamento, disponivel, data)
    aplicar_eventos_ate(corte)
    for saldo in saldos:
        atualizar(saldo, corte)
        saldo['total_centavos'] = saldo['principal_centavos'] + saldo['juros_centavos'] + saldo['multa_centavos']
    return {'saldos': saldos, 'recebimentos': pagamentos}
