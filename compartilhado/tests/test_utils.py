"""Testes dos utilitários com arquivos de configuração fictícios e temporários."""
import json
import logging
import os
import tempfile
import unittest
from unittest.mock import patch

from compartilhado import utils
class UtilsTest(unittest.TestCase):
    def test_carrega_json_ficticio_e_aplica_nivel_de_log(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, 'entrada.json')
            with open(caminho, 'w', encoding='utf-8') as arquivo:
                json.dump({'log_level': 'DEBUG', 'opcao': 'valor de teste'}, arquivo)
            with patch.object(utils, 'setup_logging') as configurar:
                self.assertEqual(utils.load_config(caminho), {'log_level': 'DEBUG', 'opcao': 'valor de teste'})
            configurar.assert_called_once_with('DEBUG')

    def test_carrega_config_relativa_a_partir_da_raiz_do_projeto(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta_utils = os.path.join(pasta, 'compartilhado')
            os.makedirs(pasta_utils)
            with open(os.path.join(pasta, 'entrada.json'), 'w', encoding='utf-8') as arquivo:
                json.dump({'wl': 'portal-ficticio', 'log_level': 'DEBUG'}, arquivo)
            with patch.object(utils, '__file__', os.path.join(pasta_utils, 'utils.py')), \
                 patch.object(utils, 'setup_logging'):
                config = utils.load_config('entrada.json')
            self.assertEqual(config['wl'], 'portal-ficticio')
            self.assertEqual(config['log_level'], 'DEBUG')

    def test_arquivo_inexistente_e_nivel_desconhecido(self):
        with tempfile.TemporaryDirectory() as pasta:
            with self.assertRaises(FileNotFoundError):
                utils.load_config(os.path.join(pasta, 'ausente.json'))
        logger = logging.getLogger('winker')
        anteriores, nivel = logger.handlers[:], logger.level
        try:
            self.assertEqual(utils.setup_logging('desconhecido').level, logging.INFO)
            self.assertEqual(len(logger.handlers), 1)
        finally:
            logger.handlers = anteriores
            logger.setLevel(nivel)
