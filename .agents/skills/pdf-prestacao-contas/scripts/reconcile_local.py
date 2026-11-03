"""Local candidate audits. Never rewrites reviewed ledgers, SQL or a database."""
import argparse
from collections import Counter,defaultdict
from decimal import Decimal
import json
from pathlib import Path
import re

IDENTITY=('tipo','categoria','classe','data','apartamento','competencia','fornecedor','conta')


def row_cents(row):
    for field in ('valor_centavos','cents'):
        if field in row and row[field] is not None:
            value=row[field]
            if type(value) is not int:
                raise ValueError('Integer cents required: '+field)
            return value
    if row.get('valor') is not None:
        value=Decimal(str(row['valor']))*100
        if value!=value.to_integral_value():
            raise ValueError('Fractional cent in source.')
        return int(value)
    raise ValueError('Missing amount.')


def identity(row):
    missing=[key for key in IDENTITY if key not in row]
    if missing:
        return None,missing
    # NULL and missing are different. Never fill a missing identity from the gold
    # ledger, infer competência from payment or alias accounts without evidence.
    values=tuple(' '.join(row[key].split()) if key=='descricao' and isinstance(row[key],str) else row[key] for key in IDENTITY)
    invoice=tuple(re.findall(r'\bNF\s*:?\s*(\d+)',row.get('descricao',''),re.I))
    return values+(row_cents(row),invoice),[]


def compare(candidates,reviewed):
    gold=Counter();candidate=Counter();missing=[];gold_history=Counter();candidate_history=Counter()
    for i,row in enumerate(reviewed):
        key,fields=identity(row)
        if key is None:
            raise ValueError('Reviewed reference lacks identity fields: '+str(fields))
        gold[key]+=1
        gold_history[key+(' '.join(row.get('descricao','').split()),)]+=1
    for i,row in enumerate(candidates):
        try:
            key,fields=identity(row)
        except ValueError as error:
            missing.append({'index':i,'reason':str(error)});continue
        if key is None:
            missing.append({'index':i,'fields':fields});continue
        candidate[key]+=1
        candidate_history[key+(' '.join(row.get('descricao','').split()),)]+=1
    exact=sum((gold&candidate).values())
    history_exact=sum((gold_history&candidate_history).values())
    # Preserve duplicate counts: sets hide a duplicated payment plus an omission.
    absent=gold-candidate;extra=candidate-gold
    def samples(counter):
        return [{'identity':list(key),'count':count} for key,count in counter.items()][:20]
    def totals(rows):
        result=defaultdict(int)
        for row in rows:
            try:result[row.get('tipo',row.get('kind','unknown'))]+=row_cents(row)
            except ValueError:pass
        return dict(result)
    return {'reviewed_count':len(reviewed),'candidate_count':len(candidates),'exact_identity_matches':exact,
            'exact_history_matches':history_exact,'history_or_identity_differences':len(reviewed)-history_exact,
            'missing_reference_rows':sum(absent.values()),'extra_candidate_rows':sum(extra.values()),
            'unresolved_candidate_rows':len(missing),'unresolved_examples':missing[:20],
            'missing_examples':samples(absent),'extra_examples':samples(extra),
            'candidate_totals_cents':totals(candidates),'reference_totals_cents':totals(reviewed),
            'status':'MATCH' if not absent and not extra and not missing and history_exact==len(reviewed) else 'EXCEPTIONS_REQUIRED'}


def bank_paths(opening,closing,rows,max_states=128):
    """Select only observed OCR triples that uniquely satisfy an entire chain.

    Each physical row has alternatives [{credit,debit,balance,evidence}]. Never
    synthesize an absent amount from a balance difference. Ambiguity is preserved,
    even when different paths merge at the same balance.
    """
    if type(opening) is not int or type(closing) is not int:
        return {'status':'MISSING_ENDPOINTS'}
    states={opening:[[]]}
    for index,row in enumerate(rows):
        alternatives=row.get('alternatives',[row]);observed={}
        for alt in alternatives:
            triple=tuple(alt.get(k) for k in ('credit','debit','balance'))
            if all(type(v) is int for v in triple) and min(triple[:2])>=0:
                observed.setdefault(triple,alt)
        next_states=defaultdict(list)
        for prior,paths in states.items():
            for triple,alt in observed.items():
                credit,debit,balance=triple
                if prior+credit-debit==balance:
                    for path in paths:
                        if len(next_states[balance])<2:
                            next_states[balance].append(path+[alt])
        if not next_states:
            return {'status':'NO_OBSERVED_PATH','row':index}
        if len(next_states)>max_states:
            return {'status':'SEARCH_LIMIT','row':index}
        states=next_states
    paths=states.get(closing,[])
    if len(paths)!=1:
        return {'status':'AMBIGUOUS' if paths else 'CLOSING_MISMATCH','paths_at_least':len(paths)}
    return {'status':'UNIQUE_OBSERVED_PATH','rows':paths[0],
            'note':'Numeric consistency only; identity and source review remain required.'}


def statements_report(statements):
    results=[]
    seen=set()
    for index,statement in enumerate(statements):
        alias=statement.get('alias')
        # Alias/physical key is required: two physical accounts may map to one DB name.
        if not alias:
            results.append({'index':index,'status':'MISSING_PHYSICAL_ACCOUNT'});continue
        key=(alias,statement.get('period',index))
        if key in seen:
            results.append({'index':index,'alias':alias,'status':'DUPLICATE_PHYSICAL_STATEMENT'});continue
        seen.add(key)
        results.append({'index':index,'alias':alias,**bank_paths(statement.get('opening'),statement.get('closing'),statement['rows'])})
    return results


def corpus(root,output):
    results=[]
    for source in sorted(root.glob('????-??')):
        gold=source/'ledger.json'
        if not gold.exists():
            continue
        reviewed=json.loads(gold.read_text(encoding='utf8'))
        # Candidate artifacts are evaluated as they were; never edited/retrained
        # from gold values. Different stages remain separate in the report.
        files=[source/name for name in ('ledger_candidates.json','ledger_candidates_refined.json','ledger_merged.json') if (source/name).exists()]
        for candidate in files:
            rows=json.loads(candidate.read_text(encoding='utf8'))
            if not isinstance(rows,list):continue
            try:result=compare(rows,reviewed)
            except ValueError as error:result={'status':'REFERENCE_SCHEMA_UNSUPPORTED','error':str(error)}
            results.append({'month':source.name,'stage':candidate.name,**result})
    report={'mode':'historical_candidate_audit','results':results,
            'note':'Historical reviewed rows are a test oracle, never an extraction input.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    summary={'months':len({r['month'] for r in results}),'stages':len(results),
             'exact_identity_matches':sum(r.get('exact_identity_matches',0) for r in results),
             'unresolved_rows':sum(r.get('unresolved_candidate_rows',0) for r in results),'output':str(output)}
    print(json.dumps(summary,ensure_ascii=True))
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    group=ap.add_mutually_exclusive_group(required=True)
    group.add_argument('--corpus',type=Path);group.add_argument('--candidates',type=Path);group.add_argument('--statements',type=Path)
    ap.add_argument('--reference',type=Path);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args()
    if args.corpus:
        corpus(args.corpus,args.output)
    else:
        if args.statements:
            data=json.loads(args.statements.read_text(encoding='utf8'))
            result=statements_report(data['statements'])
        else:
            if not args.reference:ap.error('--reference is required with --candidates')
            result=compare(json.loads(args.candidates.read_text(encoding='utf8')),json.loads(args.reference.read_text(encoding='utf8')))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        print(json.dumps({'output':str(args.output),'status':'LOCAL_AUDIT_WRITTEN'}))
