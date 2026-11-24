"""Limites de competência disponíveis para o extrato de recebimentos."""
import calendar
from datetime import datetime

import models


def obter_limites(condo_id):
    if not models.Condominio.get_or_none(id=condo_id):
        raise ValueError('Condomínio não encontrado.')
    meses = []
    for mes in models.Meses.select().where(models.Meses.condominio_id == condo_id):
        if mes.competencia:
            try:
                meses.append(datetime.strptime(mes.competencia, '%Y-%m').date().replace(day=1))
            except (TypeError, ValueError):
                raise ValueError(f'Competência inválida: {mes.competencia}.')
    if not meses:
        raise ValueError('Não há meses cadastrados para este condomínio.')
    inicio, fim = min(meses), max(meses)
    return {'inicio': inicio.isoformat(),
            'fim': fim.replace(day=calendar.monthrange(fim.year, fim.month)[1]).isoformat()}
