import sys
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

with patch('compartilhado.setup_deps.install_dependencies'):
    from bff.relatorios import Relatorios


class TestRelatorioInadimplencia(unittest.TestCase):
    def test_filtra_agrupa_ordena_e_totaliza_sem_encargos(self):
        api = Mock()
        relatorios = Relatorios(api)
        api._calcular_posicao_unificada = Mock(return_value={'grupos': []})
        resultado = [
            {'unidade': '202', 'taxas': [{'id': 4, 'competencia': '2024-02', 'vencimento': '12/02/2024', 'valor': 999, 'multa': 3}]},
            {'unidade': '101', 'taxas': [
                {'id': 1, 'competencia': '2024-02', 'vencimento': '10/02/2024', 'descricao': 'B', 'valor': 10.1, 'juros_total': 100},
                {'id': 2, 'competencia': '2024-01', 'vencimento': '10/01/2024', 'descricao': 'A', 'valor': 20.2, 'multa': 90},
                {'id': 3, 'competencia': '2024-02', 'vencimento': '10/02/2024', 'descricao': 'C', 'valor': 30.3, 'total': 900},
            ]}
        ]
        with patch('bff.apresentacao_conciliacao.inadimplencia', return_value=resultado):
            resposta = relatorios.get_relatorio_inadimplencia({'data_corte': '2024-03-01', 'apartamentos': ['101']})
        api._calcular_posicao_unificada.assert_called_once_with('2024-03-01', {'apartamentos': ['101']}, permitir_inconclusivo=True)
        dados = resposta['data']
        self.assertEqual([u['apartamento'] for u in dados['apartamentos']], ['101'])
        unidade = dados['apartamentos'][0]
        self.assertEqual([g['competencia'] for g in unidade['competencias']], ['2024-01', '2024-02'])
        self.assertEqual([t['valor'] for t in unidade['competencias'][1]['taxas']], [30.3, 10.1])
        self.assertEqual(unidade['competencias'][1]['subtotal'], 40.4)
        self.assertEqual(unidade['subtotal'], 60.6)
        self.assertEqual(dados['total'], 60.6)
        self.assertNotIn('juros_total', unidade['competencias'][1]['taxas'][1])
        self.assertNotIn('multa', unidade['competencias'][0]['taxas'][0])

    def test_retorna_erro_do_calculo_e_valida_data(self):
        api = Mock()
        relatorios = Relatorios(api)
        api._calcular_posicao_unificada = Mock(side_effect=ValueError('Falha de conciliação'))
        self.assertEqual(relatorios.get_relatorio_inadimplencia({'data_corte': '2024-01-01'}), {'status': 'error', 'message': 'Falha de conciliação'})
        self.assertEqual(relatorios.get_relatorio_inadimplencia({})['status'], 'error')
