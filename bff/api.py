"""Interface desktop e estado compartilhado entre os módulos de tela."""
import json
import os

from compartilhado import models
from bff.relatorios import Relatorios
from bff.configuracoes import Configuracoes
from bff.dashboard import Dashboard
from bff.transacoes import Transacoes
from bff.revisao import Revisao
from bff.inadimplencia import Inadimplencia
from bff.taxas import Taxas
from bff.renegociacoes import Renegociacoes
from bff.arquivos import Arquivos
from bff.preferencias import Preferencias
from bff.validacao import validar_margem_encargos
from bff.importacao import Importacao


class Api:
    def __init__(self, db_path=None, raiz_projeto=None):
        self._raiz_projeto = raiz_projeto or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._importacao = Importacao(self)
        self._relatorios = Relatorios(self)
        self._tela_configuracoes = Configuracoes(self)
        self._tela_dashboard = Dashboard(self)
        self._tela_transacoes = Transacoes(self)
        self._tela_revisao = Revisao(self)
        self._tela_inadimplencia = Inadimplencia(self)
        self._tela_taxas = Taxas(self)
        self._tela_renegociacoes = Renegociacoes(self)
        self._tela_arquivos = Arquivos(self)
        self._tela_preferencias = Preferencias(self)
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

    def _calcular_posicao_unificada(self, data_corte, filtros=None, permitir_inconclusivo=False):
        """Consulta e calcula a posição sem alterar os registros de origem."""
        from bff.conciliacao_unificada import calcular_posicao, consultar
        condo = models.Condominio.get_or_none(models.Condominio.id == self.condo_id)
        if not condo:
            raise ValueError('Condomínio não encontrado.')
        apartamentos = json.loads(condo.apartamentos or '[]')
        if not isinstance(apartamentos, list) or not all(isinstance(a, str) for a in apartamentos):
            raise ValueError('Cadastro de apartamentos inválido.')
        filtros = filtros or {}
        selecionados = filtros.get('apartamentos') or []
        if not isinstance(selecionados, list) or not all(isinstance(a, str) for a in selecionados):
            raise ValueError('Filtro de apartamentos inválido.')
        if selecionados:
            apartamentos = list(dict.fromkeys(selecionados))
        taxas, recebimentos = consultar(models.db.connection(), self.condo_id, selecionados)
        return calcular_posicao(self.condo_id, data_corte, apartamentos, taxas, recebimentos,
                                condo.tipo_juros_multa or 'N',
                                margem_encargos_centavos=validar_margem_encargos(condo.margem_diferenca_encargos), filtros=filtros,
                                permitir_inconclusivo=permitir_inconclusivo)

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

    def listar_configs_importacao(self):
        return self._importacao.arquivos()

    def carregar_config_importacao(self, nome):
        return self._importacao.carregar(nome)

    def iniciar_importacao(self, nome, dados, condominio_id):
        return self._importacao.iniciar(nome, dados, condominio_id)

    def obter_estado_importacao(self, cursor=0):
        return self._importacao.obter_estado(cursor)

    def enviar_entrada_importacao(self, texto):
        return self._importacao.enviar_entrada(texto)

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

    def salvar_relatorio_pdf(self, nome=None):
        return self._relatorios.salvar_relatorio_pdf(nome)

    def get_contas_relatorio(self):
        return self._relatorios.get_contas_relatorio()

    def get_relatorio_conta(self, filtros=None):
        return self._relatorios.get_relatorio_conta(filtros)

    def get_relatorio_inadimplencia(self, filtros=None):
        return self._relatorios.get_relatorio_inadimplencia(filtros)

    def get_relatorio_recebimentos(self, filtros=None):
        return self._relatorios.get_relatorio_recebimentos(filtros)

    def get_apartamentos(self):
        if self.init_error:
            return {"status": "error", "message": self.init_error}
        try:
            condo = models.Condominio.get_or_none(id=self.condo_id)
            if not condo:
                return {"status": "error", "message": "Condomínio não encontrado."}
            apartamentos = json.loads(condo.apartamentos) if condo.apartamentos else []
            if not isinstance(apartamentos, list) or not all(isinstance(a, str) for a in apartamentos):
                raise ValueError("Cadastro de apartamentos inválido.")
            return {"status": "success", "data": apartamentos}
        except (ValueError, TypeError):
            return {"status": "error", "message": "Cadastro de apartamentos inválido."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_condominio_config(self):
        return self._tela_configuracoes.get_condominio_config()

    def update_condominio_config(self, payload):
        return self._tela_configuracoes.update_condominio_config(payload)

    def get_pendencias_revisao_count(self, exibir_revisados=False):
        return self._tela_revisao.get_pendencias_revisao_count(exibir_revisados)

    def get_dashboard_kpis(self):
        return self._tela_dashboard.get_dashboard_kpis()

    def get_transacoes(self, start_date=None, end_date=None):
        return self._tela_transacoes.get_transacoes(start_date, end_date)

    def get_registros_nao_revisados(self, tipo_tabela, exibir_revisados=False):
        return self._tela_revisao.get_registros_nao_revisados(tipo_tabela, exibir_revisados)

    def update_registro_revisado(self, tipo_tabela, payload):
        return self._tela_revisao.update_registro_revisado(tipo_tabela, payload)

    def get_inadimplencia(self, data_corte=None, apartamentos=None):
        return self._tela_inadimplencia.get_inadimplencia(data_corte, apartamentos)



    def get_taxas_por_apartamento(self, apartamento, competencia, tipos=None):
        return self._tela_taxas.get_taxas_por_apartamento(apartamento, competencia, tipos)

    def get_taxas(self, tipos=None):
        return self._tela_taxas.get_taxas(tipos)

    def delete_taxa(self, taxa_id):
        return self._tela_taxas.delete_taxa(taxa_id)

    def update_taxa(self, taxa_id, payload):
        return self._tela_taxas.update_taxa(taxa_id, payload)

    def insert_taxa(self, payload):
        return self._tela_taxas.insert_taxa(payload)

    def get_renegociacao(self, renegociacao_id):
        return self._tela_renegociacoes.get_renegociacao(renegociacao_id)

    def _renegociacao_tem_dependentes(self, renegociacao_id):
        return self._tela_renegociacoes._renegociacao_tem_dependentes(renegociacao_id)

    def delete_renegociacao(self, renegociacao_id):
        return self._tela_renegociacoes.delete_renegociacao(renegociacao_id)

    def salvar_renegociacao(self, payload):
        return self._tela_renegociacoes.salvar_renegociacao(payload)


    def selecionar_arquivo(self):
        return self._tela_arquivos.selecionar_arquivo()

    def abrir_arquivo_local(self, caminho_local):
        return self._tela_arquivos.abrir_arquivo_local(caminho_local)

    def get_anexos_transacao(self, transacao_id):
        return self._tela_arquivos.get_anexos_transacao(transacao_id)

    def get_prestacoes_contas_mes(self, mes_competencia):
        return self._tela_arquivos.get_prestacoes_contas_mes(mes_competencia)

    def get_preferencias(self):
        return self._tela_preferencias.get_preferencias()

    def salvar_preferencias(self, dados):
        return self._tela_preferencias.salvar_preferencias(dados)

    def sync_preferencias_cache(self, dados):
        return self._tela_preferencias.sync_preferencias_cache(dados)

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

    @property
    def raiz_projeto(self):
        return self._raiz_projeto

    def _get_db_path(self):
        return os.path.join(self._raiz_projeto, "compartilhado", "database", "winker_data.db")
