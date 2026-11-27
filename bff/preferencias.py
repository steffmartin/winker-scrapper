"""Operações de preferencias do dashboard."""

import json
import os
import subprocess
import sys
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger
from bff.validacao import validar_margem_encargos


class Preferencias:
    def __init__(self, contexto):
        self.ctx = contexto

    def get_preferencias(self):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            pref = models.PreferenciasUsuario.select().first()
            if pref:
                return {"status": "success", "data": pref.__data__}
            return {"status": "success", "data": None}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def salvar_preferencias(self, dados):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            pref = models.PreferenciasUsuario.select().first()
            if not pref:
                pref = models.PreferenciasUsuario()
            
            if 'modo_escuro' in dados: pref.modo_escuro = dados['modo_escuro']
            if 'cor_primaria' in dados: pref.cor_primaria = dados['cor_primaria']
            if 'cor_superficie' in dados: pref.cor_superficie = dados['cor_superficie']
            if 'tema_preset' in dados: pref.tema_preset = dados['tema_preset']
            if 'modo_menu' in dados: pref.modo_menu = dados['modo_menu']
            # We don't overwrite condominio_id here, it's done via set_condominio
            
            pref.save()
            return {"status": "success", "data": pref.__data__}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def sync_preferencias_cache(self, dados):
        self.ctx.prefs_cache = dados
        return {"status": "success"}
