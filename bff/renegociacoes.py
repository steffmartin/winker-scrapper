"""Operações de renegociacoes do dashboard."""

import json
import os
import subprocess
import sys
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger
from bff.validacao import validar_margem_encargos


class Renegociacoes:
    def __init__(self, contexto):
        self.ctx = contexto

    def get_renegociacao(self, renegociacao_id):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            ren = models.Renegociacao.get_by_id(renegociacao_id)
            taxas = list(models.Taxas.select().where(models.Taxas.renegociacao_id == renegociacao_id).dicts())
            parcelas = [t for t in taxas if t['tipo'] == 'P']
            originais = [t for t in taxas if t['tipo'] == 'R']
            
            parcelas.sort(key=lambda p: datetime.strptime(p['vencimento'], '%d/%m/%Y') if p.get('vencimento') else datetime.max)
            
            return {
                "status": "success", 
                "data": {
                    "id": ren.id,
                    "apartamento": ren.apartamento,
                    "competencia_inicial": ren.competencia_inicial,
                    "competencia_final": ren.competencia_final,
                    "numero": ren.numero,
                    "data_renegociacao": ren.data_renegociacao,
                    "vencimento_primeira_parcela": ren.vencimento_primeira_parcela,
                    "quantidade_parcelas": ren.quantidade_parcelas,
                    "despesas_adicionais": ren.despesas_adicionais,
                    "descontos_adicionais": ren.descontos_adicionais,
                    "parcelas": parcelas,
                    "taxas_originais": originais
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _renegociacao_tem_dependentes(self, renegociacao_id):
        parcelas = models.Taxas.select(models.Taxas.id).where(
            (models.Taxas.renegociacao_id == renegociacao_id) & (models.Taxas.tipo == 'P')
        )
        return models.Taxas.select().where(
            (models.Taxas.taxa_id.in_(parcelas)) & (models.Taxas.tipo == 'R') &
            (models.Taxas.renegociacao_id != renegociacao_id)
        ).exists()

    def delete_renegociacao(self, renegociacao_id):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            with models.db.atomic():
                if self.ctx._renegociacao_tem_dependentes(renegociacao_id):
                    return {"status": "error", "message": "Esta renegociação possui parcelas usadas em outra renegociação e não pode ser excluída."}
                models.Renegociacao.delete().where(models.Renegociacao.id == renegociacao_id).execute()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def salvar_renegociacao(self, payload):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            ren_id = payload.get('id')
            apartamento = payload.get('apartamento')
            comp_ini = payload.get('competencia_inicial')
            comp_fim = payload.get('competencia_final')
            numero = payload.get('numero')
            data_ren = payload.get('data_renegociacao')
            venc_prim = payload.get('vencimento_primeira_parcela')
            qtd_parc = payload.get('quantidade_parcelas', 1)
            desp_add = payload.get('despesas_adicionais', 0.0)
            desc_add = payload.get('descontos_adicionais', 0.0)
            
            taxas_originais = payload.get('taxas_originais', []) 
            parcelas = payload.get('parcelas', [])
            
            meses_map_inv = {1: 'JAN', 2: 'FEV', 3: 'MAR', 4: 'ABR', 5: 'MAI', 6: 'JUN', 7: 'JUL', 8: 'AGO', 9: 'SET', 10: 'OUT', 11: 'NOV', 12: 'DEZ'}

            with models.db.atomic():
                selecionadas = list(models.Taxas.select().where(models.Taxas.id.in_(taxas_originais)))
                selecionados_ids = {t.id for t in selecionadas}
                if any(t.tipo == 'D' and t.taxa_id_id not in selecionados_ids for t in selecionadas):
                    return {"status": "error", "message": "Selecione a taxa vinculada a cada desconto."}
                if ren_id:
                    if self.ctx._renegociacao_tem_dependentes(ren_id):
                        return {"status": "error", "message": "Esta renegociação possui parcelas usadas em outra renegociação e não pode ser editada."}
                    if models.Taxas.select().where(
                        (models.Taxas.id.in_(taxas_originais)) &
                        (models.Taxas.renegociacao_id == ren_id)
                    ).exists():
                        return {"status": "error", "message": "Uma renegociação não pode incluir suas próprias parcelas."}
                    models.Renegociacao.delete().where(models.Renegociacao.id == ren_id).execute()
                
                nova_ren = models.Renegociacao.create(
                    condominio_id=self.ctx.condo_id,
                    apartamento=apartamento,
                    competencia_inicial=comp_ini,
                    competencia_final=comp_fim,
                    numero=numero,
                    data_renegociacao=data_ren,
                    vencimento_primeira_parcela=venc_prim,
                    quantidade_parcelas=qtd_parc,
                    despesas_adicionais=desp_add,
                    descontos_adicionais=desc_add
                )
                
                for p in parcelas:
                    try:
                        p_venc = datetime.strptime(p['vencimento'], '%d/%m/%Y')
                        exib_str = f"{meses_map_inv[p_venc.month]}/{p_venc.year}"
                    except:
                        exib_str = ""
                    p_comp = p.get('competencia') or (p_venc.strftime('%Y-%m') if 'p_venc' in locals() else "")
                        
                    models.Taxas.create(
                        condominio_id=self.ctx.condo_id,
                        renegociacao_id=nova_ren.id,
                        competencia=p_comp,
                        exibicao=exib_str,
                        vencimento=p.get('vencimento'),
                        descricao=p.get('descricao'),
                        valor_original=p.get('valor_original', 0.0),
                        desconto_vista=p.get('desconto_vista', 0.0),
                        multa_percentual=p.get('multa_percentual', 0.0),
                        juros_mes_percentual=p.get('juros_mes_percentual', 0.0),
                        apartamento=apartamento,
                        tipo='P'
                    )
                
                for t_id in taxas_originais:
                    t_orig = models.Taxas.get_by_id(t_id)
                    models.Taxas.create(
                        condominio_id=self.ctx.condo_id,
                        renegociacao_id=nova_ren.id,
                        taxa_id=t_orig.id,
                        competencia=t_orig.competencia,
                        exibicao=t_orig.exibicao,
                        vencimento=t_orig.vencimento,
                        descricao=f"Renegociado: {t_orig.descricao}",
                        valor_original=t_orig.valor_original,
                        desconto_vista=t_orig.desconto_vista,
                        multa_percentual=t_orig.multa_percentual,
                        juros_mes_percentual=t_orig.juros_mes_percentual,
                        apartamento=apartamento,
                        tipo='R'
                    )
                    
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
