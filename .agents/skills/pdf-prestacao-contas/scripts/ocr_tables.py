"""Targeted, cached spatial OCR. stdout contains counts, never full report text."""
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
from table_geometry import words_from_tesseract,header_columns,physical_rows,apply_grid_borders

ENGINE_VERSION=3


def grid_variant(image):
    """Optional measured line removal. Raw image is always kept as another variant."""
    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise RuntimeError('Grid repair needs optional opencv-python-headless and numpy.') from error
    array=np.asarray(image.convert('L'))
    small=cv2.resize(array,None,fx=.4,fy=.4)
    edges=cv2.threshold(small,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    lines=cv2.HoughLinesP(edges,1,np.pi/1800,threshold=100,
                          minLineLength=max(50,int(small.shape[1]*.35)),maxLineGap=15)
    angles=[]
    if lines is not None:
        for x1,y1,x2,y2 in lines.reshape(-1,4):
            value=float(np.degrees(np.arctan2(y2-y1,x2-x1)))
            if abs(value)<3:angles.append(value)
    angle=float(np.median(angles)) if angles else 0.0
    h,w=array.shape
    array=cv2.warpAffine(array,cv2.getRotationMatrix2D((w/2,h/2),angle,1),(w,h),borderValue=255)
    bw=cv2.threshold(array,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    h,w=array.shape
    vertical=cv2.morphologyEx(bw,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,max(40,h//35))))
    horizontal=cv2.morphologyEx(bw,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(max(60,w//25),1)))
    score=vertical.sum(axis=0)
    indexes=np.where(score>max(255*h*.12,float(score.max())*.35))[0]
    groups=[]
    for x in indexes:
        if groups and x-groups[-1][-1]<=max(2,w*.002):
            groups[-1].append(x)
        else:
            groups.append([x])
    borders=[float(sum(g)/len(g)/w) for g in groups]
    mask=cv2.bitwise_or(vertical,horizontal)
    cleaned=cv2.inpaint(array,mask,1,cv2.INPAINT_TELEA)
    return Image.fromarray(cleaned),borders,angle


def read_variant(image,section,out,key,metadata,remove_grid=False):
    path=out/(key+'.json')
    if path.exists():
        cached=json.loads(path.read_text(encoding='utf8'))
        if cached['metadata']==metadata:
            # Pure geometry improvements reuse expensive OCR words. Recompute
            # derived rows/queues rather than invalidating OCR for every parser edit.
            columns,issues=header_columns(cached['words'],section)
            columns=apply_grid_borders(columns,cached.get('grid_borders',[]))
            rows,row_issues,last_unit=physical_rows(cached['words'],columns,section)
            queue=[]
            for index,row in enumerate(rows):
                for field,cell in row['cells'].items():
                    if 'cents' in cell and cell['cents'] is None:
                        col=columns[field]
                        queue.append(dict(row=index,field=field,page=metadata['page'],
                                          bbox=[col['left'],row['bbox'][1],col['right'],row['bbox'][3]],
                                          raw=cell['raw'],reason='unresolved_cell'))
            cached.update(columns=columns,rows=rows,issues=issues+row_issues,last_unit=last_unit,repair_queue=queue)
            path.write_text(json.dumps(cached,ensure_ascii=False,indent=2),encoding='utf8')
            return cached,True
    borders=[];deskew=0.0
    if remove_grid:
        image,borders,deskew=grid_variant(image)
    data=pytesseract.image_to_data(image,lang=metadata['language'],config='--psm '+str(metadata['psm']),
                                   output_type=pytesseract.Output.DICT,timeout=120)
    words=words_from_tesseract(data,image.width,image.height)
    columns,issues=header_columns(words,section)
    columns=apply_grid_borders(columns,borders)
    if section=='recebimentos' and 'due' in columns:
        # A narrow, independently segmented unit column recovers headings that
        # full-width OCR merged with tall border boxes. No unit list is assumed.
        import re
        crop=image.crop((0,0,max(1,int(columns['due']['left']*image.width)),image.height))
        unit_data=pytesseract.image_to_data(crop,lang=metadata['language'],config='--psm 11',
                                           output_type=pytesseract.Output.DICT,timeout=90)
        for word in words_from_tesseract(unit_data,image.width,image.height):
            raw=word['text'].strip(' |:.,[]()')
            if re.fullmatch(r'\d{1,6}[A-Za-z]?',raw):
                word.update(text=raw,unit_heading=True)
                words.append(word)
    rows,row_issues,last_unit=physical_rows(words,columns,section)
    queue=[]
    for index,row in enumerate(rows):
        for field,cell in row['cells'].items():
            if 'cents' in cell and cell['cents'] is None:
                column=columns[field]
                queue.append({'row':index,'field':field,'page':metadata['page'],
                              'bbox':[column['left'],row['bbox'][1],column['right'],row['bbox'][3]],
                              'raw':cell['raw'],'reason':'unresolved_cell'})
    result={'metadata':metadata,'columns':columns,'grid_borders':borders,'deskew_degrees':deskew,
            'words':words,'rows':rows,'repair_queue':queue,
            'issues':issues+row_issues,'last_unit':last_unit,'status':'CANDIDATE_ONLY'}
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    return result,False


def process(pdf,manifest,out,pages=None,psms=(6,),dpi=300,remove_grid=False,config=None):
    cfg=load_config(config).get('ocr',{})
    if cfg.get('tesseract'):
        pytesseract.pytesseract.tesseract_cmd=cfg['tesseract']
    if cfg.get('tessdata'):
        os.environ['TESSDATA_PREFIX']=cfg['tessdata']
    fingerprint=hashlib.sha256(pdf.read_bytes()).hexdigest()
    if manifest.get('source_sha256') and manifest['source_sha256']!=fingerprint:
        raise ValueError('Manifest belongs to a different PDF. Refusing stale page selection.')
    selected={n:g['section'] for g in manifest['selected'] for n in g['pages']}
    targets=sorted(selected if pages is None else pages)
    if any(n not in selected for n in targets):
        raise ValueError('Requested page is not in the supplied selection.')
    if any(n<1 for n in targets) or not 72<=dpi<=600:
        raise ValueError('Invalid page/DPI.')
    out.mkdir(parents=True,exist_ok=True)
    summary=[]
    with fitz.open(pdf) as doc:
        for number in targets:
            section=selected[number]
            meta_path=Path(manifest['_directory'])/f'page_{number:03}.json'
            discovery_path=Path(manifest['_directory'])/f'discovery_{number:03}.json'
            source_meta=json.loads((meta_path if meta_path.exists() else discovery_path).read_text(encoding='utf8'))
            rotation=source_meta.get('ocr_rotation',source_meta.get('rotation',0))
            pix=doc[number-1].get_pixmap(dpi=dpi,alpha=False)
            image=Image.frombytes('RGB',[pix.width,pix.height],pix.samples).rotate(rotation,expand=True)
            for transform in (('raw','grid_removed') if remove_grid else ('raw',)):
                for psm in psms:
                    metadata={'version':ENGINE_VERSION,'pdf_sha256':fingerprint,'page':number,'section':section,
                              'rotation':rotation,'dpi':dpi,'psm':psm,'transform':transform,'language':cfg.get('language','por')}
                    digest=hashlib.sha256(json.dumps(metadata,sort_keys=True).encode()).hexdigest()[:12]
                    key=f'p{number:03}_{transform}_psm{psm}_{digest}'
                    result,cached=read_variant(image,section,out,key,metadata,transform=='grid_removed')
                    summary.append({'page':number,'variant':key,'cached':cached,'rows':len(result['rows']),
                                    'unresolved_cells':sum(len(r['issues']) for r in result['rows']),'issues':result['issues']})
    report={'pdf_sha256':fingerprint,'variants':summary,'status':'CANDIDATE_ONLY'}
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=True))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--pages',type=int,nargs='+')
    parser.add_argument('--psm',type=int,nargs='+',default=[6])
    parser.add_argument('--dpi',type=int,default=300)
    parser.add_argument('--remove-grid',action='store_true')
    parser.add_argument('--config',type=Path)
    args=parser.parse_args()
    manifest=json.loads(args.manifest.read_text(encoding='utf8'));manifest['_directory']=str(args.manifest.parent)
    process(Path(manifest['pdf']),manifest,args.output,args.pages,args.psm,args.dpi,args.remove_grid,args.config)
