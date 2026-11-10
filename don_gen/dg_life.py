# -*- coding: utf-8 -*-
"""Minute-based NPC travel, appointments and witnessed shared time."""
from __future__ import unicode_literals
import copy
PEERS=('mi','dv','un','sl','mz','el','sh')

def ensure(state):return state.setdefault('npc_life',{'people':{},'plans':[],'day':0,'last':None,'history':[]})

def location(state,who):
    person=state.get('npc_life',{}).get('people',{}).get(who)
    return person.get('place') if person and not __import__('dg_camp').in_intro(state) else None

def _plans(state):
    import dg_social,dg_world
    s=ensure(state)
    if s['day']==state['day']:return
    s['day']=state['day'];s['plans']=[]
    # One social appointment per day, with a real invitation and a stable result.
    pool=[(dg_social.bond(state,a,b),a,b) for i,a in enumerate(PEERS) for b in PEERS[i+1:]]
    salt=dg_world._seed(state['id'],state['day'],'appointment')
    score,a,b=sorted(pool,reverse=True)[salt%min(5,len(pool))]
    place='music' if a in ('mi','dv') or b in ('mi','dv') else 'clubs' if a in ('el','sh') or b in ('el','sh') else 'library'
    s['plans'].append({'id':'%d:%s:%s'%(state['day'],a,b),'pair':[a,b],'place':place,'start':1020,'end':1060,
                       'kind':'private_meeting' if score>=65 else 'shared_interest','status':'planned','progress':0,'last':None})

def tick(state):
    import dg_rpg,dg_camp,dg_clock,dg_visits,dg_agents,dg_social,dg_epistemic
    if 'camp_life' not in state or state['finished'] or dg_camp.in_intro(state):return
    s=ensure(state);now=dg_clock.absolute(state);minute=dg_clock.minute(state)
    if s['last']==now:return
    s['last']=now;_plans(state);dg_agents.ensure(state)
    for who in dg_agents.PROFILES:
        if who=='uv':continue
        current=dg_rpg.where_is(state,who)
        p=s['people'].setdefault(who,{'place':current,'destination':current,'route':[],'next':now+5})
        if who=='cs':p.update(place='infirmary',destination='infirmary',route=[]);continue
        imposed=dg_camp.location(state,who)
        if imposed:
            p.update(place=imposed,destination=imposed,route=[],next=now+5);continue
        if state.get('dialogue_clock',{}).get('who')==who or (state.get('interaction',{}).get('who')==who and now<=state['interaction']['until']):
            p.update(place=state['place'],route=[]);continue
        if state['slot']==3:
            p.update(place=dg_rpg.where_is(dict(state,npc_life={}),who),route=[]);continue
        appointment=next((r for r in s['plans'] if who in r['pair'] and r['start']-30<=minute<r['end'] and r['status'] in ('planned','meeting')),None)
        goal=state.get('npc_agendas',{}).get('people',{}).get(who,{})
        target=appointment['place'] if appointment else goal.get('goal',{}).get('place')
        if dg_visits.busy(state,who) or dg_visits.location(state,who):
            p.update(place=current,route=[]);continue
        if target and target!=p['destination']:
            path=dg_visits.route(p['place'],target)
            p.update(destination=target,route=path[1:],next=now+5)
        while p['route'] and now>=p['next']:
            p['place']=p['route'].pop(0);p['next']+=5
    for plan in s['plans']:
        if plan['status'] in ('done','missed'):continue
        if minute>=plan['end']:
            plan['status']='missed';continue
        if minute<plan['start'] or plan['last']==now:continue
        if all(dg_rpg.where_is(state,w)==plan['place'] for w in plan['pair']):
            plan['status']='meeting';plan['progress']+=min(10,now-(plan['last'] or now-5));plan['last']=now
            if plan['progress']>=20:
                a,b=plan['pair'];key=dg_social._pair(a,b)
                dg_social.ensure(state)['bonds'][key]=min(100,dg_social.bond(state,a,b)+3)
                witnesses=plan['pair']+(['hero'] if state['place']==plan['place'] else [])
                dg_epistemic.record(state,'meeting',plan['id'],{'pair':plan['pair'],'place':plan['place'],'kind':plan['kind']},witnesses)
                plan['status']='done';s['history'].append(copy.deepcopy(plan));s['history']=s['history'][-48:]

def report(state,who=None):
    s=state.get('npc_life',{})
    return {'appointments':copy.deepcopy([p for p in s.get('plans',[]) if who in p['pair']]) if who else [],
            'rule':u'Личные планы известны участникам. planned — приглашение на будущее; только done означает состоявшуюся встречу. Совместное время не доказывает роман или интим.'}

def validate(state):
    v=state.get('npc_life')
    if v is None:return
    import dg_rpg
    if not isinstance(v,dict) or not isinstance(v.get('people'),dict) or len(v['people'])>11 or not isinstance(v.get('plans'),list) or len(v['plans'])>8 or not isinstance(v.get('history'),list) or len(v['history'])>48:raise ValueError('Invalid NPC life')
    for who,p in v['people'].items():
        if who not in dg_rpg.NPC_NAMES or not isinstance(p,dict) or p.get('place') not in dg_rpg.PLACE_NAMES or p.get('destination') not in dg_rpg.PLACE_NAMES or not isinstance(p.get('route'),list) or len(p['route'])>64 or any(n not in dg_rpg.PLACE_NAMES for n in p['route']) or type(p.get('next')) is not int:raise ValueError('Invalid NPC travel')
    for p in v['plans']+v['history']:
        if not isinstance(p,dict) or p.get('status') not in ('planned','meeting','done','missed') or p.get('place') not in dg_rpg.PLACE_NAMES or not isinstance(p.get('pair'),list) or len(p['pair'])!=2 or any(w not in PEERS for w in p['pair']) or type(p.get('progress')) is not int:raise ValueError('Invalid NPC appointment')
