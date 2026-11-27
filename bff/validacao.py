"""Validações compartilhadas do dashboard."""

from decimal import Decimal, InvalidOperation


def validar_margem_encargos(valor):
    """Valida a margem em reais e retorna centavos inteiros."""
    try:
        if valor is None or isinstance(valor, bool):
            raise ValueError
        numero = Decimal(str(valor))
        centavos = numero * 100
        if not numero.is_finite() or numero < 0 or centavos != centavos.to_integral_value():
            raise ValueError
        return int(centavos)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Informe uma margem de diferença de encargos válida, não negativa e com até dois decimais.')
