import unittest
from datetime import datetime
import json
from unittest.mock import MagicMock, patch
import sqlite3

# Importa as funções do script extract_winker
from extrator.execucao import (
    parse_currency,
    parse_receita_info,
    parse_conta,
    parse_fornecedor,
    get_date_chunks,
    evaluate_entity_consistency
)

class TestExtractWinker(unittest.TestCase):

    def test_parse_currency(self):
        from extrator.execucao import parse_currency

        self.assertEqual(parse_currency("R$ 1.234,56"), 1234.56)
        self.assertEqual(parse_currency("- R$ 10,00"), -10.00)
        self.assertEqual(parse_currency("R$ 0,00"), 0.0)
        self.assertEqual(parse_currency(""), 0.0)
        self.assertEqual(parse_currency(None), 0.0)
        self.assertEqual(parse_currency("150,75"), 150.75)
        
    def test_get_competencia(self):
        from extrator.execucao import get_competencia
        self.assertEqual(get_competencia("ABR/2026"), "2026-04")
        self.assertEqual(get_competencia("DEZ/2025"), "2025-12")
        self.assertIsNone(get_competencia(None))
        self.assertIsNone(get_competencia("INVALIDO"))
        
    def test_get_extensao(self):
        from extrator.execucao import get_extensao
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

    def test_receita_extraida_mantem_competencia_propria_na_conciliacao(self):
        import os
        import tempfile
        from compartilhado import models
        from datetime import date
        from extrator.execucao import save_extraction_data_to_db
        from bff.conciliacao_unificada import calcular_posicao, consultar

        with tempfile.TemporaryDirectory() as diretorio:
            models.init_models(os.path.join(diretorio, 'isolado.db'))
            try:
                models.Condominio.create(id='a', apartamentos='["101"]')
                models.Taxas.create(condominio_id='a', tipo='I', apartamento='101', competencia='2022-06',
                                    vencimento='10/06/2022', valor_original=100)
                detalhes = {'receitas': [{'nome': 'Receitas', 'valor': '100,00', 'subcategorias': [
                    {'nome': 'Taxas', 'valor': '100,00', 'itens': [
                        {'nome': 'Taxa Apto - 101 JUN 2022 (05/09/2022)', 'valor': '100,00'}]}]}],
                    'despesas': []}
                save_extraction_data_to_db('2022-09', 'SET', 2022, 100, 0, detalhes, diretorio, condominio_id='a')
                transacao = models.Transacoes.get()
                self.assertEqual((transacao.apartamento, transacao.competencia, transacao.data),
                                 ('101', '2022-06', '05/09/2022'))
                self.assertEqual(models.Meses.get().competencia, '2022-09')
                taxas, receitas = consultar(models.db.connection(), 'a')
                posicao = calcular_posicao('a', date(2022, 9, 5), ['101'], taxas, receitas, 'N')
                self.assertEqual(posicao['grupos'][0]['quitacoes_exatas'][0]['recebimentos'], [transacao.id])
            finally:
                models.db.close()

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
            
            from extrator.execucao import extract_inadimplencia_from_pdf
            data_corte, unidades, valor = extract_inadimplencia_from_pdf("dummy_path.pdf")
            
            self.assertEqual(data_corte, "15/06/2026")
            self.assertEqual(unidades, 12)
            self.assertEqual(valor, 15340.50)

    def test_save_condominio_and_gestao(self):
        import tempfile
        from compartilhado import models
        from extrator.execucao import save_condominio_and_gestao
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
            self.assertEqual(condo_row[:9], ("12345", "Residencial Teste", None, "10/06/2026", 5, 2500.00, 0.0, "Cobrança S/A", '["3133334444"]'))
            
            cursor.execute("SELECT condominio_id, nome, cargo FROM membros_gestao")
            membro_rows = cursor.fetchall()
            self.assertEqual(len(membro_rows), 2)
            self.assertEqual(membro_rows[0], ("12345", "João Silva", "Síndico"))
            self.assertEqual(membro_rows[1], ("12345", "Maria Santos", "Conselheiro"))
            
            # Testa preservação quando membros for vazio (cenário de fallback)
            save_condominio_and_gestao(
                condo_id="12345",
                condo_nome=None,
                data_corte=None,
                unidades=None,
                valor=None,
                administradora=None,
                telefone=None,
                membros=[]
            )
            cursor.execute("SELECT condominio_id, nome, cargo FROM membros_gestao")
            membros_preservados = cursor.fetchall()
            self.assertEqual(len(membros_preservados), 2)
            self.assertEqual(membros_preservados[0], ("12345", "João Silva", "Síndico"))
            self.assertEqual(membros_preservados[1], ("12345", "Maria Santos", "Conselheiro"))
            
        finally:
            conn.close()
            models.db.close()
            import os
            try:
                os.close(temp_fd)
                os.unlink(temp_path)
            except: pass

    def test_get_ip_address(self):
        from extrator.execucao import get_ip_address
        ip = get_ip_address()
        self.assertTrue(ip is None or isinstance(ip, str))

    def test_get_mac_address(self):
        from extrator.execucao import get_mac_address
        mac = get_mac_address()
        self.assertTrue(mac is None or isinstance(mac, str))

    def test_save_auditoria(self):
        import tempfile
        from compartilhado import models
        from extrator.execucao import create_auditoria, update_auditoria, update_auditoria_condominio_id
        temp_fd, temp_path = tempfile.mkstemp(suffix='_test_extract_aud.db')
        models.init_models(temp_path)
        
        try:
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            with patch('extrator.auditoria.get_ip_address') as mock_get_ip, \
                 patch('extrator.auditoria.get_mac_address') as mock_get_mac:
                 
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

    @patch('builtins.input', return_value='0')
    @patch('extrator.execucao.sync_playwright')
    @patch('extrator.execucao.init_db')
    @patch('extrator.execucao.create_auditoria')
    @patch('extrator.execucao.extract_condominio_and_gestao')
    def test_extract_winker_portal_index(self, mock_extract_condominio, mock_auditoria, mock_init, mock_sp, mock_input):
        from extrator.execucao import extract_winker
        from datetime import datetime
        import tempfile
        
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
        
        mock_auditoria.return_value = None
        with tempfile.TemporaryDirectory() as pasta, \
             patch('extrator.execucao.project_root', pasta), \
             patch('extrator.execucao.selecionar_condominio_fallback', return_value=(None, None)):
            extract_winker("user", "pass", "123", datetime.now(), datetime.now(), True, portal_index=2)
            
        mock_page.locator.assert_any_call("#content hgroup > div > table tbody tr")

    @patch('extrator.execucao.models.Condominio.select')
    @patch('builtins.input', return_value='1')
    def test_selecionar_condominio_fallback_escolha_valida(self, mock_input, mock_select):
        from extrator.execucao import selecionar_condominio_fallback
        mock_c = MagicMock()
        mock_c.id = "TEST-123"
        mock_c.nome = "Condomínio Teste"
        mock_select.return_value.order_by.return_value = [mock_c]

        condo_id, condo_nome = selecionar_condominio_fallback()
        self.assertEqual(condo_id, "TEST-123")
        self.assertEqual(condo_nome, "Condomínio Teste")

    @patch('extrator.execucao.models.Condominio.select')
    @patch('builtins.input', return_value='0')
    def test_selecionar_condominio_fallback_desistir(self, mock_input, mock_select):
        from extrator.execucao import selecionar_condominio_fallback
        mock_c = MagicMock()
        mock_c.id = "TEST-123"
        mock_c.nome = "Condomínio Teste"
        mock_select.return_value.order_by.return_value = [mock_c]

        condo_id, condo_nome = selecionar_condominio_fallback()
        self.assertIsNone(condo_id)
        self.assertIsNone(condo_nome)

    @patch('extrator.execucao.models.Condominio.select')
    def test_selecionar_condominio_fallback_sem_condominios(self, mock_select):
        from extrator.execucao import selecionar_condominio_fallback
        mock_select.return_value.order_by.return_value = []

        condo_id, condo_nome = selecionar_condominio_fallback()
        self.assertIsNone(condo_id)
        self.assertIsNone(condo_nome)

    def test_parse_currency_e_receita_info_casos_limite(self):
        from extrator.execucao import parse_currency, parse_receita_info
        self.assertEqual(parse_currency('texto-invalido'), 0.0)
        self.assertEqual(parse_currency(''), 0.0)
        self.assertEqual(parse_currency('R$ -1.234,56'), -1234.56)
        self.assertEqual(parse_receita_info('Receita QUAL 2023'), (None, None))
        self.assertEqual(parse_receita_info('Pagamento Apto/101 - Doc'), ('101', None))
        self.assertEqual(parse_receita_info('Taxa FEV 2024 Apto-205'), ('205', '2024-02'))
        self.assertEqual(parse_receita_info(''), (None, None))

    def test_parse_fornecedor_prefixos_e_casos_limite(self):
        from extrator.execucao import parse_fornecedor
        self.assertIsNone(parse_fornecedor(''))
        self.assertIsNone(parse_fornecedor('TARIFA BANCARIA'))
        self.assertIsNone(parse_fornecedor('IOF sobre operação'))
        self.assertIsNone(parse_fornecedor('IRRF retido'))
        self.assertEqual(parse_fornecedor('Pagamento Empresa XYZ - Doc 123'), 'EMPRESA XYZ')
        self.assertEqual(parse_fornecedor('PAGAMENTO FORNECEDOR ABC - NF 9'), 'FORNECEDOR ABC')
        self.assertEqual(parse_fornecedor('Servico Prestado - CTA. PGTO: 55'), 'SERVICO PRESTADO')
        self.assertEqual(parse_fornecedor('Servico - NF: 77'), 'SERVICO')
        self.assertIsNone(parse_fornecedor('Descricao sem padrao'))

    def test_parse_conta_e_get_competencia_e_extensao_limites(self):
        from extrator.execucao import parse_conta, get_competencia, get_extensao
        self.assertIsNone(parse_conta('', ['Conta A']))
        self.assertIsNone(parse_conta('desc', []))
        self.assertEqual(parse_conta('Pagamento CONTA ENERGIA aqui', ['Conta Energia', 'Conta Agua']), 'Conta Energia')
        self.assertIsNone(parse_conta('nada relacionado', ['Conta A']))
        self.assertIsNone(get_competencia(''))
        self.assertIsNone(get_competencia('2024'))
        self.assertEqual(get_competencia('XYZ/2024'), '2024-01')
        self.assertEqual(get_extensao(''), None)
        self.assertEqual(get_extensao('sem_extensao'), None)
        self.assertEqual(get_extensao('arquivo.PDF?x=1'), 'pdf')
        self.assertEqual(get_extensao('arquivo.tar.gz#frag'), 'gz')

    def test_extract_inadimplencia_pdf_parcial_e_erro(self):
        with patch('pypdf.PdfReader') as mock_pdf_reader:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = 'Inadimplência do condomínio em 01/02/2024\nUnidades inadimplentes: 3'
            mock_reader = MagicMock()
            mock_reader.pages = [mock_page]
            mock_pdf_reader.return_value = mock_reader
            from extrator.execucao import extract_inadimplencia_from_pdf
            data_corte, unidades, valor = extract_inadimplencia_from_pdf('x.pdf')
            self.assertEqual((data_corte, unidades, valor), ('01/02/2024', 3, None))
        with patch('pypdf.PdfReader', side_effect=Exception('pdf corrompido')):
            self.assertEqual(extract_inadimplencia_from_pdf('x.pdf'), (None, None, None))

    def test_evaluate_consistency_cobre_todos_os_tipos_e_ramos(self):
        from extrator.execucao import evaluate_entity_consistency as ev
        # mes: consistente e cada motivo de inconsistência
        self.assertEqual(ev('mes', rec_total_mes=100, soma_cat_rec=100, desp_total_mes=50, soma_cat_desp=50, anexos=1), (1, None))
        c, m = ev('mes', rec_total_mes=100, soma_cat_rec=90, desp_total_mes=50, soma_cat_desp=50, anexos=0)
        self.assertEqual(c, 0)
        self.assertIn('receitas', m)
        self.assertIn('prestação', m)
        c, m = ev('mes', rec_total_mes=100, soma_cat_rec=100, desp_total_mes=50, soma_cat_desp=40, anexos=1)
        self.assertIn('despesas', m)
        c, m = ev('tipo_invalido') if False else (None, None)
        # categoria e subcategoria divergentes
        self.assertEqual(ev('categoria', cat_nome='X', cat_val_num=10, soma_sub=10), (1, None))
        self.assertEqual(ev('categoria', cat_val_num=10, soma_sub=9)[0], 0)
        self.assertEqual(ev('subcategoria', sub_val_num=10, soma_itens=10), (1, None))
        self.assertEqual(ev('subcategoria', sub_val_num=10, soma_itens=8)[0], 0)
        # transacao receita completa e incompleta
        r = ev('transacao', tipo_flag='R', desc_completa='Receita Apto/101 FEV 2024 CONTA A - Doc',
               desc_f='', anexos_esperados=1, anexos_baixados=1, contas_list=['Conta A'],
               regras_preenchimento=[])
        self.assertEqual(r[0], 1)
        r = ev('transacao', tipo_flag='R', desc_completa='Receita sem dados', desc_f='',
               anexos_esperados=1, anexos_baixados=2, contas_list=[], regras_preenchimento=[])
        self.assertEqual(r[0], 0)
        motivos = json.loads(r[1])
        self.assertIn('Apartamento não identificado', motivos)
        self.assertIn('Competência não identificada', motivos)
        self.assertIn('Conta não identificada', motivos)
        self.assertIn('Quantidade de anexos divergente', motivos)
        # transacao despesa com fornecedor, conta e regra de preenchimento
        d = ev('transacao', tipo_flag='D', desc_completa='SERVICO CONTA B - NF: 1', desc_f='xyz sem fornecedor',
               anexos_esperados=0, anexos_baixados=0, contas_list=['Conta B'],
               regras_preenchimento=[{'descricao_contem': 'servico', 'campo': 'fornecedor', 'valor': 'FORNECEDOR X'},
                                     {'descricao_contem': 'nada', 'campo': 'conta', 'valor': 'Conta B'}])
        self.assertEqual(d[0], 1)
        self.assertEqual(d[4], 'FORNECEDOR X')
        # despesa sem fornecedor e sem anexo válido
        d2 = ev('transacao', tipo_flag='D', desc_completa='algo sem fornecedor', desc_f='algo sem fornecedor',
                anexos_esperados=1, anexos_baixados=0, contas_list=['Conta B'],
                regras_preenchimento=[], despesa_anexo_valido=False)
        self.assertEqual(d2[0], 0)
        motivos_d = json.loads(d2[1])
        self.assertIn('Fornecedor não identificado', motivos_d)
        self.assertIn('Despesa sem comprovantes', motivos_d)
        # anexo e prestacao_contas
        self.assertEqual(ev('anexo', extensao='pdf'), (1, None))
        self.assertEqual(ev('anexo', extensao='')[0], 0)
        self.assertEqual(ev('anexo', extensao='x'*10)[0], 0)
        self.assertEqual(ev('prestacao_contas', extensao='pdf'), (1, None))
        self.assertEqual(ev('prestacao_contas', extensao=None)[0], 0)
        with self.assertRaises(ValueError):
            ev('desconhecido')

    def _contexto_api(self, portais=None, busca=None, about=None):
        from unittest.mock import MagicMock
        context = MagicMock()
        respostas = {'portal': portais, 'busca': busca, 'about': about}

        def _resp(payload, ok=True):
            r = MagicMock()
            r.ok = ok
            r.json.return_value = payload
            return r

        def _get(url, **kw):
            chave = 'about' if 'about' in url else 'portal'
            return _resp(respostas[chave], ok=True)

        def _post(url, **kw):
            return _resp(respostas['busca'], ok=ok_busca[0])

        ok_busca = [True]
        context.request.get.side_effect = _get
        context.request.post.side_effect = _post
        return context, ok_busca

    def test_extrair_condominio_api_caminhos_de_erro(self):
        from extrator.execucao import extrair_condominio_api
        with self.assertRaises(ValueError):
            extrair_condominio_api(MagicMock(), 'tok', 'abc')
        with self.assertRaises(ValueError):
            extrair_condominio_api(MagicMock(), None, '123')
        context, _ = self._contexto_api()
        context.request.get.return_value.ok = False
        with self.assertRaises(ValueError):
            extrair_condominio_api(context, 'tok', '123')
        context, _ = self._contexto_api(portais={'nao': 'lista'})
        with self.assertRaises(ValueError):
            extrair_condominio_api(context, 'tok', '123')
        context, _ = self._contexto_api(portais=[])
        with self.assertRaises(ValueError):
            extrair_condominio_api(context, 'tok', '123')
        context, _ = self._contexto_api(portais=[{'id_portal': 999, 'url': 'https://app.winker.com.br/x/y', 'name': 'P'}])
        with self.assertRaises(ValueError):
            extrair_condominio_api(context, 'tok', '123')
        context, _ = self._contexto_api(portais=[{'id_portal': 123, 'url': 'http://invalido/x', 'name': 'P'}])
        with self.assertRaises(ValueError):
            extrair_condominio_api(context, 'tok', '123')

    def test_extrair_condominio_api_sucesso_e_gestao(self):
        from extrator.execucao import extrair_condominio_api
        portais = [{'id_portal': 123, 'url': 'https://app.winker.com.br/condominio-slug', 'name': 'Portal X'}]
        busca = {'id_condominio': 123, 'codigo_seguranca': ' COD123 ', 'nome': 'Condo API'}
        about = {'users': {
            'manager': {'name': 'Síndico A', 'title': 'Presidente'},
            'boardMembers': [{'name': 'Membro B', 'groups': [{'name': 'Tesoureiro'}]}, {'name': None}],
            'providers': [{'name': 'Admin SA', 'phone': '(11) 99999-0000',
                           'activities': [{'activitie': 'ADMINISTRADORA'}]}]}}
        context, _ = self._contexto_api(portais=portais, busca=busca, about=about)
        codigo, nome, membros, adm, tel = extrair_condominio_api(context, 'tok', '123')
        self.assertEqual((codigo, nome, adm), ('COD123', 'Condo API', 'Admin SA'))
        self.assertEqual(tel, ['11999990000'])
        self.assertEqual(membros[0], {'nome': 'Síndico A', 'cargo': 'Presidente'})
        self.assertEqual(membros[1]['nome'], 'Membro B')
        # about falha -> gestão vazia mas resultado ok
        context2, _ = self._contexto_api(portais=portais, busca=busca, about={})
        context2.request.get.side_effect = lambda url, **kw: MagicMock(ok=True, json=MagicMock(return_value={} if 'about' in url else portais))
        codigo2, _, membros2, adm2, tel2 = extrair_condominio_api(context2, 'tok', '123')
        self.assertEqual(membros2, [])
        # busca retorna lista
        context3, _ = self._contexto_api(portais=portais, busca=[busca], about=about)
        self.assertEqual(extrair_condominio_api(context3, 'tok', '123')[0], 'COD123')
        # codigo ausente
        context4, _ = self._contexto_api(portais=portais, busca={'id_condominio': 123}, about=about)
        with self.assertRaises(ValueError):
            extrair_condominio_api(context4, 'tok', '123')

    def test_capturar_sessao_api_fallbacks(self):
        from extrator.execucao import capturar_sessao_api
        page = MagicMock()
        page.evaluate.side_effect = [None, None]
        page.content.side_effect = ['PORTAL_DATA = {id_portal: 42}', 'TOKEN_API = "TOK456"']
        page.frames = []
        portal, token = capturar_sessao_api(page)
        self.assertEqual((portal, token), ('42', 'TOK456'))
        # token via frame quando evaluate e regex falham
        frame = MagicMock()
        frame.url = 'https://appweb.winker.com.br/x?token=FRAME_TOK'
        page2 = MagicMock()
        page2.evaluate.side_effect = ['PORTAL9', None]
        page2.content.return_value = ''
        page2.frames = [frame]
        self.assertEqual(capturar_sessao_api(page2), ('PORTAL9', 'FRAME_TOK'))
        page3 = MagicMock()
        page3.evaluate.side_effect = [None, None]
        page3.content.return_value = ''
        page3.frames = [frame]
        self.assertEqual(capturar_sessao_api(page3), (None, 'FRAME_TOK'))

    def test_waits_e_close_modal(self):
        from extrator.execucao import wait_for_new_list_and_items, wait_for_list_close, close_last_modal
        iframe = MagicMock()
        lists = MagicMock()
        lists.count.return_value = 2
        lists.last = MagicMock()
        lists.last.locator.return_value.count.return_value = 3
        iframe.locator.return_value = lists
        self.assertTrue(wait_for_new_list_and_items(iframe, 1))
        self.assertFalse(wait_for_new_list_and_items(iframe, 5, timeout_ms=0))
        iframe.locator.return_value.count.return_value = 0
        self.assertTrue(wait_for_list_close(iframe, 1))
        self.assertFalse(wait_for_list_close(iframe, 0, timeout_ms=0))
        iframe2 = MagicMock()
        iframe2.locator.return_value.count.return_value = 3
        close_last_modal(iframe2)
        iframe2.get_by_role.return_value.last.click.assert_called_once()

    def test_selecionar_condominio_fallback_interacao(self):
        from extrator.execucao import selecionar_condominio_fallback
        condo = MagicMock()
        condo.nome = 'Condo Fallback'
        condo.id = 'fb-1'
        with patch('extrator.execucao.models.Condominio.select') as sel, \
             patch('builtins.input', side_effect=['0']):
            sel.return_value.order_by.return_value = [condo]
            self.assertEqual(selecionar_condominio_fallback(), (None, None))
        with patch('extrator.execucao.models.Condominio.select') as sel, \
             patch('builtins.input', side_effect=['1']):
            sel.return_value.order_by.return_value = [condo]
            self.assertEqual(selecionar_condominio_fallback(), ('fb-1', 'Condo Fallback'))
        with patch('extrator.execucao.models.Condominio.select') as sel, \
             patch('builtins.input', side_effect=['x', '0']):
            sel.return_value.order_by.return_value = [condo]
            self.assertEqual(selecionar_condominio_fallback(), (None, None))
        with patch('extrator.execucao.models.Condominio.select', side_effect=RuntimeError('db')):
            self.assertEqual(selecionar_condominio_fallback(), (None, None))
        with patch('extrator.execucao.models.Condominio.select') as sel, \
             patch('builtins.input', side_effect=EOFError):
            sel.return_value.order_by.return_value = [condo]
            self.assertEqual(selecionar_condominio_fallback(), (None, None))

    def test_extract_condominio_and_gestao_ramos(self):
        from extrator.execucao import extract_condominio_and_gestao
        page = MagicMock()
        # info_cond strong
        page.locator.side_effect = lambda sel: {
            'div.info_cond_codigo_seguranca strong': MagicMock(inner_text=MagicMock(return_value=' COD-9 ')),
        }.get(sel, MagicMock())
        # locator('#breadcrumb a').first.count -> 0 ; sindico count -> 0 ; rows -> []
        def _loc(sel):
            m = MagicMock()
            if sel == '#breadcrumb a':
                m.first.count.return_value = 0
            elif sel == 'div.panel.panel-info label.label-success':
                m.first.count.return_value = 1
                m.first.inner_text.return_value = 'João Silva - Síndico'
            elif sel == '#lista_corpo_diretivo .row':
                m.all.return_value = []
            else:
                m.count.return_value = 0
            return m
        page.locator.side_effect = _loc
        # info_cond precisa inner_text
        def _loc2(sel):
            m = MagicMock()
            if sel == 'div.info_cond_codigo_seguranca strong':
                m.inner_text.return_value = ' COD-9 '
            elif sel == '#breadcrumb a':
                m.first.count.return_value = 1
                m.first.inner_text.return_value = 'Condo Breadcrumb'
            elif sel == 'div.panel.panel-info label.label-success':
                m.first.count.return_value = 1
                m.first.inner_text.return_value = 'Maria Souza - Síndica'
            elif sel == '#lista_corpo_diretivo .row':
                row = MagicMock()
                nome_el = MagicMock()
                nome_el.count.return_value = 1
                nome_el.first.inner_text.return_value = 'Pedro'
                row.locator.return_value = nome_el
                row.inner_text.return_value = 'Pedro - Tesoureiro'
                vazio = MagicMock()
                vazio.locator.return_value.count.return_value = 0
                m.all.return_value = [row, vazio]
            else:
                m.count.return_value = 0
            return m
        page.locator.side_effect = _loc2
        condo_id, nome, membros = extract_condominio_and_gestao(page)
        self.assertEqual(condo_id, 'COD-9')
        self.assertEqual(nome, 'Condo Breadcrumb')
        self.assertEqual(membros[0], {'nome': 'Maria Souza', 'cargo': 'Síndico'})
        self.assertEqual(membros[1]['nome'], 'Pedro')
        self.assertEqual(membros[1]['cargo'], 'Tesoureiro')

    def test_extract_inadimplencia_boleto_caminhos(self):
        import tempfile
        from extrator.execucao import extract_inadimplencia_boleto
        page = MagicMock()
        page.locator.return_value.all.return_value = []
        page.locator.return_value.first.count.return_value = 0
        page.locator.return_value.last.count.return_value = 0
        page.wait_for_selector.side_effect = Exception('timeout')
        with patch('extrator.inadimplencia.download_file_from_button') as dl:
            r = extract_inadimplencia_boleto(page, MagicMock())
            self.assertEqual(r[:3], (None, None, None))
            dl.assert_not_called()
        # sem badge
        page.wait_for_selector.side_effect = None
        page.locator.return_value.last.count.return_value = 1
        inner = MagicMock()
        inner.count.return_value = 1
        page.locator.return_value.last.locator.return_value.first = inner
        inner.count.return_value = 0
        with patch('extrator.inadimplencia.download_file_from_button') as dl:
            r = extract_inadimplencia_boleto(page, MagicMock())
            self.assertIsNone(r[0])
            dl.assert_not_called()
        # sucesso e exceção no download (isola project_root -> pasta de anexos de teste)
        with tempfile.TemporaryDirectory() as td, patch('extrator.inadimplencia.project_root', td):
            badge = MagicMock()
            badge.count.return_value = 1
            page.locator.return_value.last.locator.return_value.first = badge
            page.locator.return_value.last.count.return_value = 1
            with patch('extrator.inadimplencia.download_file_from_button', return_value=('/tmp/b.pdf', 'b.pdf')), \
                 patch('extrator.inadimplencia.extract_inadimplencia_from_pdf', return_value=('01/01/2024', 2, 100.0)), \
                 patch('os.path.exists', return_value=False):
                r = extract_inadimplencia_boleto(page, MagicMock())
                self.assertEqual(r[:3], ('01/01/2024', 2, 100.0))
            with patch('extrator.inadimplencia.download_file_from_button', side_effect=Exception('falha')):
                r = extract_inadimplencia_boleto(page, MagicMock())
                self.assertIsNone(r[0])

    def test_helpers_revisao_e_arquivos(self):
        import json as _json
        import tempfile, os
        from extrator.execucao import _motivos, _reaplicar_revisao_transacao, _restaurar_documentos, _atualizar_arquivos_mes
        self.assertEqual(_motivos('["a", "b"]'), {'a', 'b'})
        self.assertEqual(_motivos('invalido'), set())
        self.assertEqual(_motivos('{"a": 1}'), set())
        self.assertEqual(_motivos(None), set())
        # reaplicar revisão
        trans = MagicMock()
        trans.motivo_inconsistencia = _json.dumps(['Apartamento não identificado', 'Conta não identificada'])
        trans.lista_anexos = []
        trans.consistente = 0
        revisao = {'motivos': _json.dumps(['Apartamento não identificado', 'Conta não identificada']),
                   'campos': {'apartamento': '202', 'competencia': None, 'fornecedor': None, 'conta': 'Conta X'},
                   'documentos': []}
        _reaplicar_revisao_transacao(trans, revisao, 0)
        self.assertEqual(trans.apartamento, '202')
        self.assertEqual(trans.conta, 'Conta X')
        self.assertEqual(trans.revisado_usuario, 1)
        trans.save.assert_called()
        # documento preservado limpa motivos de anexo
        trans2 = MagicMock()
        trans2.motivo_inconsistencia = _json.dumps(['Despesa sem comprovantes', 'Quantidade de anexos divergente'])
        doc = MagicMock()
        doc.nome_original = 'boleto.pdf'
        trans2.lista_anexos = [doc]
        trans2.consistente = 0
        revisao2 = {'motivos': trans2.motivo_inconsistencia,
                    'campos': {'apartamento': None, 'competencia': None, 'fornecedor': None, 'conta': None},
                    'documentos': [{'nome_original': 'boleto.pdf'}]}
        _reaplicar_revisao_transacao(trans2, revisao2, 1)
        self.assertEqual(trans2.revisado_usuario, 1)
        # restaurar documentos
        modelo = MagicMock()
        modelo.select.return_value.where.return_value = []
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, 'anexos'))
            with open(os.path.join(td, 'anexos', 'a.pdf'), 'w') as f:
                f.write('x')
            docs = [{'nome_original': 'a.pdf', 'caminho_local': 'anexos/a.pdf', 'extensao': 'pdf',
                     'consistente': 1, 'motivo_inconsistencia': None, 'revisado_usuario': 0}]
            from types import SimpleNamespace
            campo = SimpleNamespace(name='transacao_id')
            restaurados = _restaurar_documentos(modelo, campo, 5, docs, td)
            self.assertEqual(restaurados, ['anexos/a.pdf'])
            modelo.create.assert_called_once()
            with self.assertRaises(FileNotFoundError):
                _restaurar_documentos(modelo, MagicMock(), 5,
                                      [{'nome_original': 'b.pdf', 'caminho_local': 'anexos/b.pdf'}], td)
        # atualizar arquivos do mês
        with tempfile.TemporaryDirectory() as td:
            origem = os.path.join(td, 'orig.pdf')
            with open(origem, 'w') as f:
                f.write('dado')
            mes_dir = os.path.join(td, 'mes')
            os.makedirs(mes_dir)
            with open(os.path.join(mes_dir, 'velho.txt'), 'w') as f:
                f.write('v')
            temp_mov = os.path.join(td, 'temp.pdf')
            with open(temp_mov, 'w') as f:
                f.write('novo')
            destino_final = os.path.join(mes_dir, 'novo.pdf')
            _atualizar_arquivos_mes(td, mes_dir, ['orig.pdf'],
                                   [{'temp_path': temp_mov, 'caminho_final': destino_final}])
            self.assertFalse(os.path.exists(os.path.join(mes_dir, 'velho.txt')))
            self.assertTrue(os.path.exists(os.path.join(td, 'orig.pdf')))
            self.assertTrue(os.path.exists(destino_final))
            with self.assertRaises(FileNotFoundError):
                _atualizar_arquivos_mes(td, mes_dir, [], [{'temp_path': 'nao-existe.pdf', 'caminho_final': 'x'}])

    def test_ip_mac_e_auditoria(self):
        from extrator import execucao as ew
        # _get_ip_address: urlopen retorna IP válido
        with patch('urllib.request.urlopen') as urlopen:
            resp = MagicMock()
            resp.read.return_value = b'  192.168.0.5  '
            resp.__enter__ = lambda s: s
            resp.__exit__ = MagicMock(return_value=False)
            urlopen.return_value = resp
            self.assertEqual(ew._get_ip_address(), '192.168.0.5')
        # todos urls falham -> fallback socket local
        with patch('urllib.request.urlopen', side_effect=Exception('rede')):
            sock = MagicMock()
            sock.getsockname.return_value = ('10.0.0.1', 0)
            with patch('socket.socket', return_value=sock):
                self.assertEqual(ew._get_ip_address(), '10.0.0.1')
        # get_ip_address usa thread + fallback
        with patch('extrator.auditoria._get_ip_address', return_value='1.2.3.4'):
            self.assertEqual(ew.get_ip_address(), '1.2.3.4')
        with patch('extrator.auditoria._get_ip_address', return_value=None):
            sock = MagicMock()
            sock.getsockname.return_value = ('10.1.1.1', 0)
            sock.__enter__ = lambda s: s
            sock.__exit__ = MagicMock(return_value=False)
            with patch('socket.socket', return_value=sock):
                self.assertEqual(ew.get_ip_address(), '10.1.1.1')
            with patch('socket.socket', side_effect=OSError('sem rede')):
                self.assertEqual(ew.get_ip_address(), 'indisponível')
        # get_mac_address
        with patch('socket.socket') as msock, patch('subprocess.run') as run:
            s = MagicMock()
            s.getsockname.return_value = ('10.0.0.2', 0)
            msock.return_value = s
            run.return_value.stdout = 'AA-BB-CC-DD-EE-FF'
            self.assertEqual(ew.get_mac_address(), 'aa:bb:cc:dd:ee:ff')
            run.return_value.stdout = 'invalido'
            self.assertIsNone(ew.get_mac_address())
        with patch('socket.socket', side_effect=Exception('falha')):
            self.assertIsNone(ew.get_mac_address())
        # auditoria
        with patch.object(ew.models.Auditoria, 'create', return_value=MagicMock(id=7)) as create, \
             patch('extrator.auditoria.get_ip_address', return_value='1.1.1.1'), \
             patch('extrator.auditoria.get_mac_address', return_value='aa:bb:cc:dd:ee:ff'):
            self.assertEqual(ew.create_auditoria('2024-01', '2024-12'), 7)
            create.assert_called_once()
        with patch.object(ew.models.Auditoria, 'create', side_effect=Exception('db')):
            self.assertIsNone(ew.create_auditoria('a', 'b'))
        with patch.object(ew.models.Auditoria, 'update') as upd:
            upd.return_value.where.return_value.execute.return_value = 1
            ew.update_auditoria_condominio_id('aud-1', 'condo-1')
            upd.assert_called()
            ew.update_auditoria_condominio_id(None, 'x')
            ew.update_auditoria(None, {}, 0, 0, 0, False, False, False)
            ew.update_auditoria('aud-1', {'uuid': 'u'}, 1, 2, 3, True, False, True)
            upd.assert_called()

    def test_download_http_file_extensoes_e_erros(self):
        import tempfile
        from extrator.execucao import download_http_file
        context = MagicMock()
        resp = MagicMock()
        resp.status = 200
        resp.body.return_value = b'%PDF-1.4 fake'
        resp.headers = {'content-type': 'application/pdf'}
        context.request.get.return_value = resp
        with tempfile.TemporaryDirectory() as td:
            # extensão da URL
            path, nome = download_http_file(context, 'https://x.com/a/boleto.PDF?dl=1', td)
            self.assertTrue(path.endswith('boleto.pdf'))
            self.assertEqual(nome, 'boleto.pdf')
            # sem extensão -> content-type jpg
            resp.headers = {'content-type': 'image/jpeg'}
            resp.body.return_value = b'\xff\xd8img'
            path, nome = download_http_file(context, 'https://x.com/sem_ext', td, default_filename='foto')
            self.assertTrue(nome.endswith('.jpg'))
            # content-type png
            resp.headers = {'content-type': 'image/png'}
            path, nome = download_http_file(context, 'https://x.com/x', td)
            self.assertTrue(nome.endswith('.png'))
            # gif
            resp.headers = {'content-type': 'image/gif'}
            path, nome = download_http_file(context, 'https://x.com/x', td)
            self.assertTrue(nome.endswith('.gif'))
            # fallback pdf + nome higinizado + sem nome -> timestamp
            resp.headers = {'content-type': 'text/plain'}
            resp.body.return_value = b'outro'
            path, nome = download_http_file(context, 'https://x.com/x', td, default_filename='nome?com/*chars*')
            self.assertTrue(nome.endswith('.pdf'))
            self.assertNotIn('?', nome)
            # erro HTTP
            resp.status = 404
            with self.assertRaises(Exception):
                download_http_file(context, 'https://x.com/x', td)

    def test_download_file_from_button_download_e_popup(self):
        import tempfile
        from extrator.execucao import download_file_from_button
        with tempfile.TemporaryDirectory() as td:
            # Caso download direto
            page = MagicMock()
            listeners = {}
            page.on.side_effect = lambda ev, cb: listeners.__setitem__(ev, cb)
            btn = MagicMock()
            btn.page = page
            dl = MagicMock()
            dl.suggested_filename = 'doc.pdf'
            def _click():
                listeners['download'](dl)
            btn.click.side_effect = _click
            dl.save_as.side_effect = lambda p: open(p, 'wb').write(b'x')
            path, nome = download_file_from_button(MagicMock(), btn, td, filename_prefix='pre_', default_filename='padrao.pdf')
            self.assertTrue(path.endswith('pre_padrao.pdf'))
            self.assertEqual(nome, 'padrao.pdf')
            page.remove_listener.assert_any_call('download', listeners['download'])
            # Caso popup com viewer.html?file=
            page2 = MagicMock()
            listeners2 = {}
            page2.on.side_effect = lambda ev, cb: listeners2.__setitem__(ev, cb)
            btn2 = MagicMock()
            btn2.page = page2
            popup = MagicMock()
            popup.url = 'https://viewer.winker.com/viewer.html?file=https%3A%2F%2Fcdn.com%2Farq.pdf'
            def _click2():
                listeners2['popup'](popup)
            btn2.click.side_effect = _click2
            context = MagicMock()
            with patch('extrator.arquivos.download_http_file', return_value=('/tmp/x.pdf', 'arq.pdf')) as dh:
                path2, nome2 = download_file_from_button(context, btn2, td)
                self.assertEqual((path2, nome2), ('/tmp/x.pdf', 'arq.pdf'))
                self.assertIn('arq.pdf', dh.call_args[0][1])
            popup.close.assert_called()
            # Caso timeout: nenhum evento -> exceção
            page3 = MagicMock()
            page3.on.side_effect = lambda ev, cb: None
            btn3 = MagicMock()
            btn3.page = page3
            times = iter([0, 1, 20])
            with patch('extrator.execucao.time.time', side_effect=lambda: next(times, 20)):
                with self.assertRaises(Exception):
                    download_file_from_button(MagicMock(), btn3, td)

    def test_get_date_chunks_multiplos_meses(self):
        from extrator.execucao import get_date_chunks
        from datetime import datetime
        chunks = get_date_chunks(datetime(2024, 1, 15), datetime(2025, 3, 20))
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0][0], datetime(2024, 1, 15))
        self.assertEqual(chunks[-1][1], datetime(2025, 3, 20))
        self.assertTrue(all(c[0] <= c[1] for c in chunks))
        self.assertEqual(get_date_chunks(datetime(2024, 5, 1), datetime(2024, 5, 10)), [(datetime(2024, 5, 1), datetime(2024, 5, 10))])

if __name__ == "__main__":
    unittest.main()

