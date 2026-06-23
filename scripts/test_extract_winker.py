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
        self.assertEqual(parse_currency("R$ 1.234,56"), 1234.56)
        self.assertEqual(parse_currency("- R$ 10,00"), -10.00)
        self.assertEqual(parse_currency("R$ 0,00"), 0.0)
        self.assertEqual(parse_currency(""), 0.0)
        self.assertEqual(parse_currency(None), 0.0)
        self.assertEqual(parse_currency("150,75"), 150.75)

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
        self.assertEqual(parse_conta("Recebimento Apto - 301 Competência AGO 2024 - Conta: CONTA CORRENTE - SICOOB"), "CONTA CORRENTE")
        self.assertEqual(parse_conta("Pagamento Guardian Condo Serv De Port. Remota Ltda Doc.: 4929 - Conta: CONTA CORRENTE - SICOOB - Código de barra/Qr Code"), "CONTA CORRENTE")
        self.assertEqual(parse_conta("UND: Apto / 402 - FEV 2025 - CTA. PGTO: CONTA CORRENTE - SICOOB"), "CONTA CORRENTE")
        self.assertEqual(parse_conta("Pagamento Flavio Borges Gonçalves - Conta: CONTA CORRENTE - SICOOB - Pix"), "CONTA CORRENTE")
        self.assertEqual(parse_conta("Pagamento Guardian Condo Serv De Port. Remota Ltda - Doc.: 5894 - Conta: CONTA CORRENTE - SICOOB - DÉB.TIT.COMPE EFETIVADO"), "CONTA CORRENTE")
        self.assertIsNone(parse_conta("Sem conta na descrição"))

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
            'mes', rec_total_mes=100.0, soma_cat_rec=100.0, desp_total_mes=50.0, soma_cat_desp=50.0
        )
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)

        # Mês inconsistente (divergência em despesas)
        consistente, motivo = evaluate_entity_consistency(
            'mes', rec_total_mes=100.0, soma_cat_rec=100.0, desp_total_mes=50.0, soma_cat_desp=49.9
        )
        self.assertEqual(consistente, 0)
        reasons = json.loads(motivo)
        self.assertIn("Divergência em despesas", reasons)

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
            anexos_esperados=1, anexos_baixados=1, despesa_anexo_valido=True
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
            anexos_esperados=1, anexos_baixados=0, despesa_anexo_valido=True
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
            anexos_esperados=1, anexos_baixados=1, despesa_anexo_valido=True
        )
        consistente, motivo, apto, comp, fornecedor, conta = res
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)
        self.assertEqual(fornecedor, "CEMIG")
        self.assertEqual(conta, "CONTA CORRENTE")

        # Despesa inconsistente por falta de comprovantes (regra nova), fornecedor ausente e conta ausente
        res = evaluate_entity_consistency(
            'transacao', tipo_flag="D", desc_completa="Copa", desc_f="Copa",
            anexos_esperados=0, anexos_baixados=0, despesa_anexo_valido=False
        )
        consistente, motivo, apto, comp, fornecedor, conta = res
        self.assertEqual(consistente, 0)
        reasons = json.loads(motivo)
        self.assertIn("Fornecedor não identificado", reasons)
        self.assertIn("Despesa sem comprovantes", reasons)
        self.assertIn("Conta não identificada", reasons)

    def test_evaluate_consistency_anexo(self):
        # Anexo consistente (com extensão válida)
        consistente, motivo = evaluate_entity_consistency('anexo', nome_original="boleto.pdf")
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)

        # Anexo inconsistente (sem extensão ou muito curta/longa)
        consistente, motivo = evaluate_entity_consistency('anexo', nome_original="boleto_invalido")
        self.assertEqual(consistente, 0)
        self.assertEqual(json.loads(motivo)[0], "Extensão de arquivo inválida ou ausente")

    def test_evaluate_consistency_prestacao_contas(self):
        # Prestação de contas baixada com sucesso
        consistente, motivo = evaluate_entity_consistency('prestacao_contas', sucesso=True)
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)

        # Prestação de contas indisponível
        consistente, motivo = evaluate_entity_consistency('prestacao_contas', sucesso=False)
        self.assertEqual(consistente, 0)
        self.assertEqual(json.loads(motivo)[0], "Prestação de contas indisponível")

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
        class MockConnectionWrapper:
            def __init__(self, conn):
                self._conn = conn
            def cursor(self):
                return self._conn.cursor()
            def commit(self):
                return self._conn.commit()
            def rollback(self):
                return self._conn.rollback()
            def close(self):
                pass # Não faz nada para não apagar o banco em memória
                
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS condominio (
                id TEXT PRIMARY KEY,
                nome TEXT,
                inadimplencia_data_corte TEXT,
                inadimplencia_unidades INTEGER,
                inadimplencia_valor REAL,
                administradora TEXT,
                telefone_administradora TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS membros_gestao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condominio_id TEXT,
                nome TEXT,
                cargo TEXT,
                FOREIGN KEY (condominio_id) REFERENCES condominio(id)
            )
        """)
        conn.commit()
        
        wrapper = MockConnectionWrapper(conn)
        
        with patch('extract_winker.init_db') as mock_init_db:
            mock_init_db.return_value = wrapper
            
            from extract_winker import save_condominio_and_gestao
            
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
                telefone="3133334444",
                membros=membros
            )
            
            cursor.execute("SELECT * FROM condominio")
            condo_row = cursor.fetchone()
            self.assertEqual(condo_row, ("12345", "Residencial Teste", "10/06/2026", 5, 2500.00, "Cobrança S/A", "3133334444"))
            
            cursor.execute("SELECT condominio_id, nome, cargo FROM membros_gestao")
            membro_rows = cursor.fetchall()
            self.assertEqual(len(membro_rows), 2)
            self.assertEqual(membro_rows[0], ("12345", "João Silva", "Síndico"))
            self.assertEqual(membro_rows[1], ("12345", "Maria Santos", "Conselheiro"))
            
        conn.close()

    def test_get_ip_address(self):
        from extract_winker import get_ip_address
        ip = get_ip_address()
        self.assertTrue(ip is None or isinstance(ip, str))

    def test_get_mac_address(self):
        from extract_winker import get_mac_address
        mac = get_mac_address()
        self.assertTrue(mac is None or isinstance(mac, str))

    def test_save_auditoria(self):
        class MockConnectionWrapper:
            def __init__(self, conn):
                self._conn = conn
            def cursor(self):
                return self._conn.cursor()
            def commit(self):
                return self._conn.commit()
            def rollback(self):
                return self._conn.rollback()
            def close(self):
                pass
                
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condominio_id TEXT,
                usuario_uuid TEXT,
                usuario_id INTEGER,
                usuario_name TEXT,
                usuario_cpf TEXT,
                usuario_rg TEXT,
                usuario_fone TEXT,
                usuario_apto TEXT,
                data_hora_captura TEXT,
                ip TEXT,
                mac TEXT,
                periodo_inicio TEXT,
                periodo_fim TEXT,
                downloads_realizados INTEGER,
                transacoes_lidas INTEGER,
                tempo_duracao REAL,
                capturou_condominio INTEGER,
                capturou_inadimplencia INTEGER,
                capturou_membros INTEGER
            )
        """)
        conn.commit()
        
        wrapper = MockConnectionWrapper(conn)
        
        with patch('extract_winker.init_db') as mock_init_db, \
             patch('extract_winker.get_ip_address') as mock_get_ip, \
             patch('extract_winker.get_mac_address') as mock_get_mac:
             
            mock_init_db.return_value = wrapper
            mock_get_ip.return_value = "192.168.1.10"
            mock_get_mac.return_value = "00:11:22:33:44:55"
            
            from extract_winker import create_auditoria, update_auditoria, update_auditoria_condominio_id
            
            auditoria_id = create_auditoria(periodo_inicio="2026-01", periodo_fim="2026-02")
            self.assertEqual(auditoria_id, 1)
            
            cursor.execute("SELECT * FROM auditoria WHERE id = ?", (auditoria_id,))
            initial_row = cursor.fetchone()
            self.assertIsNotNone(initial_row)
            # condominio_id deve ser NULL no início (índice 1 com a nova coluna)
            self.assertIsNone(initial_row[1])
            self.assertEqual(initial_row[10], "192.168.1.10")
            self.assertEqual(initial_row[11], "00:11:22:33:44:55")
            self.assertEqual(initial_row[12], "2026-01")
            self.assertEqual(initial_row[13], "2026-02")
            self.assertEqual(initial_row[14], 0)
            self.assertEqual(initial_row[15], 0)
            self.assertEqual(initial_row[16], 0.0)
            self.assertEqual(initial_row[17], 0)
            self.assertEqual(initial_row[18], 0)
            self.assertEqual(initial_row[19], 0)
            
            user_data = {
                "uuid": "test-uuid-123",
                "id_user": 999,
                "name": "Audit User",
                "cpf": "111.111.111-11",
                "rg": "MG-11.111.111",
                "phones": [{"number": "31988888888"}],
                "units": [{"name": "302"}]
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

            # Testa update_auditoria_condominio_id: preenche condominio_id após obtenção
            update_auditoria_condominio_id(auditoria_id=auditoria_id, condominio_id="CONDO-001")
            
            cursor.execute("SELECT * FROM auditoria WHERE id = ?", (auditoria_id,))
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            # Verifica condominio_id atualizado (índice 1)
            self.assertEqual(row[1], "CONDO-001")
            self.assertEqual(row[2], "test-uuid-123")
            self.assertEqual(row[3], 999)
            self.assertEqual(row[4], "Audit User")
            self.assertEqual(row[5], "111.111.111-11")
            self.assertEqual(row[6], "MG-11.111.111")
            self.assertEqual(row[7], "31988888888")
            self.assertEqual(row[8], "302")
            self.assertEqual(row[10], "192.168.1.10")
            self.assertEqual(row[11], "00:11:22:33:44:55")
            self.assertEqual(row[12], "2026-01")
            self.assertEqual(row[13], "2026-02")
            self.assertEqual(row[14], 5)
            self.assertEqual(row[15], 150)
            self.assertEqual(row[16], 12.5)
            self.assertEqual(row[17], 1)
            self.assertEqual(row[18], 0)
            self.assertEqual(row[19], 1)
            
        conn.close()

    def test_database_migration_add_condominio_id(self):
        """Testa a migração que adiciona condominio_id nas tabelas meses, membros_gestao e auditoria."""
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()

        # Cria o schema antigo (sem condominio_id)
        cursor.execute("""
            CREATE TABLE condominio (
                id TEXT PRIMARY KEY,
                nome TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE meses (
                id TEXT PRIMARY KEY,
                exibicao TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE membros_gestao (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT,
                cargo TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                periodo_inicio TEXT,
                periodo_fim TEXT
            )
        """)

        # Popula com dados de teste
        cursor.execute("INSERT INTO condominio (id, nome) VALUES ('CONDO-001', 'Residencial Teste')")
        cursor.execute("INSERT INTO meses (id, exibicao) VALUES ('202601', 'JAN/2026')")
        cursor.execute("INSERT INTO meses (id, exibicao) VALUES ('202602', 'FEV/2026')")
        cursor.execute("INSERT INTO membros_gestao (nome, cargo) VALUES ('João', 'Síndico')")
        cursor.execute("INSERT INTO auditoria (periodo_inicio, periodo_fim) VALUES ('2026-01', '2026-02')")
        conn.commit()

        from migration_add_condominio_id import migrate_db
        migrate_db(conn=conn)

        # Verifica meses: condominio_id deve ter sido preenchido
        cursor.execute("PRAGMA table_info(meses)")
        colunas_meses = [col[1] for col in cursor.fetchall()]
        self.assertIn("condominio_id", colunas_meses)
        cursor.execute("SELECT id, condominio_id FROM meses ORDER BY id")
        meses_rows = cursor.fetchall()
        self.assertEqual(meses_rows[0], ("202601", "CONDO-001"))
        self.assertEqual(meses_rows[1], ("202602", "CONDO-001"))

        # Verifica membros_gestao: condominio_id deve ter sido preenchido
        cursor.execute("PRAGMA table_info(membros_gestao)")
        colunas_mg = [col[1] for col in cursor.fetchall()]
        self.assertIn("condominio_id", colunas_mg)
        cursor.execute("SELECT nome, condominio_id FROM membros_gestao")
        mg_rows = cursor.fetchall()
        self.assertEqual(mg_rows[0], ("João", "CONDO-001"))

        # Verifica auditoria: condominio_id deve ser NULL (campo opcional)
        cursor.execute("PRAGMA table_info(auditoria)")
        colunas_aud = [col[1] for col in cursor.fetchall()]
        self.assertIn("condominio_id", colunas_aud)
        cursor.execute("SELECT periodo_inicio, condominio_id FROM auditoria")
        aud_rows = cursor.fetchall()
        self.assertEqual(aud_rows[0], ("2026-01", None))

        conn.close()

    def test_database_migration(self):
        # Cria um banco de dados temporário em memória para testar a migração
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        
        # Cria a tabela transacoes sem a coluna conta
        cursor.execute("""
            CREATE TABLE transacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT,
                consistente INTEGER DEFAULT 1,
                motivo_inconsistencia TEXT
            )
        """)
        
        # Insere dados de teste:
        # 1. Transação consistente com conta no formato 'Conta:'
        cursor.execute("INSERT INTO transacoes (descricao, consistente, motivo_inconsistencia) VALUES (?, ?, ?)",
                       ("Recebimento Apto - 301 Competência AGO 2024 - Conta: CONTA CORRENTE - SICOOB", 1, None))
        
        # 2. Transação consistente com conta no formato 'CTA. PGTO:'
        cursor.execute("INSERT INTO transacoes (descricao, consistente, motivo_inconsistencia) VALUES (?, ?, ?)",
                       ("UND: Apto / 402 - FEV 2025 - CTA. PGTO: CONTA CORRENTE - SICOOB", 1, None))
                       
        # 3. Transação que já era inconsistente e não tem conta
        cursor.execute("INSERT INTO transacoes (descricao, consistente, motivo_inconsistencia) VALUES (?, ?, ?)",
                       ("Juros S/ Aplicação", 0, '["Apartamento não identificado"]'))
                       
        # 4. Transação consistente mas que ficará inconsistente por falta de conta
        cursor.execute("INSERT INTO transacoes (descricao, consistente, motivo_inconsistencia) VALUES (?, ?, ?)",
                       ("Taxa ordinaria sem conta", 1, None))
                       
        conn.commit()
        
        # Importa e executa a migração
        from migration_add_conta import migrate_db
        migrate_db(conn=conn)
        
        # Verifica se a coluna conta foi adicionada e os valores foram preenchidos corretamente
        cursor.execute("PRAGMA table_info(transacoes)")
        colunas = [col[1] for col in cursor.fetchall()]
        self.assertIn("conta", colunas)
        
        # Seleciona os registros e valida as transformações
        cursor.execute("SELECT id, descricao, consistente, motivo_inconsistencia, conta FROM transacoes ORDER BY id")
        rows = cursor.fetchall()
        
        # 1. Primeira transação
        self.assertEqual(rows[0][4], "CONTA CORRENTE")
        self.assertEqual(rows[0][2], 1)
        self.assertIsNone(rows[0][3])
        
        # 2. Segunda transação
        self.assertEqual(rows[1][4], "CONTA CORRENTE")
        self.assertEqual(rows[1][2], 1)
        self.assertIsNone(rows[1][3])
        
        # 3. Terceira transação (já inconsistente, sem conta)
        self.assertIsNone(rows[2][4])
        self.assertEqual(rows[2][2], 0)
        reasons_3 = json.loads(rows[2][3])
        self.assertIn("Apartamento não identificado", reasons_3)
        self.assertIn("Conta não identificada", reasons_3)
        
        # 4. Quarta transação (ficou inconsistente por falta de conta)
        self.assertIsNone(rows[3][4])
        self.assertEqual(rows[3][2], 0)
        reasons_4 = json.loads(rows[3][3])
        self.assertEqual(reasons_4, ["Conta não identificada"])
        
        conn.close()


if __name__ == "__main__":
    unittest.main()
