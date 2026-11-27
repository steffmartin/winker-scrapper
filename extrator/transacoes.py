"""Leitura de registros e seus anexos no portal."""

import logging
import sys
import time

from compartilhado.utils import logger
from extrator.interpretacao import parse_currency
from extrator.arquivos import download_anexos


def extract_list_from_modal(iframe, context=None, raiz_projeto=None):
    """
    Extrai as categorias, subcategorias ou transações presentes no modal atual.
    """
    results = []
    last_list = iframe.locator("ion-list").last
    if last_list.count() == 0:
        return results
    locators = last_list.locator("button.item-block, ion-item.item-block")
    count = locators.count()
    for i in range(count):
        try:
            loc = locators.nth(i)
            label_el = loc.locator("ion-label")
            if label_el.count() == 0:
                continue
            h2_el = label_el.locator("h2")
            if h2_el.count() > 0:
                nome = h2_el.first.inner_text().strip()
                p_el = label_el.locator("p")
                if p_el.count() > 0:
                    nome += f" ({p_el.first.inner_text().strip()})"
            else:
                span_el = label_el.locator("span")
                nome = span_el.first.inner_text().strip() if span_el.count() > 0 else label_el.inner_text().strip()
            
            if "R$" in nome and len(nome) < 20:
                continue
                
            valor_el = loc.locator("span[item-right]").first
            valor = valor_el.inner_text().strip() if valor_el.count() > 0 else "R$ 0,00"
            valor = " ".join(valor.split())
            
            anexos = []
            anexos_count = 0
            if context:
                anexos, anexos_count = download_anexos(loc, context, raiz_projeto=raiz_projeto)
                
            if nome:
                results.append({
                    "nome": nome,
                    "valor": valor,
                    "index": i,
                    "anexos": anexos,
                    "anexos_count": anexos_count
                })
        except Exception as e:
            logger.error(f"Erro em extract_list_from_modal no item {i}: {e}", exc_info=True)
            continue
    return results


def ler_transacoes_mes(iframe, context, rec_total_mes, des_total_mes, nome_mes_abbr, ano_item,
                       raiz_projeto, ao_ler, *, ler_lista, esperar_lista, fechar_modal):
    transacoes_lidas = 0
    detalhes_mes = {"receitas": [], "despesas": []}
    for tipo in ["Receita", "Despesa"]:
        val_lado = rec_total_mes if tipo == "Receita" else des_total_mes
        if val_lado == 0:
            continue
        iframe.get_by_role("button", name=tipo, exact=True).click()
        time.sleep(0.5) # Ajustado: Troca rec/desp

        categorias = ler_lista(iframe)
        for cat in categorias:
            cat_val_num = parse_currency(cat['valor'])
            lists_before_cat = iframe.locator("ion-list").count()
            iframe.locator("ion-list").last.locator("button.item-block, ion-item.item-block").nth(cat['index']).click()
            esperar_lista(iframe, lists_before_cat, expected_non_zero=(abs(cat_val_num) > 0.01))

            sub_categorias_lista = ler_lista(iframe)
            sub_data_list = []
            for sub in sub_categorias_lista:
                sub_val_num = parse_currency(sub['valor'])
                lists_before_sub = iframe.locator("ion-list").count()
                iframe.locator("ion-list").last.locator("button.item-block, ion-item.item-block").nth(sub['index']).click()
                esperar_lista(iframe, lists_before_sub, expected_non_zero=(abs(sub_val_num) > 0.01))

                itens_finais = ler_lista(iframe, context, raiz_projeto=raiz_projeto)
                transacoes_lidas += len(itens_finais)
                ao_ler(len(itens_finais))

                if logger.isEnabledFor(logging.INFO):
                    sys.stdout.write(f"\r  Processando transações de {nome_mes_abbr}/{ano_item}: {transacoes_lidas} transações lidas...")
                    sys.stdout.flush()

                sub_data_list.append({
                    "nome": sub['nome'],
                    "valor": sub['valor'],
                    "itens": [{
                        "nome": i['nome'],
                        "valor": i['valor'],
                        "anexos": i.get("anexos", []),
                        "anexos_count": i.get("anexos_count", 0)
                    } for i in itens_finais]
                })

                fechar_modal(iframe)

            detalhes_mes[tipo.lower() + "s"].append({
                "nome": cat['nome'], "valor": cat['valor'], "subcategorias": sub_data_list
            })
            fechar_modal(iframe)

    if logger.isEnabledFor(logging.INFO):
        sys.stdout.write("\n")
        sys.stdout.flush()

    return detalhes_mes
