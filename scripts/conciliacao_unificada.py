"""Conciliação de cobranças e recebimentos sem escrita no banco.

Os registros de origem e as alocações são preservados. Valores são convertidos
a centavos com arredondamento decimal HALF_DOWN; buscas limitadas sinalizam
resultado inconclusivo em vez de retornar quitações parciais como completas.
"""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_DOWN
from itertools import combinations, permutations
from math import factorial
from collections import defaultdict


class ConciliacaoInconclusiva(Exception):
    """O limite de busca foi atingido; não há resultado financeiro confiável."""


def _data(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    for formato in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(valor, formato).date()
        except (TypeError, ValueError):
            pass
    raise ValueError(f'Data inválida: {valor!r}')


def _centavos(valor):
    numero = Decimal(str(valor if valor is not None else 0))
    if not numero.is_finite():
        raise ValueError('Valor monetário não finito.')
    return int((numero * 100).quantize(Decimal('1'), rounding=ROUND_HALF_DOWN))


def calcular_encargos(principal_centavos, juros_mensal, multa_percentual, dias, modalidade):
    """Calcula posição sem pagamentos parciais, com total arredondado uma vez.

    Os componentes brutos são preservados. A multa exibida é arredondada
    separadamente e os juros recebem o resíduo para que os componentes somem
    ao total; o ajuste com relação ao arredondamento independente é informado.
    Esta convenção provisória não comprova a política aplicada em um boleto.
    """
    if modalidade not in ('N', 'M', 'J') or dias < 0 or principal_centavos < 0:
        raise ValueError('Parâmetros de encargos inválidos.')
    principal = Decimal(principal_centavos) / 100
    juros_taxa = Decimal(str(juros_mensal or 0)) / 3000 * dias
    multa_taxa = Decimal(str(multa_percentual or 0)) / 100 if dias else Decimal(0)
    if not juros_taxa.is_finite() or not multa_taxa.is_finite() or juros_taxa < 0 or multa_taxa < 0:
        raise ValueError('Percentual de encargos inválido.')
    multa = principal * multa_taxa
    juros = (principal + multa if modalidade == 'J' else principal) * juros_taxa
    if modalidade == 'M':
        multa = (principal + juros) * multa_taxa
    total = _centavos(principal + juros + multa)
    multa_centavos = _centavos(multa)
    juros_centavos = total - principal_centavos - multa_centavos
    return {'principal_centavos': principal_centavos, 'juros_centavos': juros_centavos,
            'multa_centavos': multa_centavos, 'total_centavos': total,
            'juros_bruto': juros, 'multa_bruta': multa,
            'ajuste_arredondamento_centavos': juros_centavos - _centavos(juros)}


def _validar_detalhes_quitacao(detalhes, desconto, encargos, diferenca):
    saldos = detalhes['saldos']
    pagamentos = detalhes['recebimentos']
    desconto_calculado = sum(s['desconto_concedido_centavos'] for s in saldos)
    pendente = sum(s['juros_centavos'] + s['multa_centavos'] for s in saldos)
    pago = sum(a['juros_centavos'] + a['multa_centavos'] for p in pagamentos for a in p['alocacoes'])
    excedente = sum(p['nao_alocado_centavos'] for p in pagamentos)
    if (any(s['principal_centavos'] for s in saldos) or desconto_calculado != desconto
            or pago + pendente != encargos or excedente - pendente != diferenca):
        raise ConciliacaoInconclusiva('Não foi possível reproduzir os componentes da quitação.')


def consultar(conexao, condominio_id, apartamentos=None):
    """Consulta registros de um condomínio na conexão fornecida pelo chamador.

    A função executa apenas SELECT. O chamador deve fornecer uma conexão
    aberta em modo somente leitura ao usar o banco oficial.
    """
    def linhas(sql, parametros):
        cursor = conexao.execute(sql, parametros)
        nomes = [coluna[0] for coluna in cursor.description]
        return [dict(zip(nomes, linha)) for linha in cursor.fetchall()]

    unidades = list(dict.fromkeys(apartamentos or []))
    parametros = [condominio_id]
    filtro_taxas = filtro_receitas = ''
    if unidades:
        marcadores = ','.join('?' for _ in unidades)
        filtro_taxas = f" AND (t.tipo IN ('C', 'E') OR t.apartamento IN ({marcadores}))"
        filtro_receitas = f' AND t.apartamento IN ({marcadores})'
        parametros.extend(unidades)

    taxas = linhas('''SELECT t.*, r.data_renegociacao
        FROM taxas AS t LEFT JOIN renegociacao AS r
          ON r.id = t.renegociacao_id AND r.condominio_id = t.condominio_id
        WHERE t.condominio_id = ?''' + filtro_taxas, parametros)
    receitas = linhas('''SELECT t.*, m.condominio_id
        FROM transacoes AS t
        JOIN subcategorias AS s ON s.id = t.subcategoria_id
        JOIN categorias AS c ON c.id = s.categoria_id
        JOIN meses AS m ON m.id = c.mes_id
        WHERE m.condominio_id = ? AND t.tipo = 'R' ''' + filtro_receitas, parametros)
    return taxas, receitas


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
                                modalidade, habilitar_desconto=(prioridade == 1), desconto_agrupado=True)
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
                                          habilitar_desconto=(prioridade == 1), desconto_agrupado=(chave_selecao[2] == 0))
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


def normalizar(condominio_id, data_corte, apartamentos, taxas, recebimentos, apartamentos_filtro=None):
    """Filtra dados de origem e expande taxas gerais sem inferir competência.

    Taxas futuras são mantidas para associar pagamentos antecipados; parcelas
    e marcadores só existem na posição depois da data da renegociação.
    Descontos sem data são mantidos como nos registros legados.
    """
    corte = _data(data_corte)
    unidades = list(dict.fromkeys(apartamentos_filtro or apartamentos))
    selecionados = set(apartamentos_filtro or [])
    taxas_resultado, ajustes, receitas = [], [], []
    for original in taxas:
        if original.get('condominio_id') != condominio_id:
            continue
        tipo = original.get('tipo')
        if selecionados and tipo not in ('C', 'E') and original.get('apartamento') not in selecionados:
            continue
        if tipo not in ('C', 'E', 'I', 'P', 'D', 'R'):
            continue
        if tipo in ('P', 'R'):
            data_renegociacao = original.get('data_renegociacao')
            if not data_renegociacao:
                raise ValueError('Parcela ou marcador sem data de renegociação.')
            if _data(data_renegociacao) > corte:
                continue
        if tipo == 'D' and original.get('vencimento') and _data(original['vencimento']) > corte:
            continue
        destinos = unidades if tipo in ('C', 'E') else [original.get('apartamento')]
        for apartamento in destinos:
            if not apartamento:
                continue
            item = dict(original, apartamento=apartamento)
            item['valor_centavos'] = _centavos(original.get('valor_original'))
            if original.get('vencimento'):
                item['vencimento'] = _data(original['vencimento'])
            if tipo in ('D', 'R'):
                ajustes.append(item)
            else:
                if not item.get('competencia') or not item.get('vencimento'):
                    raise ValueError('Cobrança sem competência ou vencimento.')
                taxas_resultado.append(item)
    for original in recebimentos:
        if original.get('condominio_id') != condominio_id or original.get('tipo') != 'R':
            continue
        apartamento, competencia = original.get('apartamento'), original.get('competencia')
        if selecionados and apartamento not in selecionados:
            continue
        if not isinstance(apartamento, str) or not apartamento.strip() or not isinstance(competencia, str) or not competencia.strip():
            continue
        data = _data(original.get('data'))
        if data <= corte:
            receitas.append(dict(original, data=data, valor_centavos=_centavos(original.get('valor'))))
    return {'taxas': taxas_resultado, 'ajustes': ajustes, 'recebimentos': receitas}


def aplicar_ajustes(dados):
    """Aplica descontos e marcadores vigentes a cópias das cobranças.

    Marcadores que apontam para descontos anulam o desconto em vez de abater
    novamente a cobrança; os demais marcadores reduzem a cobrança vinculada.
    A normalização deve ter filtrado previamente o corte e os acordos.
    """
    campos = ('valor_original', 'desconto_vista', 'multa_percentual', 'juros_mes_percentual')
    descontos = {(a['apartamento'], a['id']): a for a in dados['ajustes'] if a['tipo'] == 'D'}
    cancelamentos = {}
    for ajuste in dados['ajustes']:
        chave = (ajuste['apartamento'], ajuste.get('taxa_id'))
        if ajuste['tipo'] == 'R' and chave in descontos:
            soma = cancelamentos.setdefault(chave, {campo: Decimal(0) for campo in campos})
            for campo in campos:
                soma[campo] += Decimal(str(ajuste.get(campo) or 0))
    agregados = {}
    for ajuste in dados['ajustes']:
        chave_origem = (ajuste['apartamento'], ajuste.get('taxa_id'))
        if ajuste['tipo'] == 'R' and chave_origem in descontos:
            continue
        soma = agregados.setdefault(chave_origem, {campo: Decimal(0) for campo in campos})
        cancelado = cancelamentos.get((ajuste['apartamento'], ajuste['id']), {}) if ajuste['tipo'] == 'D' else {}
        for campo in campos:
            soma[campo] += max(Decimal(0), Decimal(str(ajuste.get(campo) or 0)) - cancelado.get(campo, Decimal(0)))
    resultado = []
    for original in dados['taxas']:
        taxa = dict(original)
        taxa['origem'] = dict(original)
        abatimento = agregados.get((taxa['apartamento'], taxa['id']), {})
        taxa['ajustes_origem'] = [a['id'] for a in dados['ajustes']
                                  if a['apartamento'] == taxa['apartamento'] and a.get('taxa_id') == taxa['id']]
        for campo in campos:
            taxa[campo] = max(Decimal(0), Decimal(str(original.get(campo) or 0)) - abatimento.get(campo, Decimal(0)))
        taxa['valor_centavos'] = _centavos(taxa['valor_original'])
        resultado.append(taxa)
    return resultado


def distribuir_parciais(taxas, recebimentos, data_corte, modalidade, ajustes=None, habilitar_desconto=False,
                         desconto_agrupado=False, ordem_taxas=None, reservas=None, data_reserva=None):
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

    def alocar(pagamento, disponivel, data):
        for saldo in saldos:
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

    for receita in sorted(recebimentos, key=lambda r: (r['data'], r['id'] not in recebimentos_reservados,
                                                        -r['valor_centavos'], str(r['id']))):
        data = _data(receita['data'])
        if data > corte:
            continue
        aplicar_eventos_ate(data)
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


def filtrar_grupos(dados, filtros, corte):
    """Seleciona unidades e competências antes de aplicar ajustes e conciliar.

    No filtro de recebimento, mantém todo o histórico dos grupos com movimento
    no intervalo para não perder pagamentos ou ajustes anteriores.
    """
    escolhidos = set(filtros.get('apartamentos') or [])
    tipo = filtros.get('tipo')
    periodo = filtros.get('periodo')
    taxas = [t for t in dados['taxas'] if not escolhidos or t['apartamento'] in escolhidos]
    receitas = [r for r in dados['recebimentos'] if not escolhidos or r['apartamento'] in escolhidos]
    ajustes = [a for a in dados['ajustes'] if not escolhidos or a['apartamento'] in escolhidos]
    taxas_por_id = {(t['apartamento'], t['id']): t for t in taxas}
    ajustes_por_id = {(a['apartamento'], a['id']): a for a in ajustes}

    def chave_ajuste(ajuste):
        chave = (ajuste['apartamento'], ajuste.get('taxa_id'))
        taxa = taxas_por_id.get(chave)
        if taxa is None and chave in ajustes_por_id:
            taxa = taxas_por_id.get((ajuste['apartamento'], ajustes_por_id[chave].get('taxa_id')))
        return (taxa['apartamento'], taxa['competencia']) if taxa else None

    chaves = {(t['apartamento'], t['competencia']) for t in taxas}
    chaves.update((r['apartamento'], r['competencia']) for r in receitas)
    if tipo == 'completo':
        chaves = {chave for chave in chaves if chave[1] <= corte.strftime('%Y-%m')}
    elif tipo == 'competencia':
        inicio, fim = periodo
        chaves = {chave for chave in chaves if inicio <= chave[1] <= fim}
    elif tipo == 'recebimento':
        inicio, fim = (_data(valor) for valor in periodo)
        chaves_movimento = {(t['apartamento'], t['competencia']) for t in taxas
                            if inicio <= t['vencimento'] <= fim}
        chaves_movimento.update((r['apartamento'], r['competencia']) for r in receitas
                                 if inicio <= r['data'] <= fim)
        for ajuste in ajustes:
            data = ajuste.get('vencimento') if ajuste['tipo'] == 'D' else ajuste.get('data_renegociacao')
            if data and inicio <= _data(data) <= fim:
                chave = chave_ajuste(ajuste)
                if chave:
                    chaves_movimento.add(chave)
        chaves &= chaves_movimento
    return {
        'taxas': [t for t in taxas if (t['apartamento'], t['competencia']) in chaves],
        'recebimentos': [r for r in receitas if (r['apartamento'], r['competencia']) in chaves],
        'ajustes': [a for a in ajustes if chave_ajuste(a) in chaves],
    }


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
