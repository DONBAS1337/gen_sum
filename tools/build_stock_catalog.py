# -*- coding: utf-8 -*-
"""Index installed donor art, without executing/copying donor scripts or images."""
from pathlib import Path
import argparse,csv,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'don_gen'))
import dg_catalog

def probe(path):
    # Pillow is only a build-tool dependency. RenPy uses the saved portable metadata.
    from PIL import Image,UnidentifiedImageError
    try:
        with Image.open(path) as image:
            alpha=False
            if image.mode in ('RGBA','LA'):alpha=image.getchannel('A').getextrema()[0]<255
            elif image.mode=='P' and 'transparency' in image.info:alpha=image.convert('RGBA').getchannel('A').getextrema()[0]<255
            return list(image.size),alpha
    except (UnidentifiedImageError,OSError,ValueError):return None,None

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workshop',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'don_gen/stock_catalog.json')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    data=dg_catalog.scan({code:str(args.workshop/code) for code in ('3266357374','451835368')},probe=probe)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')),encoding='utf-8')
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        with args.report.open('w',encoding='utf-8-sig',newline='') as f:
            fields=('source','relative','kind','dimensions','readable','alpha','actors','motifs','time_slots','setting','metadata_status','visual_review','restrictions','sha256')
            writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(data['assets'])
    print(json.dumps(dg_catalog.summary(data),ensure_ascii=True,sort_keys=True))

if __name__=='__main__':main()
