"""Operações de taxas do dashboard."""

import calendar
import json
import os
import subprocess
import sys
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger
from bff.validacao import validar_margem_encargos


class Taxas:
    def __init__(self, contexto):
        self.ctx = contexto

    def get_taxas_por_apartamento(self, apartamento, competencia, tipos=None):
        if tipos is None:
            tipos = ['C','E','I']
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            query = models.Taxas.select().where(
                (models.Taxas.condominio_id == self.ctx.condo_id) &
                (models.Taxas.tipo.in_(tipos))
            )
            query = query.where(models.Taxas.competencia.between(competencia[0], competencia[1]))
            # Only common ('C','E') or specific to the apartment
            query = query.where(
                (models.Taxas.tipo.in_(['C', 'E'])) |
                (models.Taxas.apartamento == apartamento)
            )
            taxas = list(query.order_by(models.Taxas.competencia.desc()).dicts())
            return {"status": "success", "data": taxas}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_taxas(self, tipos=None):
        if tipos is None:
            tipos = ['C']
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            taxas = list(models.Taxas.select().where(
                (models.Taxas.condominio_id == self.ctx.condo_id) &
                (models.Taxas.tipo.in_(tipos))
            ).order_by(models.Taxas.competencia.desc()).dicts())
            return {"status": "success", "data": taxas}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def delete_taxa(self, taxa_id):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            taxa = models.Taxas.get_by_id(taxa_id)
            if taxa.tipo == 'D' and models.Taxas.select().where((models.Taxas.taxa_id == taxa.id) & (models.Taxas.tipo == 'R')).exists():
                return {"status": "error", "message": "Este desconto está vinculado a uma renegociação e não pode ser excluído."}
            if taxa.tipo in ['P', 'R']:
                return {"status": "error", "message": "Taxas de renegociação não podem ser excluídas individualmente. Exclua a renegociação inteira."}
            taxa.delete_instance()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_taxa(self, taxa_id, payload):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            taxa = models.Taxas.get_by_id(taxa_id)
            if taxa.tipo == 'D' and models.Taxas.select().where((models.Taxas.taxa_id == taxa.id) & (models.Taxas.tipo == 'R')).exists():
                return {"status": "error", "message": "Este desconto está vinculado a uma renegociação e não pode ser editado."}
            if taxa.tipo in ['P', 'R']:
                return {"status": "error", "message": "Taxas de renegociação não podem ser editadas individualmente. Edite a renegociação inteira."}
            if 'competencia' in payload: 
                taxa.competencia = payload['competencia']
                try:
                    comp_dt = datetime.strptime(taxa.competencia, '%Y-%m')
                    meses_map_inv = {1: 'JAN', 2: 'FEV', 3: 'MAR', 4: 'ABR', 5: 'MAI', 6: 'JUN', 7: 'JUL', 8: 'AGO', 9: 'SET', 10: 'OUT', 11: 'NOV', 12: 'DEZ'}
                    taxa.exibicao = f"{meses_map_inv[comp_dt.month]}/{comp_dt.year}"
                except:
                    if 'exibicao' in payload: taxa.exibicao = payload['exibicao']
            elif 'exibicao' in payload: 
                taxa.exibicao = payload['exibicao']
            
            tipo = payload.get('tipo', taxa.tipo)
            taxa_vinculada_id = payload.get('taxa_id', taxa.taxa_id)
            
            if tipo == 'D' and taxa_vinculada_id:
                taxa.taxa_id = taxa_vinculada_id
            else:
                taxa.taxa_id = None
            if 'vencimento' in payload: taxa.vencimento = payload['vencimento']
                
            if 'descricao' in payload: taxa.descricao = payload['descricao']
            if 'valor_original' in payload: taxa.valor_original = payload['valor_original']
            if 'desconto_vista' in payload: taxa.desconto_vista = payload['desconto_vista']
            if 'multa_percentual' in payload: taxa.multa_percentual = payload['multa_percentual']
            if 'juros_mes_percentual' in payload: taxa.juros_mes_percentual = payload['juros_mes_percentual']
            if 'tipo' in payload: taxa.tipo = payload['tipo']
            if 'apartamento' in payload: taxa.apartamento = payload['apartamento']
            taxa.save()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def insert_taxa(self, payload):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            meses_repeticao = payload.get('meses_repeticao', 1)
            base_competencia = payload.get('competencia')
            tipo = payload.get('tipo', 'C')
            taxa_id_ref = payload.get('taxa_id')
            
            base_vencimento = payload.get('vencimento')
            if tipo == 'D' and taxa_id_ref and not base_vencimento:
                taxa_pai = models.Taxas.get_by_id(taxa_id_ref)
                base_vencimento = taxa_pai.vencimento
                
            descricao = payload.get('descricao')
            valor_original = payload.get('valor_original', 0.0)
            desconto_vista = payload.get('desconto_vista', 0.0)
            multa_percentual = payload.get('multa_percentual', 0.0)
            juros_mes_percentual = payload.get('juros_mes_percentual', 0.0)
            apartamento = payload.get('apartamento')
            
            def add_months(d, months):
                month = d.month - 1 + months
                year = d.year + month // 12
                month = month % 12 + 1
                day = min(d.day, calendar.monthrange(year, month)[1])
                return d.replace(year=year, month=month, day=day)
            
            dt_comp = datetime.strptime(base_competencia, '%Y-%m') if base_competencia else datetime.now()
            dt_venc = datetime.strptime(base_vencimento, '%d/%m/%Y') if base_vencimento else datetime.now()
            
            meses_map_inv = {1: 'JAN', 2: 'FEV', 3: 'MAR', 4: 'ABR', 5: 'MAI', 6: 'JUN', 7: 'JUL', 8: 'AGO', 9: 'SET', 10: 'OUT', 11: 'NOV', 12: 'DEZ'}

            with models.db.atomic():
                for i in range(meses_repeticao):
                    curr_comp = add_months(dt_comp, i)
                    curr_venc = add_months(dt_venc, i)
                    
                    comp_str = curr_comp.strftime('%Y-%m')
                    venc_str = curr_venc.strftime('%d/%m/%Y')
                    exib_str = f"{meses_map_inv[curr_comp.month]}/{curr_comp.year}"
                    
                    models.Taxas.create(
                        condominio_id=self.ctx.condo_id,
                        competencia=comp_str,
                        exibicao=exib_str,
                        vencimento=venc_str,
                        descricao=descricao,
                        valor_original=valor_original,
                        desconto_vista=desconto_vista,
                        multa_percentual=multa_percentual,
                        juros_mes_percentual=juros_mes_percentual,
                        tipo=tipo,
                        apartamento=apartamento,
                        taxa_id=taxa_id_ref if tipo == 'D' else None
                    )
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
