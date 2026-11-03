"""Replay cached discovery evidence without re-OCR, DB access or financial output.

Reviewed page maps are test oracles only; never used by the production classifier.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from extract_local import classify


def benchmark(sources,output):
    results=[]
    for source in sorted(sources.glob('????-??')):
        auto=source/'auto';reference=auto/'discovery_review.json'
        if not reference.exists():continue
        reviewed=json.loads(reference.read_text(encoding='utf8'))
        for group in reviewed['selected']:
            for page in group['pages']:
                evidence=[]
                for name in (f'header_{page:03}.txt',f'page_{page:03}.txt',f'binary_{page:03}.txt',f'refined_{page:03}.txt'):
                    path=auto/name
                    if not path.exists():continue
                    label=classify(path.read_text(encoding='utf8'))
                    evidence.append({'file':name,'recognized_section':label})
                recognized=any(e['recognized_section']==group['section'] for e in evidence)
                results.append({'month':source.name,'page':page,'expected_section':group['section'],
                                'recognized_from_cached_text':recognized,'evidence':evidence})
    by_year=defaultdict(lambda:{'pages':0,'recognized':0,'needs_spatial_or_crop':0})
    for row in results:
        result=by_year[row['month'][:4]];result['pages']+=1
        result['recognized' if row['recognized_from_cached_text'] else 'needs_spatial_or_crop']+=1
    report={'mode':'cached_text_classification','years':dict(by_year),'results':results,
            'limitations':'Positive-page recall only; not false-positive accuracy or a full OCR/ledger audit.'}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'years':dict(by_year),'output':str(output)},ensure_ascii=True))
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sources',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();benchmark(args.sources,args.output)
