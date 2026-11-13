# -*- coding: utf-8 -*-
"""Engine-confirmed facts and private beliefs. Prose is never a fact source."""
from __future__ import unicode_literals
import copy,hashlib,json

def ensure(state):
    v=state.setdefault('epistemic',{'facts':[],'beliefs':{}});v.setdefault('identities',{});return v

def record(state,kind,subject,data,witnesses):
    import dg_clock,dg_rpg
    if kind not in ('recognition','transfer','meeting','testimony','account','resolution','observation'):raise ValueError('Unknown fact type')
    people=sorted(set(w for w in witnesses if w in dg_rpg.NPC_NAMES or w=='hero'))
    value={'kind':kind,'subject':subject,'data':copy.deepcopy(data),'at':dg_clock.absolute(state),'witnesses':people}
    key=hashlib.sha1(json.dumps(value,ensure_ascii=True,sort_keys=True).encode('ascii')).hexdigest()
    system=ensure(state)
    if kind=='recognition':
        item=system['identities'].setdefault(subject,dict(data,witnesses=[]))
        item['witnesses']=sorted(set(item['witnesses']+people))
    facts=system['facts']
    if not any(f['id']==key for f in facts):facts.append(dict(value,id=key))
    state['epistemic']['facts']=facts[-256:]
    return key

def knows(state,who,kind,subject):
    if kind=='recognition' and who in state.get('epistemic',{}).get('identities',{}).get(subject,{}).get('witnesses',[]):return True
    return any(f['kind']==kind and f['subject']==subject and who in f['witnesses'] for f in state.get('epistemic',{}).get('facts',[]))

def believe(state,who,subject,claim,confidence,status='uncertain'):
    if status not in ('uncertain','supported','refuted'):raise ValueError('Invalid belief status')
    rows=ensure(state)['beliefs'].setdefault(who,[])
    rows[:]=[r for r in rows if r['subject']!=subject]
    rows.append({'subject':subject,'claim':claim[:500],'confidence':max(0,min(100,confidence)),'status':status})
    del rows[:-16]

def recall(state,who):
    system=state.get('epistemic',{})
    return {'identities':copy.deepcopy(dict((k,dict((field,value) for field,value in v.items() if field!='witnesses')) for k,v in system.get('identities',{}).items() if who in v['witnesses'])),'facts':copy.deepcopy([f for f in system.get('facts',[]) if who in f['witnesses']][-12:]),
            'beliefs':copy.deepcopy(system.get('beliefs',{}).get(who,[])),
            'rule':u'facts — только лично известные сведения. beliefs — мнение с ограниченной уверенностью; не выдавай его за истину. Отсутствие факта не доказывает противоположное.'}

def validate(state):
    v=state.get('epistemic')
    if v is None:return
    import dg_rpg
    if not isinstance(v,dict) or not isinstance(v.get('facts'),list) or len(v['facts'])>256 or not isinstance(v.get('beliefs'),dict) or len(v['beliefs'])>12:raise ValueError('Invalid knowledge state')
    if not isinstance(v.get('identities',{}),dict) or len(v.get('identities',{}))>128:raise ValueError('Invalid durable recognition')
    for f in v['facts']:
        if not isinstance(f,dict) or f.get('kind') not in ('recognition','transfer','meeting','testimony','account','resolution','observation') or not isinstance(f.get('id'),(str,type(u''))) or len(f['id'])!=40 or type(f.get('at')) is not int or not isinstance(f.get('data'),dict) or not isinstance(f.get('subject'),(str,type(u''))) or len(f['subject'])>120 or not isinstance(f.get('witnesses'),list) or len(f['witnesses'])>12 or any(w not in tuple(dg_rpg.NPC_NAMES)+('hero',) for w in f['witnesses']):raise ValueError('Invalid confirmed fact')
    for who,rows in v['beliefs'].items():
        if who not in tuple(dg_rpg.NPC_NAMES)+('hero',) or not isinstance(rows,list) or len(rows)>16:raise ValueError('Invalid belief owner')
        for r in rows:
            if not isinstance(r,dict) or r.get('status') not in ('uncertain','supported','refuted') or type(r.get('confidence')) is not int or not 0<=r['confidence']<=100 or not isinstance(r.get('claim'),(str,type(u''))) or len(r['claim'])>500:raise ValueError('Invalid private belief')
