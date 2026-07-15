import unittest
from datetime import datetime
import json
from unittest.mock import MagicMock, patch
import sqlite3

# Importa as funções do script extract_winker
from extract_winker import (
    parse_currency,
    parse_receita_info,
    parse_conta,
    parse_fornecedor,
    get_date_chunks,
    evaluate_entity_consistency
)

class TestExtractWinker(unittest.TestCase):

    def test_parse_currency(self):
        from extract_winker import parse_currency

        self.assertEqual(parse_currency("R$ 1.234,56"), 1234.56)
        self.assertEqual(parse_currency("- R$ 10,00"), -10.00)
        self.assertEqual(parse_currency("R$ 0,00"), 0.0)
        self.assertEqual(parse_currency(""), 0.0)
        self.assertEqual(parse_currency(None), 0.0)
        self.assertEqual(parse_currency("150,75"), 150.75)
        
    def test_get_competencia(self):
        from extract_winker import get_competencia
        self.assertEqual(get_competencia("ABR/2026"), "2026-04")
        self.assertEqual(get_competencia("DEZ/2025"), "2025-12")
        self.assertIsNone(get_competencia(None))
        self.assertIsNone(get_competencia("INVALIDO"))
        
    def test_get_extensao(self):
        from extract_winker import get_extensao
        self.assertEqual(get_extensao("documento.pdf"), "pdf")
        self.assertEqual(get_extensao("foto.JPG"), "jpg")
        self.assertEqual(get_extensao("arquivo.tar.gz"), "gz")
        self.assertEqual(get_extensao("nome-do-arquivo.pdf&h"), "pdf")
        self.assertEqual(get_extensao("doc.pdf?version=1"), "pdf")
        self.assertEqual(get_extensao("planilha.xlsx#section"), "xlsx")
        self.assertEqual(get_extensao("img.png!"), "png")
        self.assertIsNone(get_extensao("sem_extensao"))
        self.assertIsNone(get_extensao(None))

    def test_parse_receita_info(self):
        apto, comp = parse_receita_info("Taxa Ordinária Apto - 101 JUN 2026")
        self.assertEqual(apto, "101")
        self.assertEqual(comp, "2026-06")

        apto, comp = parse_receita_info("Fundo de Reserva Apto/202 OUT 2025")
        self.assertEqual(apto, "202")
        self.assertEqual(comp, "2025-10")

        apto, comp = parse_receita_info("Receita Diversa Sem Apto")
        self.assertIsNone(apto)
        self.assertIsNone(comp)

    def test_parse_fornecedor(self):
        self.assertIsNone(parse_fornecedor("Tarifa Mensal Cobrança"))
        self.assertIsNone(parse_fornecedor("IOF s/ Aplicação"))

        self.assertEqual(parse_fornecedor("Pagamento Cemig Distribuição - Conta Energia"), "CEMIG DISTRIBUIÇÃO")
        self.assertEqual(parse_fornecedor("Pagamento Copasa - CTA. PGTO"), "COPASA")
        self.assertEqual(parse_fornecedor("Pagamento Limpeza S/A - NF: 1222"), "LIMPEZA S/A")
        self.assertEqual(parse_fornecedor("Seguro Predial SulAmerica - NF: 334"), "SEGURO PREDIAL SULAMERICA")

    def test_parse_conta(self):
        contas = ["CONTA CORRENTE", "CTA. PGTO"]
        self.assertEqual(parse_conta("Recebimento Apto - 301 Competência AGO 2024 - Conta: CONTA CORRENTE - SICOOB", contas), "CONTA CORRENTE")
        self.assertEqual(parse_conta("Pagamento Guardian Condo Serv De Port. Remota Ltda Doc.: 4929 - Conta: CONTA CORRENTE - SICOOB - Código de barra/Qr Code", contas), "CONTA CORRENTE")
        self.assertEqual(parse_conta("UND: Apto / 402 - FEV 2025 - CTA. PGTO: CONTA CORRENTE - SICOOB", contas), "CONTA CORRENTE")
        self.assertEqual(parse_conta("Pagamento Flavio Borges Gonçalves - Conta: CONTA CORRENTE - SICOOB - Pix", contas), "CONTA CORRENTE")
        self.assertEqual(parse_conta("Pagamento Guardian Condo Serv De Port. Remota Ltda - Doc.: 5894 - Conta: CONTA CORRENTE - SICOOB - DÉB.TIT.COMPE EFETIVADO", contas), "CONTA CORRENTE")
        self.assertIsNone(parse_conta("Sem conta na descrição", contas))

    def test_get_date_chunks(self):
        start = datetime(2025, 1, 1)
        end = datetime(2026, 3, 1)
        chunks = get_date_chunks(start, end)
        
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0][0], datetime(2025, 1, 1))
        self.assertEqual(chunks[0][1], datetime(2025, 12, 1))
        self.assertEqual(chunks[1][0], datetime(2026, 1, 1))
        self.assertEqual(chunks[1][1], datetime(2026, 3, 1))

    # =======================================================
    # Testes do Validador de Consistência Unificado
    # =======================================================

    def test_evaluate_consistency_mes(self):
        # Mês consistente
        consistente, motivo = evaluate_entity_consistency(
            'mes', rec_total_mes=100.0, soma_cat_rec=100.0, desp_total_mes=50.0, soma_cat_desp=50.0, anexos=1
        )
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)

        # Mês inconsistente (divergência em despesas)
        consistente, motivo = evaluate_entity_consistency(
            'mes', rec_total_mes=100.0, soma_cat_rec=100.0, desp_total_mes=50.0, soma_cat_desp=49.9, anexos=1
        )
        self.assertEqual(consistente, 0)
        reasons = json.loads(motivo)
        self.assertIn("Divergência em despesas", reasons)

        # Mês inconsistente (sem anexos)
        consistente, motivo = evaluate_entity_consistency(
            'mes', rec_total_mes=100.0, soma_cat_rec=100.0, desp_total_mes=50.0, soma_cat_desp=50.0, anexos=0
        )
        self.assertEqual(consistente, 0)
        reasons = json.loads(motivo)
        self.assertIn("Mês sem prestação de contas", reasons)

    def test_evaluate_consistency_categoria(self):
        # Categoria consistente
        consistente, motivo = evaluate_entity_consistency(
            'categoria', cat_nome="Receitas", cat_val_num=500.0, soma_sub=500.0
        )
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)

        # Categoria inconsistente
        consistente, motivo = evaluate_entity_consistency(
            'categoria', cat_nome="Receitas", cat_val_num=500.0, soma_sub=450.0
        )
        self.assertEqual(consistente, 0)
        self.assertEqual(json.loads(motivo)[0], "Soma das subcategorias difere do total da categoria")

    def test_evaluate_consistency_subcategoria(self):
        # Subcategoria consistente
        consistente, motivo = evaluate_entity_consistency(
            'subcategoria', sub_nome="Luz", sub_val_num=200.0, soma_itens=200.0
        )
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)

        # Subcategoria inconsistente
        consistente, motivo = evaluate_entity_consistency(
            'subcategoria', sub_nome="Luz", sub_val_num=200.0, soma_itens=190.0
        )
        self.assertEqual(consistente, 0)
        self.assertEqual(json.loads(motivo)[0], "Soma das transações difere do total da subcategoria")

    def test_evaluate_consistency_transacao_receita(self):
        # Receita consistente
        res = evaluate_entity_consistency(
            'transacao', tipo_flag="R", desc_completa="Taxa Apto - 101 JUN 2026 - Conta: CONTA CORRENTE - SICOOB", desc_f="Taxa Apto - 101 JUN 2026 - Conta: CONTA CORRENTE - SICOOB",
            anexos_esperados=1, anexos_baixados=1, despesa_anexo_valido=True, contas_list=["CONTA CORRENTE"]
        )
        consistente, motivo, apto, comp, fornecedor, conta = res
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)
        self.assertEqual(apto, "101")
        self.assertEqual(comp, "2026-06")
        self.assertEqual(conta, "CONTA CORRENTE")

        # Receita inconsistente
        res = evaluate_entity_consistency(
            'transacao', tipo_flag="R", desc_completa="Taxa Avulsa", desc_f="Taxa Avulsa",
            anexos_esperados=1, anexos_baixados=0, despesa_anexo_valido=True, contas_list=["CONTA CORRENTE"]
        )
        consistente, motivo, apto, comp, fornecedor, conta = res
        self.assertEqual(consistente, 0)
        reasons = json.loads(motivo)
        self.assertIn("Apartamento não identificado", reasons)
        self.assertIn("Competência não identificada", reasons)
        self.assertIn("Quantidade de anexos divergente", reasons)
        self.assertIn("Conta não identificada", reasons)

    def test_evaluate_consistency_transacao_despesa(self):
        # Despesa consistente
        res = evaluate_entity_consistency(
            'transacao', tipo_flag="D", desc_completa="Pagamento Cemig - Conta Energia - Conta: CONTA CORRENTE - SICOOB", desc_f="Pagamento Cemig - Conta: CONTA CORRENTE - SICOOB",
            anexos_esperados=1, anexos_baixados=1, despesa_anexo_valido=True, contas_list=["CONTA CORRENTE"]
        )
        consistente, motivo, apto, comp, fornecedor, conta = res
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)
        self.assertEqual(fornecedor, "CEMIG")
        self.assertEqual(conta, "CONTA CORRENTE")

        # Despesa inconsistente por falta de comprovantes (regra nova), fornecedor ausente e conta ausente
        res = evaluate_entity_consistency(
            'transacao', tipo_flag="D", desc_completa="Copa", desc_f="Copa",
            anexos_esperados=0, anexos_baixados=0, despesa_anexo_valido=False, contas_list=["CONTA CORRENTE"]
        )
        consistente, motivo, apto, comp, fornecedor, conta = res
        self.assertEqual(consistente, 0)
        reasons = json.loads(motivo)
        self.assertIn("Fornecedor não identificado", reasons)
        self.assertIn("Despesa sem comprovantes", reasons)
        self.assertIn("Conta não identificada", reasons)

    def test_evaluate_consistency_anexo(self):
        # Anexo consistente (com extensão válida)
        consistente, motivo = evaluate_entity_consistency('anexo', extensao="pdf")
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)

        # Anexo inconsistente (sem extensão ou muito curta/longa)
        consistente, motivo = evaluate_entity_consistency('anexo', extensao=None)
        self.assertEqual(consistente, 0)
        self.assertEqual(json.loads(motivo)[0], "Extensão de arquivo inválida ou ausente")

        consistente, motivo = evaluate_entity_consistency('anexo', extensao="toolong")
        self.assertEqual(consistente, 0)

    def test_evaluate_consistency_prestacao_contas(self):
        # Prestação de contas com extensão válida
        consistente, motivo = evaluate_entity_consistency('prestacao_contas', extensao="pdf")
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)

        # Prestação de contas indisponível ou sem extensão
        consistente, motivo = evaluate_entity_consistency('prestacao_contas', extensao="")
        self.assertEqual(consistente, 0)
        self.assertEqual(json.loads(motivo)[0], "Extensão de arquivo inválida ou ausente")

    def test_extract_inadimplencia_from_pdf(self):
        with patch('pypdf.PdfReader') as mock_pdf_reader:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = (
                "ATENÇÃO: Inadimplência do condomínio em 15/06/2026\n"
                "Unidades inadimplentes: 12\n"
                "Valor Total: 15.340,50"
            )
            mock_reader = MagicMock()
            mock_reader.pages = [mock_page]
            mock_pdf_reader.return_value = mock_reader
            
            from extract_winker import extract_inadimplencia_from_pdf
            data_corte, unidades, valor = extract_inadimplencia_from_pdf("dummy_path.pdf")
            
            self.assertEqual(data_corte, "15/06/2026")
            self.assertEqual(unidades, 12)
            self.assertEqual(valor, 15340.50)

    def test_save_condominio_and_gestao(self):
        import tempfile
        import models
        from extract_winker import save_condominio_and_gestao
        temp_fd, temp_path = tempfile.mkstemp(suffix='_test_extract.db')
        models.init_models(temp_path)
        
        try:
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            
            membros = [
                {"nome": "João Silva", "cargo": "Síndico"},
                {"nome": "Maria Santos", "cargo": "Conselheiro"}
            ]
            
            save_condominio_and_gestao(
                condo_id="12345",
                condo_nome="Residencial Teste",
                data_corte="10/06/2026",
                unidades=5,
                valor=2500.00,
                administradora="Cobrança S/A",
                telefone=["3133334444"],
                membros=membros
            )
            
            cursor.execute("SELECT * FROM condominio")
            condo_row = cursor.fetchone()
            self.assertEqual(condo_row[:7], ("12345", "Residencial Teste", "10/06/2026", 5, 2500.00, "Cobrança S/A", '["3133334444"]'))
            
            cursor.execute("SELECT condominio_id, nome, cargo FROM membros_gestao")
            membro_rows = cursor.fetchall()
            self.assertEqual(len(membro_rows), 2)
            self.assertEqual(membro_rows[0], ("12345", "João Silva", "Síndico"))
            self.assertEqual(membro_rows[1], ("12345", "Maria Santos", "Conselheiro"))
            
        finally:
            conn.close()
            models.db.close()
            import os
            try:
                os.close(temp_fd)
                os.unlink(temp_path)
            except: pass

    def test_get_ip_address(self):
        from extract_winker import get_ip_address
        ip = get_ip_address()
        self.assertTrue(ip is None or isinstance(ip, str))

    def test_get_mac_address(self):
        from extract_winker import get_mac_address
        mac = get_mac_address()
        self.assertTrue(mac is None or isinstance(mac, str))

    def test_save_auditoria(self):
        import tempfile
        import models
        from extract_winker import create_auditoria, update_auditoria, update_auditoria_condominio_id
        temp_fd, temp_path = tempfile.mkstemp(suffix='_test_extract_aud.db')
        models.init_models(temp_path)
        
        try:
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            with patch('extract_winker.get_ip_address') as mock_get_ip, \
                 patch('extract_winker.get_mac_address') as mock_get_mac:
                 
                mock_get_ip.return_value = "192.168.1.10"
                mock_get_mac.return_value = "00:11:22:33:44:55"
                
                auditoria_id = create_auditoria(periodo_inicio="2026-01", periodo_fim="2026-02")
                self.assertEqual(auditoria_id, 1)
                
                cursor.execute("SELECT * FROM auditoria WHERE id = ?", (auditoria_id,))
                initial_row = cursor.fetchone()
                self.assertIsNotNone(initial_row)
                
                user_data = {
                    "uuid": "test-uuid-123",
                    "id": 999,
                    "name": "Audit User",
                    "cpf": "111.111.111-11",
                    "rg": "MG-11.111.111",
                    "fone": "31988888888",
                    "apto": "302"
                }
                
                update_auditoria(
                    auditoria_id=auditoria_id,
                    user_data=user_data,
                    downloads_realizados=5,
                    transacoes_lidas=150,
                    tempo_duracao=12.5,
                    capturou_condominio=1,
                    capturou_inadimplencia=0,
                    capturou_membros=1
                )
    
                update_auditoria_condominio_id(auditoria_id=auditoria_id, condominio_id="CONDO-001")
                
                cursor.execute("SELECT * FROM auditoria WHERE id = ?", (auditoria_id,))
                row = cursor.fetchone()
                self.assertIsNotNone(row)
                
            conn.close()
        finally:
            models.db.close()
            import os
            try:
                os.close(temp_fd)
                os.unlink(temp_path)
            except: pass

    @patch('extract_winker.sync_playwright')
    @patch('extract_winker.init_db')
    @patch('extract_winker.create_auditoria')
    @patch('extract_winker.extract_condominio_and_gestao')
    def test_extract_winker_portal_index(self, mock_extract_condominio, mock_auditoria, mock_init, mock_sp):
        from extract_winker import extract_winker
        from datetime import datetime
        
        mock_extract_condominio.side_effect = Exception("Stop Execution")
        
        mock_page = MagicMock()
        mock_page.url = "https://app.winker.com.br/intra/default/escolherPortal"
        
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page
        
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        
        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_sp.return_value.__enter__.return_value = mock_p
        
        try:
            extract_winker("user", "pass", "123", datetime.now(), datetime.now(), True, portal_index=2)
        except Exception as e:
            self.assertEqual(str(e), "Stop Execution")
            
        mock_page.locator.assert_any_call("#content hgroup > div > table tbody tr")

if __name__ == "__main__":
    unittest.main()
