# -*- coding: utf-8 -*-
"""Dependent shared projects with owned items and distinct contributions."""
from __future__ import unicode_literals
import copy,re
# key, title, (kind, place, item, target, required, eligible NPCs)
DEFINITIONS={
 'concert':{'title':u'Новый номер для лагеря','arc':'festival','steps':[
  ('read','library','notes',None,1,('un','mz')),
  ('help','music','notes','mi',1,()),
  ('music','music',None,None,2,('mi','dv','us')),
  ('organize','stage',None,None,2,('mi','dv','sl'))]},
 'radio':{'title':u'Лагерный радиоэфир','arc':'radio','steps':[
  ('explore','warehouse','parts',None,1,('el','sh')),
  ('help','clubs','parts','sh',1,()),
  ('repair','clubs',None,None,2,('el','sh')),
  ('organize','radio',None,None,2,('mz','el','sh'))]}}
CAPTIONS={('concert',0):u'Найти ноты в библиотеке',('concert',1):u'Передать ноты Мику в кружке',('concert',2):u'Порепетировать общий номер',('concert',3):u'Выступить с общим номером',
 ('radio',0):u'Найти детали в хозяйственном дворе',('radio',1):u'Передать детали Шурику в клубах',('radio',2):u'Собрать радиооборудование',('radio',3):u'Провести лагерный радиоэфир'}
ITEMS={'notes':u'Ноты общего номера','parts':u'Детали радиооборудования'}

def ensure(state):
    system=state.setdefault('projects',{'records':{},'inventory':{},'npc_inventory':{}})
    for key in DEFINITIONS:
        system['records'].setdefault(key,{'stage':0,'contributions':{},'history':[]})
    return system

def report(state):
    return copy.deepcopy(state.get('projects',{}))

def step(state,key):
    record=state.get('projects',{}).get('records',{}).get(key,{'stage':0})
    index=record['stage']
    return (index,DEFINITIONS[key]['steps'][index]) if index<4 else (index,None)

def pouch(system,actor):
    return system['inventory'] if actor=='hero' else system['npc_inventory'].setdefault(actor,{})

def _contribute(state,key,actor):
    system=ensure(state);record=system['records'][key];index,spec=step(state,key)
    kind,place,item,target,required,eligible=spec
    bag=pouch(system,actor)
    if index==0:
        if actor in record['contributions'].get(str(index),[]): return False
        bag[item]=bag.get(item,0)+1
    elif index==1:
        if bag.get(item,0)<1: return False
        import dg_rpg
        if dg_rpg.where_is(state,target)!=place: return False
        bag[item]-=1
    people=record['contributions'].setdefault(str(index),[])
    if actor in people: return False
    people.append(actor)
    record['history'].append({'stage':index,'actor':actor,'day':state['day'],'place':place})
    record['history']=record['history'][-24:]
    if len(people)>=required:
        record['stage']+=1
        if record['stage']==4:
            import dg_world
            world=dg_world.ensure(state)
            world['preparations'][DEFINITIONS[key]['arc']]=dg_world.clamp(world['preparations'].get(DEFINITIONS[key]['arc'],0)+8)
    if actor=='hero':
        __import__('dg_relationships').contributed(state,key,index)
    return True

def available(state):
    import dg_rpg
    rows=[];system=state.get('projects',{})
    for key in sorted(DEFINITIONS):
        index,spec=step(state,key)
        if spec is None: continue
        kind,place,item,target,required,eligible=spec
        contributors=system.get('records',{}).get(key,{}).get('contributions',{}).get(str(index),[])
        rows.append({'project':key,'stage':index,'caption':CAPTIONS[(key,index)],'place':place,'target':target,
                     'ready':state['place']==place and 'hero' not in contributors and (index!=1 or (system.get('inventory',{}).get(item,0)>0 and dg_rpg.where_is(state,target)==place)),
                     'progress':len(contributors),'required':required})
    return rows

def parse(state,text):
    # Exact visible action captions are supported; promises/negations cannot be grants.
    if isinstance(text,bytes):text=text.decode("utf-8")
    value=text.strip().rstrip('.!').lower()
    return next((row for row in available(state) if row['caption'].lower()==value),None)

def act(state,key):
    row=next((x for x in available(state) if x['project']==key),None)
    if not row or not row['ready'] or state['finished'] or state['energy']<8: raise ValueError(u'Шаг пока недоступен: проверь место, предметы, участников и силы.')
    if not _contribute(state,key,'hero'): raise ValueError(u'Этот вклад уже учтён.')
    state['energy']-=8
    record=state['projects']['records'][key]
    text=row['caption']+u'. Твой вклад подтверждён. '+(u'Проект завершён.' if record['stage']==4 else u'Следующие этапы выполняются отдельно; вклад других участников ещё может потребоваться.')
    import dg_rpg
    dg_rpg._journal(state,text);dg_rpg._tick(state)
    return {'status':'done','title':DEFINITIONS[key]['title'],'text':text,'who':row['target'],'kind':'project','project':key}

def offer_goal(state,who):
    system=ensure(state)
    for key in sorted(DEFINITIONS):
        index,spec=step(state,key)
        if spec is None: continue
        kind,place,item,target,required,eligible=spec
        bag=system['npc_inventory'].get(who,{})
        if index==1:
            if target==who and bag.get(item,0)<1:
                return {'kind':'music' if key=='concert' else 'repair','place':place,'arc':DEFINITIONS[key]['arc'],'title':u'Дождаться материалов для общего дела','project':key,'project_stage':index,'project_role':'recipient'}
            if bag.get(item,0)<1: continue
        elif who not in eligible: continue
        if who in system['records'][key]['contributions'].get(str(index),[]): continue
        return {'kind':kind,'place':place,'arc':DEFINITIONS[key]['arc'],'title':CAPTIONS[(key,index)],'project':key,'project_stage':index}
    return None

def npc_complete(state,who,goal):
    key=goal.get('project')
    if key not in DEFINITIONS: return True
    index,spec=step(state,key)
    if spec is None or index!=goal.get('project_stage'): return True
    if goal['place']!=spec[1] or goal.get('project_role')=='recipient': return False
    return _contribute(state,key,who)

def validate(state):
    system=state.get('projects')
    if system is None: return
    import dg_rpg
    if not isinstance(system,dict) or not isinstance(system.get('records'),dict) or set(system['records'])!=set(DEFINITIONS) or not isinstance(system.get('npc_inventory'),dict) or any(who not in dg_rpg.NPC_NAMES for who in system['npc_inventory']): raise ValueError('Invalid projects')
    for bag in [system.get('inventory')]+list(system['npc_inventory'].values()):
        if not isinstance(bag,dict) or any(item not in ITEMS or not isinstance(n,int) or isinstance(n,bool) or not 0<=n<=3 for item,n in bag.items()): raise ValueError('Invalid project inventory')
    for key,row in system['records'].items():
        if not isinstance(row,dict) or not isinstance(row.get('stage'),int) or not 0<=row['stage']<=4 or not isinstance(row.get('contributions'),dict) or not isinstance(row.get('history'),list) or len(row['history'])>24: raise ValueError('Invalid project record')
        for index,people in row['contributions'].items():
            if index not in ('0','1','2','3') or not isinstance(people,list) or len(people)>11 or any(who not in tuple(dg_rpg.NPC_NAMES)+('hero',) for who in people) or len(set(people))!=len(people): raise ValueError('Invalid project contributions')

        if isinstance(row['stage'],bool):raise ValueError('Invalid project stage type')
        for index in range(4):
            people=row['contributions'].get(str(index),[])
            required=DEFINITIONS[key]['steps'][index][4]
            if len(people)>required or (index<row['stage'] and len(people)!=required) or (index>row['stage'] and people):raise ValueError('Broken project dependency')
        for event in row['history']:
            if not isinstance(event,dict) or event.get('stage') not in (0,1,2,3) or event.get('actor') not in tuple(dg_rpg.NPC_NAMES)+('hero',) or not isinstance(event.get('day'),int) or not 1<=event['day']<=50000 or event.get('place')!=DEFINITIONS[key]['steps'][event['stage']][1]:raise ValueError('Invalid project history')


def meetings(state):
    # A courier and recipient can finish the handover when their plans overlap,
    # even if their individual work ticks fall on different turns.
    import dg_rpg,dg_agents
    system=state.get('projects')
    if not system:return
    for key in sorted(DEFINITIONS):
        index,spec=step(state,key)
        if index!=1:continue
        kind,place,item,target,required,eligible=spec
        if dg_rpg.where_is(state,target)!=place:continue
        for who,bag in sorted(system['npc_inventory'].items()):
            person=state.get('npc_agendas',{}).get('people',{}).get(who,{})
            goal=person.get('goal',{})
            if (bag.get(item,0)<1 or goal.get('project')!=key or goal.get('project_stage')!=1 or goal.get('progress',0)<2 or dg_rpg.where_is(state,who)!=place):continue
            person['energy']=max(0,person['energy']-4)
            goal['progress']=goal['required']
            dg_agents._complete(state,who,person)
            recipient=state['npc_agendas']['people'].get(target)
            if recipient and recipient['goal'].get('project')==key and recipient['goal'].get('project_role')=='recipient':
                recipient['goal']['progress']=recipient['goal']['required']
                dg_agents._complete(state,target,recipient)
            break
