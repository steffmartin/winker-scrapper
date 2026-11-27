"""Operações de dashboard do dashboard."""

import json
import os
import subprocess
import sys
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger
from bff.validacao import validar_margem_encargos


class Dashboard:
    def __init__(self, contexto):
        self.ctx = contexto

    def get_dashboard_kpis(self):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        
        try:
            condo = models.Condominio.get_or_none(id=self.ctx.condo_id)
            
            inadimplencia = {}
            administradora = {}
            estatisticas = {
                "ultima_atualizacao": None,
                "transacoes_total": 0,
                "meses_lidos": 0,
                "anexos_baixados": 0
            }
            
            if condo:
                inadimplencia = {
                    "valor": condo.inadimplencia_valor or 0,
                    "unidades": condo.inadimplencia_unidades or 0,
                    "data_corte": condo.inadimplencia_data_corte
                }
                tels = condo.telefone_administradora
                try:
                    if tels: tels = json.loads(tels)
                except Exception:
                    pass
                administradora = {
                    "nome": condo.administradora,
                    "telefone": tels
                }
                estatisticas["ultima_atualizacao"] = condo.ultima_atualizacao
            
            m = models.Meses
            c = models.Categorias
            s = models.Subcategorias
            t = models.Transacoes
            a = models.Anexos
            p = models.PrestacoesContas
            
            estatisticas["transacoes_total"] = t.select().join(s).join(c).join(m).where(m.condominio_id == self.ctx.condo_id).count()
            estatisticas["meses_lidos"] = m.select().where(m.condominio_id == self.ctx.condo_id).count()
            
            anexos_count = a.select().join(t).join(s).join(c).join(m).where(m.condominio_id == self.ctx.condo_id).count()
            prestacoes_count = p.select().join(m).where(m.condominio_id == self.ctx.condo_id).count()
            estatisticas["anexos_baixados"] = anexos_count + prestacoes_count
            
            membros_gestao = list(models.MembrosGestao.select().where(models.MembrosGestao.condominio_id == self.ctx.condo_id).dicts())
            
            gestao = {
                "membros": membros_gestao,
                "administradora": administradora
            }
            
            totais = m.select(
                models.fn.SUM(m.receita_total).alias('tr'),
                models.fn.SUM(m.despesa_total).alias('td')
            ).where(m.condominio_id == self.ctx.condo_id).scalar(as_tuple=True)
            
            if totais:
                tr, td = totais
            else:
                tr, td = 0, 0
                
            contas_info = models.Contas.select(
                models.fn.SUM(models.Contas.saldo_inicial).alias('total'),
                models.fn.COUNT(models.Contas.id).alias('count')
            ).where(models.Contas.condominio_id == self.ctx.condo_id).scalar(as_tuple=True)
            
            if contas_info and contas_info[0] is not None:
                saldo_inicial_total, count_contas = contas_info
            else:
                saldo_inicial_total, count_contas = 0, 0

            tr = tr or 0
            td = td or 0
            saldo_total = saldo_inicial_total + tr - td

            saldos = {
                "saldo_total": round(saldo_total, 2) if saldo_total else 0,
                "count_contas": count_contas,
                "saldo_declarado": round(condo.saldo_declarado, 2) if condo.saldo_declarado is not None else None
            }
            
            current_date_str = datetime.now().strftime("%Y-%m")
            mes = m.get_or_none((m.condominio_id == self.ctx.condo_id) & (m.competencia == current_date_str))
            
            if mes:
                rec = mes.receita_total or 0
                desp = mes.despesa_total or 0
                resumo_mes = {
                    "competencia": mes.competencia,
                    "receita_total": rec,
                    "despesa_total": desp,
                    "resultado": rec - desp
                }
            else:
                resumo_mes = {
                    "competencia": current_date_str,
                    "receita_total": 0,
                    "despesa_total": 0,
                    "resultado": 0
                }
                
            return {
                "status": "success",
                "data": {
                    "inadimplencia": inadimplencia,
                    "gestao": gestao,
                    "saldos": saldos,
                    "resumo_mes": resumo_mes,
                    "estatisticas": estatisticas
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
