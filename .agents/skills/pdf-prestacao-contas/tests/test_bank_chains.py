"""Synthetic independent physical bank-chain validation."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_sql import validate_bank_chains

class BankChainTests(unittest.TestCase):
    def test_independent_chains_can_share_canonical_account(self):
        bank = {'statements': [
            {'alias': 'physical A', 'account': 'Current', 'opening': 100,
             'closing': 130, 'rows': [{'credit': 40, 'debit': 10, 'balance': 130}]},
            {'alias': 'physical B', 'account': 'Current', 'opening': 500,
             'closing': 480, 'rows': [{'credit': 0, 'debit': 20, 'balance': 480}]}]}
        self.assertEqual(validate_bank_chains(bank), 2)
        bank['statements'][1]['rows'][0]['balance'] = 479
        with self.assertRaises(AssertionError):
            validate_bank_chains(bank)

    def test_legacy_and_empty_movements_preserve_closing_check(self):
        self.assertEqual(validate_bank_chains({'opening': 100, 'closing': 100, 'rows': []}), 0)
        with self.assertRaises(AssertionError):
            validate_bank_chains({'opening': 100, 'closing': 101, 'rows': []})

if __name__ == '__main__':
    unittest.main()
