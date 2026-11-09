# -*- coding: utf-8 -*-
"""Read-only voice references from installed BKRR scripts; never runs donor code."""
from __future__ import unicode_literals
import ast,hashlib,io,json,os,re
_CACHE={}
SPEAKERS=('mi','dv','un','sl','us','mz','mt','cs','el','sh','uv')
LINE=re.compile(r'^\s*(mi|dv|un|sl|us|mz|mt|cs|el|sh|uv)\s+((?:u)?"(?:\\.|[^"\\])*"|(?:u)?\'(?:\\.|[^\'\\])*\')\s*$')
UNSAFE=re.compile(u'люблю|любим|поцел|свад|навсегда|интим|секс|обнаж|голая|голый|зарез|убью|убить|погиб|умер|кров',re.I)

def load(root):
    if not root:return []
    base=os.path.realpath(root);folder=os.path.join(base,'bkrr','days')
    if not os.path.isdir(folder):return []
    paths=[]
    for name in sorted(os.listdir(folder)):
        match=re.match(r'^bkrr_day(\d+)\.rpy$',name)
        if not match:continue
        path=os.path.realpath(os.path.join(folder,name))
        if not os.path.normcase(path).startswith(os.path.normcase(base+os.sep)):continue
        stat=os.stat(path)
        if stat.st_size>4*1024*1024:continue
        paths.append((path,int(match.group(1)),stat.st_size,stat.st_mtime))
    signature=hashlib.sha256(json.dumps(paths,ensure_ascii=True).encode('utf-8')).hexdigest()
    if signature in _CACHE:return _CACHE[signature]
    rows=[]
    for path,day,size,mtime in paths:
        label='';expression={}
        with io.open(path,'r',encoding='utf-8-sig') as handle:
            for number,line in enumerate(handle,1):
                if len(line)>4096:continue
                heading=re.match(r'^label\s+([a-zA-Z0-9_]+):',line)
                if heading:label=heading.group(1)
                stage=re.match(r'^\s*show\s+([a-z]+)\s+([a-z]+)',line)
                if stage and stage.group(1) in SPEAKERS:expression[stage.group(1)]=stage.group(2)
                match=LINE.match(line)
                if not match:continue
                try:text=ast.literal_eval(match.group(2))
                except (ValueError,SyntaxError):continue
                if isinstance(text,bytes):text=text.decode('utf-8','replace')
                text=re.sub(r'\{[^}]*\}','',text).strip()
                if not 15<=len(text)<=260 or '[' in text or ']' in text or UNSAFE.search(text):continue
                text=re.sub(u'Сем[её]н(?:а|ом|у)?|Сеня|Сень',u'<исходный герой>',text)
                rows.append({'day':day,'who':match.group(1),'text':text,'expression':expression.get(match.group(1)),'file':os.path.basename(path),'line':number,'label':label})
                if len(rows)>=24000:break
    _CACHE.clear();_CACHE[signature]=rows
    return rows

def select(rows,who,query,day,limit=3):
    if who not in SPEAKERS:return []
    terms=set(re.findall(u'[а-яёa-z]{4,}',query.lower()))
    eligible=[]
    for row in rows:
        if row['who']!=who or row['day']>day:continue
        score=sum(1 for word in terms if word in row['text'].lower())
        # Earlier examples are a safer fallback than later route revelations.
        eligible.append((-score,row['day'],row['line'],row))
    eligible.sort(key=lambda item:item[:3])
    result=[];seen=set()
    for score,day,number,row in eligible:
        if row['text'] in seen:continue
        seen.add(row['text']);result.append(dict(row))
        if len(result)>=limit:break
    return result

def context(root,people,query,day):
    rows=load(root);examples=[]
    for who in people[:4]:examples.extend(select(rows,who,query,day,2))
    return {'source':'БКРР','usage':'voice_reference_only','examples':examples,
            'rule':u'Это примеры речи из другой истории. Не цитируй и не переноси события, знакомство с исходным героем, отношения или знания в текущую смену. День источника ограничен текущим днём. Пустая выборка не разрешает выдумывать канон.'}
