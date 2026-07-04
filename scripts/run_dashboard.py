import argparse
import os
import subprocess
import sys
from datetime import datetime

# Módulos internos independentes
from utils import logger

# Garantir dependências antes de importar libs externas
from setup_deps import install_dependencies
install_dependencies()

# Dependências externas e modelos
import webview

import models

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)

class Api:
    def __init__(self, condo_id=None, db_path=None):
        self.condo_id = condo_id
        self.db_path = db_path or self._get_db_path()
        self.init_error = None
        self.prefs_cache = None
        self._splash_window = None
        self._main_window = None
        
        if not os.path.exists(self.db_path):
            self.init_error = "Banco de dados não encontrado."
        else:
            models.init_models(self.db_path)
            if not self.condo_id:
                self._initialize_default_condo_id()
                
            if not self.condo_id:
                self.init_error = "Nenhum condomínio definido ou encontrado no banco."

    def _initialize_default_condo_id(self):
        try:
            condo = models.Condominio.select().first()
            if condo:
                self.condo_id = condo.id
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

    def get_condominio_config(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}

        try:
            condo = models.Condominio.get_or_none(id=self.condo_id)
            if condo:
                condo_data = condo.__data__
                membros = list(models.MembrosGestao.select().where(models.MembrosGestao.condominio_id == self.condo_id).dicts())
                return {"status": "success", "data": {"condominio": condo_data, "membros": membros}}
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
                if 'telefone_administradora' in condo_data: condo.telefone_administradora = condo_data['telefone_administradora']
                if 'saldo_inicial' in condo_data: condo.saldo_inicial = condo_data['saldo_inicial']
                if 'prazo_fechamento' in condo_data: condo.prazo_fechamento = condo_data['prazo_fechamento']
                if 'inadimplencia_data_corte' in condo_data: condo.inadimplencia_data_corte = condo_data['inadimplencia_data_corte']
                if 'inadimplencia_unidades' in condo_data: condo.inadimplencia_unidades = condo_data['inadimplencia_unidades']
                if 'inadimplencia_valor' in condo_data: condo.inadimplencia_valor = condo_data['inadimplencia_valor']
                
                from datetime import datetime
                condo.ultima_atualizacao = datetime.now().isoformat()
                
                condo.save()
                
                models.MembrosGestao.delete().where(models.MembrosGestao.condominio_id == self.condo_id).execute()
                
                for m in membros_data:
                    models.MembrosGestao.create(
                        condominio_id=self.condo_id,
                        nome=m.get('nome'),
                        cargo=m.get('cargo')
                    )
                    
            return {"status": "success", "message": "Configurações atualizadas com sucesso."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_inconsistencies_count(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        
        try:
            m = models.Meses
            c = models.Categorias
            s = models.Subcategorias
            t = models.Transacoes
            a = models.Anexos
            p = models.PrestacoesContas
            
            c_m = m.select().where((m.consistente == 0) & (m.revisado_usuario == 0) & (m.condominio_id == self.condo_id)).count()
            c_c = c.select().join(m).where((c.consistente == 0) & (c.revisado_usuario == 0) & (m.condominio_id == self.condo_id)).count()
            c_s = s.select().join(c).join(m).where((s.consistente == 0) & (s.revisado_usuario == 0) & (m.condominio_id == self.condo_id)).count()
            c_t = t.select().join(s).join(c).join(m).where((t.consistente == 0) & (t.revisado_usuario == 0) & (m.condominio_id == self.condo_id)).count()
            c_a = a.select().join(t).join(s).join(c).join(m).where((a.consistente == 0) & (a.revisado_usuario == 0) & (m.condominio_id == self.condo_id)).count()
            c_p = p.select().join(m).where((p.consistente == 0) & (p.revisado_usuario == 0) & (m.condominio_id == self.condo_id)).count()
            
            details = {}
            if c_m > 0: details["meses"] = c_m
            if c_c > 0: details["categorias"] = c_c
            if c_s > 0: details["subcategorias"] = c_s
            if c_t > 0: details["transacoes"] = c_t
            if c_a > 0: details["anexos"] = c_a
            if c_p > 0: details["prestacoes_contas"] = c_p
            
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
                administradora = {
                    "nome": condo.administradora,
                    "telefone": condo.telefone_administradora
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
                
            saldo_inicial = condo.saldo_inicial or 0
            tr = tr or 0
            td = td or 0
            saldo_total = saldo_inicial + tr - td

            saldos = {
                "saldo_total": saldo_total
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
            m = models.Meses
            c = models.Categorias
            s = models.Subcategorias
            t = models.Transacoes
            
            query = (t.select(
                        m.competencia.alias('mes_competencia'),
                        m.exibicao.alias('mes_exibicao'),
                        m.consistente.alias('mes_consistente'),
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
            if len(rows) == 0 and start_date and end_date:
                from datetime import datetime
                try:
                    s_date = datetime.strptime(start_date, '%Y-%m-%d')
                    e_date = datetime.strptime(end_date, '%Y-%m-%d')
                    y, m = s_date.year, s_date.month
                    while (y < e_date.year) or (y == e_date.year and m <= e_date.month):
                        mes_exibicao = f"{m:02d}/{y}"
                        mes_competencia = f"{y}-{m:02d}"
                        meses_dict[mes_competencia] = {
                            "data": {"descricao": mes_exibicao, "competencia": mes_competencia, "valor_total": 0, "tipo_node": "mes", "consistente": 0, "anexos": 0},
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
                except ValueError:
                    pass
            
            for row in rows:
                mes = row["mes_competencia"]
                mes_exibicao = row["mes_exibicao"]
                tipo = "Receitas" if row["categoria_tipo"] == "R" else "Despesas"
                categoria = row["categoria_nome"]
                subcategoria = row["subcategoria_nome"]
                
                if mes not in meses_dict:
                    meses_dict[mes] = {
                        "data": {"descricao": mes_exibicao, "competencia": mes, "valor_total": 0, "tipo_node": "mes", "consistente": row.get("mes_consistente", 1), "anexos": row.get("mes_anexos", 0)},
                        "expanded": False,
                        "children_dict": {}
                    }
                
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
                "data": tree
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def abrir_arquivo_local(self, caminho_local):
        if not caminho_local:
            return {"status": "error", "message": "Caminho inválido."}
        full_path = os.path.join(project_root, caminho_local)
        if os.path.exists(full_path):
            try:
                os.startfile(full_path)
                return {"status": "success"}
            except AttributeError:
                import subprocess
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--condo-id', help='ID do condomínio a ser carregado', default=None)
    parser.add_argument('--dev', action='store_true', help='Modo de desenvolvimento')
    args = parser.parse_args()

    html_content = None
    html_path = None
    
    # 1. Verifica se a base de dados SQLite existe
    db_path = os.path.join(project_root, "database", "winker_data.db")
    if not args.dev and not os.path.exists(db_path):
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
        


    api = Api(condo_id=args.condo_id)

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
                import ctypes
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
