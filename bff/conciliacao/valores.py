"""Conversões monetárias, datas e encargos."""

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_DOWN


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
