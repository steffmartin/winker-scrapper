"""Operações de transacoes do dashboard."""

import json
import os
import subprocess
import sys
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger
from bff.validacao import validar_margem_encargos


class Transacoes:
    def __init__(self, contexto):
        self.ctx = contexto

    def get_transacoes(self, start_date=None, end_date=None):
        if self.ctx.init_error:
            return {"status": "error", "message": self.ctx.init_error}
            
        try:
            condo = models.Condominio.get_or_none(models.Condominio.id == self.ctx.condo_id)
            prazo_fechamento = condo.prazo_fechamento or 0
            
            m = models.Meses
            c = models.Categorias
            s = models.Subcategorias
            t = models.Transacoes
            
            query = (t.select(
                        m.competencia.alias('mes_competencia'),
                        m.exibicao.alias('mes_exibicao'),
                        m.consistente.alias('mes_consistente'),
                        m.revisado_usuario.alias('mes_revisado'),
                        m.anexos.alias('mes_anexos'),
                        c.nome.alias('categoria_nome'),
                        c.tipo.alias('categoria_tipo'),
                        s.nome.alias('subcategoria_nome'),
                        t.id.alias('transacao_id'),
                        t.descricao.alias('transacao_descricao'),
                        t.apartamento,
                        t.data,
                        t.valor,
                        t.consistente,
                        t.revisado_usuario,
                        t.anexos.alias('anexos_count')
                     )
                     .join(s)
                     .join(c)
                     .join(m)
                     .where(m.condominio_id == self.ctx.condo_id))
                     
            if start_date:
                query = query.where(models.fn.substr(t.data, 7, 4).concat('-').concat(models.fn.substr(t.data, 4, 2)).concat('-').concat(models.fn.substr(t.data, 1, 2)) >= start_date)
            if end_date:
                query = query.where(models.fn.substr(t.data, 7, 4).concat('-').concat(models.fn.substr(t.data, 4, 2)).concat('-').concat(models.fn.substr(t.data, 1, 2)) <= end_date)
                
            query = query.order_by(t.data.asc())
            
            rows = list(query.dicts())
            
            meses_dict = {}
            
            s_year = s_month = e_year = e_month = None

            if start_date:
                try:
                    s_date = datetime.strptime(start_date, '%Y-%m-%d')
                    s_year, s_month = s_date.year, s_date.month
                except ValueError:
                    pass
            elif len(rows) > 0:
                min_mes = min(r["mes_competencia"] for r in rows)
                s_year, s_month = int(min_mes.split('-')[0]), int(min_mes.split('-')[1])

            if end_date:
                try:
                    e_date = datetime.strptime(end_date, '%Y-%m-%d')
                    e_year, e_month = e_date.year, e_date.month
                except ValueError:
                    pass
            elif len(rows) > 0:
                max_mes = max(r["mes_competencia"] for r in rows)
                e_year, e_month = int(max_mes.split('-')[0]), int(max_mes.split('-')[1])
                
            meses_map_inv = {1: 'JAN', 2: 'FEV', 3: 'MAR', 4: 'ABR', 5: 'MAI', 6: 'JUN', 7: 'JUL', 8: 'AGO', 9: 'SET', 10: 'OUT', 11: 'NOV', 12: 'DEZ'}
            if s_year and s_month and e_year and e_month:
                y, m = s_year, s_month
                while (y < e_year) or (y == e_year and m <= e_month):
                    mes_exibicao = f"{meses_map_inv[m]}/{y}"
                    mes_competencia = f"{y}-{m:02d}"
                    meses_dict[mes_competencia] = {
                        "data": {"descricao": mes_exibicao, "competencia": mes_competencia, "valor_total": 0, "tipo_node": "mes", "consistente": 0, "revisado_usuario": 0, "anexos": 0},
                        "expanded": False,
                        "children_dict": {
                            "Receitas": {
                                "data": {"descricao": "Receitas", "valor_total": 0, "porcentagem": 0.0, "tipo_node": "tipo"},
                                "expanded": False,
                                "children_dict": {}
                            },
                            "Despesas": {
                                "data": {"descricao": "Despesas", "valor_total": 0, "porcentagem": 0.0, "tipo_node": "tipo"},
                                "expanded": False,
                                "children_dict": {}
                            }
                        }
                    }
                    if m == 12:
                        m = 1
                        y += 1
                    else:
                        m += 1
            
            for row in rows:
                mes = row["mes_competencia"]
                mes_exibicao = row["mes_exibicao"]
                tipo = "Receitas" if row["categoria_tipo"] == "R" else "Despesas"
                categoria = row["categoria_nome"]
                subcategoria = row["subcategoria_nome"]
                
                if mes not in meses_dict:
                    meses_dict[mes] = {
                        "data": {"descricao": mes_exibicao, "competencia": mes, "valor_total": 0, "tipo_node": "mes", "consistente": row.get("mes_consistente", 1), "revisado_usuario": row.get("mes_revisado", 0), "anexos": row.get("mes_anexos", 0)},
                        "expanded": False,
                        "children_dict": {}
                    }
                else:
                    meses_dict[mes]["data"]["descricao"] = mes_exibicao
                    meses_dict[mes]["data"]["consistente"] = row.get("mes_consistente", 1)
                    meses_dict[mes]["data"]["revisado_usuario"] = row.get("mes_revisado", 0)
                    meses_dict[mes]["data"]["anexos"] = row.get("mes_anexos", 0)
                
                mes_node = meses_dict[mes]
                if tipo not in mes_node["children_dict"]:
                    mes_node["children_dict"][tipo] = {
                        "data": {"descricao": tipo, "valor_total": 0, "porcentagem": 0.0, "tipo_node": "tipo"},
                        "expanded": False,
                        "children_dict": {}
                    }
                
                tipo_node = mes_node["children_dict"][tipo]
                if categoria not in tipo_node["children_dict"]:
                    tipo_node["children_dict"][categoria] = {
                        "data": {"descricao": categoria, "valor_total": 0, "porcentagem": 0.0, "tipo_node": "categoria"},
                        "expanded": False,
                        "children_dict": {}
                    }
                
                categoria_node = tipo_node["children_dict"][categoria]
                if subcategoria not in categoria_node["children_dict"]:
                    categoria_node["children_dict"][subcategoria] = {
                        "data": {"descricao": subcategoria, "valor_total": 0, "porcentagem": 0.0, "tipo_node": "subcategoria"},
                        "expanded": False,
                        "children": []
                    }
                
                subcategoria_node = categoria_node["children_dict"][subcategoria]
                
                valor = row["valor"] or 0
                
                transacao_data = {
                    "id": row["transacao_id"],
                    "data": row["data"],
                    "descricao": row["transacao_descricao"],
                    "apartamento": row["apartamento"],
                    "valor": valor,
                    "consistente": row["consistente"],
                    "revisado_usuario": row["revisado_usuario"],
                    "anexos": row["anexos_count"],
                    "tipo_node": "transacao"
                }
                
                subcategoria_node["children"].append({
                    "data": transacao_data
                })
                
                subcategoria_node["data"]["valor_total"] += valor
                categoria_node["data"]["valor_total"] += valor
                tipo_node["data"]["valor_total"] += valor
                mes_node["data"]["valor_total"] += valor
                
            tree = []
            sorted_meses = sorted(meses_dict.keys())
            
            for mes in sorted_meses:
                mes_node = meses_dict[mes]
                mes_node["children"] = []
                
                sorted_tipos = sorted(mes_node["children_dict"].keys(), key=lambda x: (x.lower() != 'receitas', x))
                
                for tipo in sorted_tipos:
                    tipo_node = mes_node["children_dict"][tipo]
                    tipo_node["children"] = []
                    tipo_total = tipo_node["data"]["valor_total"]
                    mes_total = mes_node["data"]["valor_total"]
                    if mes_total > 0:
                        tipo_node["data"]["porcentagem"] = round((tipo_total / mes_total) * 100, 2)
                    
                    sorted_categorias = sorted(tipo_node["children_dict"].values(), key=lambda x: x["data"]["valor_total"], reverse=True)
                    
                    for cat_node in sorted_categorias:
                        cat_node["children"] = []
                        cat_total = cat_node["data"]["valor_total"]
                        if tipo_total > 0:
                            cat_node["data"]["porcentagem"] = round((cat_total / tipo_total) * 100, 2)
                        
                        sorted_subcats = sorted(cat_node["children_dict"].values(), key=lambda x: x["data"]["valor_total"], reverse=True)
                        for sub_node in sorted_subcats:
                            sub_total = sub_node["data"]["valor_total"]
                            if cat_total > 0:
                                sub_node["data"]["porcentagem"] = round((sub_total / cat_total) * 100, 2)
                            
                            for trans_node in sub_node["children"]:
                                if sub_total > 0:
                                    trans_node["data"]["porcentagem"] = round((trans_node["data"]["valor"] / sub_total) * 100, 2)
                                else:
                                    trans_node["data"]["porcentagem"] = 0.0
                            
                            cat_node["children"].append(sub_node)
                            
                        del cat_node["children_dict"]
                        tipo_node["children"].append(cat_node)
                        
                    del tipo_node["children_dict"]
                    mes_node["children"].append(tipo_node)
                    
                del mes_node["children_dict"]
                tree.append(mes_node)
                
            return {
                "status": "success",
                "data": {
                    "tree": tree,
                    "prazo_fechamento": prazo_fechamento
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
