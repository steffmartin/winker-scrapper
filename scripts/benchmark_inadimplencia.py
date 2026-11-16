"""Compara o cálculo anterior e o atual sem inicializar a aplicação ou escrever no banco.

Exemplo: python scripts/benchmark_inadimplencia.py --db database/winker_data.db
         --condominio ID --data 2026-11-03 --anterior HEAD
"""

import argparse
import ast
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import itertools
import json
import logging
import math
from pathlib import Path
import subprocess
import sys
from threading import Thread
import time
import types
from datetime import datetime

from conciliacao import LimiteConciliacao, encontrar_combinacao
from peewee import JOIN


ROOT = Path(__file__).resolve().parents[1]


class MedicaoInterrompida(BaseException):
    pass


def carregar_modelos(db_path):
    arvore = ast.parse((ROOT / 'scripts/models.py').read_text(encoding='utf-8-sig'))
    declaracoes = [
        node for node in arvore.body
        if isinstance(node, ast.ClassDef)
        or (isinstance(node, ast.ImportFrom) and node.module == 'peewee')
        or (isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == 'db' for t in node.targets))
    ]
    namespace = {}
    exec(compile(ast.Module(body=declaracoes, type_ignores=[]), 'modelos', 'exec'), namespace)
    modelos = types.SimpleNamespace(**namespace)
    modelos.db.init('file:' + db_path.resolve().as_posix() + '?mode=ro', uri=True)
    modelos.db.connect()
    modelos.db.execute_sql('PRAGMA query_only = ON')
    return modelos


def carregar_metodo(fonte, recentes):
    arvore = ast.parse(fonte)
    classe = next(n for n in arvore.body if isinstance(n, ast.ClassDef) and n.name == 'Api')
    metodo = next(n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == 'get_inadimplencia')
    bloco = metodo.body[1].body  # corpo do try que contém as consultas
    for indice in range(len(bloco) - 1, -1, -1):
        node = bloco[indice]
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        destino = node.targets[0]
        if not isinstance(destino, ast.Name) or destino.id not in {'condo', 'taxas', 'todas_transacoes'}:
            continue
        node.value = ast.Call(
            func=ast.Name(id='medir_consulta', ctx=ast.Load()),
            args=[ast.Lambda(args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[],
                                               kw_defaults=[], defaults=[]), body=node.value)],
            keywords=[],
        )
        if destino.id in {'taxas', 'todas_transacoes'}:
            extras = []
            if destino.id == 'taxas' and recentes:
                extras.extend(ast.parse("taxas = [t for t in taxas if t['competencia'] >= '2024-09']").body)
            extras.extend(ast.parse(f"volumes['{destino.id}'] = len({destino.id})").body)
            bloco[indice + 1:indice + 1] = extras
    return ast.fix_missing_locations(ast.Module(body=[metodo], type_ignores=[]))


def medir(fonte, modelos, condo_id, data, recentes, limite_segundos, limite_combinacoes,
          podar_positivos=False):
    consultas = 0.0
    volumes = {}
    combinacoes = 0
    inicio = time.perf_counter()

    def medir_consulta(funcao):
        nonlocal consultas
        comeco = time.perf_counter()
        try:
            return funcao()
        finally:
            consultas += time.perf_counter() - comeco

    def combinacoes_limitadas(itens, tamanho):
        nonlocal combinacoes
        if podar_positivos and all(item[1]['valor'] >= 0 for item in itens):
            # Somente no controle de equivalência: nenhum valor maior que os
            # dois alvos pode participar de uma soma de parcelas não negativas.
            # A ordem e os índices dos candidatos remanescentes são preservados.
            taxa = sys._getframe(1).f_locals['taxa']
            valor = taxa['valor_original']
            descontado = valor - (taxa['desconto_vista'] or 0)
            margem = (math.fsum(abs(item[1]['valor']) for item in itens) + abs(valor) +
                      abs(descontado) + 1) * len(itens) * sys.float_info.epsilon * 8
            teto = max(valor, descontado) + 0.01 + margem
            itens = [item for item in itens if item[1]['valor'] <= teto]
        for combinacao in itertools.combinations(itens, tamanho):
            combinacoes += 1
            if combinacoes >= limite_combinacoes or time.perf_counter() - inicio >= limite_segundos:
                raise MedicaoInterrompida()
            yield combinacao

    namespace = {
        'models': modelos, 'datetime': datetime, 'json': json, 'JOIN': JOIN,
        'itertools': types.SimpleNamespace(combinations=combinacoes_limitadas),
        'logger': logging.getLogger('benchmark_inadimplencia'),
        'medir_consulta': medir_consulta, 'volumes': volumes,
        'encontrar_combinacao': encontrar_combinacao, 'LimiteConciliacao': LimiteConciliacao,
    }
    exec(compile(carregar_metodo(fonte, recentes), 'get_inadimplencia', 'exec'), namespace)
    api = types.SimpleNamespace(init_error=None, condo_id=condo_id)
    resultado = None
    interrompido = False
    try:
        resultado = namespace['get_inadimplencia'](api, data)
    except MedicaoInterrompida:
        interrompido = True
    total = time.perf_counter() - inicio
    resumo = {
        'status': 'interrompido' if interrompido else resultado.get('status'),
        'consultas_segundos': round(consultas, 4),
        'processamento_e_instrumentacao_segundos': round(total - consultas, 4),
        'total_segundos': round(total, 4),
        'combinacoes_anteriores': combinacoes,
        'volumes': volumes,
    }
    if resultado is not None:
        resumo['sha256_resultado'] = hashlib.sha256(
            json.dumps(resultado, ensure_ascii=False, sort_keys=True).encode('utf-8')
        ).hexdigest()
        if resultado.get('status') != 'success':
            resumo['erro'] = resultado.get('message')
    return resumo, resultado


def medir_renderizacao(build_dir, chrome, resultado):
    """Mede do retorno da API simulada até o desenho da tabela em navegador local."""
    from playwright.sync_api import sync_playwright

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(build_dir.resolve()), **kwargs)

        def log_message(self, *_args):
            pass

    # O servidor expõe somente o build; dados da resposta ficam na memória.
    servidor = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = Thread(target=servidor.serve_forever, daemon=True)
    worker.start()
    url = f'http://127.0.0.1:{servidor.server_port}'
    dados = json.dumps(resultado, ensure_ascii=False)
    init_script = """
        const resultadoInadimplencia = DADOS_RESULTADO;
        window.pywebview = { api: new Proxy({}, { get: (_, nome) => {
            if (nome === 'get_inadimplencia') return () => {
                const inicio = performance.now();
                const observador = new MutationObserver(() => {
                    const tela = document.querySelector('app-inadimplencia');
                    if (tela && (tela.querySelector('p-tabs') ||
                                 tela.textContent.includes('Sem Inadimplência'))) {
                        observador.disconnect();
                        requestAnimationFrame(() => requestAnimationFrame(() => {
                            window.__renderMs = performance.now() - inicio;
                            window.__renderTabelas = tela.querySelectorAll('p-table').length;
                        }));
                    }
                });
                observador.observe(document.documentElement, { childList: true, subtree: true });
                return Promise.resolve(resultadoInadimplencia);
            };
            if (nome === 'get_nome_condominio') return () => Promise.resolve({status: 'success', data: {nome: 'Teste'}});
            if (nome === 'get_pendencias_revisao_count') return () => Promise.resolve({status: 'success', data: {count: 0}});
            return () => Promise.resolve({status: 'success', data: []});
        }})};
    """.replace('DADOS_RESULTADO', dados)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=str(chrome), headless=True)
            try:
                page = browser.new_page()
                page.route('**/*', lambda rota: rota.continue_() if rota.request.url.startswith(url + '/') else rota.abort())
                page.add_init_script(init_script)
                page.goto(url + '/#/inadimplencia', wait_until='domcontentloaded')
                page.wait_for_function('window.__renderMs !== undefined', timeout=15000)
                return page.evaluate("""() => ({
                    segundos: Math.round(window.__renderMs) / 1000,
                    tabelas_renderizadas: window.__renderTabelas
                })""")
            finally:
                browser.close()
    finally:
        servidor.shutdown()
        servidor.server_close()
        worker.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path)
    parser.add_argument('--condominio', required=True)
    parser.add_argument('--data', required=True)
    parser.add_argument('--anterior', default='HEAD', help='Revisão Git anterior à correção')
    parser.add_argument('--limite-segundos', type=float, default=10)
    parser.add_argument('--limite-combinacoes', type=int, default=500_000)
    parser.add_argument('--render-dir', type=Path, help='Diretório browser do frontend compilado')
    parser.add_argument('--chrome', type=Path, help='Executável do Chrome para medir a renderização')
    args = parser.parse_args()
    if bool(args.render_dir) != bool(args.chrome):
        parser.error('--render-dir e --chrome devem ser informados juntos')

    # A origem anterior é obtida do Git; o banco não passa pelo inicializador do app.
    anterior = subprocess.check_output(
        ['git', 'show', f'{args.anterior}:scripts/run_dashboard.py'], cwd=ROOT, encoding='utf-8')
    atual = (ROOT / 'scripts/run_dashboard.py').read_text(encoding='utf-8-sig')
    modelos = carregar_modelos(args.db)
    try:
        saida = {'data_corte': args.data, 'revisao_anterior': args.anterior, 'cenarios': {}}
        for nome, recentes in [('taxas_recentes', True), ('historico_completo', False)]:
            antes, resultado_antes = medir(anterior, modelos, args.condominio, args.data, recentes,
                                           args.limite_segundos, args.limite_combinacoes)
            depois, resultado_depois = medir(atual, modelos, args.condominio, args.data, recentes,
                                              args.limite_segundos, args.limite_combinacoes)
            saida['cenarios'][nome] = {
                'anterior': antes, 'atual': depois,
                'resultados_iguais': (
                    resultado_antes == resultado_depois
                    if antes['status'] == depois['status'] == 'success' else None),
            }
            if not recentes:
                controle, resultado_controle = medir(
                    anterior, modelos, args.condominio, args.data, False,
                    args.limite_segundos, args.limite_combinacoes, podar_positivos=True)
                saida['cenarios'][nome]['controle_anterior_com_poda_positiva'] = controle
                saida['cenarios'][nome]['igual_ao_controle'] = (
                    resultado_controle == resultado_depois
                    if controle['status'] == depois['status'] == 'success' else None)
                if args.render_dir and resultado_depois and resultado_depois.get('status') == 'success':
                    saida['cenarios'][nome]['renderizacao_navegador'] = medir_renderizacao(
                        args.render_dir, args.chrome, resultado_depois)
        print(json.dumps(saida, ensure_ascii=False, indent=2))
    finally:
        modelos.db.close()


if __name__ == '__main__':
    main()
