"""Synthetic multi-layout/identity regressions; no processed financial data."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from table_geometry import amount_readings,valid_dates,date_readings,header_columns,physical_rows
from reconcile_local import compare,bank_paths,statements_report


def word(text,x,y=.1,w=.04,h=.01,line=1):
    return {'text':text,'x':x,'y':y,'w':w,'h':h,'confidence':90,'line':[1,1,line]}


class GeometryTests(unittest.TestCase):
    def test_money_rejects_missing_separator_and_preserves_sign(self):
        self.assertEqual(amount_readings('12345'),[])
        self.assertEqual([r['cents'] for r in amount_readings('-1.234,56 7.80 +0,01')],[-123456,780,1])

    def test_dates_do_not_depend_on_year_or_accept_partial_invalid_date(self):
        self.assertEqual(valid_dates('31/02/2021 01/03/2031 101/03/2031'),['01/03/2031'])
        self.assertEqual(date_readings('01032031')[0]['value'],'01/03/2031')
        self.assertEqual(date_readings('101/03/2031'),[])
        self.assertEqual(date_readings('31.02.2031'),[])

    def test_unit_header_delimits_date_column_without_fixed_margin(self):
        ws=[word('Unidade',.03),word('Vencimento',.24),word('Pagamento',.4),word('Liquidado',.7)]
        columns,_=header_columns(ws,'recebimentos')
        self.assertGreater(columns['due']['left'],columns['unit']['center'])
        self.assertLess(columns['due']['left'],columns['due']['center'])

    def test_columns_follow_headers_when_their_order_changes(self):
        ws=[word('Data',.18),word('Saldo',.40),word('Crédito',.60),word('Débito',.80)]
        cols,issues=header_columns(ws,'extrato')
        self.assertFalse(issues)
        self.assertLess(cols['balance']['center'],cols['credit']['center'])
        self.assertLess(cols['date']['right'],cols['credit']['right'])

    def test_brackets_and_multiword_settlement_header(self):
        ws=[word('[Vencimento',.2),word('Pagamento',.35),word('Valor',.6),word('Pago',.65)]
        cols,issues=header_columns(ws,'recebimentos')
        self.assertIn('due',cols);self.assertIn('settled',cols);self.assertFalse(issues)

    def test_date_anchor_not_tall_border_determines_row(self):
        cols={k:dict(left=l,right=r,header_y=.1) for k,l,r in [('due',.2,.3),('paid',.3,.4),('settled',.6,.7)]}
        ws=[word('14B',.05,.18,line=2),word('01/05/2031',.22,.2,w=.06,line=3),
            word('03/05/2031',.32,.2,w=.06,line=3),word('20,00',.62,.2,line=3),
            word('|',.01,.12,h=.7,line=3)]
        rows,issues,unit=physical_rows(ws,cols,'recebimentos')
        self.assertFalse(issues);self.assertEqual(unit,'14B');self.assertAlmostEqual(rows[0]['source_y'],.205)
        self.assertEqual(rows[0]['cells']['settled']['cents'],2000)

    def test_missing_header_is_unresolved_instead_of_a_fixed_column_guess(self):
        cols,issues=header_columns([word('unreadable',.5)],'recebimentos')
        self.assertEqual(cols,{});self.assertTrue(issues)


class ReconciliationTests(unittest.TestCase):
    def row(self,unit,value):
        return dict(tipo='R',categoria='group',classe='class',data='01/01/2031',apartamento=unit,
                    competencia='2031-01',fornecedor=None,conta='registered',descricao='original history',valor_centavos=value)

    def test_equal_totals_do_not_hide_duplicated_unit_and_missing_unit(self):
        gold=[self.row('A',100),self.row('B',100)]
        result=compare([self.row('A',100),self.row('A',100)],gold)
        self.assertEqual(result['candidate_totals_cents'],result['reference_totals_cents'])
        self.assertEqual(result['missing_reference_rows'],1)
        self.assertEqual(result['extra_candidate_rows'],1)
        self.assertEqual(result['status'],'EXCEPTIONS_REQUIRED')

    def test_missing_identity_is_not_filled_from_reference(self):
        candidate=self.row('A',100);del candidate['competencia']
        self.assertEqual(compare([candidate],[self.row('A',100)])['unresolved_candidate_rows'],1)

    def test_history_and_document_are_checked_even_when_amount_matches(self):
        candidate=self.row('A',100);candidate['descricao']='supplier NF:12 service omitted'
        self.assertEqual(compare([candidate],[self.row('A',100)])['exact_identity_matches'],0)
        candidate['descricao']='history changed, no invoice difference'
        result=compare([candidate],[self.row('A',100)])
        self.assertEqual(result['exact_identity_matches'],1)
        self.assertEqual(result['exact_history_matches'],0)
        self.assertEqual(result['status'],'EXCEPTIONS_REQUIRED')

    def test_only_existing_ocr_values_may_satisfy_chain(self):
        bad={'credit':5,'debit':0,'balance':120}
        good={'credit':20,'debit':0,'balance':120,'evidence':'crop'}
        result=bank_paths(100,120,[{'alternatives':[bad,good]}])
        self.assertEqual(result['status'],'UNIQUE_OBSERVED_PATH')
        self.assertEqual(result['rows'],[good])
        self.assertEqual(bank_paths(100,120,[bad])['status'],'NO_OBSERVED_PATH')

    def test_merged_paths_remain_ambiguous_even_with_same_closing_balance(self):
        alternatives=[{'credit':20,'debit':0,'balance':120}, {'credit':30,'debit':10,'balance':120}]
        self.assertEqual(bank_paths(100,120,[{'alternatives':alternatives}])['status'],'AMBIGUOUS')

    def test_two_physical_accounts_do_not_share_chain_even_with_same_name(self):
        statements=[dict(alias='A',account='current',opening=100,closing=120,rows=[dict(credit=20,debit=0,balance=120)]),
                    dict(alias='B',account='current',opening=400,closing=390,rows=[dict(credit=0,debit=10,balance=390)])]
        self.assertEqual([r['status'] for r in statements_report(statements)],['UNIQUE_OBSERVED_PATH']*2)


if __name__=='__main__':unittest.main()
