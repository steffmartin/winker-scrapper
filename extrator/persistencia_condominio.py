"""Persistência de condomínio, inadimplência e gestão."""

import json
from datetime import datetime

from compartilhado import models
from compartilhado.utils import logger


def save_condominio_and_gestao(condo_id, condo_nome, data_corte, unidades, valor, administradora, telefone, membros):
    """
    Salva ou atualiza os dados raiz do condomínio e sua gestão (síndico, conselheiros).
    """

    try:
        cond, created = models.Condominio.get_or_create(id=condo_id)
        if condo_nome:
            cond.nome = condo_nome
        if data_corte and unidades is not None and valor is not None:
            cond.inadimplencia_data_corte = data_corte
            cond.inadimplencia_unidades = unidades
            cond.inadimplencia_valor = valor
        if administradora: cond.administradora = administradora
        if telefone is not None: cond.telefone_administradora = json.dumps(telefone)
        cond.ultima_atualizacao = datetime.now().isoformat()
        cond.save()
        
        # Preserva os membros existentes caso 'membros' esteja vazio ou ausente (modo fallback)
        if membros:
            membros_validos = [m for m in membros if m and m.get('nome') and str(m.get('nome')).strip()]
            if membros_validos:
                models.MembrosGestao.delete().where(models.MembrosGestao.condominio_id == condo_id).execute()
                for m in membros_validos:
                    models.MembrosGestao.create(condominio_id=condo_id, nome=str(m['nome']).strip(), cargo=m.get('cargo') or 'Membro da Gestão')
            else:
                logger.debug("Nenhum membro válido extraído; preservando membros da gestão existentes no banco.")
        else:
            logger.debug("Lista de membros vazia ou não obtida; preservando síndico e corpo diretivo existentes no banco.")
    except Exception as e:
        logger.error(f"Erro ao salvar dados do condomínio: {e}")


def atualizar_saldo_declarado(condominio_id, saldo):
    """Atualiza o saldo lido no balancete do condomínio."""
    models.Condominio.update(saldo_declarado=saldo).where(models.Condominio.id == condominio_id).execute()
