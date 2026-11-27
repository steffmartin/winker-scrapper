"""Operações de configuracoes do dashboard."""

import json
import os
import subprocess
import sys
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger
from bff.validacao import validar_margem_encargos


class Configuracoes:
    def __init__(self, contexto):
        self.ctx = contexto

    def get_condominio_config(self):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}

        try:
            condo = models.Condominio.get_or_none(id=self.ctx.condo_id)
            if condo:
                condo_data = condo.__data__
                if condo_data.get('telefone_administradora'):
                    try:
                        condo_data['telefone_administradora'] = json.loads(condo_data['telefone_administradora'])
                    except Exception:
                        pass
                if condo_data.get('apartamentos'):
                    try:
                        condo_data['apartamentos'] = json.loads(condo_data['apartamentos'])
                    except Exception:
                        pass
                membros = list(models.MembrosGestao.select().where(models.MembrosGestao.condominio_id == self.ctx.condo_id).dicts())
                contas = list(models.Contas.select().where(models.Contas.condominio_id == self.ctx.condo_id).dicts())
                regras = list(models.RegrasPreenchimento.select().where(models.RegrasPreenchimento.condominio_id == self.ctx.condo_id).order_by(models.RegrasPreenchimento.id).dicts())
                return {"status": "success", "data": {"condominio": condo_data, "membros": membros, "contas": contas, "regras_preenchimento": regras}}
            else:
                return {"status": "error", "message": "Condomínio não encontrado."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_condominio_config(self, payload):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        
        try:
            with models.db.atomic():
                condo = models.Condominio.get_or_none(id=self.ctx.condo_id)
                if not condo:
                    return {"status": "error", "message": "Condomínio não encontrado."}
                
                condo_data = payload.get("condominio", {})
                membros_data = payload.get("membros", [])
                
                if 'margem_diferenca_encargos' in condo_data:
                    condo.margem_diferenca_encargos = validar_margem_encargos(condo_data['margem_diferenca_encargos']) / 100
                if 'nome' in condo_data: condo.nome = condo_data['nome']
                if 'administradora' in condo_data: condo.administradora = condo_data['administradora']
                if 'telefone_administradora' in condo_data: condo.telefone_administradora = json.dumps(condo_data['telefone_administradora'])
                if 'apartamentos' in condo_data: condo.apartamentos = json.dumps(condo_data['apartamentos'])
                if 'prazo_fechamento' in condo_data: condo.prazo_fechamento = condo_data['prazo_fechamento']
                if 'inadimplencia_data_corte' in condo_data: condo.inadimplencia_data_corte = condo_data['inadimplencia_data_corte']
                if 'inadimplencia_unidades' in condo_data: condo.inadimplencia_unidades = condo_data['inadimplencia_unidades']
                if 'inadimplencia_valor' in condo_data: condo.inadimplencia_valor = condo_data['inadimplencia_valor']
                if 'saldo_declarado' in condo_data: condo.saldo_declarado = condo_data['saldo_declarado']
                if 'tipo_juros_multa' in condo_data: condo.tipo_juros_multa = condo_data['tipo_juros_multa']
                if 'taxa_renegociacao' in condo_data: condo.taxa_renegociacao = condo_data['taxa_renegociacao']
                
                condo.ultima_atualizacao = datetime.now().isoformat()
                
                condo.save()
                
                models.MembrosGestao.delete().where(models.MembrosGestao.condominio_id == self.ctx.condo_id).execute()
                
                for m in membros_data:
                    models.MembrosGestao.create(
                        condominio_id=self.ctx.condo_id,
                        nome=m.get('nome'),
                        cargo=m.get('cargo')
                    )
                
                if "regras_preenchimento" in payload:
                    regras = payload["regras_preenchimento"]
                    if not isinstance(regras, list):
                        raise ValueError("Lista de regras inválida.")
                    existentes = {r.id: r for r in models.RegrasPreenchimento.select().where(
                        models.RegrasPreenchimento.condominio_id == self.ctx.condo_id)}
                    ids = set()
                    for regra in regras:
                        if (not isinstance(regra, dict) or regra.get("campo") not in ("fornecedor", "conta")
                                or not isinstance(regra.get("descricao_contem"), str) or not regra["descricao_contem"].strip()
                                or not isinstance(regra.get("valor"), str) or not regra["valor"].strip()):
                            raise ValueError("Regra de preenchimento inválida.")
                        regra_id = regra.get("id")
                        if regra_id is not None:
                            if type(regra_id) is not int or regra_id not in existentes or regra_id in ids:
                                raise ValueError("Identificador de regra inválido.")
                            ids.add(regra_id)
                    ordem_atual = [regra.get("id") for regra in regras]
                    ids_na_ordem = [regra_id for regra_id in ordem_atual if regra_id is not None]
                    reordenou = ids_na_ordem != sorted(ids_na_ordem) or (
                        None in ordem_atual and any(regra_id is not None for regra_id in ordem_atual[ordem_atual.index(None):]))
                    if reordenou:
                        # O extrator usa id crescente como prioridade; recriar mantém a ordem escolhida.
                        models.RegrasPreenchimento.delete().where(models.RegrasPreenchimento.condominio_id == self.ctx.condo_id).execute()
                        for regra in regras:
                            models.RegrasPreenchimento.create(condominio_id=self.ctx.condo_id, **{
                                chave: regra[chave] for chave in ("descricao_contem", "campo", "valor")})
                    else:
                        for regra_id, regra_existente in existentes.items():
                            if regra_id not in ids:
                                regra_existente.delete_instance()
                        for regra in regras:
                            valores = {chave: regra[chave] for chave in ("descricao_contem", "campo", "valor")}
                            if regra.get("id") is None:
                                models.RegrasPreenchimento.create(condominio_id=self.ctx.condo_id, **valores)
                            else:
                                existente = existentes[regra["id"]]
                                for chave, valor in valores.items():
                                    setattr(existente, chave, valor)
                                existente.save()

                contas_data = payload.get("contas", [])
                models.Contas.delete().where(models.Contas.condominio_id == self.ctx.condo_id).execute()
                for c in contas_data:
                    models.Contas.create(
                        condominio_id=self.ctx.condo_id,
                        conta=c.get('conta'),
                        saldo_inicial=c.get('saldo_inicial', 0.0)
                    )
                    
            resposta = {"status": "success", "message": "Configurações atualizadas com sucesso."}
            if "regras_preenchimento" in payload:
                resposta["regras_preenchimento"] = list(models.RegrasPreenchimento.select().where(
                    models.RegrasPreenchimento.condominio_id == self.ctx.condo_id).order_by(models.RegrasPreenchimento.id).dicts())
            return resposta
        except Exception as e:
            return {"status": "error", "message": str(e)}
