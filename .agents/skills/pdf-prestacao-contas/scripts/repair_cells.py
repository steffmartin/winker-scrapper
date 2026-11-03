"""Retry only unresolved spatial cells; save proposals without editing evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import pymupdf as fitz
import pytesseract
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parent))
from local_config import load_config
from table_geometry import amount_readings


def repair(variant_path,manifest_path,out,limit=30,dpi=400,config=None):
    if limit<1 or not 150<=dpi<=600:
        raise ValueError('Invalid repair budget or DPI.')
    variant=json.loads(variant_path.read_text(encoding='utf8'))
    manifest=json.loads(manifest_path.read_text(encoding='utf8'))
    meta=variant['metadata'];pdf=Path(manifest['pdf'])
    digest=hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest!=meta['pdf_sha256']:
        raise ValueError('Variant belongs to a different PDF.')
    cfg=load_config(config).get('ocr',{})
    if cfg.get('tesseract'):pytesseract.pytesseract.tesseract_cmd=cfg['tesseract']
    if cfg.get('tessdata'):os.environ['TESSDATA_PREFIX']=cfg['tessdata']
    out.mkdir(parents=True,exist_ok=True)
    queue=variant.get('repair_queue',[]);results=[];calls=0
    with fitz.open(pdf) as doc:
        pix=doc[meta['page']-1].get_pixmap(dpi=dpi,alpha=False)
        image=Image.frombytes('RGB',[pix.width,pix.height],pix.samples).rotate(meta['rotation'],expand=True)
        angle=variant.get('deskew_degrees',0)
        if angle:image=image.rotate(angle,fillcolor='white')
        for cell in queue:
            settings={'engine':1,'pdf_sha256':digest,'source_variant_sha256':hashlib.sha256(variant_path.read_bytes()).hexdigest(),
                      'page':meta['page'],'bbox':cell['bbox'],'row':cell['row'],'field':cell['field'],
                      'dpi':dpi,'rotation':meta['rotation'],'deskew':angle,'psms':[7,13]}
            key=hashlib.sha256(json.dumps(settings,sort_keys=True).encode()).hexdigest()[:16]
            dest=out/(key+'.json')
            if dest.exists():
                results.append(json.loads(dest.read_text(encoding='utf8')));continue
            if calls>=limit*2:
                continue
            x0,y0,x1,y1=cell['bbox']
            crop=image.crop((int(x0*image.width)+1,int(y0*image.height),int(x1*image.width)-1,int(y1*image.height)))
            readings=[]
            for psm in (7,13):
                raw=pytesseract.image_to_string(crop,lang=cfg.get('language','por'),config=f'--psm {psm}',timeout=90)
                values=amount_readings(raw);calls+=1
                readings.append({'psm':psm,'raw':raw,'cents':values[0]['cents'] if len(values)==1 else None})
            values={r['cents'] for r in readings if r['cents'] is not None}
            agreed=len(values)==1 and all(r['cents'] is not None for r in readings)
            result={'settings':settings,'cell':cell,'readings':readings,'proposal_cents':next(iter(values)) if agreed else None,
                    'status':'OBSERVED_CONSENSUS_CANDIDATE' if agreed else 'UNRESOLVED',
                    'note':'OCR agreement is not independent financial evidence or approval.'}
            if not agreed:
                crop.save(out/(key+'.png'))
                result['crop']=key+'.png'
            dest.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
            results.append(result)
    report={'source_variant':str(variant_path),'queue_size':len(queue),'processed':len(results),'ocr_calls':calls,
            'consensus_proposals':sum(r['status']=='OBSERVED_CONSENSUS_CANDIDATE' for r in results),
            'remaining_after_budget':len(queue)-len(results),'results':results,'status':'CANDIDATE_ONLY'}
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},ensure_ascii=True))
    return report


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--variant',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);ap.add_argument('--limit',type=int,default=30)
    ap.add_argument('--dpi',type=int,default=400);ap.add_argument('--config',type=Path)
    args=ap.parse_args();repair(args.variant,args.manifest,args.output,args.limit,args.dpi,args.config)
