"""Operações de arquivos do dashboard."""

import json
import os
import subprocess
import sys
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger
from bff.validacao import validar_margem_encargos


class Arquivos:
    def __init__(self, contexto):
        self.ctx = contexto

    def selecionar_arquivo(self):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        if self.ctx._main_window:
            import webview
            result = self.ctx._main_window.create_file_dialog(webview.OPEN_DIALOG)
            if result and len(result) > 0:
                path = result[0]
                # Nao aceitar sem extensao
                if '.' not in os.path.basename(path):
                    return {"status": "error", "message": "O arquivo selecionado não possui extensão."}
                return {"status": "success", "data": path}
            return {"status": "cancelled"}
        return {"status": "error", "message": "Janela não disponível."}

    def abrir_arquivo_local(self, caminho_local):
        if not caminho_local:
            return {"status": "error", "message": "Caminho inválido."}
        full_path = os.path.join(self.ctx.raiz_projeto, caminho_local)
        if os.path.exists(full_path):
            try:
                os.startfile(full_path)
                return {"status": "success"}
            except AttributeError:
                if sys.platform == 'darwin':
                    subprocess.call(('open', full_path))
                else:
                    subprocess.call(('xdg-open', full_path))
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Arquivo não encontrado no disco."}

    def get_anexos_transacao(self, transacao_id):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            anexos = list(models.Anexos.select().where(models.Anexos.transacao_id == transacao_id).dicts())
            return {"status": "success", "data": anexos}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_prestacoes_contas_mes(self, mes_competencia):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            mes = models.Meses.get_or_none((models.Meses.condominio_id == self.ctx.condo_id) & (models.Meses.competencia == mes_competencia))
            if not mes:
                return {"status": "error", "message": "Mês não encontrado."}
                
            prestacoes = list(models.PrestacoesContas.select().where(models.PrestacoesContas.mes_id == mes.id).dicts())
            return {"status": "success", "data": prestacoes}
        except Exception as e:
            return {"status": "error", "message": str(e)}
