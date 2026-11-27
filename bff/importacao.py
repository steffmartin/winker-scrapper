"""Execução assíncrona do extrator e configurações de importação."""
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path


class Importacao:
    CAMPOS = ('user', 'password', 'wl', 'portal_index', 'log_level', 'start', 'end', 'headless', 'no_wait')

    def __init__(self, ctx):
        self.ctx = ctx
        self.diretorio = Path(ctx.raiz_projeto) / 'compartilhado' / 'config'
        self.lock = threading.Lock()
        self.processo = None
        self.sequencia = 0
        self.estado = {'is_running': False, 'resultado': None, 'erro': None, 'condominio_id': None, 'arquivo': None, 'log': ''}

    def _arquivo(self, nome):
        if not isinstance(nome, str) or Path(nome).name != nome or not nome.endswith('.config') or nome.lower() == 'example.config':
            raise ValueError('Arquivo de configuração inválido.')
        caminho = self.diretorio / nome
        if not caminho.is_file() or caminho.resolve().parent != self.diretorio.resolve():
            raise ValueError('Arquivo de configuração não encontrado.')
        return caminho

    def arquivos(self):
        arquivos = sorted(p.name for p in self.diretorio.glob('*.config') if p.name.lower() != 'example.config' and p.is_file() and p.resolve().parent == self.diretorio.resolve())
        try:
            with (self.diretorio / 'importacoes.json').open(encoding='utf-8') as arquivo:
                selecionado = json.load(arquivo).get(str(self.ctx.condo_id))
        except (OSError, ValueError, AttributeError):
            selecionado = None
        return {'status': 'success', 'data': arquivos, 'selecionado': selecionado if selecionado in arquivos else None}

    def carregar(self, nome):
        try:
            with self._arquivo(nome).open(encoding='utf-8') as arquivo:
                dados = json.load(arquivo)
            parametros = {k: dados.get(k) for k in self.CAMPOS if k not in ('start', 'end')}
            inicio, fim = dados.get('start') or '', dados.get('end') or ''
            parametros['periodo'] = [inicio or None, fim or None] if inicio or fim else None
            return {'status': 'success', 'data': parametros, 'condominio_id': self.ctx.condo_id}
        except (OSError, ValueError, TypeError) as erro:
            return {'status': 'error', 'message': str(erro)}

    def iniciar(self, nome, dados, condominio_id):
        try:
            if condominio_id != self.ctx.condo_id:
                raise ValueError('O condomínio selecionado mudou. Recarregue a configuração.')
            caminho = self._arquivo(nome)
            if not isinstance(dados, dict) or set(dados) != (set(self.CAMPOS) - {'start', 'end'}) | {'periodo'}:
                raise ValueError('Parâmetros de importação inválidos.')
            dados = dict(dados)
            periodo = dados.pop('periodo')
            if periodo is None:
                periodo = [None, None]
            if not isinstance(periodo, list) or len(periodo) != 2 or any(valor is not None and not isinstance(valor, str) for valor in periodo):
                raise ValueError('Período inválido.')
            dados['start'], dados['end'] = (valor or '' for valor in periodo)
            if not all(isinstance(dados[k], str) for k in ('user', 'password', 'wl', 'log_level', 'start', 'end')) or not dados['user'] or not dados['password']:
                raise ValueError('Informe usuário e senha válidos.')
            if type(dados['portal_index']) is not int or dados['portal_index'] < 1 or any(type(dados[k]) is not bool for k in ('headless', 'no_wait')):
                raise ValueError('Parâmetros de importação inválidos.')
            if dados['log_level'] not in ('DEBUG', 'INFO', 'WARNING', 'ERROR'):
                raise ValueError('Nível de log inválido.')
            for campo in ('start', 'end'):
                if dados[campo] and not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', dados[campo]):
                    raise ValueError('Competência inválida.')
            if dados['start'] and dados['end'] and dados['start'] > dados['end']:
                raise ValueError('A competência inicial deve ser anterior à final.')
            with self.lock:
                if self.estado['is_running']:
                    raise ValueError('Já existe uma importação em andamento.')
                with caminho.open(encoding='utf-8') as arquivo:
                    atual = json.load(arquivo)
                atual.update(dados)
                with caminho.open('w', encoding='utf-8') as arquivo:
                    json.dump(atual, arquivo, ensure_ascii=False, indent=4)
                    arquivo.write('\n')
                try:
                    with (self.diretorio / 'importacoes.json').open(encoding='utf-8') as arquivo:
                        associacoes = json.load(arquivo)
                    if not isinstance(associacoes, dict):
                        associacoes = {}
                except (OSError, ValueError):
                    associacoes = {}
                associacoes[str(condominio_id)] = nome
                with (self.diretorio / 'importacoes.json').open('w', encoding='utf-8') as arquivo:
                    json.dump(associacoes, arquivo, ensure_ascii=False, indent=4)
                self.sequencia += 1
                self.estado = {'id': self.sequencia, 'is_running': True, 'resultado': None, 'erro': None, 'condominio_id': condominio_id, 'arquivo': nome, 'log': ''}
                threading.Thread(target=self._executar, args=(caminho,), daemon=True).start()
            return {'status': 'success'}
        except (OSError, ValueError, TypeError) as erro:
            return {'status': 'error', 'message': str(erro)}

    def _executar(self, caminho):
        processo = None
        try:
            ambiente = os.environ.copy()
            ambiente['PYTHONIOENCODING'] = 'utf-8'
            processo = subprocess.Popen([sys.executable, '-u', str(Path(self.ctx.raiz_projeto) / 'extrator' / 'main.py'), '--config-file', str(caminho)], cwd=self.ctx.raiz_projeto, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', env=ambiente, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            with self.lock:
                self.processo = processo
            for linha in iter(lambda: processo.stdout.read(1), ''):
                with self.lock:
                    self.estado['log'] += linha
            codigo = processo.wait()
            with self.lock:
                self.estado['resultado'] = 'sucesso' if codigo == 0 else 'falha'
                self.estado['erro'] = None if codigo == 0 else f'Extrator encerrado com código {codigo}.'
        except Exception as erro:
            with self.lock:
                self.estado['resultado'] = 'falha'
                self.estado['erro'] = str(erro)
        finally:
            with self.lock:
                self.processo = None
                self.estado['is_running'] = False
            if processo:
                processo.stdin.close()
                processo.stdout.close()

    def enviar_entrada(self, texto):
        if not isinstance(texto, str) or '\n' in texto or '\r' in texto:
            return {'status': 'error', 'message': 'Entrada inválida.'}
        with self.lock:
            try:
                if not self.processo or not self.estado['is_running']:
                    raise ValueError('Nenhuma importação disponível para receber entrada.')
                self.processo.stdin.write(texto + '\n')
                self.processo.stdin.flush()
                self.estado['log'] += texto + '\n'
                return {'status': 'success'}
            except (OSError, ValueError) as erro:
                return {'status': 'error', 'message': str(erro)}

    def obter_estado(self, cursor=0):
        with self.lock:
            estado = dict(self.estado)
            log = estado.pop('log')
            cursor = cursor if type(cursor) is int and 0 <= cursor <= len(log) else 0
            estado.update(log=log[cursor:], cursor=len(log))
            return {'status': 'success', 'data': estado}
