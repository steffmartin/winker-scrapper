"""Avaliação de consistência dos dados extraídos."""

import json
import re

from compartilhado.utils import logger
from extrator.interpretacao import parse_conta, parse_fornecedor, parse_receita_info


def evaluate_entity_consistency(entity_type, **kwargs):
    """
    Avalia as regras de negócio para consistência de diferentes entidades do sistema.
    Tipos suportados: 'mes', 'categoria', 'subcategoria', 'transacao', 'anexo', 'prestacao_contas'.
    Retorna uma tupla onde os dois primeiros elementos são sempre (consistente_flag, motivo_inconsistencia).
    Para 'transacao', retorna adicionalmente (apto, competencia, fornecedor, conta).
    """
    if entity_type == 'mes':
        rec_total = kwargs.get('rec_total_mes', 0.0)
        soma_rec = kwargs.get('soma_cat_rec', 0.0)
        desp_total = kwargs.get('desp_total_mes', 0.0)
        soma_desp = kwargs.get('soma_cat_desp', 0.0)
        
        anexos = kwargs.get('anexos', 0)
        
        mes_rec_ok = abs(rec_total - soma_rec) < 0.01
        mes_desp_ok = abs(desp_total - soma_desp) < 0.01
        mes_prestacao_ok = anexos > 0
        consistente = 1 if (mes_rec_ok and mes_desp_ok and mes_prestacao_ok) else 0
        
        motivo = None
        if not consistente:
            reasons = []
            if not mes_rec_ok:
                reasons.append("Divergência em receitas")
            if not mes_desp_ok:
                reasons.append("Divergência em despesas")
            if not mes_prestacao_ok:
                reasons.append("Mês sem prestação de contas")
            if not reasons:
                reasons.append("Divergência em receitas ou despesas")
            motivo = json.dumps(reasons, ensure_ascii=False)
            
        return consistente, motivo

    elif entity_type == 'categoria':
        nome = kwargs.get('cat_nome', '')
        val_num = kwargs.get('cat_val_num', 0.0)
        soma_sub = kwargs.get('soma_sub', 0.0)
        
        consistente = 1 if abs(val_num - soma_sub) < 0.01 else 0
        motivo = None
        if not consistente:
            logger.debug(f"    [AVISO CONSISTÊNCIA] Categoria '{nome}': Valor informado = R$ {val_num:.2f} | Soma subcategorias = R$ {soma_sub:.2f}")
            motivo = json.dumps(["Soma das subcategorias difere do total da categoria"], ensure_ascii=False)
            
        return consistente, motivo

    elif entity_type == 'subcategoria':
        nome = kwargs.get('sub_nome', '')
        val_num = kwargs.get('sub_val_num', 0.0)
        soma_itens = kwargs.get('soma_itens', 0.0)
        
        consistente = 1 if abs(val_num - soma_itens) < 0.01 else 0
        motivo = None
        if not consistente:
            logger.debug(f"    [AVISO CONSISTÊNCIA] Subcategoria '{nome}': Valor informado = R$ {val_num:.2f} | Soma transações = R$ {soma_itens:.2f}")
            motivo = json.dumps(["Soma das transações difere do total da subcategoria"], ensure_ascii=False)
            
        return consistente, motivo

    elif entity_type == 'transacao':
        tipo_flag = kwargs.get('tipo_flag', '')
        desc_completa = kwargs.get('desc_completa', '')
        desc_f = kwargs.get('desc_f', '')
        anexos_esperados = kwargs.get('anexos_esperados', 0)
        anexos_baixados = kwargs.get('anexos_baixados', 0)
        despesa_anexo_valido = kwargs.get('despesa_anexo_valido', True)
        
        fields_ok = True
        apto, comp = (None, None)
        fornecedor = None
        
        if tipo_flag == "R":
            apto, comp = parse_receita_info(desc_completa)
            if not (apto and apto.strip() and comp and comp.strip()):
                fields_ok = False
        elif tipo_flag == "D":
            fornecedor = parse_fornecedor(desc_f)
                
        contas_list = kwargs.get('contas_list', [])
        conta = parse_conta(desc_completa, contas_list=contas_list)
        for regra in kwargs.get('regras_preenchimento', []):
            if regra['descricao_contem'].strip() and regra['descricao_contem'].casefold() in desc_completa.casefold():
                if regra['campo'] == 'fornecedor' and tipo_flag == 'D' and not (fornecedor and fornecedor.strip()):
                    fornecedor = regra['valor']
                elif regra['campo'] == 'conta' and not (conta and conta.strip()):
                    conta = regra['valor']
        if tipo_flag == 'D' and not (fornecedor and fornecedor.strip()):
            fields_ok = False
        if not (conta and conta.strip()):
            fields_ok = False
            
        anexos_ok = (anexos_esperados == anexos_baixados)
        consistente = 1 if (fields_ok and anexos_ok and despesa_anexo_valido) else 0
        
        motivo = None
        if not consistente:
            reasons = []
            if tipo_flag == "R":
                if not (apto and apto.strip()):
                    reasons.append("Apartamento não identificado")
                if not (comp and comp.strip()):
                    reasons.append("Competência não identificada")
            elif tipo_flag == "D":
                if not (fornecedor and fornecedor.strip()):
                    reasons.append("Fornecedor não identificado")
                if not despesa_anexo_valido:
                    reasons.append("Despesa sem comprovantes")
            if not (conta and conta.strip()):
                reasons.append("Conta não identificada")
            if not anexos_ok:
                reasons.append("Quantidade de anexos divergente")
            if not reasons:
                reasons.append("Dados da transação inconsistentes")
            motivo = json.dumps(reasons, ensure_ascii=False)
            
        return consistente, motivo, apto, comp, fornecedor, conta

    elif entity_type == 'anexo':
        extensao = kwargs.get('extensao', '')
        # Anexo consistente se tiver uma extensão válida de 2 a 5 caracteres alfanuméricos
        consistente = 1 if extensao and re.match(r"^[a-zA-Z0-9]{2,5}$", extensao) else 0
        
        motivo = None
        if not consistente:
            motivo = json.dumps(["Extensão de arquivo inválida ou ausente"], ensure_ascii=False)
            
        return consistente, motivo

    elif entity_type == 'prestacao_contas':
        extensao = kwargs.get('extensao', '')
        consistente = 1 if extensao and re.match(r"^[a-zA-Z0-9]{2,5}$", extensao) else 0
        
        motivo = None
        if not consistente:
            motivo = json.dumps(["Extensão de arquivo inválida ou ausente"], ensure_ascii=False)
            
        return consistente, motivo

    else:
        raise ValueError(f"Tipo de entidade desconhecido para validação de consistência: {entity_type}")
