# -*- coding: utf-8 -*-
"""Grounded object affordances. The model selects a rule, never its effects."""
from __future__ import unicode_literals
import copy,re

# id: title, locations, recognition stems, available verbs, materials/tools.
OBJECTS={
 'benches':(u'скамейки',('square','gate','cabins','lake'),(u'скам',u'лавоч'),('inspect','clean','repair')),
 'paths':(u'дорожки',('square','cabins','forest_path'),(u'дорож',u'тропин',u'мусор'),('inspect','clean')),
 'shelves':(u'книжные полки',('library',),(u'полк',u'стеллаж'),('inspect','clean','organize')),
 'stage':(u'площадку сцены',('stage','outdoor_stage'),(u'площадк',u'сцен'),('inspect','clean','organize')),
 'tables':(u'столы',('canteen','clubs'),(u'стол',),('inspect','clean','repair')),
 'instrument':(u'музыкальный инструмент кружка',('music',),(u'гитар',u'пианин',u'инструмент'),('inspect','practice')),
 'court':(u'спортивную площадку',('sports',),(u'спортплощад',u'мяч',u'площадк'),('inspect','clean','practice')),
 'workbench':(u'рабочее место мастерской',('clubs',),(u'верстак',u'рабочее место'),('inspect','clean','organize'))}
VERBS={'inspect':(u'осмотр',u'осматр',u'провер',u'изуч'),
       'clean':(u'убра',u'убер',u'убира',u'очист',u'почист',u'вытер',u'вытир'),
       'repair':(u'почин',u'ремонт',u'отремонт'),
       'organize':(u'разлож',u'расстав',u'упорядоч',u'подготов'),
       'practice':(u'потренир',u'тренир',u'порепетир',u'репетир',u'поигра')}
LABELS={'inspect':u'Осмотреть','clean':u'Убрать','repair':u'Починить','organize':u'Привести в порядок','practice':u'Потренироваться: '}
DURATION={'inspect':10,'clean':20,'repair':30,'organize':20,'practice':25}
COST={'inspect':3,'clean':8,'repair':10,'organize':6,'practice':9}

def ensure(state):return state.setdefault('affordances',{'objects':{},'done':{},'records':[]})

def definitions(state):
    rows=[]
    for obj,(title,places,words,verbs) in sorted(OBJECTS.items()):
        if state['place'] not in places:continue
        for verb in verbs:
            key=verb+':'+obj+':'+state['place']
            rows.append({'key':key,'title':LABELS[verb]+('' if verb=='practice' else ' ')+title,
                         'place':state['place'],'who':None,'minutes':DURATION[verb],
                         'verb':verb,'object':obj,'cost':COST[verb]})
    return rows

def reason(state,row):
    if 'camp_life' not in state:return u'Нужен режим лагерного распорядка.'
    if state['finished']:return u'Смена закончилась.'
    if state['camp_life']['arrival']<4:return u'Сначала заверши знакомство с лагерем.'
    if state.get('affordances',{}).get('done',{}).get(row['key'])==state['day']:return u'Сегодня это уже сделано.'
    if state['energy']<row['cost']:return u'Недостаточно сил.'
    if row['verb'] in ('clean','repair','practice') and __import__('dg_risk').injured(state):return u'Нагрузка пока противопоказана.'
    if state['slot']==3:return u'Ночью это дело стоит отложить.'
    if row['verb']=='repair':
        inventory=__import__('dg_inventory');shadow=copy.deepcopy(state);inventory.ensure(shadow)
        if inventory.free_count(shadow,'hero','toolkit')<1 or inventory.free_count(shadow,'hero','tape')<1:
            return u'Нужны свободные набор инструментов и изолента; вещи общего проекта использовать нельзя.'
    if row['object']=='instrument' and row['verb']=='practice' and state['camp_life']['club']!='music':
        return u'Для самостоятельного занятия сначала вступи в музыкальный кружок.'
    return None

def available(state,include_blocked=False):
    rows=[]
    for row in definitions(state):
        why=reason(state,row);row.update(ready=why is None,reason=why or '',story=u'Конкретный поступок с объектом лагеря; без автоматического завершения чужих заданий.')
        if include_blocked or not why:rows.append(row)
    return rows

def parse(state,text):
    text=text.strip().lower().rstrip('.!')
    rows=definitions(state)
    exact=next((r for r in rows if r['title'].lower()==text),None)
    if exact:return exact
    if re.search(u'\\b(?:не|если|потом|затем|завтра|обещаю|планирую)\\b',text):return None
    verbs=[v for v,stems in VERBS.items() if any(w in text for w in stems)]
    objects=[o for o,spec in OBJECTS.items() if any(w in text for w in spec[2])]
    if len(verbs)!=1 or len(objects)!=1:return None
    return next((r for r in rows if r['verb']==verbs[0] and r['object']==objects[0]),None)

def recognizes(text):
    text=text.lower()
    return (not re.search(u'\\b(?:не|если|потом|затем|завтра|обещаю|планирую)\\b',text)
            and any(any(w in text for w in spec[2]) for spec in OBJECTS.values())
            and any(any(w in text for w in stems) for stems in VERBS.values()))

def act(state,key):
    row=next((r for r in definitions(state) if r['key']==key),None)
    if not row:raise ValueError(u'Уточни объект и место действия.')
    why=reason(state,row)
    if why:raise ValueError(why)
    import dg_clock,dg_inventory,dg_epistemic,dg_rpg
    dg_inventory.ensure(state);before=dg_clock.absolute(state)
    witnesses=['hero']+[w for w,n in dg_rpg.at_place(state)]
    system=ensure(state);objkey=row['object']+':'+state['place']
    obj=system['objects'].setdefault(objkey,{'cleaned':None,'repaired':None,'organized':None,'inspected':None})
    verb=row['verb']
    if verb=='repair':
        dg_inventory.bag(state,'hero')['tape']-=1;dg_inventory.log(state,'use','tape','hero',state['place'])
    field={'clean':'cleaned','repair':'repaired','organize':'organized','inspect':'inspected'}.get(verb)
    if field:obj[field]=before
    state['energy']-=row['cost'];system['done'][key]=state['day']
    system['done']={k:v for k,v in system['done'].items() if v>=state['day']-7}
    result={'key':key,'at':before,'place':state['place'],'verb':verb,'object':row['object'],'witnesses':witnesses}
    system['records'].append(result);system['records']=system['records'][-96:]
    dg_rpg._tick(state,row['minutes'])
    result['completed']=dg_clock.absolute(state)
    witnesses=[w for w in witnesses if w=='hero' or dg_rpg.where_is(state,w)==result['place']]
    result['witnesses']=witnesses
    dg_epistemic.record(state,'account','action:'+key+':'+str(before),result,witnesses)
    # Completion, rather than starting before the deadline, is the evidence.
    __import__('dg_commitments').performed(state,key,result['completed'],witnesses)
    text=(u'Выполнено: %s. Потрачено %d минут и %d сил. ' % (row['title'],row['minutes'],row['cost']))
    text+=({ 'inspect':u'Замечено только состояние этого объекта; скрытые предметы и тайны не найдены автоматически.',
             'clean':u'Объект убран; это не завершает отдельное принятое дежурство.',
             'repair':u'Небольшой ремонт выполнен инструментами и одной единицей изоленты. Инструменты сохранены; большое оборудование не починено автоматически.',
             'organize':u'Рабочее пространство приведено в порядок. Предметы лагеря не переходят в собственность героя.',
             'practice':u'Состоялось самостоятельное занятие. Оно не даёт мгновенного мастерства или близости с персонажем.'}[verb])
    dg_rpg._journal(state,row['title'])
    return {'status':'done','kind':'affordance','title':row['title'],'text':text,'action_key':key,'who':None}

def report(state,who=None):
    system=state.get('affordances',{})
    return {'objects':copy.deepcopy({k:v for k,v in system.get('objects',{}).items() if k.endswith(':'+state['place'])}),
            'known_deeds':copy.deepcopy([r for r in system.get('records',[]) if r['place']==state['place'] and (who is None or who in r['witnesses'])][-6:]),
            'rule':u'Состояние объекта видно на месте; знание о том, кто и когда работал, требует свидетельства. Дата уборки не гарантирует вечной чистоты.'}

def validate(state):
    s=state.get('affordances')
    if s is None:return
    if not isinstance(s,dict) or not isinstance(s.get('objects'),dict) or len(s['objects'])>80 or not isinstance(s.get('done'),dict) or len(s['done'])>240 or not isinstance(s.get('records'),list) or len(s['records'])>96:raise ValueError('Invalid object actions')
    import dg_rpg
    for key,obj in s['objects'].items():
        parts=key.split(':')
        if len(parts)!=2 or parts[0] not in OBJECTS or parts[1] not in OBJECTS[parts[0]][1] or not isinstance(obj,dict) or set(obj)!=set(('cleaned','repaired','organized','inspected')) or any(v is not None and (type(v) is not int or v<0) for v in obj.values()):raise ValueError('Invalid object condition')
    for key,day in s['done'].items():
        parts=key.split(':')
        if len(parts)!=3 or parts[0] not in VERBS or parts[1] not in OBJECTS or parts[2] not in OBJECTS[parts[1]][1] or type(day) is not int or not 1<=day<=state['day']:raise ValueError('Invalid completed affordance')
    for r in s['records']:
        if not isinstance(r,dict) or r.get('verb') not in VERBS or r.get('object') not in OBJECTS or r.get('place') not in dg_rpg.PLACE_NAMES or type(r.get('at')) is not int or r['at']<0:raise ValueError('Invalid action evidence')
