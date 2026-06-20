import unittest
from datetime import datetime
import json

# Importa as funções do script extract_winker
from extract_winker import (
    parse_currency,
    parse_receita_info,
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
            'transacao', tipo_flag="R", desc_completa="Taxa Apto - 101 JUN 2026", desc_f="Taxa Apto - 101 JUN 2026",
            anexos_esperados=1, anexos_baixados=1, despesa_anexo_valido=True
        )
        consistente, motivo, apto, comp, fornecedor = res
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)
        self.assertEqual(apto, "101")
        self.assertEqual(comp, "2026-06")

        # Receita inconsistente
        res = evaluate_entity_consistency(
            'transacao', tipo_flag="R", desc_completa="Taxa Avulsa", desc_f="Taxa Avulsa",
            anexos_esperados=1, anexos_baixados=0, despesa_anexo_valido=True
        )
        consistente, motivo, apto, comp, fornecedor = res
        self.assertEqual(consistente, 0)
        reasons = json.loads(motivo)
        self.assertIn("Apartamento não identificado", reasons)
        self.assertIn("Competência não identificada", reasons)
        self.assertIn("Quantidade de anexos divergente", reasons)

    def test_evaluate_consistency_transacao_despesa(self):
        # Despesa consistente
        res = evaluate_entity_consistency(
            'transacao', tipo_flag="D", desc_completa="Pagamento Cemig - Conta Energia", desc_f="Pagamento Cemig",
            anexos_esperados=1, anexos_baixados=1, despesa_anexo_valido=True
        )
        consistente, motivo, apto, comp, fornecedor = res
        self.assertEqual(consistente, 1)
        self.assertIsNone(motivo)
        self.assertEqual(fornecedor, "CEMIG")

        # Despesa inconsistente por falta de comprovantes (regra nova) e fornecedor ausente
        res = evaluate_entity_consistency(
            'transacao', tipo_flag="D", desc_completa="Copa", desc_f="Copa",
            anexos_esperados=0, anexos_baixados=0, despesa_anexo_valido=False
        )
        consistente, motivo, apto, comp, fornecedor = res
        self.assertEqual(consistente, 0)
        reasons = json.loads(motivo)
        self.assertIn("Fornecedor não identificado", reasons)
        self.assertIn("Despesa sem comprovantes", reasons)

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

if __name__ == "__main__":
    unittest.main()
