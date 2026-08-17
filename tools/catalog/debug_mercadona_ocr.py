from __future__ import annotations

import json
from pathlib import Path
import tempfile

from label_text_extractor import extract_with_tesseract
from mercadona_label_pipeline import download_label_image
from mercadona_product_adapter import fetch_product

PRODUCTS = [("14325","galletas"),("23049","batido"),("23773","chocolate"),("80862","hummus")]


def main():
    out=[]
    with tempfile.TemporaryDirectory(prefix='rumbo-debug-') as td:
        for pid,label in PRODUCTS:
            p=fetch_product(pid,timeout=8.0)
            ev=p.label_images[-1]
            path=Path(td)/f'{pid}.jpg'
            download_label_image(ev.image_url,path,timeout=8.0)
            row={'id':pid,'label':label,'name':p.name,'ean':p.ean,'image_index':ev.image_index,'readings':[]}
            for psm in (6,11,3):
                x=extract_with_tesseract(path,language='spa',psm=psm)
                row['readings'].append({'psm':psm,'confidence':x.confidence,'text':x.text[:5000]})
            out.append(row)
    Path('debug-mercadona-ocr.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
