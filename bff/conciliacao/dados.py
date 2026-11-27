"""Consulta, normalização e filtragem de registros da conciliação."""

from decimal import Decimal
from bff.conciliacao.valores import _centavos, _data


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
