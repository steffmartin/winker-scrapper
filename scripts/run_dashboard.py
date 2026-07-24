import ctypes
import os
import subprocess
import sys
import json
import calendar
from datetime import datetime

# Módulos internos independentes
from utils import logger

# Garantir dependências antes de importar libs externas
from setup_deps import install_dependencies
install_dependencies()

# Dependências externas e modelos
import webview

import models
from peewee import JOIN
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

class Api:
    def __init__(self, db_path=None):
        self.db_path = db_path or self._get_db_path()
        self.init_error = None
        self.prefs_cache = None
        self._splash_window = None
        self._main_window = None
        self.condo_id = None
        
        if not os.path.exists(self.db_path):
            self.init_error = "Banco de dados não encontrado."
        else:
            models.init_models(self.db_path)
            self._initialize_condo_id()
                
            if not self.condo_id:
                self.init_error = "Nenhum condomínio definido ou encontrado no banco."

    def _initialize_condo_id(self):
        try:
            pref = models.PreferenciasUsuario.select().first()
            if pref and pref.condominio_id:
                self.condo_id = pref.condominio_id
            else:
                condo = models.Condominio.select().first()
                if condo:
                    self.condo_id = condo.id
                    if not pref:
                        models.PreferenciasUsuario.create(condominio_id=condo.id)
                    else:
                        pref.condominio_id = condo.id
                        pref.save()
        except Exception:
            pass

    def get_nome_condominio(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}

        try:
            condo = models.Condominio.get_or_none(id=self.condo_id)
            if condo:
                return {"status": "success", "data": {"nome": condo.nome}}
            else:
                return {"status": "error", "message": "Condomínio não encontrado."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_condominios(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            condominios = list(models.Condominio.select(models.Condominio.id, models.Condominio.nome).order_by(models.Condominio.nome).dicts())
            return {"status": "success", "data": condominios, "current_id": self.condo_id}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def set_condominio(self, condo_id):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            self.condo_id = condo_id
            pref = models.PreferenciasUsuario.select().first()
            if pref:
                pref.condominio_id = condo_id
                pref.save()
            else:
                models.PreferenciasUsuario.create(condominio_id=condo_id)
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def exit_app(self):
        try:
            if self.prefs_cache:
                self.salvar_preferencias({
                    'modo_escuro': 1 if self.prefs_cache.get('darkTheme') else 0,
                    'cor_primaria': self.prefs_cache.get('primary'),
                    'cor_superficie': self.prefs_cache.get('surface'),
                    'tema_preset': self.prefs_cache.get('preset'),
                    'modo_menu': self.prefs_cache.get('menuMode')
                })
        except Exception:
            pass

        if self._main_window:
            self._main_window.destroy()
            
        import os
        import threading
        threading.Timer(0.5, lambda: os._exit(0)).start()
        return {"status": "success"}

    def get_condominio_config(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}

        try:
            condo = models.Condominio.get_or_none(id=self.condo_id)
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
                membros = list(models.MembrosGestao.select().where(models.MembrosGestao.condominio_id == self.condo_id).dicts())
                contas = list(models.Contas.select().where(models.Contas.condominio_id == self.condo_id).dicts())
                return {"status": "success", "data": {"condominio": condo_data, "membros": membros, "contas": contas}}
            else:
                return {"status": "error", "message": "Condomínio não encontrado."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_condominio_config(self, payload):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        
        try:
            with models.db.atomic():
                condo = models.Condominio.get_or_none(id=self.condo_id)
                if not condo:
                    return {"status": "error", "message": "Condomínio não encontrado."}
                
                condo_data = payload.get("condominio", {})
                membros_data = payload.get("membros", [])
                
                if 'nome' in condo_data: condo.nome = condo_data['nome']
                if 'administradora' in condo_data: condo.administradora = condo_data['administradora']
                if 'telefone_administradora' in condo_data: condo.telefone_administradora = json.dumps(condo_data['telefone_administradora'])
                if 'apartamentos' in condo_data: condo.apartamentos = json.dumps(condo_data['apartamentos'])
                if 'prazo_fechamento' in condo_data: condo.prazo_fechamento = condo_data['prazo_fechamento']
                if 'inadimplencia_data_corte' in condo_data: condo.inadimplencia_data_corte = condo_data['inadimplencia_data_corte']
                if 'inadimplencia_unidades' in condo_data: condo.inadimplencia_unidades = condo_data['inadimplencia_unidades']
                if 'inadimplencia_valor' in condo_data: condo.inadimplencia_valor = condo_data['inadimplencia_valor']
                if 'saldo_declarado' in condo_data: condo.saldo_declarado = condo_data['saldo_declarado']
                
                condo.ultima_atualizacao = datetime.now().isoformat()
                
                condo.save()
                
                models.MembrosGestao.delete().where(models.MembrosGestao.condominio_id == self.condo_id).execute()
                
                for m in membros_data:
                    models.MembrosGestao.create(
                        condominio_id=self.condo_id,
                        nome=m.get('nome'),
                        cargo=m.get('cargo')
                    )
                
                contas_data = payload.get("contas", [])
                models.Contas.delete().where(models.Contas.condominio_id == self.condo_id).execute()
                for c in contas_data:
                    models.Contas.create(
                        condominio_id=self.condo_id,
                        conta=c.get('conta'),
                        saldo_inicial=c.get('saldo_inicial', 0.0)
                    )
                    
            return {"status": "success", "message": "Configurações atualizadas com sucesso."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_pendencias_revisao_count(self, exibir_revisados=False):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        
        try:
            m = models.Meses
            c = models.Categorias
            s = models.Subcategorias
            t = models.Transacoes
            a = models.Anexos
            p = models.PrestacoesContas
            
            def get_cond(model):
                if exibir_revisados:
                    return (model.revisado_usuario == 1) & (model.consistente == 0) & (m.condominio_id == self.condo_id)
                else:
                    return (model.revisado_usuario == 0) & (m.condominio_id == self.condo_id)
            
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

    def get_dashboard_kpis(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        
        try:
            condo = models.Condominio.get_or_none(id=self.condo_id)
            
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
            
            estatisticas["transacoes_total"] = t.select().join(s).join(c).join(m).where(m.condominio_id == self.condo_id).count()
            estatisticas["meses_lidos"] = m.select().where(m.condominio_id == self.condo_id).count()
            
            anexos_count = a.select().join(t).join(s).join(c).join(m).where(m.condominio_id == self.condo_id).count()
            prestacoes_count = p.select().join(m).where(m.condominio_id == self.condo_id).count()
            estatisticas["anexos_baixados"] = anexos_count + prestacoes_count
            
            membros_gestao = list(models.MembrosGestao.select().where(models.MembrosGestao.condominio_id == self.condo_id).dicts())
            
            gestao = {
                "membros": membros_gestao,
                "administradora": administradora
            }
            
            totais = m.select(
                models.fn.SUM(m.receita_total).alias('tr'),
                models.fn.SUM(m.despesa_total).alias('td')
            ).where(m.condominio_id == self.condo_id).scalar(as_tuple=True)
            
            if totais:
                tr, td = totais
            else:
                tr, td = 0, 0
                
            contas_info = models.Contas.select(
                models.fn.SUM(models.Contas.saldo_inicial).alias('total'),
                models.fn.COUNT(models.Contas.id).alias('count')
            ).where(models.Contas.condominio_id == self.condo_id).scalar(as_tuple=True)
            
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
            mes = m.get_or_none((m.condominio_id == self.condo_id) & (m.competencia == current_date_str))
            
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

    def get_transacoes(self, start_date=None, end_date=None):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
            
        try:
            condo = models.Condominio.get_or_none(models.Condominio.id == self.condo_id)
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
                        t.data,
                        t.valor,
                        t.consistente,
                        t.revisado_usuario,
                        t.anexos.alias('anexos_count')
                     )
                     .join(s)
                     .join(c)
                     .join(m)
                     .where(m.condominio_id == self.condo_id))
                     
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

    def get_registros_nao_revisados(self, tipo_tabela, exibir_revisados=False):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            m = models.Meses
            c = models.Categorias
            s = models.Subcategorias
            t = models.Transacoes
            
            def get_cond(model):
                if exibir_revisados:
                    return (model.revisado_usuario == 1) & (model.consistente == 0) & (m.condominio_id == self.condo_id)
                else:
                    return (model.revisado_usuario == 0) & (m.condominio_id == self.condo_id)
            
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
        if self.init_error:
            return {"status": "error", "message": self.init_error}
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
                                    abs_file_path = os.path.join(project_root, pc.caminho_local)
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
                                dest_dir = os.path.join(project_root, "anexos", str(reg.condominio_id), chave_unica)
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
                                    abs_file_path = os.path.join(project_root, anexo.caminho_local)
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
                                dest_dir = os.path.join(project_root, "anexos", str(mes.condominio_id), chave_unica)
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
                        old_path = os.path.join(project_root, reg.caminho_local)
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

    def get_inadimplencia(self, data_corte=None):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
            
        try:
            # Se data de corte não for informada, utiliza a data do sistema
            hoje_dt = datetime.now()
            if data_corte:
                corte_dt = datetime.strptime(data_corte, "%Y-%m-%d")
            else:
                corte_dt = hoje_dt
                data_corte = hoje_dt.strftime("%Y-%m-%d")
                
            hoje_str = hoje_dt.strftime("%Y-%m-%d")
            
            condo = models.Condominio.get_or_none(models.Condominio.id == self.condo_id)
            if not condo:
                return {"status": "error", "message": "Condomínio não encontrado."}
                
            apartamentos = []
            if condo.apartamentos:
                apartamentos = json.loads(condo.apartamentos)
                
            taxas_query = models.Taxas.select(
                models.Taxas, models.Renegociacao.data_renegociacao
            ).join(
                models.Renegociacao, JOIN.LEFT_OUTER, on=(models.Taxas.renegociacao_id == models.Renegociacao.id)
            ).where(
                (models.Taxas.condominio_id == self.condo_id) &
                (models.Taxas.tipo.in_(['C', 'I', 'D', 'E', 'P', 'R']))
            )
            taxas = list(taxas_query.dicts())
            
            # Pre-filter taxas by date in Python to avoid SQLite string format issues
            # vencimento is stored as DD/MM/YYYY
            taxas_comuns_filtradas = []
            taxas_individuais_map = {}
            
            descontos_agregados = {}
            
            for t in taxas:
                if t['tipo'] in ['P', 'R']:
                    if t.get('data_renegociacao'):
                        try:
                            # Tenta parsear formato do bd
                            dt_ren = datetime.strptime(t['data_renegociacao'], "%d/%m/%Y")
                        except Exception:
                            try:
                                dt_ren = datetime.strptime(t['data_renegociacao'], "%Y-%m-%d")
                            except Exception:
                                dt_ren = None
                        if dt_ren and corte_dt.date() < dt_ren.date():
                            continue # descarta
                            
                if t['tipo'] in ['D', 'R']:
                    key = (t.get('apartamento'), t.get('taxa_id'))
                    if key not in descontos_agregados:
                        descontos_agregados[key] = {
                            'valor_original': 0, 'desconto_vista': 0, 
                            'multa_atraso': 0, 'juros_dia_atraso': 0
                        }
                    d_agg = descontos_agregados[key]
                    d_agg['valor_original'] += (t.get('valor_original') or 0)
                    d_agg['desconto_vista'] += (t.get('desconto_vista') or 0)
                    d_agg['multa_atraso'] += (t.get('multa_atraso') or 0)
                    d_agg['juros_dia_atraso'] += (t.get('juros_dia_atraso') or 0)
                    continue
                try:
                    v_dt = datetime.strptime(t['vencimento'], "%d/%m/%Y")
                    if v_dt < corte_dt:
                        t['_venc_dt'] = v_dt
                        if t['tipo'] in ['C', 'E']:
                            taxas_comuns_filtradas.append(t)
                        elif t['tipo'] in ['I', 'P']:
                            apto_taxa = t.get('apartamento')
                            if apto_taxa:
                                if apto_taxa not in taxas_individuais_map:
                                    taxas_individuais_map[apto_taxa] = []
                                taxas_individuais_map[apto_taxa].append(t)
                except Exception:
                    pass
            
            # Buscar transações de recebimento (tipo 'R') do condomínio
            todas_transacoes = list(models.Transacoes.select(
                models.Transacoes.apartamento,
                models.Transacoes.competencia,
                models.Transacoes.valor,
                models.Transacoes.data
            ).join(models.Subcategorias).join(models.Categorias).join(models.Meses).where(
                (models.Meses.condominio_id == self.condo_id) &
                (models.Transacoes.tipo == 'R') &
                (models.Transacoes.apartamento.is_null(False)) &
                (models.Transacoes.competencia.is_null(False))
            ).dicts())
            
            # Filtrar transações por data_corte no Python, já que SQLite não suporta string compare para DD/MM/YYYY
            transacoes = []
            for t in todas_transacoes:
                try:
                    t_data = datetime.strptime(t['data'], "%d/%m/%Y").date()
                except Exception:
                    try:
                        t_data = datetime.strptime(t['data'], "%Y-%m-%d").date()
                    except Exception:
                        continue
                
                if t_data <= corte_dt.date():
                    transacoes.append(t)
            
            resultado = []
            
            for apto in apartamentos:
                taxas_apto = [dict(t) for t in taxas_comuns_filtradas] # Cópia independente
                if apto in taxas_individuais_map:
                    taxas_apto.extend([dict(t) for t in taxas_individuais_map[apto]])
                    
                # Aplicar descontos na memória
                for t_apto in taxas_apto:
                    key = (apto, t_apto['id'])
                    if key in descontos_agregados:
                        d_agg = descontos_agregados[key]
                        t_apto['valor_original'] = max(0, t_apto['valor_original'] - d_agg['valor_original'])
                        t_apto['desconto_vista'] = max(0, (t_apto['desconto_vista'] or 0) - d_agg['desconto_vista'])
                        t_apto['multa_atraso'] = max(0, (t_apto['multa_atraso'] or 0) - d_agg['multa_atraso'])
                        t_apto['juros_dia_atraso'] = max(0, (t_apto['juros_dia_atraso'] or 0) - d_agg['juros_dia_atraso'])
                
                # Agrupar transações do apartamento por competência para evitar iteração linear excessiva
                transacoes_apto_map = {}
                for t in transacoes:
                    if t['apartamento'] == apto:
                        comp = t['competencia']
                        if comp not in transacoes_apto_map:
                            transacoes_apto_map[comp] = []
                        transacoes_apto_map[comp].append(t)
                
                taxas_nao_pagas = []
                for taxa in taxas_apto:
                    if taxa['valor_original'] == 0:
                        continue # Deduzido a zero, considerada paga
                    pagamento_encontrado = False
                    comp_taxa = taxa['competencia']
                    
                    if comp_taxa in transacoes_apto_map:
                        transacoes_comp = transacoes_apto_map[comp_taxa]
                        # Encontrar se houve pagamento exato correspondente considerando desconto_vista
                        for idx, transacao in enumerate(transacoes_comp):
                            try:
                                t_data = datetime.strptime(transacao['data'], "%d/%m/%Y").date()
                            except Exception:
                                # Fallback em caso de formato inesperado
                                try:
                                    t_data = datetime.strptime(transacao['data'], "%Y-%m-%d").date()
                                except Exception:
                                    continue
                            
                            v_date = taxa['_venc_dt'].date()
                            if t_data <= v_date:
                                valor_esperado = taxa['valor_original'] - (taxa['desconto_vista'] or 0)
                            else:
                                valor_esperado = taxa['valor_original']
                                
                            if abs(transacao['valor'] - valor_esperado) < 0.01:
                                pagamento_encontrado = True
                                # Remover a transação para não dar match duplo
                                transacoes_comp.pop(idx)
                                break
                            
                    if not pagamento_encontrado:
                        taxa_venc_dt = taxa['_venc_dt']
                        dias_atraso = (corte_dt.date() - taxa_venc_dt.date()).days
                        if dias_atraso < 0:
                            dias_atraso = 0
                            
                        juros_total = dias_atraso * (taxa['juros_dia_atraso'] or 0)
                        
                        taxas_nao_pagas.append({
                            "competencia": taxa['competencia'],
                            "exibicao": taxa['exibicao'],
                            "valor": taxa['valor_original'],
                            "vencimento": taxa['vencimento'],
                            "descricao": taxa['descricao'],
                            "multa": taxa['multa_atraso'],
                            "juros_total": juros_total,
                            "dias_vencidos": dias_atraso,
                            "_venc_dt": taxa_venc_dt
                        })
                
                if taxas_nao_pagas:
                    # Ordenar taxas_nao_pagas por ordem crescente (do mais antigo para o mais recente)
                    taxas_nao_pagas.sort(key=lambda x: x['_venc_dt'])
                    # Remover campo auxiliar antes de devolver ao front
                    for t in taxas_nao_pagas:
                        t.pop('_venc_dt', None)
                        
                    resultado.append({
                        "unidade": apto,
                        "taxas": taxas_nao_pagas
                    })
                    
            # Ordenar os apartamentos alfabeticamente
            resultado.sort(key=lambda x: str(x['unidade']))
            
                    
            return {"status": "success", "data": resultado}
            
        except Exception as e:
            logger.error(f"Erro em get_inadimplencia: {e}")
            return {"status": "error", "message": str(e)}



    def get_taxas_por_apartamento(self, apartamento, competencia, tipos=None):
        if tipos is None:
            tipos = ['C','E','I']
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            query = models.Taxas.select().where(
                (models.Taxas.condominio_id == self.condo_id) &
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
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            taxas = list(models.Taxas.select().where(
                (models.Taxas.condominio_id == self.condo_id) &
                (models.Taxas.tipo.in_(tipos))
            ).order_by(models.Taxas.competencia.desc()).dicts())
            return {"status": "success", "data": taxas}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def delete_taxa(self, taxa_id):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            taxa = models.Taxas.get_by_id(taxa_id)
            if taxa.tipo in ['P', 'R']:
                return {"status": "error", "message": "Taxas de renegociação não podem ser excluídas individualmente. Exclua a renegociação inteira."}
            taxa.delete_instance()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def update_taxa(self, taxa_id, payload):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            taxa = models.Taxas.get_by_id(taxa_id)
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
                taxa_pai = models.Taxas.get_by_id(taxa_vinculada_id)
                taxa.vencimento = taxa_pai.vencimento
                taxa.taxa_id = taxa_vinculada_id
            else:
                if 'vencimento' in payload: taxa.vencimento = payload['vencimento']
                taxa.taxa_id = None
                
            if 'descricao' in payload: taxa.descricao = payload['descricao']
            if 'valor_original' in payload: taxa.valor_original = payload['valor_original']
            if 'desconto_vista' in payload: taxa.desconto_vista = payload['desconto_vista']
            if 'multa_atraso' in payload: taxa.multa_atraso = payload['multa_atraso']
            if 'juros_dia_atraso' in payload: taxa.juros_dia_atraso = payload['juros_dia_atraso']
            if 'tipo' in payload: taxa.tipo = payload['tipo']
            if 'apartamento' in payload: taxa.apartamento = payload['apartamento']
            taxa.save()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def insert_taxa(self, payload):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            meses_repeticao = payload.get('meses_repeticao', 1)
            base_competencia = payload.get('competencia')
            tipo = payload.get('tipo', 'C')
            taxa_id_ref = payload.get('taxa_id')
            
            base_vencimento = payload.get('vencimento')
            if tipo == 'D' and taxa_id_ref:
                taxa_pai = models.Taxas.get_by_id(taxa_id_ref)
                base_vencimento = taxa_pai.vencimento
                
            descricao = payload.get('descricao')
            valor_original = payload.get('valor_original', 0.0)
            desconto_vista = payload.get('desconto_vista', 0.0)
            multa_atraso = payload.get('multa_atraso', 0.0)
            juros_dia_atraso = payload.get('juros_dia_atraso', 0.0)
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
                        condominio_id=self.condo_id,
                        competencia=comp_str,
                        exibicao=exib_str,
                        vencimento=venc_str,
                        descricao=descricao,
                        valor_original=valor_original,
                        desconto_vista=desconto_vista,
                        multa_atraso=multa_atraso,
                        juros_dia_atraso=juros_dia_atraso,
                        tipo=tipo,
                        apartamento=apartamento,
                        taxa_id=taxa_id_ref if tipo == 'D' else None
                    )
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_renegociacao(self, renegociacao_id):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
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

    def delete_renegociacao(self, renegociacao_id):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            models.Renegociacao.delete().where(models.Renegociacao.id == renegociacao_id).execute()
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def salvar_renegociacao(self, payload):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
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
                if ren_id:
                    models.Renegociacao.delete().where(models.Renegociacao.id == ren_id).execute()
                
                nova_ren = models.Renegociacao.create(
                    condominio_id=self.condo_id,
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
                        condominio_id=self.condo_id,
                        renegociacao_id=nova_ren.id,
                        competencia=p_comp,
                        exibicao=exib_str,
                        vencimento=p.get('vencimento'),
                        descricao=p.get('descricao'),
                        valor_original=p.get('valor_original', 0.0),
                        desconto_vista=p.get('desconto_vista', 0.0),
                        multa_atraso=p.get('multa_atraso', 0.0),
                        juros_dia_atraso=p.get('juros_dia_atraso', 0.0),
                        apartamento=apartamento,
                        tipo='P'
                    )
                
                for t_id in taxas_originais:
                    t_orig = models.Taxas.get_by_id(t_id)
                    models.Taxas.create(
                        condominio_id=self.condo_id,
                        renegociacao_id=nova_ren.id,
                        taxa_id=t_orig.id,
                        competencia=t_orig.competencia,
                        exibicao=t_orig.exibicao,
                        vencimento=t_orig.vencimento,
                        descricao=f"Renegociado: {t_orig.descricao}",
                        valor_original=t_orig.valor_original,
                        desconto_vista=t_orig.desconto_vista,
                        multa_atraso=t_orig.multa_atraso,
                        juros_dia_atraso=t_orig.juros_dia_atraso,
                        apartamento=apartamento,
                        tipo='R'
                    )
                    
            return {"status": "success"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


    def selecionar_arquivo(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        if self._main_window:
            import webview
            result = self._main_window.create_file_dialog(webview.OPEN_DIALOG)
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
        full_path = os.path.join(project_root, caminho_local)
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
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            anexos = list(models.Anexos.select().where(models.Anexos.transacao_id == transacao_id).dicts())
            return {"status": "success", "data": anexos}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_prestacoes_contas_mes(self, mes_competencia):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            mes = models.Meses.get_or_none((models.Meses.condominio_id == self.condo_id) & (models.Meses.competencia == mes_competencia))
            if not mes:
                return {"status": "error", "message": "Mês não encontrado."}
                
            prestacoes = list(models.PrestacoesContas.select().where(models.PrestacoesContas.mes_id == mes.id).dicts())
            return {"status": "success", "data": prestacoes}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_preferencias(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            pref = models.PreferenciasUsuario.select().first()
            if pref:
                return {"status": "success", "data": pref.__data__}
            return {"status": "success", "data": None}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def salvar_preferencias(self, dados):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
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
        self.prefs_cache = dados
        return {"status": "success"}

    def app_ready(self):
        """Chamado pelo Angular quando o tema foi aplicado e o DOM está pronto."""
        # Mostra a janela principal (que estava hidden)
        if self._main_window:
            try:
                self._main_window.show()
            except Exception:
                pass
        # Destrói a splash screen
        if self._splash_window:
            try:
                self._splash_window.destroy()
            except Exception:
                pass
            self._splash_window = None
        return {"status": "success"}

    def _get_db_path(self):
        return os.path.join(project_root, "database", "winker_data.db")

def main():
    html_content = None
    html_path = None
    
    # 1. Verifica se a base de dados SQLite existe
    db_path = os.path.join(project_root, "database", "winker_data.db")
    if not os.path.exists(db_path):
        logger.warning("AVISO: Banco de dados não encontrado em database/winker_data.db!")
        html_content = "<html><head><meta charset='utf-8'/><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;padding:40px;background:#1e293b;color:#f8fafc;}h2{color:#eab308;}code{background:#334155;padding:2px 6px;border-radius:4px;font-family:monospace;}ol{line-height:1.6;}</style></head><body><h2>Banco de Dados Não Encontrado</h2><p>Não foi possível localizar o banco de dados local em <code>database/winker_data.db</code>.</p><p><b>Como resolver:</b> Você precisa realizar a extração inicial de dados para criar e popular o banco de dados antes de abrir o painel. Por favor:</p><ol><li>Dê um duplo clique no atalho <b><code>Extrair_Dados.lnk</code></b> (ou <b><code>Extrair_Dados_Headless.lnk</code></b>) na raiz do projeto.</li><li>Aguarde o extrator concluir o processamento de pelo menos um período de transações.</li><li>Após o término da extração com sucesso, abra novamente o dashboard.</li></ol></body></html>"
        logger.info("Carregando aviso de banco de dados ausente...")
    else:
        # 2. Se o banco de dados existe, verifica a existência do frontend compilado
        angular_dist_dir = os.path.join(project_root, "compilados", "browser")
        angular_index = os.path.join(angular_dist_dir, "index.html")
        angular_src_dir = os.path.join(project_root, "dashboard")
        
        if not os.path.exists(angular_index):
            logger.warning("Compilados do frontend não encontrados na pasta 'compilados/'.")
            logger.info("Iniciando montagem automática do frontend...")
            
            node_modules_dir = os.path.join(angular_src_dir, "node_modules")
            
            # 1. Verifica se node_modules existe, senão instala
            if not os.path.exists(node_modules_dir):
                logger.info("Pasta node_modules não encontrada. Executando 'npm install'...")
                try:
                    subprocess.check_call(["npm", "install"], cwd=angular_src_dir, shell=True)
                    logger.info("Instalação das dependências concluída com sucesso!")
                except subprocess.CalledProcessError as e:
                    logger.error(f"Erro ao instalar dependências via npm install: {e}")
                    sys.exit(1)
                    
            # 2. Executa a compilação de produção
            logger.info("Executando compilação do Angular ('npm run build')...")
            try:
                subprocess.check_call(["npm", "run", "build"], cwd=angular_src_dir, shell=True)
                logger.info("Compilação concluída com sucesso!")
            except subprocess.CalledProcessError as e:
                logger.error(f"Erro ao compilar o frontend: {e}")
                
        # Verifica novamente se o build foi criado
        if os.path.exists(angular_index):
            html_path = angular_index
            logger.info(f"Carregando interface Angular compilada de: {html_path}")
        else:
            html_path = os.path.join(project_root, "dashboard.html")
            if not os.path.exists(html_path):
                html_content = "<html><head><meta charset='utf-8'/><style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;padding:40px;background:#1e293b;color:#f8fafc;}h2{color:#f43f5e;}code{background:#334155;padding:2px 6px;border-radius:4px;font-family:monospace;}</style></head><body><h2>Erro de Inicialização do Dashboard</h2><p>Não foi possível encontrar ou compilar a interface do dashboard.</p><p><b>Possível Solução:</b> O sistema precisa do <b>Node.js</b> instalado para compilar o frontend Angular pela primeira vez. Por favor:</p><ol><li>Instale o Node.js (recomendado v18 ou superior).</li><li>Abra um terminal na pasta <code>dashboard/</code> do projeto e execute:</li><pre><code>npm install<br/>npm run build</code></pre><li>Após a compilação, reinicie este aplicativo.</li></ol></body></html>"
            logger.warning(f"Interface Angular não disponível. Carregando fallback: {html_path}")
        


    api = Api()

    # Cria a splash screen como janela separada (banner de carregamento)
    splash_window = None
    if html_content is None:
        splash_html_path = None
        candidates = [
            os.path.join(project_root, "compilados", "browser", "splash.html"),
            os.path.join(project_root, "dashboard", "public", "splash.html")
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                splash_html_path = candidate
                break
        
        if splash_html_path:
            # Calcula posição centralizada na tela
            splash_w, splash_h = 480, 350
            scr_w, scr_h = 1920, 1080
            try:
                user32 = ctypes.windll.user32
                scr_w = user32.GetSystemMetrics(0)
                scr_h = user32.GetSystemMetrics(1)
            except Exception:
                pass
            splash_x = (scr_w - splash_w) // 2
            splash_y = (scr_h - splash_h) // 2
            
            splash_window = webview.create_window(
                title="",
                url=splash_html_path,
                width=splash_w,
                height=splash_h,
                x=splash_x,
                y=splash_y,
                resizable=False,
                frameless=True,
                on_top=True,
                background_color='#E9F2FC'
            )
            api._splash_window = splash_window
            logger.info("Splash screen criada.")
    
    # Cria a janela desktop nativa provida pelo PyWebView
    if html_content is not None:
        # Janela de erro — exibe imediatamente, sem splash
        window = webview.create_window(
            title="Dashboard",
            html=html_content,
            js_api=api,
            width=1280,
            height=800,
            resizable=True,
            maximized=True
        )
    else:
        # Janela Angular — inicia oculta até o tema ser aplicado
        window = webview.create_window(
            title="Dashboard",
            url=html_path,
            js_api=api,
            width=1280,
            height=800,
            resizable=True,
            maximized=True,
            hidden=True
        )
    
    api._main_window = window

    def on_closing():
        try:
            if api.prefs_cache:
                api.salvar_preferencias({
                    'modo_escuro': 1 if api.prefs_cache.get('darkTheme') else 0,
                    'cor_primaria': api.prefs_cache.get('primary'),
                    'cor_superficie': api.prefs_cache.get('surface'),
                    'tema_preset': api.prefs_cache.get('preset'),
                    'modo_menu': api.prefs_cache.get('menuMode')
                })
        except Exception as e:
            logger.error(f"Erro ao salvar preferências no encerramento: {e}")

    window.events.closing += on_closing
    
    # Inicia o loop de eventos
    webview.start()

if __name__ == "__main__":
    main()
