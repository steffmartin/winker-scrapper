"""Formatação dos dados de inadimplência para o relatório."""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


def formatar(resultado, data_corte, apartamentos):
    escolhidos = set(apartamentos)
    unidades = []
    total_geral = 0
    for unidade in resultado:
        nome = str(unidade['unidade'])
        if escolhidos and nome not in escolhidos:
            continue
        grupos = {}
        for taxa in unidade['taxas']:
            competencia = taxa.get('competencia')
            data = datetime.strptime(taxa['vencimento'], '%d/%m/%Y').date().isoformat()
            centavos = int((Decimal(str(taxa['valor'])) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            grupos.setdefault(competencia, []).append({'id': taxa['id'], 'vencimento': data,
                'descricao': taxa.get('descricao') or '', 'valor': centavos / 100})
        competencias = []
        subtotal_unidade = 0
        for competencia in sorted(grupos, key=lambda valor: (valor is None, valor or '')):
            taxas = sorted(grupos[competencia], key=lambda t: (t['vencimento'], -t['valor'], t['id']))
            subtotal = sum(int((Decimal(str(t['valor'])) * 100).quantize(Decimal('1'))) for t in taxas)
            subtotal_unidade += subtotal
            competencias.append({'competencia': competencia, 'taxas': taxas, 'subtotal': subtotal / 100})
        total_geral += subtotal_unidade
        unidades.append({'apartamento': nome, 'competencias': competencias, 'subtotal': subtotal_unidade / 100})
    unidades.sort(key=lambda u: u['apartamento'].casefold())
    return {'data_corte': data_corte, 'apartamentos': unidades, 'total': total_geral / 100}
