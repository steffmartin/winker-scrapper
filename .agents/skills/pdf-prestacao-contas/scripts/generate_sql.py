"""Generate a reviewed ledger as readable idempotent SQL; never execute SQL."""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_config import load_config, condominium_id

MONTHS=['JAN','FEV','MAR','ABR','MAI','JUN','JUL','AGO','SET','OUT','NOV','DEZ']

def quote(v):
    if v is None:return 'NULL'
    if isinstance(v,str):return "'"+v.replace("'","''")+"'"
    return str(v)

def money(cents):return format(Decimal(cents)/100,'.2f')

def generate(source,output,config=None,condominio_id=None):
    settings=load_config(config)
    condo=condominium_id(settings,condominio_id)
    name=settings.get('condominium',{}).get('name','Condomínio')
    ledger=json.loads((source/'ledger.json').read_text(encoding='utf8'))
    controls=json.loads((source/'controls.json').read_text(encoding='utf8'))
    meta=json.loads((source/'review.json').read_text(encoding='utf8'))
    assert meta['approved_for_generation'] is True
    month=meta['month']
    actual=defaultdict(int)
    rows=[r for r in ledger if not r.get('excluded')]
    expected={(c['tipo'],c['categoria'],c['classe']):c['valor_centavos'] for c in controls if not c.get('excluded')}
    for r in rows:
        assert r['valor_centavos']>0 and r['data'] and r['descricao'] and r['conta'],r
        actual[r['tipo'],r['categoria'],r['classe']]+=r['valor_centavos']
    assert dict(actual)==expected,{'actual':dict(actual),'expected':expected}
    total={t:sum(v for k,v in expected.items() if k[0]==t) for t in ['R','D']}
    lines=[]
    def section(title):lines.extend(['','-- '+'='*76,'-- '+title,'-- '+'='*76])
    def insert(table,fields,records,comments=None):
        if not records:return
        lines.append(f"INSERT INTO {table} ({', '.join(fields)})")
        lines.append('VALUES')
        formatted=[]
        for index,row in enumerate(records):
            prefix='    -- '+comments[index]+'\n' if comments else ''
            formatted.append(prefix+'    ('+', '.join(row)+')')
        lines.append(',\n'.join(formatted)+';')
        lines.append('')
    section(f'0. {month} — {name.replace(chr(10)," ").replace(chr(13)," ")} — fontes e conciliação')
    lines.extend([f'-- Receitas econômicas: R$ {money(total["R"])}; despesas econômicas: R$ {money(total["D"])}.',
                  '-- Valores conciliados em centavos com controles independentes do PDF.',
                  '-- Nenhum documento/comprovante importado; razões oficiais de ausência mantidas.'])
    for note in meta.get('notes',[]):lines.append('-- '+note.replace('\n',' '))
    lines.extend(['','PRAGMA foreign_keys = ON;','BEGIN TRANSACTION;'])
    section('1. Limpeza da competência (cascata por chaves estrangeiras)')
    lines.extend(['DELETE FROM meses',f'WHERE condominio_id = {quote(condo)} AND competencia = {quote(month)};'])
    mid=f'(SELECT id FROM meses WHERE condominio_id = {quote(condo)} AND competencia = {quote(month)})'
    section('2. Mês')
    insert('meses',['condominio_id','exibicao','competencia','receita_total','despesa_total','anexos','consistente','motivo_inconsistencia','revisado_usuario'],[[quote(condo),quote(MONTHS[int(month[-2:])-1]+'/'+month[:4]),quote(month),money(total['R']),money(total['D']),'0','0',quote('["Mês sem prestação de contas"]'),'0']])
    lookups={}
    for typ in ['R','D']:
        section('3. Estrutura de receitas' if typ=='R' else '4. Estrutura de despesas')
        cats=list(dict.fromkeys(k[1] for k in expected if k[0]==typ))
        for cat in cats:
            cv=sum(v for k,v in expected.items() if k[:2]==(typ,cat))
            lines.append(f'-- {typ} | {cat} | {money(cv)}')
            insert('categorias',['mes_id','tipo','nome','valor','consistente','motivo_inconsistencia','revisado_usuario'],[[mid,quote(typ),quote(cat),money(cv),'1','NULL','1']])
            cid=f'(SELECT id FROM categorias WHERE mes_id = {mid} AND tipo = {quote(typ)} AND nome = {quote(cat)})'
            subs=[]
            for (t,c,cls),v in expected.items():
                if (t,c)!=(typ,cat):continue
                subs.append([cid,quote(typ),quote(cls),money(v),'1','NULL','1'])
                lookups[t,c,cls]=f'(SELECT id FROM subcategorias WHERE categoria_id = {cid} AND nome = {quote(cls)})'
            insert('subcategorias',['categoria_id','tipo','nome','valor','consistente','motivo_inconsistencia','revisado_usuario'],subs)
    fields=['subcategoria_id','tipo','data','descricao','valor','apartamento','competencia','fornecedor','conta','anexos','consistente','motivo_inconsistencia','revisado_usuario']
    for typ in ['R','D']:
        section('5. Lançamentos de receitas' if typ=='R' else '6. Lançamentos de despesas')
        tuples=[];comments=[]
        for r in rows:
            if r['tipo']!=typ:continue
            reasons=list(r.get('motivos',[]))
            if typ=='D' and 'Despesa sem comprovantes' not in reasons:reasons.append('Despesa sem comprovantes')
            if r['competencia'] is None and 'Competência não identificada' not in reasons:reasons.append('Competência não identificada')
            ok=int(not reasons)
            comments.append(f'{typ} | {r["classe"]} | {r["data"]} | {money(r["valor_centavos"])} | PDF p.{r["pagina"]}')
            tuples.append([lookups[typ,r['categoria'],r['classe']],quote(typ),quote(r['data']),quote(r['descricao']),money(r['valor_centavos']),quote(r['apartamento']),quote(r['competencia']),quote(r['fornecedor']),quote(r['conta']),'0',str(ok),quote(json.dumps(reasons,ensure_ascii=False)) if reasons else 'NULL',str(ok)])
        insert('transacoes',fields,tuples,comments)
    section('7. Conclusão da transação')
    lines.extend(['COMMIT;',''])
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text('\n'.join(lines).lstrip(),encoding='utf8')
    return {'month':month,'totals_cents':total,'transactions':len(rows),'output':str(output)}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--config',type=Path)
    ap.add_argument('--condominio-id')
    args=ap.parse_args();print(json.dumps(generate(args.source,args.output,args.config,args.condominio_id),ensure_ascii=True))
