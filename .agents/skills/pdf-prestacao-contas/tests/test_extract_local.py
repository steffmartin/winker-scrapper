"""Synthetic regressions without processed PDFs, personal data, DB or network."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

path=Path(__file__).resolve().parents[1]/'scripts/extract_local.py'
spec=importlib.util.spec_from_file_location('extract_local',path)
ex=importlib.util.module_from_spec(spec);spec.loader.exec_module(ex)

class Page:
    def get_text(self,*args,**kwargs):return ''

class Image:
    def __init__(self,angle=0):self.angle=angle
    def rotate(self,angle,expand=True):return Image(angle)

class DiscoveryTests(unittest.TestCase):
    def test_garbled_contents_page_is_not_a_synthetic_table(self):
        text='SURUÁRRO\nCONTAS RECEBIDAS\nSINTÉTICO DE DESPESAS\nDESPESAS POR GRUPO E CLASSE\nVencimento Pagamento Valor Classe Fornecedor'
        self.assertIsNone(ex.classify(text))

    def test_first_investment_statement_does_not_end_incomplete_package(self):
        kinds=['demonstrativo','recebimentos','extrato','sintetico','analitico','extrato',None]
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            for number,kind in enumerate(kinds,1):
                ex.save(out/f'discovery_{number:03}.json',dict(page=number,section=kind,rotation=0,method='native',fraction=[1,1],source_sha256='synthetic',version=ex.VERSION))
            records=ex.discover([Page() for _ in kinds],out,'synthetic')
            self.assertEqual([r['section'] for r in records],kinds[:6])

    def test_partial_statement_requires_financial_structure(self):
        self.assertEqual(ex.classify('DEMONSTRATIVO PARCIAL\nRECEITAS DESPESAS VALORES EM R$'), 'demonstrativo')
        self.assertIsNone(ex.classify('DEMONSTRATIVO PARCIAL'))

    def test_global_pagination_is_not_section_pagination(self):
        self.assertEqual(ex.global_page_denominators({'demonstrativo':[[3,98],[4,98]],'recebimentos':[[7,98]]},100),{98})
        self.assertEqual(ex.global_page_denominators({'demonstrativo':[[1,2]],'recebimentos':[[1,7]]},100),set())

    def test_titleless_continuation_keeps_best_orientation(self):
        def ocr(image,psm=6):return 'supplier 01/01/2025 10,00 10,00' if image.angle==0 else 'unreadable'
        with tempfile.TemporaryDirectory() as directory,patch.object(ex,'render',return_value=Image()),patch.object(ex,'ocr',side_effect=ocr),patch.object(ex,'classify',return_value=None):
            out=Path(directory)
            record=dict(page=1,section='analitico',rotation=0,method='native',source_sha256='synthetic',version=ex.VERSION)
            text=ex.extract(Page(),record,out)
            self.assertIn('supplier',text)
            self.assertIn('"ocr_rotation": 0',(out/'page_001.json').read_text())

if __name__=='__main__':unittest.main()
