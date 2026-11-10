# -*- coding: utf-8 -*-
"""Portable inventory of donor art; static script references, never donor execution."""
from __future__ import unicode_literals
import hashlib,io,json,os,re,struct

VERSION=1
_CACHE={}
KINDS={'cg':('cg','cgs','custom_cg','custom_sg'),'bg':('bg','bgs','background','backgrounds'),'sprite':('sprite','sprites')}
ALIASES={'embrace':'hug','hug':'hug','walking':'walk','walk':'walk','dance':'dance','disco':'dance',
         'guitar':'guitar','piano':'piano','rehearsal':'rehearsal','book':'book','reading':'book',
         'campfire':'campfire','bonfire':'campfire','tea':'tea','cards':'cards','concert':'concert',
         'rain':'rain','beach':'beach','read':'book','picnic':'picnic','confession':'confession','sing':'sing','song':'sing','draw':'draw','drawing':'draw'}
ACTOR_ALIASES={'miku':'mi','alisa':'dv','lena':'un','slavya':'sl','ulyana':'us','olga':'mt','viola':'cs','zhenya':'mz','electronik':'el','shurik':'sh'}

def kind(path):
    parts=path.replace('\\','/').lower().split('/')[:-1]
    # A UI directory called sprites_pref is intentionally not a sprite directory.
    return next((k for k,names in KINDS.items() if any(p in names for p in parts)),None)

def dimensions(path):
    with open(path,'rb') as f:
        head=f.read(32)
        if head[:8]==b'\x89PNG\r\n\x1a\n' and len(head)>=26:return list(struct.unpack('>II',head[16:24])),(head[25] if isinstance(head[25],int) else ord(head[25])) in (4,6)
        if head[:2]==b'\xff\xd8':
            f.seek(2)
            while f.tell()<256*1024:
                c=f.read(1)
                if not c:break
                if c!=b'\xff':continue
                marker=f.read(1)
                while marker==b'\xff':marker=f.read(1)
                if marker in (b'\xd9',b'\xda'):break
                if marker==b'\x00' or marker in (b'\xd8',b'\x01'):continue
                length=f.read(2)
                if len(length)!=2:break
                n=struct.unpack('>H',length)[0]
                if n<2:break
                code=ord(marker)
                if code in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
                    data=f.read(5)
                    if len(data)==5:
                        h,w=struct.unpack('>HH',data[1:]);return [w,h],False
                    break
                f.seek(n-2,1)
    return None,None

def _hash(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        while True:
            chunk=f.read(1024*1024)
            if not chunk:break
            h.update(chunk)
    return h.hexdigest()

def _scripts(root,stems):
    # Store identifiers and line numbers only, never copy dialogue or run source.
    refs={};archives=[]
    for folder,dirs,files in os.walk(root):
        dirs[:]=sorted(d for d in dirs if d not in ('.git','cache'))
        for name in sorted(files):
            path=os.path.join(folder,name);rel=os.path.relpath(path,root).replace('\\','/')
            if name.lower().endswith('.rpa'):archives.append(rel)
            if not name.lower().endswith('.rpy'):continue
            bg=None
            try:
                with io.open(path,'r',encoding='utf-8-sig',errors='replace') as f:
                    for number,line in enumerate(f,1):
                        code=line.strip()
                        if code.startswith('#'):continue
                        if re.match(r'label\s+',code):bg=None
                        match=re.match(r'(?:scene|show)\s+(?:\w+\s+)?bg\s+([a-zA-Z0-9_]+)',code)
                        if match:bg=match.group(1)
                        # CG references and image declarations; no prose token search.
                        if not re.search(r'\b(?:scene|show|image|cg|CG)\b',code) and not re.search(r'[/\\]cg[/\\]',code):continue
                        tokens=set(re.findall(r'[A-Za-z0-9_]+',code))
                        for stem in tokens.intersection(stems):
                            usage={'script':rel,'line':number,'bg':bg,'reference':'scene' if re.match(r'(?:scene|show)\s+',code) else 'declaration'}
                            found=refs.setdefault(stem,[])
                            if usage['reference']=='scene':found.append(usage);refs[stem]=found[-8:]
                            elif len(found)<2:found.append(usage)
            except (IOError,OSError):continue
    return refs,archives

def scan(sources,probe=None):
    import dg_gallery
    rows=[];warnings=[];archives={}
    for source,root in sorted(sources.items()):
        root=os.path.realpath(root)
        if not os.path.isdir(root):warnings.append('Missing source '+source);continue
        pending=[]
        for folder,dirs,files in os.walk(root):
            dirs[:]=sorted(d for d in dirs if d not in ('.git','cache','music','sounds','sound','video'))
            for name in sorted(files):
                stem,ext=os.path.splitext(name.lower())
                if ext not in ('.png','.jpg','.jpeg','.webp'):continue
                path=os.path.realpath(os.path.join(folder,name))
                if not os.path.normcase(path).startswith(os.path.normcase(root+os.sep)):continue
                rel=os.path.relpath(path,root).replace('\\','/');category=kind(rel)
                if not category:continue
                words=set(re.split('[^a-z]+',stem));motifs=sorted(set(ALIASES[w] for w in words if w in ALIASES))
                size,alpha=(probe or dimensions)(path)
                actors=words.intersection(dg_gallery.ACTORS)|set(ACTOR_ALIASES[w] for w in words if w in ACTOR_ALIASES)
                pending.append({'source':source,'relative':rel,'kind':category,'name':stem,'bytes':os.path.getsize(path),
                                'sha256':_hash(path),'dimensions':size,'alpha':alpha,'readable':bool(size),
                                'actors':sorted(actors), 'motifs':motifs,
                                'restrictions':[w for w in dg_gallery.EXCLUDE if w in stem],
                                'setting':'exterior' if words.intersection(('ext','outside','verandah','beach','campfire')) else 'interior' if words.intersection(('int','club','library','piano')) else None,
                                'time_slots':[3] if 'night' in words else [2] if 'sunset' in words else [0,1] if 'day' in words else None,
                                'metadata_status':'filename_only','visual_review':'not_reviewed'})
        refs,packed=_scripts(root,set(r['name'] for r in pending if r['kind']=='cg'));archives[source]=packed
        for row in pending:
            if row['kind']=='cg':
                row['usage']=refs.get(row['name'],[])
                bgs=set(r['bg'] for r in row['usage'] if r['bg'] and r.get('reference')=='scene')
                times=set('night' if 'night' in bg else 'sunset' if 'sunset' in bg else 'day' if 'day' in bg else 'unknown' for bg in bgs)
                settings=set('exterior' if bg.startswith('ext_') else 'interior' if bg.startswith('int_') else 'unknown' for bg in bgs)
                if not row['time_slots'] and len(times)==1 and 'unknown' not in times:row['time_slots']={'night':[3],'sunset':[2],'day':[0,1]}[next(iter(times))]
                if row['setting'] is None and len(settings)==1 and 'unknown' not in settings:row['setting']=next(iter(settings))
                if row['usage']:row['metadata_status']='script_reference'
                # Explicitly reviewed retrieval metadata from the existing dance adapter.
                if (source=='451835368' and row['name']=='d7_mi_dance') or (source=='3266357374' and row['name'] in ('d3_mi_dance_7dl','d3_mi_dance_bordo_7dl')):
                    row.update(time_slots=[2,3],setting='exterior',metadata_status='curated')
            rows.append(row)
    hashes={}
    for r in rows:hashes.setdefault(r['sha256'],[]).append(r['source']+'/'+r['relative'])
    duplicates=[v for k,v in sorted(hashes.items()) if len(v)>1]
    return {'version':VERSION,'assets':rows,'duplicates':duplicates,'archives_not_indexed':archives,'warnings':warnings,
            'policy':'Inventory completeness is not visual approval. Every CG needs scene-specific vision verification; alpha CGs may require composition. No donor source is executed or bundled.'}

def load(path=None):
    path=path or os.path.join(os.path.dirname(__file__),'stock_catalog.json')
    try:
        stamp=(os.path.getmtime(path),os.path.getsize(path))
        if path in _CACHE and _CACHE[path][0]==stamp:return _CACHE[path][1]
        with io.open(path,'r',encoding='utf-8') as f:data=json.load(f)
        if data.get('version')!=VERSION or not isinstance(data.get('assets'),list):return {'assets':[]}
        _CACHE[path]=(stamp,data);return data
    except (IOError,OSError,ValueError,AttributeError):return {'assets':[]}

def resolve(root,relative):
    if not isinstance(relative,(str,type(u''))) or os.path.isabs(relative):return None
    root=os.path.realpath(root);path=os.path.realpath(os.path.join(root,relative.replace('/',os.sep)))
    if not os.path.normcase(path).startswith(os.path.normcase(root+os.sep)):return None
    return path if os.path.isfile(path) else None

def cg_rows(directories,data=None):
    result=[];roots=dict((os.path.basename(os.path.realpath(r)),r) for r in directories)
    for row in (data or load()).get('assets',[]):
        if row.get('kind')!='cg' or row.get('source') not in roots or row.get('restrictions') or row.get('alpha') or row.get('readable') is False or not row.get('actors') or not row.get('motifs'):continue
        path=resolve(roots[row['source']],row['relative'])
        if not path or os.path.getsize(path)!=row.get('bytes'):continue
        result.append(dict(row,path=path.replace('\\','/'),night=row.get('time_slots')==[3],sunset=row.get('time_slots')==[2]))
    return result

def summary(data=None):
    data=data or load();assets=data.get('assets',[])
    return {'total':len(assets),'counts':dict((k,sum(r['kind']==k for r in assets)) for k in KINDS),
            'cg_referenced':sum(r['kind']=='cg' and bool(r.get('usage')) for r in assets),
            'cg_restricted':sum(r['kind']=='cg' and bool(r.get('restrictions')) for r in assets),
            'unreadable':sum(r.get('readable') is False for r in assets),
            'duplicate_groups':len(data.get('duplicates',[])),'archives_not_indexed':data.get('archives_not_indexed',{}),
            'warnings':data.get('warnings',[])}
