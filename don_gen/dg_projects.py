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
ITEMS=dict((key,value['title']) for key,value in __import__('dg_inventory').CATALOG.items())

def ensure(state):
    system=state.setdefault('projects',{'records':{},'inventory':{},'npc_inventory':{}})
    for key in definitions(state):
        system['records'].setdefault(key,{'stage':0,'contributions':{},'history':[]})
    return system

def report(state):
    return copy.deepcopy(state.get('projects',{}))

def step(state,key):
    record=state.get('projects',{}).get('records',{}).get(key,{'stage':0})
    index=record['stage']
    return (index,definitions(state)[key]['steps'][index]) if index<4 and not record.get('cancelled') else (index,None)

def pouch(system,actor):
    return system['inventory'] if actor=='hero' else system['npc_inventory'].setdefault(actor,{})

def _contribute(state,key,actor,resource_owned=False):
    system=ensure(state);record=system['records'][key];index,spec=step(state,key)
    kind,place,item,target,required,eligible=spec
    if not can_contribute(state,key,actor):return False
    bag=pouch(system,actor)
    if index==0:
        if actor in record['contributions'].get(str(index),[]): return False
        if not resource_owned:
            try:__import__('dg_inventory').take(state,actor,item,place)
            except ValueError:return False
        elif bag.get(item,0)<1:return False
    elif index==1:
        if bag.get(item,0)<=__import__('dg_inventory').borrowed_count(state,actor,item): return False
        import dg_rpg
        if dg_rpg.where_is(state,target)!=place: return False
        bag[item]-=1
        record.setdefault('materials',{})[item]=record.get('materials',{}).get(item,0)+1
        __import__('dg_inventory').log(state,'commit',item,actor,key)
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
            world['preparations'][definitions(state)[key]['arc']]=dg_world.clamp(world['preparations'].get(definitions(state)[key]['arc'],0)+8)
    if actor=='hero':
        __import__('dg_relationships').contributed(state,key,index)
    return True

def player_knows_project(state,key):
    camp=__import__('dg_camp')
    if not camp.enabled(state):return True
    if camp.in_intro(state):return False
    blueprint=state.get('projects',{}).get('blueprints',{}).get(key)
    people=blueprint['participants'] if blueprint else [definitions(state)[key]['steps'][1][3]]
    return all(who is None or camp.stage(state,who) in ('friend','close','romance') for who in people)


def available(state):
    if __import__("dg_camp").in_intro(state):return []
    import dg_rpg
    rows=[];system=state.get('projects',{})
    for key in sorted(definitions(state)):
        if not player_knows_project(state,key):continue
        index,spec=step(state,key)
        if spec is None: continue
        kind,place,item,target,required,eligible=spec
        contributors=system.get('records',{}).get(key,{}).get('contributions',{}).get(str(index),[])
        rows.append({'project':key,'stage':index,'caption':caption(state,key,index),'place':place,'target':target,
                     'ready':state['place']==place and (index!=0 or __import__('dg_inventory').stock_at(state,place).get(item,0)>0) and can_contribute(state,key,'hero') and 'hero' not in contributors and (index!=1 or (system.get('inventory',{}).get(item,0)>0 and dg_rpg.where_is(state,target)==place)),
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
    return {'status':'done','title':definitions(state)[key]['title'],'text':text,'who':row['target'],'kind':'project','project':key}

def offer_goal(state,who):
    system=ensure(state)
    for key in sorted(definitions(state)):
        index,spec=step(state,key)
        if spec is None: continue
        kind,place,item,target,required,eligible=spec
        bag=system['npc_inventory'].get(who,{})
        if index==1:
            if target==who and bag.get(item,0)<1:
                return {'kind':definitions(state)[key]['steps'][2][0],'place':place,'arc':definitions(state)[key]['arc'],'title':u'Дождаться материалов для общего дела','project':key,'project_stage':index,'project_role':'recipient'}
            if bag.get(item,0)<1: continue
        elif who not in eligible: continue
        if who in system['records'][key]['contributions'].get(str(index),[]) or not can_contribute(state,key,who): continue
        if kind=='music' and who not in ('mi','dv','us'):kind='help'
        if kind=='repair' and who not in ('el','sh'):kind='help'
        return {'kind':kind,'place':place,'arc':definitions(state)[key]['arc'],'title':caption(state,key,index),'project':key,'project_stage':index}
    return None

def npc_complete(state,who,goal):
    key=goal.get('project')
    if key not in definitions(state): return True
    index,spec=step(state,key)
    if spec is None or index!=goal.get('project_stage'): return True
    if goal['place']!=spec[1] or goal.get('project_role')=='recipient': return False
    if who in state['projects']['records'][key]['contributions'].get(str(index),[]):return True
    return _contribute(state,key,who)

def validate(state):
    system=state.get('projects')
    if system is None: return
    import dg_rpg
    if not isinstance(system,dict) or not isinstance(system.get('records'),dict) or set(system['records'])!=set(definitions(state)) or not isinstance(system.get('npc_inventory'),dict) or any(who not in dg_rpg.NPC_NAMES for who in system['npc_inventory']): raise ValueError('Invalid projects')
    for bag in [system.get('inventory')]+list(system['npc_inventory'].values()):
        if not isinstance(bag,dict) or any(item not in ITEMS or not isinstance(n,int) or isinstance(n,bool) or not 0<=n<=3 for item,n in bag.items()): raise ValueError('Invalid project inventory')
    for key,row in system['records'].items():
        if not isinstance(row,dict) or not isinstance(row.get('stage'),int) or not 0<=row['stage']<=4 or not isinstance(row.get('contributions'),dict) or not isinstance(row.get('history'),list) or len(row['history'])>24: raise ValueError('Invalid project record')
        for index,people in row['contributions'].items():
            if index not in ('0','1','2','3') or not isinstance(people,list) or len(people)>11 or any(who not in tuple(dg_rpg.NPC_NAMES)+('hero',) for who in people) or len(set(people))!=len(people): raise ValueError('Invalid project contributions')

        if isinstance(row['stage'],bool):raise ValueError('Invalid project stage type')
        for index in range(4):
            people=row['contributions'].get(str(index),[])
            required=definitions(state)[key]['steps'][index][4]
            if len(people)>required or (index<row['stage'] and len(people)!=required) or (index>row['stage'] and people):raise ValueError('Broken project dependency')
        for event in row['history']:
            if not isinstance(event,dict) or event.get('stage') not in (0,1,2,3) or event.get('actor') not in tuple(dg_rpg.NPC_NAMES)+('hero',) or not isinstance(event.get('day'),int) or not 1<=event['day']<=50000 or event.get('place')!=definitions(state)[key]['steps'][event['stage']][1]:raise ValueError('Invalid project history')


def meetings(state):
    # A courier and recipient can finish the handover when their plans overlap,
    # even if their individual work ticks fall on different turns.
    import dg_rpg,dg_agents
    system=state.get('projects')
    if not system:return
    for key in sorted(definitions(state)):
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


PUBLIC_PLACES=('square','music','clubs','library','stage','radio','canteen','forest_path','campfire','sports','infirmary','storage','warehouse')

def check_blueprint(value):
    import dg_rpg,dg_inventory
    required=set(('title','item','recipient','work_place','final_place','theme','participants'))
    if not isinstance(value,dict) or set(value) not in (required,required|set(('activity',))):raise ValueError(u'Неверный формат проекта.')
    title=value['title']
    if not isinstance(title,(str,type(u''))) or not 5<=len(title)<=80 or any(ord(c)<32 for c in title) or any(c in title for c in '[]{}'):raise ValueError(u'Название должно быть коротким обычным текстом.')
    if not isinstance(value['item'],(str,type(u''))) or value['item'] not in dg_inventory.CATALOG or not dg_inventory.CATALOG[value['item']]['source']:raise ValueError(u'Для проекта нужен известный материал с реальным источником.')
    if not isinstance(value['recipient'],(str,type(u''))) or value['recipient'] not in dg_rpg.NPC_NAMES or value['recipient']=='uv' or value['theme'] not in ('festival','radio','lake','council'):raise ValueError(u'Неизвестный участник или направление.')
    if value['work_place'] not in PUBLIC_PLACES or value['final_place'] not in PUBLIC_PLACES:raise ValueError(u'Место проекта недоступно.')
    people=value['participants']
    if not isinstance(people,list) or not 2<=len(people)<=4 or any(not isinstance(who,(str,type(u''))) or who not in dg_rpg.NPC_NAMES or who=='uv' for who in people) or len(set(people))!=len(people) or value['recipient'] not in people:raise ValueError(u'Нужно 2–4 известных участника, включая получателя материалов.')
    activity=value.get('activity',{'festival':'music','radio':'repair','lake':'explore','council':'organize'}[value['theme']])
    if activity not in ('music','repair','read','explore','organize','help'):raise ValueError(u'Неизвестный вид работы.')
    experts={'music':('mi','dv','us'),'repair':('el','sh')}
    if activity in experts and not set(people).intersection(experts[activity]):raise ValueError(u'Для этого направления нужен участник с соответствующими навыками.')
    result=copy.deepcopy(value);result['activity']=activity
    return result

def compile_blueprint(value):
    value=check_blueprint(value)
    import dg_inventory
    kind=value['activity']
    return {'title':value['title'],'arc':value['theme'],'steps':[
      ('explore',dg_inventory.CATALOG[value['item']]['source'],value['item'],None,1,tuple(value['participants'])),
      ('help',value['work_place'],value['item'],value['recipient'],1,()),
      (kind,value['work_place'],None,None,2,tuple(value['participants'])),
      ('organize',value['final_place'],None,None,2,tuple(value['participants']))]}

def definitions(state):
    result=dict(DEFINITIONS)
    blueprints=state.get('projects',{}).get('blueprints',{})
    if not isinstance(blueprints,dict) or len(blueprints)>12:raise ValueError('Invalid project blueprints')
    for key,value in blueprints.items():
        if not isinstance(key,(str,type(u''))) or not re.match(r'^custom_[a-f0-9]{16}$',key):raise ValueError('Invalid project identifier')
        result[key]=compile_blueprint(value)
    return result

def caption(state,key,index):
    if key in DEFINITIONS:return CAPTIONS[(key,index)]
    import dg_rpg
    blueprint=state['projects']['blueprints'][key]
    verbs=[u'Получить '+ITEMS[blueprint['item']],u'Передать материалы: '+dg_rpg.NPC_NAMES[blueprint['recipient']],u'Подготовить общее дело',u'Завершить общее дело']
    return verbs[index]+u' · '+blueprint['title']

def register(state,value):
    if __import__("dg_camp").in_intro(state):raise ValueError(u"Сначала знакомство с лагерем, обходной лист и выбор кружка.")
    import hashlib,json,dg_inventory
    value=check_blueprint(value)
    if __import__("dg_camp").enabled(state) and any(__import__("dg_camp").stage(state,who) not in ("friend","close","romance") for who in value["participants"]):raise ValueError(u"Для общего проекта сначала познакомься и подружись с участниками.")
    system=ensure(state)
    current=system.get('blueprints',{})
    if len(current)>=12 or len([row for key,row in system['records'].items() if key.startswith('custom_') and row['stage']<4 and not row.get('cancelled')])>=4:raise ValueError(u'Сначала заверши или отмени активные проекты.')
    key='custom_'+hashlib.sha256(json.dumps(value,ensure_ascii=True,sort_keys=True).encode('utf-8')).hexdigest()[:16]
    if key in definitions(state):raise ValueError(u'Такой проект уже зарегистрирован.')
    item=value['item'];stock=dg_inventory.stock_at(state,dg_inventory.CATALOG[item]['source']).get(item,0)
    holders=['hero']+list(system['npc_inventory'])
    owned=any(dg_inventory.free_count(state,actor,item)>0 for actor in holders)
    waiting=sum(1 for other,row in system['records'].items() if row['stage']==0 and not row.get('cancelled') and definitions(state)[other]['steps'][0][2]==item)
    if stock<=waiting and not owned:raise ValueError(u'Материал исчерпан или закреплён за другим делом. Выбери другой предмет.')
    system.setdefault('blueprints',{})[key]=value
    system['records'][key]={'stage':0,'contributions':{},'history':[]}
    # Already owned material can be pledged without magically finding it again.
    if owned:
        owner=next(actor for actor in holders if dg_inventory.free_count(state,actor,item)>0)
        _contribute(state,key,owner,resource_owned=True)
    return key

def claim_resource(state,actor,item,place):
    for key in sorted(definitions(state)):
        index,spec=step(state,key)
        if index==0 and spec[1]==place and spec[2]==item:
            _contribute(state,key,actor,resource_owned=True)
            return key
    return None

def cancel(state,key):
    if key not in definitions(state):raise ValueError('Unknown project')
    system=ensure(state);row=system['records'][key]
    if row['stage']==4 or row.get('cancelled'):raise ValueError(u'Проект уже закрыт.')
    row['cancelled']=True
    for person in state.get('npc_agendas',{}).get('people',{}).values():
        if person['goal'].get('project')==key and person['goal']['status'] in ('working','blocked'):
            person['goal']['status']='abandoned';person['active']=False
    for promise in state.get('relationships',{}).get('promises',[]):
        if promise['project']==key and promise['status']=='open':promise['status']='cancelled'
    return u'Проект отменён. Неиспользованные предметы остаются у владельцев; уже вложенные материалы не возникают заново.'


def can_contribute(state,key,actor):
    if actor=="hero" and not player_knows_project(state,key):return False
    index,spec=step(state,key)
    if spec is None:return False
    people=state.get('projects',{}).get('records',{}).get(key,{}).get('contributions',{}).get(str(index),[])
    if actor in people:return False
    activity=definitions(state)[key]['steps'][2][0]
    experts={'music':('mi','dv','us'),'repair':('el','sh')}.get(activity,())
    if index==2 and experts and not set(people).intersection(experts) and len(people)>=spec[4]-1 and actor not in experts:return False
    return True
