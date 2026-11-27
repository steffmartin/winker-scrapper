"""Operações de revisao do dashboard."""

import json
import os
import subprocess
import sys
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger
from bff.validacao import validar_margem_encargos


class Revisao:
    def __init__(self, contexto):
        self.ctx = contexto

    def get_pendencias_revisao_count(self, exibir_revisados=False):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        
        try:
            m = models.Meses
            c = models.Categorias
            s = models.Subcategorias
            t = models.Transacoes
            a = models.Anexos
            p = models.PrestacoesContas
            
            def get_cond(model):
                if exibir_revisados:
                    return (model.revisado_usuario == 1) & (model.consistente == 0) & (m.condominio_id == self.ctx.condo_id)
                else:
                    return (model.revisado_usuario == 0) & (m.condominio_id == self.ctx.condo_id)
            
            c_m = m.select().where(get_cond(m)).count()
            c_c = c.select().join(m).where(get_cond(c)).count()
            c_s = s.select().join(c).join(m).where(get_cond(s)).count()
            c_t = t.select().join(s).join(c).join(m).where(get_cond(t)).count()
            c_a = a.select().join(t).join(s).join(c).join(m).where(get_cond(a)).count()
            c_p = p.select().join(m).where(get_cond(p)).count()
            
            details = {}
            if c_m > 0: details["meses"] = c_m
            if c_c > 0: details["categorias"] = c_c
            if c_s > 0: details["subcategorias"] = c_s
            if c_t > 0: details["lancamentos"] = c_t
            if (c_a + c_p) > 0: details["documentos"] = c_a + c_p
            
            return {
                "status": "success",
                "data": {
                    "count": sum(details.values()),
                    "details": details
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_registros_nao_revisados(self, tipo_tabela, exibir_revisados=False):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            m = models.Meses
            c = models.Categorias
            s = models.Subcategorias
            t = models.Transacoes
            
            def get_cond(model):
                if exibir_revisados:
                    return (model.revisado_usuario == 1) & (model.consistente == 0) & (m.condominio_id == self.ctx.condo_id)
                else:
                    return (model.revisado_usuario == 0) & (m.condominio_id == self.ctx.condo_id)
            
            registros = []
            if tipo_tabela == 'meses':
                query = (m.select()
                         .where(get_cond(m))
                         .order_by(m.id.desc()))
                for row in query:
                    prestacoes = list(models.PrestacoesContas.select().where(models.PrestacoesContas.mes_id == row.id).dicts())
                    row_data = row.__data__
                    row_data['prestacoes_contas'] = prestacoes
                    registros.append(row_data)
            elif tipo_tabela == 'categorias':
                query = (c.select(c, m.exibicao.alias('mes_exibicao'), m.competencia.alias('mes_competencia'))
                         .join(m)
                         .where(get_cond(c))
                         .order_by(c.id.desc()))
                for row in query.dicts():
                    registros.append(row)
            elif tipo_tabela == 'subcategorias':
                query = (s.select(s, m.exibicao.alias('mes_exibicao'), m.competencia.alias('mes_competencia'))
                         .join(c).join(m)
                         .where(get_cond(s))
                         .order_by(s.id.desc()))
                for row in query.dicts():
                    registros.append(row)
            elif tipo_tabela == 'lancamentos':
                query = (t.select(t, m.exibicao.alias('mes_exibicao'), m.competencia.alias('mes_competencia'))
                         .join(s).join(c).join(m)
                         .where(get_cond(t))
                         .order_by(t.id.desc()))
                for row in query.dicts():
                    anexos = list(models.Anexos.select().where(models.Anexos.transacao_id == row['id']).dicts())
                    # format data dd/mm/yyyy to yyyy-mm-dd
                    if row.get('data') and len(row['data']) == 10:
                        parts = row['data'].split('/')
                        if len(parts) == 3:
                            row['data_sort'] = f"{parts[2]}-{parts[1]}-{parts[0]}"
                        else:
                            row['data_sort'] = row['data']
                    else:
                        row['data_sort'] = row.get('data', '')
                    row['anexos_lista'] = anexos
                    registros.append(row)
                    
            elif tipo_tabela == 'documentos':
                a = models.Anexos
                p = models.PrestacoesContas
                
                query_a = (a.select(a, m.exibicao.alias('mes_exibicao'), m.competencia.alias('mes_competencia'))
                           .join(t).join(s).join(c).join(m)
                           .where(get_cond(a)))
                
                for row in query_a.dicts():
                    row['tipo_doc'] = 'C'
                    registros.append(row)
                    
                query_p = (p.select(p, m.exibicao.alias('mes_exibicao'), m.competencia.alias('mes_competencia'))
                           .join(m)
                           .where(get_cond(p)))
                
                for row in query_p.dicts():
                    row['tipo_doc'] = 'P'
                    registros.append(row)
                    
                registros.sort(key=lambda x: x['id'], reverse=True)
                
            return {"status": "success", "data": registros}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_registro_revisado(self, tipo_tabela, payload):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
        try:
            import shutil
            registro_id = payload.get('id')
            if not registro_id:
                return {"status": "error", "message": "ID não informado."}
                
            with models.db.atomic():
                if tipo_tabela == 'meses':
                    reg = models.Meses.get_by_id(registro_id)
                    if 'receita_total' in payload: reg.receita_total = payload['receita_total']
                    if 'despesa_total' in payload: reg.despesa_total = payload['despesa_total']
                    if 'revisado_usuario' in payload: reg.revisado_usuario = payload['revisado_usuario']
                    
                    if 'anexos_removidos' in payload:
                        for p_id in payload['anexos_removidos']:
                            try:
                                pc = models.PrestacoesContas.get_by_id(p_id)
                                if pc.mes_id.id == reg.id:
                                    abs_file_path = os.path.join(self.ctx.raiz_projeto, pc.caminho_local)
                                    if os.path.exists(abs_file_path):
                                        os.remove(abs_file_path)
                                    pc.delete_instance()
                            except models.PrestacoesContas.DoesNotExist:
                                pass

                    if 'prestacoes_contas' in payload:
                        for p in payload['prestacoes_contas']:
                            if 'caminho_local' in p and os.path.isabs(p['caminho_local']):
                                abs_path = p['caminho_local']
                                chave_unica = reg.competencia.replace("-", "")
                                dest_dir = os.path.join(self.ctx.raiz_projeto, "anexos", str(reg.condominio_id), chave_unica)
                                os.makedirs(dest_dir, exist_ok=True)
                                import uuid
                                ext_real = os.path.splitext(abs_path)[1].lstrip('.')
                                dest_path = os.path.join(dest_dir, f"{chave_unica}_prestacao_contas_{uuid.uuid4().hex[:6]}.{ext_real}")
                                shutil.copy2(abs_path, dest_path)
                                rel_path = f"anexos/{reg.condominio_id}/{chave_unica}/{os.path.basename(dest_path)}"
                                models.PrestacoesContas.create(
                                    mes_id=reg.id,
                                    caminho_local=rel_path,
                                    nome_original=os.path.basename(abs_path),
                                    extensao=ext_real,
                                    revisado_usuario=1 if ext_real else 0,
                                    inconsistente=0 if ext_real else 1,
                                    motivo_inconsistencia=None if ext_real else '["Extensão de arquivo inválida ou ausente"]'
                                )
                        reg.anexos = models.PrestacoesContas.select().where(models.PrestacoesContas.mes_id == reg.id).count()
                    reg.save()
                    
                elif tipo_tabela == 'categorias':
                    reg = models.Categorias.get_by_id(registro_id)
                    if 'valor' in payload: reg.valor = payload['valor']
                    if 'revisado_usuario' in payload: reg.revisado_usuario = payload['revisado_usuario']
                    reg.save()
                    
                elif tipo_tabela == 'subcategorias':
                    reg = models.Subcategorias.get_by_id(registro_id)
                    if 'valor' in payload: reg.valor = payload['valor']
                    if 'revisado_usuario' in payload: reg.revisado_usuario = payload['revisado_usuario']
                    reg.save()
                    
                elif tipo_tabela == 'lancamentos':
                    reg = models.Transacoes.get_by_id(registro_id)
                    if 'apartamento' in payload:
                        novo_apartamento = payload['apartamento']
                        if novo_apartamento:
                            mes = reg.subcategoria_id.categoria_id.mes_id
                            condominio = mes.condominio_id
                            if condominio.apartamentos:
                                import json
                                try:
                                    aptos_list = json.loads(condominio.apartamentos)
                                    if novo_apartamento not in aptos_list:
                                        return {"status": "error", "message": f"Apartamento '{novo_apartamento}' não existe no condomínio."}
                                except Exception:
                                    pass
                        reg.apartamento = novo_apartamento
                    if 'competencia' in payload: reg.competencia = payload['competencia']
                    if 'fornecedor' in payload: reg.fornecedor = payload['fornecedor']
                    if 'conta' in payload: reg.conta = payload['conta']
                    if 'revisado_usuario' in payload: reg.revisado_usuario = payload['revisado_usuario']
                    
                    if 'anexos_removidos' in payload:
                        for a_id in payload['anexos_removidos']:
                            try:
                                anexo = models.Anexos.get_by_id(a_id)
                                if anexo.transacao_id.id == reg.id:
                                    abs_file_path = os.path.join(self.ctx.raiz_projeto, anexo.caminho_local)
                                    if os.path.exists(abs_file_path):
                                        os.remove(abs_file_path)
                                    anexo.delete_instance()
                            except models.Anexos.DoesNotExist:
                                pass

                    if 'anexos_lista' in payload:
                        for p in payload['anexos_lista']:
                            if 'caminho_local' in p and os.path.isabs(p['caminho_local']):
                                abs_path = p['caminho_local']
                                mes = reg.subcategoria_id.categoria_id.mes_id
                                chave_unica = mes.competencia.replace("-", "")
                                dest_dir = os.path.join(self.ctx.raiz_projeto, "anexos", str(mes.condominio_id), chave_unica)
                                os.makedirs(dest_dir, exist_ok=True)
                                import uuid
                                ext_real = os.path.splitext(abs_path)[1].lstrip('.')
                                dest_path = os.path.join(dest_dir, f"transacao_{reg.id}_{uuid.uuid4().hex[:6]}.{ext_real}")
                                shutil.copy2(abs_path, dest_path)
                                rel_path = f"anexos/{mes.condominio_id}/{chave_unica}/{os.path.basename(dest_path)}"
                                models.Anexos.create(
                                    transacao_id=reg.id,
                                    caminho_local=rel_path,
                                    nome_original=os.path.basename(abs_path),
                                    extensao=ext_real,
                                    revisado_usuario=1 if ext_real else 0,
                                    inconsistente=0 if ext_real else 1,
                                    motivo_inconsistencia=None if ext_real else '["Extensão de arquivo inválida ou ausente"]'
                                )
                        reg.anexos = models.Anexos.select().where(models.Anexos.transacao_id == reg.id).count()
                    reg.save()
                    
                elif tipo_tabela == 'documentos':
                    tipo_doc = payload.get('tipo_doc')
                    ext_nova = payload.get('extensao', '').lstrip('.')
                    if tipo_doc == 'C':
                        reg = models.Anexos.get_by_id(registro_id)
                    else:
                        reg = models.PrestacoesContas.get_by_id(registro_id)
                        
                    if ext_nova and reg.caminho_local:
                        old_path = os.path.join(self.ctx.raiz_projeto, reg.caminho_local)
                        new_path = f"{os.path.splitext(old_path)[0]}.{ext_nova}"
                        if os.path.exists(old_path):
                            os.rename(old_path, new_path)
                            
                        reg.caminho_local = f"{os.path.splitext(reg.caminho_local)[0]}.{ext_nova}"
                        if reg.nome_original:
                            reg.nome_original = f"{os.path.splitext(reg.nome_original)[0]}.{ext_nova}"
                        reg.extensao = ext_nova
                            
                    if 'revisado_usuario' in payload:
                        reg.revisado_usuario = payload['revisado_usuario']
                    reg.save()
                    
            return {"status": "success", "message": "Registro atualizado com sucesso."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
