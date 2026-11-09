# -*- coding: utf-8 -*-
"""Bounded NPC-initiated visits and encounters along explicit camp routes."""
from __future__ import unicode_literals
import copy,hashlib
PUBLIC=('gate','square','cabins','cabins_south','canteen','library','clubs','music','stage','sports','beach','lake','forest','forest_path','infirmary')
EDGES=(('gate','clubs'),('clubs','square'),('square','cabins'),('cabins','music'),('music','stage'),('square','canteen'),('square','library'),('square','infirmary'),('square','sports'),('canteen','cabins_south'),('cabins_south','beach'),('beach','lake'),('cabins','forest_path'),('forest_path','forest'),('parking','gate'),('clubhouse','clubs'),('administration','square'),('headquarters','administration'),('radio','clubs'),('washrooms','cabins'),('showers','square'),('laundry','showers'),('kitchen','canteen'),('canteen_veranda','canteen'),('storage','canteen'),('warehouse','storage'),('volleyball','sports'),('football','sports'),('badminton','sports'),('gym','sports'),('beachhouse','beach'),('pier','beach'),('boathouse','pier'),('campfire','forest_path'),('old_camp','forest'))
ROMANTIC=('mi','dv','un','sl','mz','el','sh','mt','cs')

def moment(state): return (state['day']-1)*4+state['slot']

def ensure(state):
    return state.setdefault('npc_visits',{'active':None,'history':[],'cooldowns':{},'last_turn':None,'last_offer':-10,'romance':[]})

def route(start,end):
    import dg_rpg
    if start not in dg_rpg.PLACE_NAMES or end not in dg_rpg.PLACE_NAMES: return []
    if start==end: return [start]
    graph={}
    for a,b in EDGES:
        graph.setdefault(a,[]).append(b);graph.setdefault(b,[]).append(a)
    for n in range(1,32):
        cabin='cabin_%02d'%n;zone='cabins' if n<18 else 'cabins_south'
        graph.setdefault(cabin,[]).append(zone);graph.setdefault(zone,[]).append(cabin)
    queue=[[start]];seen=set((start,))
    for path in queue:
        for node in graph.get(path[-1],[]):
            if node==end: return path+[node]
            if node not in seen: seen.add(node);queue.append(path+[node])
    return []

def busy(state,who):
    incident=state.get('social',{}).get('incident')
    if incident and incident.get('status')=='open' and incident.get('day')==state['day'] and who in incident.get('pair',[]): return True
    event=state.get('world',{}).get('event') or {}
    return event.get('day')==state['day'] and event.get('npc')==who

def _log(state,event,status):
    system=ensure(state)
    system['history'].append({'id':event['id'],'who':event['who'],'kind':event['kind'],'day':state['day'],'slot':state['slot'],'place':event.get('place') or state['place'],'status':status})
    system['history']=system['history'][-64:]

def current(state):
    event=state.get('npc_visits',{}).get('active')
    return copy.deepcopy(event) if event and event['moment']==moment(state) and event['status']=='arrived' and event['place']==state['place'] and not busy(state,event['who']) and not state.get('finished') else None

def arrive(state):
    event=state.get('npc_visits',{}).get('active')
    if not event or event['moment']!=moment(state) or event['status']!='travelling' or state['place'] not in event['route'] or busy(state,event['who']): return None
    # Never interrupt someone inside another NPC's private cabin.
    home=(state.get('housing') or {}).get('cabin')
    if state['place'].startswith('cabin_') and state['place']!=home: return None
    event.update(status='arrived',place=state['place'])
    _log(state,event,'arrived')
    return copy.deepcopy(event)

def location(state,who):
    event=state.get('npc_visits',{}).get('active')
    if event and event['who']==who and event['moment']==moment(state) and event['status'] in ('arrived','departing') and not busy(state,who): return event['place']
    return None

def tick(state,previous):
    import dg_rpg
    system=ensure(state);now=moment(state)
    if system['last_turn']==now: return
    system['last_turn']=now
    if system['active']:
        if system['active']['status']!='departing': _log(state,system['active'],'expired')
        system['active']=None
    if state.get('finished') or state['slot']==3 or now-system['last_offer']<2: return
    candidates=[]
    for who in sorted(dg_rpg.NPC_NAMES):
        if who=='uv' or busy(state,who) or now-system['cooldowns'].get(who,-10)<4: continue
        start=previous.get(who) or dg_rpg.where_is(state,who)
        person=state.get('npc_agendas',{}).get('people',{}).get(who,{})
        goal=person.get('goal',{})
        affinity=state['affinity'][who]
        kind=None;destination=None
        if goal.get('status')=='blocked': kind='help';destination=goal['place']
        elif affinity>=45 and who in state.get('met',[]): kind='visit';destination=state['place']
        if not kind or person.get('energy',80)<15: continue
        import dg_world
        if dg_world.weather(state)[0]=='rain' and destination in ('forest','forest_path','beach','lake','stage','sports'): continue
        if destination.startswith('cabin_'):
            if destination!=(state.get('housing') or {}).get('cabin') or affinity<70: continue
        elif destination not in PUBLIC and destination not in dict(EDGES) and destination not in [b for a,b in EDGES]: continue
        path=route(start,destination)
        if not path: continue
        priority=(20 if who in system['romance'] else 10 if affinity>=70 else 0)+(15 if kind=='help' else 0)
        salt=int(hashlib.sha1(('%s:%s:%s'%(state['id'],now,who)).encode('ascii')).hexdigest()[:8],16)
        candidates.append((-priority,salt,who,kind,path,goal.get('id')))
    if not candidates: return
    unused,unused2,who,kind,path,goal_id=sorted(candidates)[0]
    event={'id':'%s:%s'%(now,who),'moment':now,'who':who,'kind':kind,'route':path,'from':path[0],'destination':path[-1],
           'place':None,'status':'travelling','seen':False,'goal_id':goal_id}
    system['active']=event;system['cooldowns'][who]=now;system['last_offer']=now
    arrive(state)

def opening(state,event):
    import dg_rpg
    name=dg_rpg.NPC_NAMES[event['who']]
    if event['kind']=='help':
        approach=u'встречает тебя по пути по лагерю' if len(event['route'])>1 else u'замечает тебя рядом и подходит поговорить'
        return u'%s %s и просит обсудить затруднение в своём деле. Работа ещё не выполнена; сначала нужно понять, что мешает.'%(name,approach)
    return (u'%s сам находит тебя и предлагает побыть вместе. '%name+
            (u'Вы уже договорились о романтических отношениях; это приглашение на спокойное свидание.' if event['who'] in state.get('npc_visits',{}).get('romance',[]) else u'Близость не означает автоматически романтических отношений. Ты можешь принять приглашение или отказаться.'))

def choices(state,event):
    rows=[('accept',u'Обсудить проблему вместе' if event['kind']=='help' else u'Провести время вместе')]
    if event['kind']=='visit' and state['affinity'][event['who']]>=70 and event['who'] in ROMANTIC and event['who'] not in state['npc_visits']['romance']:
        rows.append(('date',u'Начать романтические отношения и провести свидание'))
    return rows+[('later',u'Поговорить чуть позже'),('decline',u'Вежливо отказаться')]

def respond(state,key):
    import dg_rpg,dg_world
    event=current(state)
    if not event or key not in [row[0] for row in choices(state,event)]: raise ValueError('Encounter unavailable')
    system=ensure(state);who=event['who']
    if key=='later':
        system['active']['seen']=True
        return {'who':who,'text':u'Ты предложил вернуться к разговору позже в этот период дня.','title':u'Разговор отложен'}
    if key=='decline':
        _log(state,event,'declined');system['active']['status']='departing'
        return {'who':who,'text':u'Ты вежливо отказался. Отношения не изменились.','title':u'Приглашение отклонено'}
    if state['energy']<8: raise ValueError('Для встречи нужно 8 энергии')
    state['energy']-=8
    person=state.get('npc_agendas',{}).get('people',{}).get(who)
    if person: person['energy']=max(0,person['energy']-8)
    if key=='date': system['romance'].append(who)
    if event['kind']=='help':
        person=state.get('npc_agendas',{}).get('people',{}).get(who,{})
        goal=person.get('goal',{})
        if goal.get('id')==event['goal_id'] and goal.get('status')=='blocked': goal.update(status='working',blocked_turns=0)
        text=u'Вы обсудили затруднение и наметили следующий шаг. Само поручение ещё не выполнено; работа продолжится в нужном месте.'
    else: text=u'Вы провели время вместе по взаимному согласию.'+(u' Вы по взаимному согласию начали романтические отношения и провели спокойное свидание.' if key=='date' else '')
    state['affinity'][who]=dg_world.clamp(state['affinity'][who]+3)
    _log(state,event,'accepted');system['active']=None
    dg_rpg._journal(state,dg_rpg.NPC_NAMES[who]+u': '+text)
    dg_rpg._tick(state)
    return {'who':who,'title':u'Встреча по инициативе персонажа','text':text}

def validate(state):
    system=state.get('npc_visits')
    if system is None: return
    import dg_rpg
    if not isinstance(system,dict) or not isinstance(system.get('history'),list) or len(system['history'])>64 or not isinstance(system.get('cooldowns'),dict) or len(system['cooldowns'])>11 or not isinstance(system.get('romance'),list) or len(set(system['romance']))!=len(system['romance']) or any(who not in ROMANTIC for who in system['romance']): raise ValueError('Invalid NPC visits')
    for key in ('last_turn','last_offer'):
        value=system.get(key)
        if value is not None and (not isinstance(value,int) or isinstance(value,bool) or not -10<=value<=50000): raise ValueError('Invalid encounter clock')
    for who,value in system['cooldowns'].items():
        if who not in dg_rpg.NPC_NAMES or not isinstance(value,int) or isinstance(value,bool) or not 0<=value<=50000: raise ValueError('Invalid visit cooldown')
    event=system.get('active')
    if event:
        if (not isinstance(event,dict) or event.get('who') not in dg_rpg.NPC_NAMES or event.get('who')=='uv' or event.get('kind') not in ('help','visit') or event.get('status') not in ('travelling','arrived','departing') or not isinstance(event.get('moment'),int) or not isinstance(event.get('seen'),bool) or not isinstance(event.get('route'),list) or not 1<=len(event['route'])<=40 or any(p not in dg_rpg.PLACE_NAMES for p in event['route']) or event.get('place') not in tuple(dg_rpg.PLACE_NAMES)+(None,) or event.get('moment')<0 or event.get('moment')>50000 or not isinstance(event.get('id'),(str,type(u''))) or len(event['id'])>100 or (event.get('status') in ('arrived','departing') and event.get('place') not in event['route']) or event.get('destination')!=event['route'][-1] or event.get('from')!=event['route'][0]): raise ValueError('Invalid active visit')

    for row in system['history']:
        if (not isinstance(row,dict) or row.get('who') not in dg_rpg.NPC_NAMES or row.get('kind') not in ('visit','help') or row.get('status') not in ('arrived','expired','accepted','declined') or row.get('place') not in dg_rpg.PLACE_NAMES or not isinstance(row.get('day'),int) or row['day']<1 or row.get('slot') not in (0,1,2,3) or not isinstance(row.get('id'),(str,type(u''))) or len(row['id'])>100): raise ValueError('Invalid visit history')
