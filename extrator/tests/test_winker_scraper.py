"""Contratos de execução isolada do extrator; sem rede ou banco reais."""
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from extrator.execucao import WinkerScraper
from compartilhado import models


class TestWinkerScraper(unittest.TestCase):
    def test_execucoes_isolam_estado_e_usam_dependencias_fornecidas(self):
        inicio = datetime(2025, 1, 1)
        dependencias = []
        scrapers = []
        for usuario in ('primeiro', 'segundo'):
            playwright = MagicMock()
            browser = playwright.return_value.__enter__.return_value.chromium.launch.return_value
            pagina = browser.new_context.return_value.new_page.return_value
            pagina.goto.side_effect = RuntimeError('login de teste interrompido')
            iniciar_banco = MagicMock()
            scraper = WinkerScraper(usuario, 'senha-teste', 'portal', inicio, inicio, True,
                                    playwright_factory=playwright, init_db_factory=iniciar_banco)
            playwright.assert_not_called()
            iniciar_banco.assert_not_called()
            dependencias.append((playwright, browser, iniciar_banco))
            scrapers.append(scraper)

        with tempfile.TemporaryDirectory() as pasta, \
             patch('extrator.execucao.project_root', pasta), \
             patch('extrator.execucao.create_auditoria', return_value=None):
            for scraper in scrapers:
                scraper.run()

        for playwright, browser, iniciar_banco in dependencias:
            playwright.assert_called_once_with()
            iniciar_banco.assert_called_once_with()
            browser.close.assert_called_once_with()
        self.assertIsNot(scrapers[0].user_data, scrapers[1].user_data)
        self.assertIsNot(scrapers[0].lista_contas_db, scrapers[1].lista_contas_db)
        self.assertIsNot(scrapers[0].regras_preenchimento, scrapers[1].regras_preenchimento)
        self.assertEqual([s.username for s in scrapers], ['primeiro', 'segundo'])


    def test_banco_informado_e_usado_em_cada_execucao(self):
        inicio = datetime(2025, 1, 1)
        with tempfile.TemporaryDirectory() as pasta, \
             patch('extrator.execucao.project_root', pasta), \
             patch('extrator.execucao.create_auditoria', return_value=None):
            try:
                for nome in ('primeiro.db', 'segundo.db'):
                    caminho = os.path.join(pasta, nome)
                    playwright = MagicMock()
                    browser = playwright.return_value.__enter__.return_value.chromium.launch.return_value
                    browser.new_context.return_value.new_page.return_value.goto.side_effect = RuntimeError('login simulado')
                    scraper = WinkerScraper('usuario', 'senha', 'portal', inicio, inicio, True,
                                            playwright_factory=playwright, db_path=caminho)
                    scraper.run()
                    self.assertEqual(models.db.database, caminho)
                    self.assertTrue(os.path.isfile(caminho))
                    models.db.close()
            finally:
                if not models.db.is_closed():
                    models.db.close()


if __name__ == '__main__':
    unittest.main()
