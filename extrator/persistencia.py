"""Persistência e verificação de consistência da extração."""

import json
import os
import re
import shutil
import tempfile

from compartilhado import models
from extrator.revisoes import (_snapshot_revisoes, _motivos, _reaplicar_revisao_transacao, _restaurar_documentos)
from extrator.arquivos_persistidos import _atualizar_arquivos_mes
from compartilhado.utils import logger
from extrator.consistencia import evaluate_entity_consistency
from extrator.interpretacao import (get_competencia, get_extensao, parse_conta,
    parse_currency, parse_fornecedor, parse_receita_info)








def save_extraction_data_to_db(chave_unica, nome_mes_abbr, ano_item, rec_total_mes, des_total_mes, detalhes_mes, project_root, condominio_id=None, prestacao_contas_info=None, contas_list=None, regras_preenchimento=None, anexos_preservados=None):
    if contas_list is None: contas_list = []
    db_conn = models.db
    anexos_para_mover = []
    exibicao = f"{nome_mes_abbr}/{ano_item}"
    
    try:
        with db_conn.atomic():
            antigo = models.Meses.get_or_none((models.Meses.exibicao == exibicao) & (models.Meses.condominio_id == condominio_id))
            snapshot = _snapshot_revisoes(antigo)
            ocorrencias = {}
            models.Meses.delete().where((models.Meses.exibicao == exibicao) & (models.Meses.condominio_id == condominio_id)).execute()
            
            soma_cat_rec = sum(parse_currency(cat['valor']) for cat in detalhes_mes["receitas"])
            soma_cat_desp = sum(parse_currency(cat['valor']) for cat in detalhes_mes["despesas"])
            
            anexos = 1 if prestacao_contas_info else 0
            
            mes_consistente, mes_motivo = evaluate_entity_consistency(
                'mes', rec_total_mes=rec_total_mes, soma_cat_rec=soma_cat_rec,
                desp_total_mes=des_total_mes, soma_cat_desp=soma_cat_desp,
                anexos=anexos
            )
            
            if not mes_consistente and mes_motivo and "Divergência" in mes_motivo:
                logger.debug(f"    [AVISO CONSISTÊNCIA] Receitas (R$ {rec_total_mes:.2f} / R$ {soma_cat_rec:.2f}). Despesas (R$ {des_total_mes:.2f} / R$ {soma_cat_desp:.2f}).")

            competencia = get_competencia(exibicao)
            
            mes = models.Meses.create(
                condominio_id=condominio_id, exibicao=exibicao, competencia=competencia,
                receita_total=rec_total_mes, despesa_total=des_total_mes, anexos=anexos,
                consistente=mes_consistente, motivo_inconsistencia=mes_motivo, revisado_usuario=mes_consistente
            )
            mes_id = mes.id
            if snapshot['mes'] is not None:
                mes.receita_total, mes.despesa_total = snapshot['mes'][:2]
                mes.revisado_usuario = 1
                mes.save()
            
            if prestacao_contas_info:
                models.PrestacoesContas.create(
                    mes_id=mes_id,
                    caminho_local=prestacao_contas_info["caminho_rel"],
                    nome_original=prestacao_contas_info["nome_orig_pdf"],
                    extensao=prestacao_contas_info["extensao"],
                    consistente=prestacao_contas_info["pc_consistente"],
                    motivo_inconsistencia=prestacao_contas_info["pc_motivo"],
                    revisado_usuario=prestacao_contas_info["pc_consistente"]
                )
                anexos_para_mover.append({
                    "temp_path": prestacao_contas_info["temp_path"],
                    "caminho_final": prestacao_contas_info["caminho_final"]
                })
            
            for t_key in ["receitas", "despesas"]:
                tipo_flag = "R" if t_key == "receitas" else "D"
                for cat in detalhes_mes[t_key]:
                    cat_val_num = parse_currency(cat['valor'])
                    soma_sub = sum(parse_currency(sub['valor']) for sub in cat['subcategorias'])
                    
                    cat_consistente, cat_motivo = evaluate_entity_consistency('categoria', cat_nome=cat['nome'], cat_val_num=cat_val_num, soma_sub=soma_sub)
                    
                    cat_obj = models.Categorias.create(
                        mes_id=mes_id, tipo=tipo_flag, nome=cat['nome'], valor=cat_val_num,
                        consistente=cat_consistente, motivo_inconsistencia=cat_motivo, revisado_usuario=cat_consistente
                    )
                    cat_id = cat_obj.id
                    ck = (tipo_flag, cat['nome'])
                    if ck in snapshot['categorias']:
                        cat_obj.valor = snapshot['categorias'][ck]
                        cat_obj.revisado_usuario = 1
                        cat_obj.save()
                    
                    for sub in cat['subcategorias']:
                        sub_val_num = parse_currency(sub['valor'])
                        soma_itens = sum(parse_currency(item['valor']) for item in sub['itens'])
                        
                        sub_consistente, sub_motivo = evaluate_entity_consistency('subcategoria', sub_nome=sub['nome'], sub_val_num=sub_val_num, soma_itens=soma_itens)
                        
                        sub_obj = models.Subcategorias.create(
                            categoria_id=cat_id, tipo=tipo_flag, nome=sub['nome'], valor=sub_val_num,
                            consistente=sub_consistente, motivo_inconsistencia=sub_motivo, revisado_usuario=sub_consistente
                        )
                        sub_id = sub_obj.id
                        sk = ck + (sub['nome'],)
                        if sk in snapshot['subcategorias']:
                            sub_obj.valor = snapshot['subcategorias'][sk]
                            sub_obj.revisado_usuario = 1
                            sub_obj.save()
                        
                        for item in sub['itens']:
                            desc_completa = item['nome']
                            data_t = None
                            if "(" in desc_completa and ")" in desc_completa:
                                partes = desc_completa.rsplit(" (", 1)
                                desc_f, data_t = partes[0], partes[1].replace(")", "")
                            else:
                                desc_f = desc_completa
                                
                            anexos_esperados = item.get("anexos_count", 0)
                            anexos_baixados = len(item.get("anexos", []))
                            despesa_anexo_valido = not (tipo_flag == "D" and anexos_esperados == 0)
                            
                            trans_consistente, trans_motivo, apto, comp, fornecedor, conta = evaluate_entity_consistency(
                                'transacao', tipo_flag=tipo_flag, desc_completa=desc_completa, desc_f=desc_f,
                                anexos_esperados=anexos_esperados, anexos_baixados=anexos_baixados, despesa_anexo_valido=despesa_anexo_valido,
                                contas_list=contas_list, regras_preenchimento=regras_preenchimento or []
                            )

                            if not trans_consistente:
                                logger.debug(f"    [AVISO CONSISTÊNCIA] Transação '{desc_f}' [{tipo_flag}]: Inconsistente ({trans_motivo})")
                            
                            trans_obj = models.Transacoes.create(
                                subcategoria_id=sub_id, tipo=tipo_flag, data=data_t, descricao=desc_f,
                                valor=parse_currency(item['valor']), apartamento=apto, competencia=comp,
                                fornecedor=fornecedor, conta=conta, anexos=anexos_esperados,
                                consistente=trans_consistente, motivo_inconsistencia=trans_motivo, revisado_usuario=trans_consistente
                            )
                            transacao_id = trans_obj.id
                            base = sk + (tipo_flag, data_t, desc_f, parse_currency(item['valor']))
                            n = ocorrencias.get(base, 0)
                            ocorrencias[base] = n + 1
                            revisao = snapshot['transacoes'].get(base + (n,))
                            for anexo in item.get("anexos", []):
                                temp_path = anexo["temp_path"]
                                nome_orig = anexo["nome_original"]
                                extensao = get_extensao(nome_orig)
                                
                                if os.path.exists(temp_path):
                                    anexo_consistente, anexo_motivo = evaluate_entity_consistency('anexo', extensao=extensao)
                                    
                                    anexo_obj = models.Anexos.create(
                                        transacao_id=transacao_id, caminho_local="", nome_original=nome_orig, extensao=extensao,
                                        consistente=anexo_consistente, motivo_inconsistencia=anexo_motivo, revisado_usuario=anexo_consistente
                                    )
                                    anexo_id = anexo_obj.id
                                    
                                    nome_final = f"{chave_unica}_{cat_id}_{sub_id}_{transacao_id}_{anexo_id}_{nome_orig}"
                                    caminho_relativo = f"anexos/{condominio_id}/{chave_unica}/{nome_final}"
                                    
                                    anexo_obj.caminho_local = caminho_relativo
                                    anexo_obj.save()
                                    
                                    mes_dir = os.path.join(project_root, "anexos", str(condominio_id), chave_unica)
                                    caminho_final = os.path.join(mes_dir, nome_final)
                                    
                                    anexos_para_mover.append({"temp_path": temp_path, "caminho_final": caminho_final})
                            if revisao is not None:
                                motivos_anexo = {'Despesa sem comprovantes', 'Quantidade de anexos divergente'}
                                if motivos_anexo & _motivos(revisao['motivos']) & _motivos(trans_motivo):
                                    restaurados = _restaurar_documentos(models.Anexos, models.Anexos.transacao_id, transacao_id, revisao['documentos'], project_root)
                                    if anexos_preservados is not None:
                                        anexos_preservados.extend(restaurados)
                                _reaplicar_revisao_transacao(trans_obj, revisao, anexos_esperados)
    except Exception as e:
        logger.error(f"Erro DB {chave_unica}: {e}")
        raise e
        
    return mes_id, anexos_para_mover


def persistir_mes(chave_unica, nome_mes_abbr, ano_item, rec_total_mes, des_total_mes,
                 detalhes_mes, project_root, condominio_id, prestacao_contas_info,
                 contas_list, regras_preenchimento, *, salvar, atualizar_arquivos):
    """Persiste um mês e seus arquivos dentro da mesma transação."""
    anexos_preservados = []
    with models.db.atomic():
        mes_id, anexos_para_mover = salvar(
            chave_unica, nome_mes_abbr, ano_item, rec_total_mes, des_total_mes, detalhes_mes, project_root,
            condominio_id=condominio_id, prestacao_contas_info=prestacao_contas_info,
            contas_list=contas_list, regras_preenchimento=regras_preenchimento,
            anexos_preservados=anexos_preservados)
        mes_dir = os.path.join(project_root, 'anexos', str(condominio_id), chave_unica)
        atualizar_arquivos(project_root, mes_dir, anexos_preservados, anexos_para_mover)
    return mes_id, len(anexos_para_mover)
