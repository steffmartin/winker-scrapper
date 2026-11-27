"""Operações de inadimplencia do dashboard."""

import json
import os
import subprocess
import sys
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger
from bff.validacao import validar_margem_encargos


class Inadimplencia:
    def __init__(self, contexto):
        self.ctx = contexto

    def get_inadimplencia(self, data_corte=None, apartamentos=None):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
            
        try:
            from bff.apresentacao_conciliacao import inadimplencia
            corte = datetime.strptime(data_corte, '%Y-%m-%d').date() if data_corte else datetime.now().date()
            posicao = self.ctx._calcular_posicao_unificada(corte, {'apartamentos': apartamentos or []}, permitir_inconclusivo=True)
            return {'status': 'success', 'data': inadimplencia(posicao)}
        except Exception as e:
            logger.error(f"Erro em get_inadimplencia: {e}")
            return {"status": "error", "message": str(e)}
