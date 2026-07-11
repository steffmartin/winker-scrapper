import os
import sys
import subprocess

from setup_deps import install_dependencies
install_dependencies()

from peewee import *

db = SqliteDatabase(None)

class BaseModel(Model):
    class Meta:
        database = db

class Condominio(BaseModel):
    id = CharField(primary_key=True)
    nome = CharField(null=True)
    inadimplencia_data_corte = CharField(null=True)
    inadimplencia_unidades = IntegerField(null=True)
    inadimplencia_valor = FloatField(null=True)
    administradora = CharField(null=True)
    telefone_administradora = CharField(null=True)
    ultima_atualizacao = CharField(null=True)
    prazo_fechamento = IntegerField(null=True)

    class Meta:
        table_name = 'condominio'

class MembrosGestao(BaseModel):
    condominio_id = ForeignKeyField(Condominio, backref='membros', on_delete='CASCADE', db_column='condominio_id')
    nome = CharField(null=True)
    cargo = CharField(null=True)

    class Meta:
        table_name = 'membros_gestao'

class Contas(BaseModel):
    condominio_id = ForeignKeyField(Condominio, backref='contas', on_delete='CASCADE', db_column='condominio_id')
    conta = CharField(null=True)
    saldo_inicial = FloatField(null=True)

    class Meta:
        table_name = 'contas'

class Meses(BaseModel):
    condominio_id = ForeignKeyField(Condominio, backref='meses', on_delete='CASCADE', db_column='condominio_id')
    exibicao = CharField(null=True)
    competencia = CharField(null=True)
    receita_total = FloatField(null=True)
    despesa_total = FloatField(null=True)
    anexos = IntegerField(default=0)
    consistente = IntegerField(default=1)
    motivo_inconsistencia = CharField(null=True)
    revisado_usuario = IntegerField(default=0)

    class Meta:
        table_name = 'meses'

class Categorias(BaseModel):
    mes_id = ForeignKeyField(Meses, backref='categorias', on_delete='CASCADE', db_column='mes_id')
    tipo = CharField(null=True)
    nome = CharField(null=True)
    valor = FloatField(null=True)
    consistente = IntegerField(default=1)
    motivo_inconsistencia = CharField(null=True)
    revisado_usuario = IntegerField(default=0)

    class Meta:
        table_name = 'categorias'

class Subcategorias(BaseModel):
    categoria_id = ForeignKeyField(Categorias, backref='subcategorias', on_delete='CASCADE', db_column='categoria_id')
    tipo = CharField(null=True)
    nome = CharField(null=True)
    valor = FloatField(null=True)
    consistente = IntegerField(default=1)
    motivo_inconsistencia = CharField(null=True)
    revisado_usuario = IntegerField(default=0)

    class Meta:
        table_name = 'subcategorias'

class Transacoes(BaseModel):
    subcategoria_id = ForeignKeyField(Subcategorias, backref='transacoes', on_delete='CASCADE', db_column='subcategoria_id')
    tipo = CharField(null=True)
    data = CharField(null=True)
    descricao = CharField(null=True)
    valor = FloatField(null=True)
    apartamento = CharField(null=True)
    competencia = CharField(null=True)
    fornecedor = CharField(null=True)
    conta = CharField(null=True)
    anexos = IntegerField(default=0)
    consistente = IntegerField(default=1)
    motivo_inconsistencia = CharField(null=True)
    revisado_usuario = IntegerField(default=0)

    class Meta:
        table_name = 'transacoes'

class Anexos(BaseModel):
    transacao_id = ForeignKeyField(Transacoes, backref='lista_anexos', on_delete='CASCADE', db_column='transacao_id')
    caminho_local = CharField(null=True)
    nome_original = CharField(null=True)
    extensao = CharField(null=True)
    consistente = IntegerField(default=1)
    motivo_inconsistencia = CharField(null=True)
    revisado_usuario = IntegerField(default=0)

    class Meta:
        table_name = 'anexos'

class PrestacoesContas(BaseModel):
    mes_id = ForeignKeyField(Meses, backref='prestacoes_contas', on_delete='CASCADE', db_column='mes_id')
    caminho_local = CharField(null=True)
    nome_original = CharField(null=True)
    extensao = CharField(null=True)
    consistente = IntegerField(default=1)
    motivo_inconsistencia = CharField(null=True)
    revisado_usuario = IntegerField(default=0)

    class Meta:
        table_name = 'prestacoes_contas'

class Auditoria(BaseModel):
    condominio_id = CharField(null=True)
    usuario_uuid = CharField(null=True)
    usuario_id = IntegerField(null=True)
    usuario_name = CharField(null=True)
    usuario_cpf = CharField(null=True)
    usuario_rg = CharField(null=True)
    usuario_fone = CharField(null=True)
    usuario_apto = CharField(null=True)
    data_hora_captura = CharField(null=True)
    ip = CharField(null=True)
    mac = CharField(null=True)
    periodo_inicio = CharField(null=True)
    periodo_fim = CharField(null=True)
    downloads_realizados = IntegerField(null=True, default=0)
    transacoes_lidas = IntegerField(null=True, default=0)
    tempo_duracao = FloatField(null=True, default=0.0)
    capturou_condominio = IntegerField(null=True, default=0)
    capturou_inadimplencia = IntegerField(null=True, default=0)
    capturou_membros = IntegerField(null=True, default=0)

    class Meta:
        table_name = 'auditoria'

class PreferenciasUsuario(BaseModel):
    modo_escuro = IntegerField(default=0)
    cor_primaria = CharField(null=True)
    cor_superficie = CharField(null=True)
    tema_preset = CharField(null=True)
    modo_menu = CharField(null=True)
    condominio_id = CharField(null=True)

    class Meta:
        table_name = 'preferencias_usuario'

def init_models(db_path):
    db.init(db_path, pragmas={'foreign_keys': 1})
    db.connect(reuse_if_open=True)
    db.create_tables([
        Condominio, MembrosGestao, Contas, Meses, Categorias, Subcategorias, 
        Transacoes, Anexos, PrestacoesContas, Auditoria, PreferenciasUsuario
    ], safe=True)
