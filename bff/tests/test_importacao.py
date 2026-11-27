import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bff.importacao import Importacao


class ProcessoFalso:
    def __init__(self, codigo=0):
        self.codigo = codigo
        self.entrada = []
        self.liberar = threading.Event()
        self.stdin = self
        self.stdout = self
        self.texto = iter('Selecione: ')

    def write(self, texto): self.entrada.append(texto)
    def flush(self): self.liberar.set()
    def close(self): pass
    def read(self, _):
        try: return next(self.texto)
        except StopIteration:
            self.liberar.wait(2)
            return ''
    def wait(self): return self.codigo


class TestImportacao(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pasta = Path(self.temp.name) / 'compartilhado' / 'config'
        self.pasta.mkdir(parents=True)
        self.dados = dict(user='teste', password='ficticia', wl='', portal_index=1, log_level='INFO', start='', end='', headless=True, no_wait=True)
        self.parametros = {k: v for k, v in self.dados.items() if k not in ('start', 'end')}
        self.parametros['periodo'] = None
        for nome in ('example.config', 'teste.config'):
            (self.pasta / nome).write_text(json.dumps(self.dados), encoding='utf-8')
        self.importacao = Importacao(SimpleNamespace(raiz_projeto=self.temp.name, condo_id=123))

    def aguardar(self, predicado):
        for _ in range(200):
            if predicado(): return
            time.sleep(.01)
        self.fail('Operação não terminou no tempo esperado')

    def test_arquivos_carregamento_e_validacao(self):
        self.assertEqual(self.importacao.arquivos()['data'], ['teste.config'])
        self.assertEqual(self.importacao.carregar('teste.config')['data'], self.parametros)
        self.assertEqual(self.importacao.carregar('example.config')['status'], 'error')
        self.assertEqual(self.importacao.carregar('../teste.config')['status'], 'error')
        self.assertEqual(self.importacao.iniciar('teste.config', self.parametros, 999)['status'], 'error')

    def test_rejeita_parametros_invalidos_sem_iniciar_processo(self):
        casos = [
            {},
            {**self.parametros, 'periodo': ['2025-01']},
            {**self.parametros, 'user': ''},
            {**self.parametros, 'portal_index': 0},
            {**self.parametros, 'log_level': 'INVALIDO'},
            {**self.parametros, 'periodo': ['2025-13', '2025-12']},
            {**self.parametros, 'periodo': [123, None]},
            {**self.parametros, 'headless': 'sim'},
        ]
        with patch('bff.importacao.subprocess.Popen') as criar:
            for dados in casos:
                with self.subTest(dados=dados):
                    self.assertEqual(self.importacao.iniciar('teste.config', dados, 123)['status'], 'error')
            criar.assert_not_called()

    def test_arquivo_e_associacoes_invalidos(self):
        (self.pasta / 'invalido.config').write_text('{', encoding='utf-8')
        self.assertEqual(self.importacao.carregar('invalido.config')['status'], 'error')
        (self.pasta / 'importacoes.json').write_text('[]', encoding='utf-8')
        self.assertIsNone(self.importacao.arquivos()['selecionado'])
        processo = ProcessoFalso()
        processo.liberar.set()
        with patch('bff.importacao.subprocess.Popen', return_value=processo):
            self.assertEqual(self.importacao.iniciar('teste.config', self.parametros, 123)['status'], 'success')
            self.aguardar(lambda: not self.importacao.obter_estado()['data']['is_running'])
        self.assertEqual(self.importacao.arquivos()['selecionado'], 'teste.config')

    def test_entrada_rejeitada_sem_processo_ou_com_quebra_de_linha(self):
        self.assertEqual(self.importacao.enviar_entrada('linha\noutra')['status'], 'error')
        self.assertEqual(self.importacao.enviar_entrada('texto')['status'], 'error')
        processo = ProcessoFalso()
        processo.write = lambda _: (_ for _ in ()).throw(BrokenPipeError('pipe fechado'))
        self.importacao.processo = processo
        self.importacao.estado['is_running'] = True
        self.assertEqual(self.importacao.enviar_entrada('texto')['status'], 'error')
        self.assertEqual(self.importacao.obter_estado(-1)['data']['cursor'], 0)

    def test_falha_ao_criar_processo_e_informada(self):
        with patch('bff.importacao.subprocess.Popen', side_effect=OSError('processo indisponível')):
            self.assertEqual(self.importacao.iniciar('teste.config', self.parametros, 123)['status'], 'success')
            self.aguardar(lambda: not self.importacao.obter_estado()['data']['is_running'])
        estado = self.importacao.obter_estado()['data']
        self.assertEqual(estado['resultado'], 'falha')
        self.assertIn('processo indisponível', estado['erro'])

    def test_converte_periodo_ao_carregar_e_gravar(self):
        origem = {**self.dados, 'start': '2024-12', 'end': '2025-02'}
        (self.pasta / 'teste.config').write_text(json.dumps(origem), encoding='utf-8')
        self.assertEqual(self.importacao.carregar('teste.config')['data']['periodo'], ['2024-12', '2025-02'])
        processo = ProcessoFalso()
        processo.liberar.set()
        with patch('bff.importacao.subprocess.Popen', return_value=processo):
            self.assertEqual(self.importacao.iniciar('teste.config', {**self.parametros, 'periodo': ['2025-01', '2025-03']}, 123)['status'], 'success')
            self.aguardar(lambda: not self.importacao.obter_estado()['data']['is_running'])
        gravado = json.loads((self.pasta / 'teste.config').read_text(encoding='utf-8'))
        self.assertEqual((gravado['start'], gravado['end']), ('2025-01', '2025-03'))
        self.assertNotIn('periodo', gravado)
        self.assertEqual(self.importacao.iniciar('teste.config', {**self.parametros, 'periodo': ['2025-03', '2025-01']}, 123)['status'], 'error')

    def test_execucao_interativa_duplicidade_e_polling(self):
        processo = ProcessoFalso()
        with patch('bff.importacao.subprocess.Popen', return_value=processo):
            self.assertEqual(self.importacao.iniciar('teste.config', self.parametros, 123)['status'], 'success')
            self.aguardar(lambda: self.importacao.processo is not None)
            self.assertEqual(self.importacao.iniciar('teste.config', self.parametros, 123)['status'], 'error')
            self.aguardar(lambda: 'Selecione:' in self.importacao.obter_estado()['data']['log'])
            primeiro = self.importacao.obter_estado()['data']
            self.assertEqual(self.importacao.obter_estado(primeiro['cursor'])['data']['log'], '')
            self.assertEqual(self.importacao.enviar_entrada('1')['status'], 'success')
            self.aguardar(lambda: not self.importacao.obter_estado()['data']['is_running'])
            self.assertEqual(processo.entrada, ['1\n'])
            self.assertEqual(self.importacao.obter_estado()['data']['resultado'], 'sucesso')
            self.assertEqual(self.importacao.arquivos()['selecionado'], 'teste.config')

    def test_falha_libera_execucao(self):
        processo = ProcessoFalso(2)
        processo.liberar.set()
        with patch('bff.importacao.subprocess.Popen', return_value=processo):
            self.assertEqual(self.importacao.iniciar('teste.config', self.parametros, 123)['status'], 'success')
            self.aguardar(lambda: not self.importacao.obter_estado()['data']['is_running'])
            estado = self.importacao.obter_estado()['data']
            self.assertEqual(estado['resultado'], 'falha')
            self.assertIn('2', estado['erro'])

    def test_confirmacao_final_aguarda_entrada_e_preserva_log(self):
        processo = ProcessoFalso()
        processo.texto = iter('Concluído.\nPressione Enter para continuar...')
        with patch('bff.importacao.subprocess.Popen', return_value=processo):
            self.assertEqual(self.importacao.iniciar('teste.config', self.parametros, 123)['status'], 'success')
            self.aguardar(lambda: 'Pressione Enter para continuar...' in self.importacao.obter_estado()['data']['log'])
            self.assertTrue(self.importacao.obter_estado()['data']['is_running'])
            self.assertEqual(processo.entrada, [])
            self.assertEqual(self.importacao.enviar_entrada('')['status'], 'success')
            self.aguardar(lambda: not self.importacao.obter_estado()['data']['is_running'])
            self.assertEqual(processo.entrada, ['\n'])
            self.assertIn('Pressione Enter para continuar...', self.importacao.obter_estado()['data']['log'])


if __name__ == '__main__': unittest.main()
