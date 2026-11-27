"""Preservação de revisões e documentos durante a reextração."""

import json
import os
from compartilhado import models


def _snapshot_revisoes(mes):
    snapshot = {'mes': None, 'categorias': {}, 'subcategorias': {}, 'transacoes': {}}
    if not mes:
        return snapshot
    def revisado(obj):
        return obj.revisado_usuario == 1 and obj.consistente == 0
    def documentos(query):
        return [dict(caminho_local=d.caminho_local, nome_original=d.nome_original,
                     extensao=d.extensao, consistente=d.consistente,
                     motivo_inconsistencia=d.motivo_inconsistencia,
                     revisado_usuario=d.revisado_usuario) for d in query]
    if revisado(mes):
        snapshot['mes'] = (mes.receita_total, mes.despesa_total)
    ocorrencias = {}
    for cat in mes.categorias.order_by(models.Categorias.id):
        ck = (cat.tipo, cat.nome)
        if revisado(cat):
            snapshot['categorias'][ck] = cat.valor
        for sub in cat.subcategorias.order_by(models.Subcategorias.id):
            sk = ck + (sub.nome,)
            if revisado(sub):
                snapshot['subcategorias'][sk] = sub.valor
            for trans in sub.transacoes.order_by(models.Transacoes.id):
                base = sk + (trans.tipo, trans.data, trans.descricao, trans.valor)
                n = ocorrencias.get(base, 0)
                ocorrencias[base] = n + 1
                if revisado(trans):
                    snapshot['transacoes'][base + (n,)] = {
                        'motivos': trans.motivo_inconsistencia,
                        'campos': {campo: getattr(trans, campo) for campo in ('apartamento', 'competencia', 'fornecedor', 'conta')},
                        'documentos': documentos(trans.lista_anexos),
                    }
    return snapshot

def _motivos(valor):
    try:
        motivos = json.loads(valor or '[]')
        return set(motivos) if isinstance(motivos, list) and all(isinstance(m, str) for m in motivos) else set()
    except (TypeError, ValueError):
        return set()

def _reaplicar_revisao_transacao(transacao, revisao, anexos_esperados):
    anteriores = _motivos(revisao['motivos'])
    atuais = _motivos(transacao.motivo_inconsistencia)
    corrigidos = set()
    campos = {
        'Apartamento não identificado': 'apartamento',
        'Competência não identificada': 'competencia',
        'Fornecedor não identificado': 'fornecedor',
        'Conta não identificada': 'conta',
    }
    for motivo, campo in campos.items():
        valor = revisao['campos'][campo]
        if motivo in anteriores and motivo in atuais and isinstance(valor, str) and valor.strip():
            setattr(transacao, campo, valor)
            corrigidos.add(motivo)
    documentos_anteriores = {d['nome_original'] for d in revisao['documentos']}
    documentos_atuais = list(transacao.lista_anexos)
    preservou_documento = any(d.nome_original in documentos_anteriores for d in documentos_atuais)
    if preservou_documento and 'Despesa sem comprovantes' in anteriores & atuais:
        corrigidos.add('Despesa sem comprovantes')
    if preservou_documento and len(documentos_atuais) >= anexos_esperados and 'Quantidade de anexos divergente' in anteriores & atuais:
        corrigidos.add('Quantidade de anexos divergente')
    # Um motivo desconhecido ou uma correção vazia exige nova revisão.
    transacao.revisado_usuario = int(not atuais if transacao.consistente else bool(atuais) and atuais <= corrigidos)
    transacao.save()

def _restaurar_documentos(modelo, campo_pai, pai_id, documentos, project_root):
    existentes = {d.nome_original for d in modelo.select().where(campo_pai == pai_id)}
    restaurados = []
    for doc in documentos:
        if doc['nome_original'] not in existentes:
            caminho = doc['caminho_local']
            if not caminho or not os.path.isfile(os.path.join(project_root, caminho)):
                raise FileNotFoundError(f"Documento de revisão não encontrado: {caminho}")
            modelo.create(**{campo_pai.name: pai_id}, **doc)
            restaurados.append(caminho)
            existentes.add(doc['nome_original'])
    return restaurados
