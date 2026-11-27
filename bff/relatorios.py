"""Casos de uso da tela Relatórios."""

from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger


class Relatorios:
    def __init__(self, contexto):
        self.ctx = contexto

    def salvar_relatorio_pdf(self, nome=None):
        try:
            from bff.exportar_relatorio import salvar_pdf
            return salvar_pdf(self.ctx._main_window, nome)
        except Exception as e:
            logger.error(f'Erro ao salvar relatório em PDF: {e}')
            return {'status': 'error', 'message': str(e)}

    def get_contas_relatorio(self):
        if self.ctx.init_error:
            return {'status': 'error', 'message': self.ctx.init_error}
        try:
            contas = models.Contas.select(models.Contas.conta).where(models.Contas.condominio_id == self.ctx.condo_id).order_by(models.Contas.conta)
            return {'status': 'success', 'data': [conta.conta for conta in contas if conta.conta]}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def get_relatorio_conta(self, filtros=None):
        if self.ctx.init_error:
            return {'status': 'error', 'message': self.ctx.init_error}
        try:
            from bff.relatorio_conta import gerar
            return {'status': 'success', 'data': gerar(self.ctx.condo_id, filtros or {})}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def get_relatorio_inadimplencia(self, filtros=None):
        try:
            from bff.relatorio_inadimplencia import formatar
            filtros = filtros or {}
            data_corte = filtros.get('data_corte')
            if not data_corte:
                return {'status': 'error', 'message': 'Informe a data de corte.'}
            datetime.strptime(data_corte, '%Y-%m-%d')
            apartamentos = filtros.get('apartamentos') or []
            if not isinstance(apartamentos, list) or not all(isinstance(a, str) for a in apartamentos):
                return {'status': 'error', 'message': 'Filtro de apartamentos inválido.'}
            from bff.apresentacao_conciliacao import inadimplencia
            posicao = self.ctx._calcular_posicao_unificada(data_corte, {'apartamentos': apartamentos}, permitir_inconclusivo=True)
            return {'status': 'success', 'data': formatar(inadimplencia(posicao), data_corte, apartamentos)}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    def get_relatorio_recebimentos(self, filtros=None):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            filtros = filtros or {}
            from bff.relatorio_recebimentos import obter_limites
            limites = obter_limites(self.ctx.condo_id)
            if filtros.get('limites'):
                return {'status': 'success', 'data': {'limites': limites}}
            from bff.apresentacao_conciliacao import data_corte_extrato, extrato
            corte = data_corte_extrato(filtros)
            posicao = self.ctx._calcular_posicao_unificada(corte, filtros, permitir_inconclusivo=True)
            return {'status': 'success', 'data': extrato(posicao, filtros, limites)}
        except Exception as e:
            return {"status": "error", "message": str(e)}
