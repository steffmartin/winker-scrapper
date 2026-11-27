"""Busca e prepara prestações de contas para persistência."""

import os
import re

from compartilhado.utils import logger


def extrair_prestacao_contas(page_pc, iframe_pc, page_pc2, page_pc3, context,
                             mes_num, ano_item, chave_unica, condominio_id,
                             raiz_projeto, ao_baixar, *, baixar, avaliar, extensao_de):
    # 3. Extração da Prestação de contas do mês atual (na segunda aba)
    page_pc.bring_to_front()

    prestacao_contas_info = None

    meses_portugues = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
        7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }

    mes_ext = f"{meses_portugues[mes_num]} {ano_item}"
    col_locator = iframe_pc.locator("ion-col").filter(has_text=mes_ext).first
    visualizar_btn = col_locator.locator("button:has-text('VISUALIZAR')")

    if col_locator.count() > 0 and visualizar_btn.count() > 0:
        try:
            visualizar_btn.click()

            action_sheet_btn = iframe_pc.locator("button.action-sheet-button:has-text('Visualizar')")
            action_sheet_btn.wait_for(state="visible", timeout=10000)

            # Guarda o estado das páginas abertas antes da ação
            pages_before = set(context.pages)

            with page_pc.expect_response("**/register-access*", timeout=15000) as response_info:
                action_sheet_btn.click()
            response = response_info.value

            # Aguarda um instante para o frontend processar a resposta e disparar a abertura do PDF
            page_pc.wait_for_timeout(1500)

            # Fecha quaisquer abas/popups abertos em decorrência do clique
            pages_after = set(context.pages)
            for p in pages_after - pages_before:
                try:
                    # Aguarda a página estar pronta para receber comandos (evita erro de fechamento prematuro)
                    p.wait_for_load_state("domcontentloaded", timeout=3000)
                except:
                    pass
                try:
                    p.close()
                except:
                    pass

            res_data = response.json()
            target_url = res_data.get("return", {}).get("document_link", "")

            if target_url and target_url.startswith("http") and "default/login" not in target_url:
                mes_dir = os.path.join(raiz_projeto, "anexos", "temp") # Será movido abaixo
                default_pdf_name = f"Prestação de contas {mes_ext}"

                # Baixa o arquivo direto na pasta temporária (será movido se o banco de dados commitar)
                temp_path, nome_orig_pdf = baixar(
                    context, target_url, mes_dir,
                    filename_prefix="", default_filename=default_pdf_name
                )

                # Extrai a extensão real
                ext_real = extensao_de(nome_orig_pdf) or "pdf"
                # Renomeia para o padrão da prestação de contas do mês
                caminho_final = os.path.join(raiz_projeto, "anexos", str(condominio_id), chave_unica, f"{chave_unica}_prestacao_contas.{ext_real}")
                caminho_rel = f"anexos/{condominio_id}/{chave_unica}/{chave_unica}_prestacao_contas.{ext_real}"

                pc_consistente, pc_motivo = avaliar('prestacao_contas', extensao=ext_real)

                prestacao_contas_info = {
                    "temp_path": temp_path,
                    "caminho_final": caminho_final,
                    "nome_orig_pdf": nome_orig_pdf,
                    "extensao": ext_real,
                    "caminho_rel": caminho_rel,
                    "pc_consistente": pc_consistente,
                    "pc_motivo": pc_motivo
                }
                ao_baixar()
            else:
                logger.error("  Não foi possível obter URL final de download da prestação de contas.")
        except Exception as err:
            logger.error(f"    Erro ao extrair prestação de contas de {mes_ext}: {err}")
    else:
        fallback_success = False
        try:
            page_pc3.bring_to_front()
            search_term = f"{str(mes_num).zfill(2)}-{ano_item}"
            page_pc3.get_by_placeholder("Pesquisar").fill(search_term)
            page_pc3.get_by_placeholder("Pesquisar").press("Enter")
            page_pc3.wait_for_load_state("networkidle")

            cell = page_pc3.locator("td a").filter(has_text=re.compile(rf"{search_term}$")).first
            if cell.count() > 0:
                dl_btn = cell.locator("xpath=ancestor::tr").locator("a[href*='/download/id/']").first
                if dl_btn.count() > 0:
                    href = dl_btn.get_attribute("href")
                    target_url = f"https://app.winker.com.br{href}"

                    mes_dir = os.path.join(raiz_projeto, "anexos", "temp")
                    default_pdf_name = f"Prestação de contas {mes_ext}"

                    temp_path, nome_orig_pdf = baixar(
                        context, target_url, mes_dir,
                        filename_prefix="", default_filename=default_pdf_name
                    )

                    ext_real = extensao_de(nome_orig_pdf) or "pdf"
                    caminho_final = os.path.join(raiz_projeto, "anexos", str(condominio_id), chave_unica, f"{chave_unica}_prestacao_contas.{ext_real}")
                    caminho_rel = f"anexos/{condominio_id}/{chave_unica}/{chave_unica}_prestacao_contas.{ext_real}"

                    pc_consistente, pc_motivo = avaliar('prestacao_contas', extensao=ext_real)

                    prestacao_contas_info = {
                        "temp_path": temp_path,
                        "caminho_final": caminho_final,
                        "nome_orig_pdf": nome_orig_pdf,
                        "extensao": ext_real,
                        "caminho_rel": caminho_rel,
                        "pc_consistente": pc_consistente,
                        "pc_motivo": pc_motivo
                    }
                    ao_baixar()
                    fallback_success = True
        except Exception as err:
            logger.error(f"    Erro ao extrair prestação de contas (Demonstrativos) de {mes_ext}: {err}")

        if not fallback_success:
            try:
                page_pc2.bring_to_front()
                search_term = f"{str(mes_num).zfill(2)}-{ano_item}"
                page_pc2.get_by_placeholder("Pesquisar").fill(search_term)
                page_pc2.get_by_placeholder("Pesquisar").press("Enter")
                page_pc2.wait_for_load_state("networkidle")

                cell = page_pc2.locator("td a").filter(has_text=re.compile(rf"{search_term}$")).first
                if cell.count() > 0:
                    dl_btn = cell.locator("xpath=ancestor::tr").locator("a[href*='/download/id/']").first
                    if dl_btn.count() > 0:
                        href = dl_btn.get_attribute("href")
                        target_url = f"https://app.winker.com.br{href}"

                        mes_dir = os.path.join(raiz_projeto, "anexos", "temp")
                        default_pdf_name = f"Prestação de contas {mes_ext}"

                        temp_path, nome_orig_pdf = baixar(
                            context, target_url, mes_dir,
                            filename_prefix="", default_filename=default_pdf_name
                        )

                        ext_real = extensao_de(nome_orig_pdf) or "pdf"
                        caminho_final = os.path.join(raiz_projeto, "anexos", str(condominio_id), chave_unica, f"{chave_unica}_prestacao_contas.{ext_real}")
                        caminho_rel = f"anexos/{condominio_id}/{chave_unica}/{chave_unica}_prestacao_contas.{ext_real}"

                        pc_consistente, pc_motivo = avaliar('prestacao_contas', extensao=ext_real)

                        prestacao_contas_info = {
                            "temp_path": temp_path,
                            "caminho_final": caminho_final,
                            "nome_orig_pdf": nome_orig_pdf,
                            "extensao": ext_real,
                            "caminho_rel": caminho_rel,
                            "pc_consistente": pc_consistente,
                            "pc_motivo": pc_motivo
                        }
                        ao_baixar()
                        fallback_success = True
            except Exception as err:
                logger.error(f"    Erro ao extrair prestação de contas (Balancetes) de {mes_ext}: {err}")

            if not fallback_success:
                logger.warning(f"    [AVISO CONSISTÊNCIA] Prestação de contas indisponível.")

    return prestacao_contas_info
