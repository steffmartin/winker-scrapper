"""Discover accounting sections locally; OCR selected tables, never access a DB.

Full evidence stays on disk. stdout is a compact manifest, not extracted pages.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
from difflib import SequenceMatcher
import hashlib
import json
import os
from pathlib import Path
import re
import unicodedata
import pymupdf as fitz
from PIL import Image
import pytesseract
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from local_config import load_config

VERSION = 4
TABLE_VERSION = 3
MONEY = re.compile(r'(?<![\d/])\d+(?:\.\d{3})*[.,]\d{2}(?![\d/])')
DATE = re.compile(r'\b\d{2}/\d{2}/\d{4}\b')
SPECS = {
    'demonstrativo': ('DEMONSTRATIVO DE RECEITAS E DESPESAS', ['HISTORICO','VALORES','SALDO ANTERIOR','TOTAL DE RECEITAS','CONTAS CORRENTES','C/A','C/C','CREDITOS','DEBITOS']),
    'recebimentos': ('CONTAS RECEBIDAS', ['VENCIMENTO','PAGAMENTO','LIQUIDADO','COBRANCA']),
    'sintetico': ('SINTETICO DE DESPESAS', ['CLASSE','VALOR','DESCONTO','BAIXA']),
    'analitico': ('DESPESAS POR GRUPO E CLASSE', ['FORNECEDOR','CLASSE','PAGAMENTO','VALOR PAGO']),
    'extrato': ('FLUXO DE CAIXA', ['SALDO','CREDITO','DEBITO','PERIODO']),
    'acordos': ('ACORDOS', ['UNIDADE','PARCELAS','ACORDADO','CONTAS ORIGINAIS']),
    'inadimplencia': ('UNIDADES INADIMPLENTES', ['VENCIMENTO','UNIDADE','COBRANCA','PERIODO']),
}
MAIN = {'demonstrativo','recebimentos','sintetico','analitico','extrato'}

def norm(s):
    return unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().upper()

def compact(s):
    return re.sub('[^A-Z]','',norm(s))

def contains(text, phrase):
    target = compact(phrase)
    for line in text.splitlines():
        s = compact(line)
        if target in s:
            return True
        if len(target) < 14:
            continue
        for start in range(max(1,len(s)-len(target)+1)):
            if SequenceMatcher(None,target,s[start:start+len(target)]).ratio() >= .86:
                return True
    return False

def classify(text):
    n = norm(text)
    if 'SUMARIO' in n or 'INDICE' in n:
        return None
    if not DATE.search(text) and len(MONEY.findall(text)) < 3:
        # Garbled OCR can damage the word SUMÁRIO while preserving its list of
        # report titles. A list of several titles without rows is not a table.
        if sum(contains(text,title) for title,_ in SPECS.values()) >= 3:
            return None
    for kind,(title,anchors) in SPECS.items():
        # A title without column anchors is a divider, never a table.
        if contains(text,title) and sum(a in n for a in anchors) >= 2:
            return kind
    return None

def fraction(text):
    m = re.search(r'P[áa]g[^\n]{0,12}?(\d{1,2})\s*/\s*(\d{1,2})',text,re.I)
    return list(map(int,m.groups())) if m else None

def global_page_denominators(fractions_by_section,total_pdf_pages):
    denominators=defaultdict(set)
    for section,fractions in fractions_by_section.items():
        for first,total in fractions:
            if total>=max(4,total_pdf_pages-3):denominators[total].add(section)
    return {total for total,sections in denominators.items() if len(sections)>=2}

def save(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')

def render(page,dpi):
    pix = page.get_pixmap(dpi=dpi,alpha=False)
    return Image.frombytes('RGB',[pix.width,pix.height],pix.samples)

def ocr(image,psm=6):
    return pytesseract.image_to_string(image,lang='por',config=f'--psm {psm}',timeout=90)

def discover(doc,out,fingerprint,scan_all=False):
    records = []
    for index,page in enumerate(doc):
        number = index+1
        cache = out/f'discovery_{number:03}.json'
        record = json.loads(cache.read_text(encoding='utf8')) if cache.exists() else None
        if not record or record.get('source_sha256') != fingerprint or record.get('version') != VERSION:
            native = page.get_text(sort=True)
            section = classify(native)
            record = dict(page=number,section=section,rotation=0,method='native',fraction=fraction(native),source_sha256=fingerprint,version=VERSION)
            header = native
            if section is None:
                im = render(page,110)
                for angle in (0,270,90,180):
                    upright = im.rotate(angle,expand=True)
                    strip = upright.crop((0,0,upright.width,int(upright.height*.28)))
                    text = ocr(strip)
                    found = classify(text)
                    if found:
                        header = text
                        record.update(section=found,rotation=angle,method='header_ocr',fraction=fraction(text))
                        break
            if record['section']=='extrato' and not record['fraction']:
                im=render(page,150)
                upright=im.rotate(record['rotation'],expand=True)
                top=ocr(upright.crop((0,0,upright.width,int(upright.height*.28))))
                footer=ocr(upright.crop((0,int(upright.height*.70),upright.width,upright.height)))
                if not fraction(top):
                    top += '\n'+ocr(upright.crop((0,0,upright.width,int(upright.height*.28))),3)
                record['fraction']=fraction(top)
                record['closing_balance_label']='SALDO FINAL' in norm(footer)
            (out/f'header_{number:03}.txt').write_text(header,encoding='utf8')
            save(cache,record)
        if records and record['section'] is None:
            previous=records[-1]
            frac=previous.get('fraction')
            if previous['section'] in MAIN and frac and frac[0]<frac[1]:
                im=render(page,220).rotate(previous['rotation'],expand=True)
                strip=im.crop((0,0,im.width,int(im.height*.35)))
                for psm in (3,6):
                    header=ocr(strip,psm)
                    found=fraction(header)
                    if found==[frac[0]+1,frac[1]] and contains(header,SPECS[previous['section']][0]):
                        record.update(section=previous['section'],rotation=previous['rotation'],method='header_ocr',fraction=found)
                        (out/f'header_{number:03}.txt').write_text(header,encoding='utf8')
                        save(cache,record)
                        break
        if record['section']=='extrato' and not record['fraction']:
            # Dense full-width headers can destroy the page label in OCR.
            # Read the printed pagination cell directly instead of assuming 2/2.
            im=render(page,220).rotate(record['rotation'],expand=True)
            cell=im.crop((int(im.width*.68),0,im.width,int(im.height*.12)))
            label=ocr(cell)
            (out/f'pagination_{number:03}.txt').write_text(label,encoding='utf8')
            record['fraction']=fraction(label)
            save(cache,record)
        records.append(record)
        if record['section']=='extrato' and not scan_all and MAIN <= {r['section'] for r in records}:
            frac = record['fraction']
            if (frac and frac[0]==frac[1]) or record.get('closing_balance_label') or 'SALDO FINAL' in norm(page.get_text()):
                break
    return records

def group_pages(records,out):
    groups=[]
    for r in records:
        if not r['section']:
            continue
        if groups and groups[-1]['section']==r['section'] and groups[-1]['pages'][-1]+1==r['page']:
            groups[-1]['pages'].append(r['page'])
        else:
            groups.append(dict(section=r['section'],pages=[r['page']]))
    receipts=[g for g in groups if g['section']=='recebimentos']
    eligible=[g for g in receipts if re.search(r'UNIDADE\s*:\s*TODAS',norm((out/f"header_{g['pages'][0]:03}.txt").read_text(encoding='utf8')))]
    primary=max(eligible or receipts,key=lambda g:len(g['pages'])) if receipts else None
    selected=[]; auxiliary=[]
    for g in groups:
        target=selected if g['section'] in MAIN and (g['section']!='recebimentos' or g is primary) else auxiliary
        target.append(g)
    return selected,auxiliary

def extract(page,r,out):
    path=out/f"page_{r['page']:03}.txt"
    meta=out/f"page_{r['page']:03}.json"
    if path.exists() and meta.exists():
        cached=json.loads(meta.read_text(encoding='utf8'))
        if cached.get('source_sha256')==r['source_sha256'] and cached.get('version')==VERSION and cached.get('table_version')==TABLE_VERSION:
            return path.read_text(encoding='utf8')
    im=render(page,220)
    angles=[r['rotation']] if r['method']=='header_ocr' else [0,270,90,180]
    text=''; angle=0; best=None
    psm=6
    for angle in angles:
        upright=im.rotate(angle,expand=True)
        options=[(ocr(upright,p),p) for p in (6,3,4)]
        def quality(option):
            value,_=option
            lines=value.splitlines()
            if r['section']=='sintetico':
                aligned=sum(len(MONEY.findall(l))>=5 for l in lines)
            elif r['section']=='recebimentos':
                aligned=sum(len(DATE.findall(l))>=2 and len(MONEY.findall(l))>=2 for l in lines)
            else:
                aligned=sum(bool(DATE.search(l)) and len(MONEY.findall(l))>=2 for l in lines)
            return (aligned,classify(value)==r['section'],len(MONEY.findall(value)))
        text,psm=max(options,key=quality)
        candidate=(quality((text,psm)),angle,psm,text)
        if best is None or candidate[0]>best[0]:best=candidate
        if classify(text)==r['section']:
            break
    else:
        # Continuation/closing pages may have no complete title/column signature.
        # Keep the best readable orientation, not the last attempted rotation.
        _,angle,psm,text=best
    path.write_text(text,encoding='utf8')
    save(meta,dict(**r,table_version=TABLE_VERSION,ocr_rotation=angle,dpi=220,psm=psm,ocr_section=classify(text),ocr_fraction=fraction(text)))
    return text

def money(s):
    if ',' in s:
        s=s.replace('.','').replace(',','.')
    elif s.count('.')>1:
        before,after=s.rsplit('.',1)
        s=before.replace('.','')+'.'+after
    return int(Decimal(s)*100)

def candidates(selected,texts):
    rows=[]; controls=[]; unit=None; category=None; subcategory=None
    for g in selected:
        kind=g['section']
        if kind!='recebimentos':
            unit=None
        for page in g['pages']:
            lines=texts[page].splitlines()
            for i,raw in enumerate(lines):
                line=raw.strip(); n=norm(line); dates=DATE.findall(line); amounts=MONEY.findall(line)
                evidence=dict(page=page,line=i+1,raw=line,section=kind)
                if kind=='demonstrativo':
                    for label,phrase in [('receita_bruta','TOTAL DE RECEITAS'),('despesa_bruta','TOTAL DE DESPESAS'),('saldo_final','SALDO A SER TRANSFERIDO')]:
                        if contains(line,phrase) and amounts:
                            controls.append(dict(**evidence,label=label,cents=money(amounts[-1])))
                heading=re.match(r'\W*(RECEITAS|DESPESAS)\s*[|IL:]\s*(.+)',n)
                if heading:
                    category=re.split(r'\d',heading[2])[0].strip(' |:')
                if kind=='sintetico' and amounts and not dates and not n.startswith('TOTAL'):
                    name=line[:MONEY.search(line).start()].strip(' |')
                    if name:
                        controls.append(dict(**evidence,label='classe_despesa',category=category,name=name,
                                             cents=money(amounts[-1]) if len(amounts)==5 else None,needs_review=True))
                if kind=='recebimentos':
                    u=re.fullmatch(r'\W*([2-9][0oO][1-5])\W*',line)
                    if u:
                        unit=u[1].lower().replace('o','0')
                    if len(dates)>=2 and re.match(r'(FUNDO|TAXA|RENDIMENTO|OUTRAS)',n):
                        tail=line[list(DATE.finditer(line))[1].end():]
                        values=MONEY.findall(re.split(r'C\s*[/I]\s*[CA]|CIC',tail)[0])
                        rows.append(dict(**evidence,kind='R_candidate',unit=unit,due=dates[0],paid=dates[1],
                                         cents=money(values[-1]) if values else None,needs_review=True))
                if kind=='analitico':
                    if not dates and not amounts and re.match(r'(FIXA|PREST|MATERIAL|MANUTEN|TARIFA|AQUISI)',n):
                        subcategory=line
                    if dates and not n.startswith(('CONTAS BAIXADAS','TOTAL')):
                        values=MONEY.findall(line[line.find(dates[0])+len(dates[0]):])
                        if len(values)>=2:
                            rows.append(dict(**evidence,kind='D_candidate',category=category,subcategory=subcategory,paid=dates[0],
                                             cents=money(values[1]),context=lines[max(0,i-1):i+3],needs_review=True))
                if kind=='extrato' and len(dates)==1:
                    values=MONEY.findall(line[line.find(dates[0])+len(dates[0]):])
                    if len(values)>=3:
                        rows.append(dict(**evidence,kind='statement_control',date=dates[0],credit=money(values[0]),debit=money(values[1]),balance=money(values[2])))
    return rows,controls

def run(pdf,out,scan_all=False,discover_only=False):
    out.mkdir(parents=True,exist_ok=True)
    fingerprint=hashlib.sha256(pdf.read_bytes()).hexdigest()
    with fitz.open(pdf) as doc:
        records=discover(doc,out,fingerprint,scan_all)
        selected,auxiliary=group_pages(records,out)
        texts={}
        if not discover_only:
            for g in selected:
                for number in g['pages']:
                    texts[number]=extract(doc[number-1],records[number-1],out)
        rows,controls=candidates(selected,texts) if texts else ([],[])
        values=defaultdict(set)
        for c in controls:
            if c['label'] in ('receita_bruta','despesa_bruta'):
                values[c['label']].add(c['cents'])
        issues=[]
        pagination=[]
        page_fractions={}
        fractions_by_section=defaultdict(list)
        for g in selected:
            for number in g['pages']:
                content=texts.get(number,'') or (out/f'header_{number:03}.txt').read_text(encoding='utf8')
                page_fractions[number]=[item for line in content.splitlines() if (item:=fraction(line))]
                fractions_by_section[g['section']].extend(page_fractions[number])
        global_denominators=global_page_denominators(fractions_by_section,len(doc))
        for g in selected:
            fractions=[item for number in g['pages'] for item in page_fractions[number]]
            totals={f[1] for f in fractions}
            if len(totals)==1 and not totals <= global_denominators:
                total=next(iter(totals))
                missing=sorted(set(range(1,total+1))-{f[0] for f in fractions})
                if missing:
                    issues.append(dict(reason='printed_pagination_gap',section=g['section'],physical_pages=g['pages'],missing_printed_pages=missing,total=total))
            pagination.append(dict(section=g['section'],physical_pages=g['pages'],printed_fractions=fractions,
                                   scope='global_document' if totals and totals <= global_denominators else 'section_or_unconfirmed'))
        for label in ('receita_bruta','despesa_bruta'):
            if texts and len(values[label])!=1:
                issues.append(dict(reason='missing_or_conflicting_total',label=label,values=sorted(values[label])))
        sums={}
        if texts:
            for kind,label in [('R_candidate','receita_bruta'),('D_candidate','despesa_bruta')]:
                subset=[r for r in rows if r['kind']==kind]
                sums[kind]=sum(r['cents'] or 0 for r in subset)
                if len(values[label])==1 and sums[kind]!=next(iter(values[label])):
                    issues.append(dict(reason='candidate_sum_differs_from_gross_control',kind=kind,candidate_cents=sums[kind],control_cents=next(iter(values[label]))))
                if any(r['cents'] is None for r in subset):
                    issues.append(dict(reason='unreadable_candidate_amount',kind=kind))
            incomplete=[c for c in controls if c['label']=='classe_despesa' and c['cents'] is None]
            if incomplete:
                issues.append(dict(reason='incomplete_class_control_columns',count=len(incomplete)))
            statement=[r for r in rows if r['kind']=='statement_control']
            breaks=[]
            for previous,current in zip(statement,statement[1:]):
                if previous['balance']+current['credit']-current['debit']!=current['balance']:
                    breaks.append(dict(page=current['page'],line=current['line']))
            if breaks:
                issues.append(dict(reason='statement_running_balance_break',count=len(breaks),first_locations=breaks[:3]))
        result=dict(version=VERSION,pdf=str(pdf.resolve()),source_sha256=fingerprint,total_pdf_pages=len(doc),pages_screened=len(records),
                    selected=selected,auxiliary=auxiliary,missing_sections=sorted(MAIN-{g['section'] for g in selected}),
                    totals_cents={k:sorted(v) for k,v in values.items()},issues=issues,
                    pagination=pagination,candidate_sums_cents=sums,
                    candidate_counts={k:sum(r['kind']==k for r in rows) for k in ['R_candidate','D_candidate','statement_control']},
                    status='DISCOVERY_ONLY' if discover_only else 'RECONCILIATION_REQUIRED')
    save(out/'manifest.json',result)
    if not discover_only:
        save(out/'candidates.json',rows)
        save(out/'controls_extracted.json',controls)
    print(json.dumps(result,ensure_ascii=True))
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('pdf',type=Path); ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--scan-all',action='store_true'); ap.add_argument('--discover-only',action='store_true')
    ap.add_argument('--config',type=Path)
    ap.add_argument('--tesseract')
    ap.add_argument('--tessdata')
    args=ap.parse_args()
    settings=load_config(args.config).get('ocr',{})
    executable=args.tesseract or settings.get('tesseract')
    tessdata=args.tessdata or settings.get('tessdata')
    if executable:pytesseract.pytesseract.tesseract_cmd=executable
    if tessdata:os.environ['TESSDATA_PREFIX']=tessdata
    run(args.pdf,args.output,args.scan_all,args.discover_only)
