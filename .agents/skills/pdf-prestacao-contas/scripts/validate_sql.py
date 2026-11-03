"""Validate generated SQL twice only in a read-only production snapshot in memory."""
import argparse
from collections import Counter,defaultdict
from decimal import Decimal
import hashlib,json,re,sqlite3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_config import load_config, condominium_id

TABLES=['meses','categorias','subcategorias','transacoes']

def cents(value):
    number=Decimal(str(value))*100
    assert number==number.to_integral_value(),value
    return int(number)

def dump_hash(rows):
    return hashlib.sha256(json.dumps(rows,ensure_ascii=False,sort_keys=True,default=str).encode('utf8')).hexdigest()

def target_ids(db,month,condominio_id=None):
    cid=condominium_id({} if condominio_id is not None else load_config(),condominio_id)
    result={t:set() for t in TABLES+['prestacoes_contas']}
    result['meses']={r[0] for r in db.execute('SELECT id FROM meses WHERE condominio_id = ? AND competencia = ?',(cid,month))}
    for table,parent,fk in [('categorias','meses','mes_id'),('subcategorias','categorias','categoria_id'),('transacoes','subcategorias','subcategoria_id'),('prestacoes_contas','meses','mes_id')]:
        if result[parent]:
            result[table]={r[0] for r in db.execute(f'SELECT id FROM {table} WHERE {fk} IN ({",".join("?" for _ in result[parent])})',tuple(result[parent]))}
    return result

def unrelated(db,month,condominio_id=None):
    excluded=target_ids(db,month,condominio_id);result={}
    names=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    for table in names:
        columns=[r[1] for r in db.execute(f'PRAGMA table_info("{table}")')]
        rows=db.execute(f'SELECT * FROM "{table}"').fetchall()
        if table in excluded and 'id' in columns:
            index=columns.index('id');rows=[r for r in rows if r[index] not in excluded[table]]
        result[table]=dump_hash(sorted(rows,key=repr))
    return result

def reason_flags(db,ids,allowed):
    counts={}
    for table in TABLES:
        consistent=inconsistent=0
        for tid in ids[table]:
            ok,raw,reviewed=db.execute(f'SELECT consistente,motivo_inconsistencia,revisado_usuario FROM {table} WHERE id=?',(tid,)).fetchone()
            reasons=json.loads(raw or '[]')
            assert isinstance(reasons,list) and len(reasons)==len(set(reasons))
            assert set(reasons)<=allowed[table],(table,reasons,allowed[table])
            assert ok in (0,1) and reviewed==ok,(table,tid,ok,reviewed)
            if ok:
                assert raw is None and not reasons
                consistent+=1
            else:
                assert reasons
                inconsistent+=1
            if table in ['categorias','subcategorias']:assert(ok,raw,reviewed)==(1,None,1)
        counts[table]={'consistent':consistent,'inconsistent':inconsistent}
    return counts

def validate_bank_chains(bank):
    """Validate physical account chains separately, including legacy single chains."""
    statements = bank.get('statements', [bank])
    assert statements, 'No bank statements supplied.'
    count = 0
    for statement in statements:
        balance = statement['opening']
        for row in statement['rows']:
            assert all(isinstance(row[key], int) for key in ('credit', 'debit', 'balance'))
            assert row['credit'] >= 0 and row['debit'] >= 0
            assert balance + row['credit'] - row['debit'] == row['balance'], (statement.get('alias'), row)
            balance = row['balance']
            count += 1
        assert balance == statement['closing'], statement.get('alias')
    return count


def validate(database,source,sql_path,output,config=None,condominio_id=None):
    settings=load_config(config)
    cid=condominium_id(settings,condominio_id)
    ledger=json.loads((source/'ledger.json').read_text(encoding='utf8'))
    controls=json.loads((source/'controls.json').read_text(encoding='utf8'))
    review=json.loads((source/'review.json').read_text(encoding='utf8'));month=review['month']
    assert review['approved_for_generation'] is True
    active=[r for r in ledger if not r.get('excluded')]
    control_map={(c['tipo'],c['categoria'],c['classe']):c['valor_centavos'] for c in controls if not c.get('excluded')}
    assert len(control_map)==sum(not c.get('excluded') for c in controls)
    gross={t:sum(c['valor_centavos'] for c in controls if c['tipo']==t) for t in ['R','D']}
    expected_totals={t:sum(v for key,v in control_map.items() if key[0]==t) for t in ['R','D']}
    assert gross==review['gross_cents']
    for typ in ['R','D']:assert gross[typ]-review['excluded_cents'][typ]==expected_totals[typ]
    sql=sql_path.read_text(encoding='utf8')
    assert 'INSERT INTO prestacoes_contas' not in sql
    before=hashlib.sha256(database.read_bytes()).hexdigest()
    ro=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)
    ro.execute('PRAGMA query_only = ON')
    allowed={t:{reason for raw, in ro.execute(f'SELECT DISTINCT motivo_inconsistencia FROM {t} WHERE motivo_inconsistencia IS NOT NULL') for reason in json.loads(raw or '[]')} for t in TABLES}
    accounts=dict(ro.execute('SELECT conta,saldo_inicial FROM contas WHERE condominio_id=?',(cid,)).fetchall())
    assert all(r['conta'] in accounts for r in active)
    balance_order=settings.get('accounts',{}).get('investment_initial_balance_order',[])
    assert all(name in accounts for name in balance_order)
    assert all(accounts[a]<accounts[b] for a,b in zip(balance_order,balance_order[1:]))
    db=sqlite3.connect(':memory:');ro.backup(db);ro.close()
    db.execute('PRAGMA foreign_keys = ON')
    untouched=unrelated(db,month,cid)
    previous=None;counts={};flags={}
    for run in [1,2]:
        db.executescript(sql)
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        assert unrelated(db,month,cid)==untouched,'Unrelated official snapshot data was modified.'
        ids=target_ids(db,month,cid);assert len(ids['meses'])==1 and not ids['prestacoes_contas']
        mid=next(iter(ids['meses']))
        actual_month=db.execute('SELECT receita_total,despesa_total,anexos,consistente,motivo_inconsistencia,revisado_usuario FROM meses WHERE id=?',(mid,)).fetchone()
        assert tuple(map(cents,actual_month[:2]))==(expected_totals['R'],expected_totals['D'])
        assert actual_month[2:]==(0,0,'["Mês sem prestação de contas"]',0)
        observed={};category_values={};rows=[];snapshot=[]
        for catid,typ,cat,value in db.execute('SELECT id,tipo,nome,valor FROM categorias WHERE mes_id=? ORDER BY tipo,nome',(mid,)):
            category_values[typ,cat]=cents(value);subtotal=0
            for sid,styp,cls,subvalue in db.execute('SELECT id,tipo,nome,valor FROM subcategorias WHERE categoria_id=? ORDER BY nome',(catid,)):
                assert styp==typ
                observed[typ,cat,cls]=cents(subvalue);subtotal+=cents(subvalue)
                txs=db.execute('SELECT tipo,data,descricao,valor,apartamento,competencia,fornecedor,conta,anexos,consistente,motivo_inconsistencia,revisado_usuario FROM transacoes WHERE subcategoria_id=?',(sid,)).fetchall()
                assert sum(cents(t[3]) for t in txs)==cents(subvalue),(typ,cat,cls)
                for tx in txs:
                    t,day,description,amount,unit,comp,supplier,account,attachments,ok,why,reviewed=tx
                    assert t==typ and re.fullmatch(r'\d{2}/'+month[-2:]+'/'+month[:4],day)
                    assert description and amount>0 and account in accounts and attachments==0
                    assert comp is None or re.fullmatch(r'20\d{2}-\d{2}',comp)
                    if typ=='D':assert supplier and 'Despesa sem comprovantes' in json.loads(why or '[]')
                    if comp is None:assert 'Competência não identificada' in json.loads(why or '[]')
                    rows.append((typ,cat,cls,day,description,cents(amount),unit,comp,supplier,account))
                snapshot.append((typ,cat,cls,cents(subvalue),sorted(txs,key=repr)))
            assert subtotal==cents(value),(typ,cat)
        assert observed==control_map
        for typ in ['R','D']:assert sum(v for k,v in category_values.items() if k[0]==typ)==expected_totals[typ]
        expected_rows=Counter((r['tipo'],r['categoria'],r['classe'],r['data'],r['descricao'],r['valor_centavos'],r['apartamento'],r['competencia'],r['fornecedor'],r['conta']) for r in active)
        assert Counter(rows)==expected_rows,'SQL changes a reviewed transaction field.'
        flags=reason_flags(db,ids,allowed)
        current=(actual_month,sorted(category_values.items()),snapshot,sorted(Counter(rows).items(),key=repr))
        if previous is not None:assert current==previous,'Not idempotent in logical contents/multiplicity.'
        previous=current;counts={t:len(ids[t]) for t in TABLES}
    db.close()
    bank=json.loads((source/'statement_reviewed.json').read_text(encoding='utf8'))
    bank_rows_checked=validate_bank_chains(bank)
    reconciliation=json.loads((source/'bank_reconciliation.json').read_text(encoding='utf8'))
    assert not reconciliation['unit_diffs'] and not any(reconciliation['expense_diffs'].values()) and not any(reconciliation['nonunit_diffs'].values())
    account_controls=json.loads((source/'account_controls_reviewed.json').read_text(encoding='utf8'))
    assert set(account_controls['accounts']) == set(accounts), 'Missing registered account controls.'
    for name,b in account_controls['accounts'].items():
        assert name in accounts
        assert b['opening']+b['credits']-b['debits']+sum(b['transfers'])==b['closing']
        assert sum(r['valor_centavos'] for r in ledger if r['tipo']=='R' and r['conta']==name)==b['credits']
        assert sum(r['valor_centavos'] for r in ledger if r['tipo']=='D' and r['conta']==name)==b['debits']
    assert sum(b['opening'] for b in account_controls['accounts'].values()) == account_controls['opening_consolidated']
    assert sum(b['closing'] for b in account_controls['accounts'].values()) == account_controls['closing_consolidated']
    assert sum(sum(b['transfers']) for b in account_controls['accounts'].values()) == 0
    assert account_controls['opening_consolidated']+gross['R']-gross['D']==account_controls['closing_consolidated']
    after=hashlib.sha256(database.read_bytes()).hexdigest();assert before==after
    report={'month':month,'status':'PASS','totals_cents':expected_totals,'gross_cents':gross,'excluded_internal_transfer_cents':review['excluded_cents'],
            'counts':counts,'isolated_executions':2,'foreign_keys':'OK','idempotence':'OK logical contents and counts',
            'transactions_to_subcategories':'OK integer cents','subcategories_to_categories':'OK integer cents','categories_to_month':'OK integer cents',
            'independent_pdf_class_controls':'OK','all_registered_accounts':'OK','reason_json_and_review_flags':flags,
            'bank_running_balances_checked':bank_rows_checked,'bank_payment_identity':'OK unit/date and paid expense multiplicity',
            'registered_account_rollforwards':'OK','competence_conflicts':review.get('conflicts',[]),'notes':review.get('notes',[]),
            'official_db_sha256_before':before,'official_db_sha256_after':after,'official_db_writes':0,
            'sql_sha256':hashlib.sha256(sql_path.read_bytes()).hexdigest()}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return report

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--database',required=True,type=Path);ap.add_argument('--source',required=True,type=Path)
    ap.add_argument('--sql',required=True,type=Path);ap.add_argument('--output',required=True,type=Path)
    ap.add_argument('--config',type=Path);ap.add_argument('--condominio-id')
    a=ap.parse_args();r=validate(a.database,a.source,a.sql,a.output,a.config,a.condominio_id)
    print(json.dumps({k:r[k] for k in ['month','status','totals_cents','counts','isolated_executions']},ensure_ascii=True))
