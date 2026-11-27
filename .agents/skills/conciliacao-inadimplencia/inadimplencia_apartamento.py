"""Lista as taxas inadimplentes de um apartamento pela mesma regra do app.

Replica `Api.get_inadimplencia` (bff/api.py) em modo somente
leitura: taxas C/E do condomínio + I/P do apartamento, descontos D/R agregados
por (apartamento, taxa_id), incluindo o cancelamento de D por R; pagamento único por valor exato ou combinação via
`scripts/conciliacao.encontrar_combinacao`.

Uso:
    python .agents/skills/conciliacao-inadimplencia/inadimplencia_apartamento.py --apto 204
    python .agents/skills/conciliacao-inadimplencia/inadimplencia_apartamento.py --todos --corte 2024-12-31
    python .agents/skills/conciliacao-inadimplencia/inadimplencia_apartamento.py --apto 204 --transacoes

Opções:
    --db PATH        banco SQLite (padrão: compartilhado/database/winker_data.db)
    --condominio ID  ID do condomínio (padrão: único cadastrado)
    --apto APT       apartamento(s), repetível; use --todos para todos
    --corte AAAA-MM-DD  data de corte (padrão: hoje)
    --transacoes     também lista todos os recebimentos do apartamento por competência
    --json           saída em JSON

O banco é sempre aberto com `mode=ro` + `PRAGMA query_only=ON`: o script nunca
escreve. Para correções, use os scripts de escrita do projeto ou o dashboard.
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from conciliacao import LimiteConciliacao, encontrar_combinacao  # noqa: E402

DB_PADRAO = ROOT / 'compartilhado' / 'database' / 'winker_data.db'


def conectar(db_path):
    uri = Path(db_path).resolve().as_uri() + '?mode=ro'
    con = sqlite3.connect(uri, uri=True)
    con.execute('PRAGMA query_only = ON')
    con.row_factory = sqlite3.Row
    return con


def parse_data(valor):
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(valor, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def carregar(con, condominio_id):
    taxas = [dict(r) for r in con.execute(
        '''SELECT t.*, r.data_renegociacao FROM taxas t
           LEFT JOIN renegociacao r ON t.renegociacao_id = r.id
           WHERE t.condominio_id = ? AND t.tipo IN ('C','I','D','E','P','R')''',
        (condominio_id,))]
    condo = dict(con.execute(
        'SELECT * FROM condominio WHERE id = ?', (condominio_id,)).fetchone())
    apartamentos = json.loads(condo.get('apartamentos') or '[]')
    return taxas, condo, apartamentos


def preparar_taxas(taxas, corte, apto):
    """Replica a filtragem/agregação de get_inadimplencia para um apto."""
    comuns, individuais, descontos = [], [], {}
    campos = ('valor_original', 'desconto_vista', 'multa_percentual', 'juros_mes_percentual')
    descontos_ids = {t['id'] for t in taxas if t['tipo'] == 'D'}
    cancelados = {}
    for t in taxas:
        if t['tipo'] != 'R' or t.get('taxa_id') not in descontos_ids:
            continue
        data_ren = parse_data(t.get('data_renegociacao'))
        if data_ren and corte < data_ren:
            continue
        valores = cancelados.setdefault((t.get('apartamento'), t['taxa_id']),
                                        {campo: 0 for campo in campos})
        for campo in campos:
            valores[campo] += t.get(campo) or 0
    for t in taxas:
        t = dict(t)
        if t['tipo'] in ('P', 'R') and t.get('data_renegociacao'):
            dt_ren = parse_data(t['data_renegociacao'])
            if dt_ren and corte < dt_ren:
                continue
        if t['tipo'] in ('D', 'R'):
            if t['tipo'] == 'R' and t.get('taxa_id') in descontos_ids:
                continue
            chave = (t.get('apartamento'), t.get('taxa_id'))
            agg = descontos.setdefault(chave, {
                'valor_original': 0.0, 'desconto_vista': 0.0,
                'multa_percentual': 0.0, 'juros_mes_percentual': 0.0})
            cancelamento = cancelados.get((t.get('apartamento'), t['id']), {}) if t['tipo'] == 'D' else {}
            for campo in campos:
                agg[campo] += max(0, (t.get(campo) or 0) - cancelamento.get(campo, 0))
            continue
        try:
            venc = datetime.strptime(t['vencimento'], '%d/%m/%Y').date()
        except (ValueError, TypeError, KeyError):
            venc = None
        if not venc or venc >= corte:
            continue
        t['_venc_dt'] = venc
        if t['tipo'] in ('C', 'E'):
            comuns.append(t)
        elif t['tipo'] in ('I', 'P') and t.get('apartamento') == apto:
            individuais.append(t)

    taxas_apto = [dict(t) for t in comuns] + [dict(t) for t in individuais]
    for t in taxas_apto:
        agg = descontos.get((apto, t['id']))
        if not agg:
            continue
        t['valor_original'] = max(0, t['valor_original'] - agg['valor_original'])
        t['desconto_vista'] = max(0, (t['desconto_vista'] or 0) - agg['desconto_vista'])
        t['multa_percentual'] = max(0, (t['multa_percentual'] or 0) - agg['multa_percentual'])
        t['juros_mes_percentual'] = max(0, (t['juros_mes_percentual'] or 0) - agg['juros_mes_percentual'])
    return taxas_apto


def carregar_transacoes(con, condominio_id, apto, corte):
    trs = [dict(r) for r in con.execute(
        '''SELECT t.id, t.data, t.descricao, t.valor, t.competencia,
                  s.nome AS subcategoria
           FROM transacoes t
           JOIN subcategorias s ON t.subcategoria_id = s.id
           JOIN categorias c ON s.categoria_id = c.id
           JOIN meses m ON c.mes_id = m.id
           WHERE m.condominio_id = ? AND t.tipo = 'R'
             AND t.apartamento = ? AND t.competencia IS NOT NULL''',
        (condominio_id, apto))]
    por_comp = {}
    for t in trs:
        t['_data'] = parse_data(t['data'])
        if t['_data'] and t['_data'] <= corte:
            por_comp.setdefault(t['competencia'], []).append(t)
    return trs, por_comp


def calcular_juros_multa(taxa, dias, tipo_jm):
    total = taxa['valor_original']
    juros_perc = taxa['juros_mes_percentual'] or 0.0
    multa_perc = (taxa['multa_percentual'] or 0.0) if dias > 0 else 0.0
    if tipo_jm == 'M':
        juros = total * (juros_perc / 30.0 / 100.0) * dias
        multa = (total + juros) * (multa_perc / 100.0)
    elif tipo_jm == 'J':
        multa = total * (multa_perc / 100.0)
        juros = (total + multa) * (juros_perc / 30.0 / 100.0) * dias
    else:
        juros = total * (juros_perc / 30.0 / 100.0) * dias
        multa = total * (multa_perc / 100.0)
    return multa, juros


def conciliar_apto(taxas_apto, por_comp, condo, corte):
    """Retorna (nao_pagas, pagamentos_usados). Replica o loop do app."""
    transacoes_map = {comp: list(itens) for comp, itens in por_comp.items()}
    nao_pagas, pagos = [], 0
    for taxa in taxas_apto:
        if taxa['valor_original'] == 0:
            pagos += 1
            continue
        comp = taxa['competencia']
        trs = transacoes_map.get(comp, [])
        ok = False
        if trs:
            for i, tr in enumerate(trs):
                esperado = (taxa['valor_original'] - (taxa['desconto_vista'] or 0)
                            if tr['_data'] <= taxa['_venc_dt'] else taxa['valor_original'])
                if abs(tr['valor'] - esperado) < 0.01:
                    trs.pop(i)
                    ok = True
                    break
            if not ok:
                try:
                    idx = encontrar_combinacao(
                        [(t['valor'], t['_data']) for t in trs],
                        taxa['_venc_dt'], taxa['valor_original'], taxa['desconto_vista'])
                    if idx is not None:
                        ok = True
                        for i in reversed(idx):
                            trs.pop(i)
                except LimiteConciliacao as exc:
                    raise LimiteConciliacao(
                        f'Conciliação pendente para a unidade {taxa.get("_apto", "?")}, '
                        f'competência {comp}: {exc}'
                    ) from exc
        if ok:
            pagos += 1
            continue
        dias = max(0, (corte - taxa['_venc_dt']).days)
        multa, juros = calcular_juros_multa(taxa, dias, condo.get('tipo_juros_multa') or 'N')
        nao_pagas.append({
            'taxa_id': taxa.get('id'), 'tipo': taxa['tipo'],
            'apartamento_taxa': taxa.get('apartamento'),
            'competencia': comp, 'exibicao': taxa['exibicao'],
            'descricao': taxa['descricao'], 'valor': round(taxa['valor_original'], 2),
            'desconto_vista': taxa.get('desconto_vista') or 0,
            'vencimento': taxa['vencimento'], 'dias_vencidos': dias,
            'multa': round(multa, 2), 'juros': round(juros, 2),
            'pagamentos_restantes': [
                {'id': t['id'], 'data': t['data'], 'valor': t['valor'],
                 'descricao': t.get('descricao'), 'subcategoria': t.get('subcategoria')}
                for t in trs],
        })
    return nao_pagas, pagos


def imprimir_transacoes(trs):
    por_comp = {}
    for t in trs:
        por_comp.setdefault(t['competencia'] or '(sem)', []).append(t)
    for comp in sorted(por_comp):
        print(f'  {comp}:')
        for t in sorted(por_comp[comp], key=lambda x: x['data']):
            desc = (t.get('descricao') or '')[:80]
            print(f"    {t['data']}  {t['valor']:>10.2f}  [{t.get('subcategoria')}] {desc}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--db', type=Path, default=DB_PADRAO)
    ap.add_argument('--condominio')
    ap.add_argument('--apto', action='append', default=[])
    ap.add_argument('--todos', action='store_true')
    ap.add_argument('--corte')
    ap.add_argument('--transacoes', action='store_true')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()

    corte = (datetime.strptime(args.corte, '%Y-%m-%d').date()
             if args.corte else datetime.now().date())
    con = conectar(args.db)
    try:
        if args.condominio:
            condo_id = args.condominio
        else:
            ids = [r[0] for r in con.execute('SELECT id FROM condominio')]
            if len(ids) != 1:
                ap.error(f'--condominio é obrigatório: {len(ids)} condomínios no banco')
            condo_id = ids[0]
        taxas, condo, apartamentos = carregar(con, condo_id)
        apts = sorted(set(apartamentos)) if args.todos else sorted(set(args.apto))
        if not apts:
            ap.error('informe --apto ou --todos')

        resultado = {}
        for apto in apts:
            taxas_apto = preparar_taxas(taxas, corte, apto)
            for taxa in taxas_apto:
                taxa['_apto'] = apto
            trs, por_comp = carregar_transacoes(con, condo_id, apto, corte)
            nao_pagas, pagos = conciliar_apto(taxas_apto, por_comp, condo, corte)
            resultado[apto] = {
                'taxas_pagas': pagos,
                'inadimplentes': nao_pagas,
                'transacoes': trs if args.transacoes else None,
            }

        if args.json:
            print(json.dumps({'condominio': condo_id, 'corte': str(corte),
                              'tipo_juros_multa': condo.get('tipo_juros_multa'),
                              'resultado': resultado},
                             ensure_ascii=False, indent=2, default=str))
            return

        print(f"Condomínio {condo_id} | corte {corte} | "
              f"juros/multa: {condo.get('tipo_juros_multa')}")
        for apto, res in resultado.items():
            print(f"\n=== Apto {apto}: {len(res['inadimplentes'])} taxa(s) pendente(s), "
                  f"{res['taxas_pagas']} quitada(s) ===")
            for t in res['inadimplentes']:
                print(f"  {t['exibicao'] or t['competencia']} | {t['descricao']} | "
                      f"valor {t['valor']:.2f} | venc {t['vencimento']} | "
                      f"{t['dias_vencidos']}d | multa {t['multa']:.2f} juros {t['juros']:.2f}")
                for tr in t['pagamentos_restantes']:
                    print(f"      restante: {tr['data']} {tr['valor']:.2f} "
                          f"[{tr.get('subcategoria')}] {(tr.get('descricao') or '')[:70]}")
            if args.transacoes:
                print('  Recebimentos por competência:')
                imprimir_transacoes(res['transacoes'])
    finally:
        con.close()


if __name__ == '__main__':
    main()
