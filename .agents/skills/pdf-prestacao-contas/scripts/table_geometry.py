"""Layout-independent word/column recovery. No finance-specific IDs or DB access.

Coordinates are fractions of the upright page. Columns come from printed headers,
not fixed percentages. Unreadable/ambiguous cells stay unresolved.
"""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import re
import unicodedata

ALIASES = {
    'unit': ('UNIDADE', 'APARTAMENTO'),
    'due': ('VENCIMENTO', 'VENC.'), 'paid': ('PAGAMENTO', 'BAIXA'),
    'date': ('DATA',), 'original': ('LANCAMENTO', 'VALOR LCTO', 'VALOR LANCADO'),
    'correction': ('CORRECAO',), 'penalty': ('MULTA', 'MUTA'), 'interest': ('JUROS',),
    'discount': ('DESCONTO',), 'settled': ('LIQUIDADO', 'VALOR PAGO', 'VALOR BAIXA'),
    'credit': ('CREDITO', 'CREDITOS'), 'debit': ('DEBITO', 'DEBITOS'),
    'balance': ('SALDO',), 'account': ('CONTA CORRENTE',),
    'description': ('DESCRICAO', 'HISTORICO'), 'class': ('CLASSE DA CONTA',),
}
DATE = re.compile(r'(?<![\d/])\d{2}/\d{2}/\d{4}(?![\d/])')
AMOUNT = re.compile(r'(?<![\d/])[-+]?\d+(?:[. ]\d{3})*[,.]\s*\d{2}(?![\d/])')


def norm(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().upper()


def amount_readings(text):
    """Never silently interpret an integer with a missing decimal separator."""
    result = []
    for match in AMOUNT.finditer(text):
        token = match[0].replace(' ', '')
        if ',' in token:
            value = token.replace('.', '').replace(',', '.')
        else:
            whole, fraction = token.rsplit('.', 1)
            value = whole.replace('.', '') + '.' + fraction
        result.append({'raw': match[0], 'cents': int(Decimal(value) * 100)})
    return result


def valid_dates(text):
    result = []
    for match in DATE.finditer(text):
        try:
            datetime.strptime(match[0], '%d/%m/%Y')
        except ValueError:
            continue
        result.append(match[0])
    return result


def date_readings(text):
    """OCR date variants only inside an already identified date column.

    Preserve the original token. Never infer a year or derive competência here.
    """
    pattern=r'(?<![\d/])(\d{2})[/.:\- ]?(\d{2})[/.:\- ]?(\d{4})(?![\d/])'
    readings=[]
    for match in re.finditer(pattern,text):
        value='/'.join(match.groups())
        if valid_dates(value):
            readings.append({'raw':match[0],'value':value,'normalized':match[0]!=value})
    return readings


def words_from_tesseract(data, width, height):
    return [dict(text=t.strip(), x=data['left'][i]/width, y=data['top'][i]/height,
                 w=data['width'][i]/width, h=data['height'][i]/height,
                 confidence=float(data['conf'][i]),
                 line=[data[k][i] for k in ('block_num','par_num','line_num')])
            for i,t in enumerate(data['text']) if t.strip()]


def lines_from_words(words):
    lines = defaultdict(list)
    for word in words:
        lines[tuple(word['line'])].append(word)
    return [sorted(ws, key=lambda w:w['x']) for ws in lines.values()]


def header_columns(words, section):
    allowed = {
        'recebimentos': {'unit','due','paid','original','correction','penalty','interest','discount','settled','account','description'},
        'analitico': {'paid','original','settled','description','class'},
        'sintetico': {'original','interest','penalty','discount','settled','class'},
        'extrato': {'date','credit','debit','balance','description'},
    }.get(section, set(ALIASES))
    candidates = []
    for line in lines_from_words(words):
        if min(w['y'] for w in line) > .5:
            continue
        found = {}
        for i in range(len(line)):
            for size in (3,2,1):
                span = line[i:i+size]
                text = re.sub(r'^\W+|\W+$','',norm(' '.join(w['text'] for w in span)))
                for key in allowed:
                    if text in ALIASES[key] and key not in found:
                        left=min(w['x'] for w in span)
                        right=max(w['x']+w['w'] for w in span)
                        found[key]={'center':(left+right)/2,'header_y':sum(w['y']+w['h']/2 for w in span)/len(span),'raw':text}
        if len(found)>=3:
            candidates.append(found)
    if not candidates:
        return {}, ['header_columns_not_identified']
    best=max(candidates,key=lambda x:len(x))
    ordered=sorted(best,key=lambda k:best[k]['center'])
    for i,key in enumerate(ordered):
        # Midpoints are provisional; no fabricated hardcoded fallback if the
        # printed column order is not recovered. Optional grid borders refine it.
        left=(best[ordered[i-1]]['center']+best[key]['center'])/2 if i else 0
        right=(best[ordered[i+1]]['center']+best[key]['center'])/2 if i+1<len(ordered) else 1
        best[key].update(left=left,right=right)
    if 'settled' not in best and section in ('recebimentos','analitico','sintetico'):
        return best, ['settlement_column_not_identified']
    return best, []


def apply_grid_borders(columns, borders):
    """Use measured long vertical lines only if they uniquely enclose a header."""
    result={key:dict(value) for key,value in columns.items()}
    for field in result.values():
        before=[b for b in borders if b<field['center']]
        after=[b for b in borders if b>field['center']]
        if before and after:
            left,right=max(before),min(after)
            if not any(left<other['center']<right and other is not field for other in result.values()):
                field.update(left=left,right=right,bounds_method='printed_grid')
    return result


def physical_rows(words, columns, section, prior_unit=None):
    date_key='due' if section=='recebimentos' else 'date' if section=='extrato' else 'paid'
    if date_key not in columns:
        return [], ['date_column_not_identified'], prior_unit
    date_col=columns[date_key]
    header_y=max(c['header_y'] for c in columns.values())
    anchors=[]
    for word in words:
        center=word['x']+word['w']/2
        dates=date_readings(word['text'])
        if dates and date_col['left']<=center<date_col['right'] and word['y']>header_y:
            y=word['y']+word['h']/2
            if not any(abs(y-a['y'])<max(.002,word['h']*.5) for a in anchors):
                anchors.append({'y':y,'h':word['h'],'date':dates[0]['value'],'date_reading':dates[0]})
    anchors.sort(key=lambda a:a['y'])
    unit_headings=[]
    for word in words:
        if word.get('unit_heading'):
            unit_headings.append({'y':word['y']+word['h']/2,'unit':word['text']})
    fallback_unit_headings=[]
    for line in lines_from_words(words):
        line=[w for w in line if w['x']+w['w']/2<date_col['left']]
        if not line:
            continue
        text=' '.join(w['text'] for w in line).strip(' |:.,')
        match=re.fullmatch(r'(?:UNIDADE\s*:?\s*)?(\d{1,6}[A-Za-z]?)',text,re.I)
        if match and max(w['x']+w['w']/2 for w in line)<date_col['left']:
            fallback_unit_headings.append({'y':sum(w['y']+w['h']/2 for w in line)/len(line),'unit':match[1]})
    if not unit_headings:
        unit_headings=fallback_unit_headings
    rows=[];issues=[];unit=prior_unit
    for index,anchor in enumerate(anchors):
        y=anchor['y']
        low=(anchors[index-1]['y']+y)/2 if index else header_y+.003
        high=(anchors[index+1]['y']+y)/2 if index+1<len(anchors) else y+max(.009,anchor['h']*1.8)
        band=[w for w in words if low<w['y']+w['h']/2<high]
        # Unit headings belong above the date anchor, never to the next row.
        if section=='recebimentos':
            headings=[w for w in unit_headings if header_y<w['y']<=y]
            if headings:
                unit=max(headings,key=lambda w:w['y'])['unit']
        row={'source_y':y,'date':anchor['date'],'date_reading':anchor['date_reading'],'unit':unit,'cells':{},'issues':[],
             'bbox':[0,low,1,high],'raw':' '.join(w['text'] for w in sorted(band,key=lambda w:(round(w['y'],3),w['x'])))}
        for key,column in columns.items():
            ws=[w for w in band if column['left']<=w['x']+w['w']/2<column['right']
                and abs(w['y']+w['h']/2-y)<=max(anchor['h']*.9,.004)]
            raw=' '.join(w['text'] for w in sorted(ws,key=lambda w:w['x']))
            readings=amount_readings(raw)
            cell={'raw':raw,'readings':readings,'confidence':min((w['confidence'] for w in ws),default=0)}
            if key in {'original','correction','penalty','interest','discount','settled','credit','debit','balance'}:
                cell['cents']=readings[0]['cents'] if len(readings)==1 else None
                if cell['cents'] is None:
                    row['issues'].append('unresolved_'+key)
            elif key in {'due','paid','date'}:
                ds=date_readings(raw);cell['date_readings']=ds;cell['value']=ds[0]['value'] if len(ds)==1 else None
            row['cells'][key]=cell
        required=('original','correction','penalty','interest','discount','settled')
        if section=='recebimentos' and all(row['cells'].get(k,{}).get('cents') is not None for k in required):
            v={k:row['cells'][k]['cents'] for k in required}
            row['component_arithmetic_ok']=v['original']+v['correction']+v['penalty']+v['interest']-v['discount']==v['settled']
            if not row['component_arithmetic_ok']:
                row['issues'].append('component_arithmetic_mismatch')
        row['needs_review']=True
        rows.append(row)
    if not rows:
        issues.append('no_date_anchored_rows')
    return rows,issues,unit
