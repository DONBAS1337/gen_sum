# -*- coding: utf-8 -*-
"""Restore embedded native snapshots, retaining the displaced session as a branch."""
from __future__ import unicode_literals
import copy,io,json,os,re

def restore(root,state,pending=None):
    import dg_rpg,dg_hybrid
    if __import__('dg_sessions').removed(root,state['id']):raise ValueError('This shift was removed; restore it from trash first')
    candidate=copy.deepcopy(pending['origin'] if pending is not None and 'origin' in pending else state)
    if pending is not None and (candidate.get('id')!=state.get('id') or dg_hybrid.fingerprint(candidate)!=pending.get('before')):raise ValueError('Pending origin fingerprint mismatch')
    candidate["native_resume"]=2
    dg_rpg.validate(candidate)
    if pending is not None and 'origin' not in pending:raise ValueError('Legacy pending turn has no safe snapshot')
    try:current=dg_rpg.load(root,candidate['id'])
    except IOError:current=None
    if current is not None and dg_hybrid.fingerprint(current)!=dg_hybrid.fingerprint(candidate):
        folder=os.path.join(root,'_rpg','_branches',candidate['id'])
        if not os.path.isdir(folder):os.makedirs(folder)
        name=dg_hybrid.fingerprint(current)+'.json';path=os.path.join(folder,name)
        if not os.path.isfile(path):
            with io.open(path+'.tmp','w',encoding='utf-8') as f:
                f.write(json.dumps(current,ensure_ascii=False,sort_keys=True));f.flush();os.fsync(f.fileno())
            os.rename(path+'.tmp',path)
        # Bounded on-disk histories; no files outside this exact branch directory.
        names=[n for n in os.listdir(folder) if re.match(r'^[a-f0-9]{64}\.json$',n)]
        for old in sorted(names,key=lambda n:os.path.getmtime(os.path.join(folder,n)))[:-24]:os.unlink(os.path.join(folder,old))
    dg_rpg.save(root,candidate)
    return candidate

def branches(root,game_id):
    if not re.match(r'^[a-f0-9]{32}$',game_id):return []
    folder=os.path.join(root,'_rpg','_branches',game_id)
    if not os.path.isdir(folder):return []
    rows=[]
    for name in os.listdir(folder):
        if not re.match(r'^[a-f0-9]{64}\.json$',name):continue
        try:
            with io.open(os.path.join(folder,name),'r',encoding='utf-8') as f:s=json.load(f)
            __import__('dg_rpg').validate(s)
            rows.append({'key':name[:-5],'day':s['day'],'slot':s['slot'],'place':s['place'],'minute':__import__('dg_clock').minute(s),'energy':s['energy']})
        except (IOError,ValueError,KeyError,TypeError):continue
    return sorted(rows,key=lambda r:(r['day'],r['slot'],r['key']),reverse=True)

def recover(root,game_id,key):
    if key not in [r['key'] for r in branches(root,game_id)]:raise ValueError('Unknown archived branch')
    with io.open(os.path.join(root,'_rpg','_branches',game_id,key+'.json'),'r',encoding='utf-8') as f:s=json.load(f)
    return restore(root,s)
