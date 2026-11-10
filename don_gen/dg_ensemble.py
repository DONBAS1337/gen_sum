# -*- coding: utf-8 -*-
"""Optional multi-day shared events with real attendance and autonomous work."""
from __future__ import unicode_literals
import copy
SPECS={
 'concert':{'title':u'Общий концертный вечер','lead':'mi','people':['mi','dv','el'],'variants':{'acoustic':u'Камерный акустический номер','amplified':u'Номер с усилением'},'work':'music'},
 'outing':{'title':u'Подготовка отрядной прогулки','lead':'sl','people':['sl','un','mt'],'variants':{'quiet':u'Тихая прогулка и наблюдения','games':u'Прогулка с командными играми'},'work':'forest_path'},
 'radio':{'title':u'Совместный вечерний эфир','lead':'el','people':['el','sh','mz'],'variants':{'interview':u'Проверенные новости кружков','music':u'Разговор о музыке и небольшой фрагмент'},'work':'library'}}
PHASES=('plan','rehearsal','scout','research','technical','ready','feedback','closed','missed')
PHASE_LABELS={'plan':u'обсуждение плана','rehearsal':u'репетиция','scout':u'проверка маршрута','research':u'подготовка материалов','technical':u'проверка оборудования','ready':u'подготовка завершена','feedback':u'обсуждение результата','closed':u'история завершена','missed':u'подготовку не удалось закончить'}

def ensure(state):return state.setdefault('ensemble',{'sequence':0,'records':[]})
def records(state):return state.get('ensemble',{}).get('records',[])
def _now(state):return __import__('dg_clock').absolute(state)
def _day(row):return row['due']//1440+1

def due(state,kind):
    for day in range(state['day'],state['duration']+1):
        w=(day-1)%7
        if kind=='concert' and w==4 and (day>state['day'] or __import__('dg_clock').minute(state)<1200):return (day-1)*1440+1200
        if kind=='outing' and day>=3 and day>state['day'] and w in (2,6):return (day-1)*1440+900
        if kind=='radio' and day>=state['day']+3 and w in (0,1,2,3):return (day-1)*1440+1230
    return None

def _venue(state,row):
    rain=__import__('dg_world').weather(state)[0]=='rain'
    return ('clubhouse' if rain else 'stage') if row['kind']=='concert' else ('clubhouse' if rain else 'beach') if row['kind']=='outing' else 'radio'

def _step(state,row):
    p=row['phase'];kind=row['kind']
    if p=='rehearsal':return 'music',['mi','dv'],20,u'Репетиция общего номера'
    if p=='scout':return ('library' if __import__('dg_world').weather(state)[0]=='rain' else 'forest_path'),['sl','un'],15,u'Проверить маршрут или дождевой план'
    if p=='research':return 'library',['mz','el'],15,u'Проверить материалы эфира'
    if p=='technical':return 'clubs',['el','sh'] if kind=='radio' else ['el'],15,u'Проверить оборудование вместе'
    return None,[],0,u''

def _tape(state,row):
    if row['kind']!='concert' or row['variant']!='amplified':return True
    inv=__import__('dg_inventory');shadow=copy.deepcopy(state);inv.ensure(shadow)
    return any(inv.free_count(shadow,w,'tape')>0 for w in ('hero','el'))

def _can_work(state,row,hero=False):
    import dg_rpg,dg_clock,dg_inventory
    place,people,minutes,title=_step(state,row)
    if not place:return False
    if not 1095<=dg_clock.minute(state)<=(1135-minutes if hero else 1135):return False
    if hero and (state['place']!=place or state['energy']<6 or __import__('dg_risk').injured(state)):return False
    if not all(dg_rpg.where_is(state,w)==place for w in people):return False
    if row['phase']=='technical':
        shadow=copy.deepcopy(state);dg_inventory.ensure(shadow)
        tool=dg_inventory.stock_at(shadow,'clubs').get('toolkit',0)>0 or any(dg_inventory.free_count(shadow,w,'toolkit')>0 for w in (['hero'] if hero else [])+people)
        if not tool or not _tape(state,row):return False
        if not hero and row['kind']=='concert' and row['variant']=='amplified' and dg_inventory.free_count(shadow,'el','tape')<1:return False
    return True

def _remember(state,row,kind,detail,people):
    for who in people:__import__('dg_personality').react(state,who,kind,'crew:'+row['id']+':'+row['phase']+':'+detail,detail)
    __import__('dg_epistemic').record(state,'account','crew:'+row['id']+':'+row['phase'],{'kind':row['kind'],'phase':row['phase'],'detail':detail},list(people)+(['hero'] if state['place'] in [__import__('dg_rpg').where_is(state,w) for w in people] else []))

def _advance(state,row,hero=False):
    place,people,minutes,title=_step(state,row);phase=row['phase']
    if phase=='technical' and row['kind']=='concert' and row['variant']=='amplified':
        inv=__import__('dg_inventory');inv.ensure(state)
        actor='hero' if hero and inv.free_count(state,'hero','tape') else 'el'
        if inv.free_count(state,actor,'tape')<1:raise ValueError(u'Нужна свободная изолента.')
        inv.bag(state,actor)['tape']-=1;inv.log(state,'use','tape',actor,'clubs')
    row['contributions'][phase]=list(people)+(['hero'] if hero else [])
    if hero:row['hero_steps'].append(phase)
    row['quality']=min(10,row['quality']+(3 if hero else 2))
    arc='festival' if row['kind']=='concert' else 'radio' if row['kind']=='radio' else 'lake'
    world=__import__('dg_world').ensure(state);world['preparations'][arc]=min(100,world['preparations'].get(arc,0)+2)
    row['history'].append({'phase':phase,'at':_now(state),'place':place,'people':list(people),'hero':hero});row['history']=row['history'][-12:]
    _remember(state,row,'shared_success',title,people)
    row['phase']='technical' if phase in ('rehearsal','research') and (row['kind']=='radio' or row['variant']=='amplified') else 'ready'
    row['progress']=0;row['last']=None
    if hero:row['seen_phase']=row['phase']

def _plan(row,variant):
    row['variant']=variant;row['phase']={'concert':'rehearsal','outing':'scout','radio':'research'}[row['kind']]

def cards(state):
    import dg_rpg,dg_camp,dg_clock
    if 'camp_life' not in state or state['finished'] or dg_camp.in_intro(state):return []
    rows=[]
    def add(key,title,place,who,minutes,ready,why=u''):
        rows.append({'key':'crew:'+key,'title':title,'place':place,'who':who,'minutes':minutes,'ready':bool(ready and state['energy']>=3),'reason':why,'story':u'Подготовка общего события по подтверждённым этапам; участие не означает роман или завершение другого проекта.'})
    for kind,spec in sorted(SPECS.items()):
        when=due(state,kind);lead=spec['lead']
        if when is None or lead not in state['met'] or sum(r['phase'] not in ('closed','missed') for r in records(state))>=3:continue
        if any(r['kind']==kind and r['due']==when for r in records(state)):continue
        place=dg_rpg.where_is(state,lead)
        if place:add('start:'+kind,u'Предложить: '+spec['title'],place,lead,5,state['place']==place)
    for r in records(state):
        lead=SPECS[r['kind']]['lead'];place=dg_rpg.where_is(state,lead)
        if r['phase'] in ('closed','missed'):continue
        if r['seen_phase']!=r['phase'] and place:
            add(r['id']+':news',u'Узнать новости общего дела',place,lead,5,state['place']==place)
        if r['phase']=='plan':
            for variant,title in SPECS[r['kind']]['variants'].items():
                if place:add(r['id']+':plan:'+variant,u'Обсудить план: '+title,place,lead,5,state['place']==place)
        elif r['phase'] in ('rehearsal','scout','research','technical'):
            where,people,cost,title=_step(state,r)
            add(r['id']+':work',title+u' · сбор 18:15–18:55',where,people[0],cost,_can_work(state,r,True),u'Нужны участники на месте, свободное вечернее окно и необходимые материалы.')
        elif r['phase']=='ready' and r['kind']=='radio':
            add(r['id']+':perform',u'Провести подготовленный эфир',_venue(state,r),'el',20,1230<=dg_clock.minute(state)<1270 and state['day']==_day(r) and state['place']=='radio' and all(dg_rpg.where_is(state,w)=='radio' for w in r['people']))
        elif r['phase']=='feedback' and state['day']>_day(r) and place:
            for key,title in (('learn',u'Разобрать результат и учесть ошибки'),('celebrate',u'Вспомнить лучшие моменты вместе')):
                add(r['id']+':feedback:'+key,title,place,lead,10,state['place']==place)
    return rows

def act(state,key):
    import dg_rpg,dg_clock,dg_camp
    option=next((r for r in cards(state) if r['key']==key and r['ready']),None)
    if not option:raise ValueError(u'Дождись участников, времени и подготовки общего дела.')
    bits=key.split(':');who=option['who'];text=option['story'];cost=option['minutes']
    if bits[1]=='start':
        kind=bits[2];spec=SPECS[kind];s=ensure(state)
        s['records']=[r for r in s['records'] if r['phase'] not in ('closed','missed')]+[r for r in s['records'] if r['phase'] in ('closed','missed')][-20:]
        s['sequence']+=1
        row={'id':str(s['sequence']),'kind':kind,'people':list(spec['people']),'due':due(state,kind),'created':_now(state),'phase':'plan','seen_phase':'plan','variant':None,'quality':0,'progress':0,'last':None,'hero_steps':[],'contributions':{},'history':[],'outcome':None}
        lesson=next((r for r in reversed(s['records']) if r['kind']==kind and r.get('lesson')=='learn' and r.get('phase')=='closed'),None)
        if lesson:row.update(quality=1,lesson_from=lesson['id'])
        s['records'].append(row)
        text=u'Предложение общего дела принято: '+spec['title']+u'. Нужно обсудить вариант, подготовиться и встретиться с участниками. Событие ещё не состоялось; готовый музыкальный или технический проект автоматически не завершён.'
        if lesson:text+=u' Вы учли прошлый разбор ошибок; это небольшое преимущество, но все этапы подготовки нужно пройти заново.'
    else:
        row=next(r for r in records(state) if r['id']==bits[1]);action=bits[2]
        if action=='plan':
            _plan(row,bits[3]);row['seen_phase']=row['phase'];row['hero_steps'].append('plan')
            text=u'Вы выбрали план: '+SPECS[row['kind']]['variants'][row['variant']]+u'. Подготовка ещё впереди. У каждого участника остаются обязательные дела; общий сбор назначен на 18:15–18:55.'
            _remember(state,row,'curious',text,[who])
        elif action=='work':
            place,people,minutes,title=_step(state,row)
            for actor in people:dg_camp._meet(state,actor)
            state['ensemble_work']={'people':people,'place':place,'until':_now(state)+cost}
            # Apply completion after the elapsed work, and keep NPC ticks from duplicating it.
            row['working']=True
            try:dg_clock.advance(state,cost)
            finally:row.pop('working',None);state.pop('ensemble_work',None)
            _advance(state,row,True);cost=0
            text=u'Вместе выполнен этап: '+title+u'. Время потрачено, вклад участников записан. Результат концерта, прогулки или эфира ещё не объявляется заранее.'
        elif action=='news':
            row['seen_phase']=row['phase'];text=u'Координатор рассказал о подтверждённом ходе дела: '+PHASE_LABELS[row['phase']]+u'. Часть работы могла быть выполнена товарищами без героя; это не личный вклад игрока.'
        elif action=='perform':
            _complete(state,row,True);text=row['outcome']['text']
        elif action=='feedback':
            row['phase']='closed';row['seen_phase']='closed';row['lesson']=bits[3]
            text=(u'Вы разобрали результат и назвали конкретную ошибку, которую стоит учесть в следующем общем деле.' if bits[3]=='learn' else u'Вы вспомнили подтверждённые удачные моменты и поблагодарили участников за их реальный вклад.')
            _remember(state,row,'honesty' if bits[3]=='learn' else 'shared_success',text,[who])
    state['energy']=max(0,state['energy']-3);state['interaction']={'who':who,'until':_now(state)+cost}
    if cost:dg_clock.advance(state,cost)
    dg_rpg._journal(state,option['title']+u'. '+text)
    return {'title':option['title'],'text':text,'who':who,'private':bits[1]!='start' and bits[2] in ('news','feedback')}

def destination(state,who):
    minute=__import__('dg_clock').minute(state)
    for r in records(state):
        if r['phase']=='ready' and r['kind']=='radio' and state['day']==_day(r) and 1195<=minute<1290 and who in r['people']:return 'radio'
        if r['phase'] not in ('rehearsal','scout','research','technical') or not 1060<=minute<1135:continue
        place,people,cost,title=_step(state,r)
        if who not in people:continue
        if r['phase']=='technical' and r['variant']=='amplified' and who=='el':
            inv=__import__('dg_inventory');shadow=copy.deepcopy(state);inv.ensure(shadow)
            if inv.free_count(shadow,'el','tape')<1 and inv.stock_at(shadow,'warehouse').get('tape',0)>0:return 'warehouse'
        return place
    return None

def _complete(state,row,hero=False):
    if row['phase'] in ('feedback','closed','missed'):return
    ready=row['phase']=='ready';place=_venue(state,row)
    people=[w for w in row['people'] if __import__('dg_rpg').where_is(state,w)==place]
    solid=ready and len(people)>=2
    text=(u'Подготовленное общее событие состоялось без серьёзной заминки.' if solid else u'Общее событие прошло с упрощённой программой: часть подготовки не удалось завершить.')
    if row['variant']:text+=u' Выбранный вариант: '+SPECS[row['kind']]['variants'][row['variant']]+u'.'
    if place=='clubhouse':text+=u' Из-за дождя программа перенесена под крышу.'
    role=u'Герой помог в подготовке.' if row['hero_steps'] else u'Подготовку выполнили другие участники; герою не приписывается их работа.'
    row['outcome']={'prepared':ready,'success':solid,'people':people,'hero_present':hero,'text':text+u' '+role,'place':place,'at':_now(state)}
    row['phase']='feedback';row['progress']=0
    if hero:row['seen_phase']='feedback'
    _remember(state,row,'shared_success' if solid else 'setback',row['outcome']['text'],people)
    __import__('dg_rpg')._journal(state,SPECS[row['kind']]['title']+u': '+text)

def calendar_result(state,kind):
    for row in records(state):
        if row['kind']==kind and state['day']==_day(row) and row['phase'] not in ('closed','missed'):
            _complete(state,row,True)
            if not row['outcome']['hero_present'] and state['place']==row['outcome']['place']:
                row['outcome']['hero_present']=True;row['outcome']['joined_late']=_now(state)
                __import__('dg_epistemic').record(state,'account','crew:'+row['id']+':late_join',{'kind':kind,'joined_at':_now(state)},['hero']+row['outcome']['people'])
            return row['outcome']['text']
    return u''

def tick(state):
    import dg_rpg,dg_clock,dg_inventory
    if 'camp_life' not in state:return
    now=_now(state)
    for row in records(state):
        if row['phase'] in ('closed','missed') or row.get('working'):continue
        if state['finished']:
            row['phase']='closed' if row.get('outcome') else 'missed';continue
        if row['phase']=='plan' and now>=row['created']+1440:
            _plan(row,{'concert':'acoustic','outing':'quiet','radio':'interview'}[row['kind']])
        if row['phase'] in ('rehearsal','scout','research','technical'):
            if row['phase']=='technical' and row['variant']=='amplified' and dg_rpg.where_is(state,'el')=='warehouse':
                dg_inventory.ensure(state)
                if dg_inventory.free_count(state,'el','tape')<1 and dg_inventory.stock_at(state,'warehouse').get('tape',0):dg_inventory.take(state,'el','tape','warehouse')
            if row.get('last')==now:continue
            if _can_work(state,row):
                row['progress']+=max(0,min(5,now-(row['last'] if row['last'] is not None else now)))
                row['last']=now
                if row['progress']>=_step(state,row)[2]:_advance(state,row)
            else:row['last']=None;row['progress']=0
        if row['phase']=='ready' and row['kind']=='radio' and row['due']<=now<row['due']+60:
            if all(dg_rpg.where_is(state,w)=='radio' for w in row['people']):_complete(state,row,state['place']=='radio')
        if row['kind']!='radio' and row['due']<=now<row['due']+60 and row['phase'] not in ('feedback','closed','missed'):_complete(state,row,state['place']==_venue(state,row))
        if now>=row['due']+60 and row['phase'] not in ('feedback','closed','missed'):row['phase']='missed'
        if row['phase']=='feedback' and state['day']>_day(row)+3:row['phase']='closed'

def report(state,who=None):
    rows=[]
    for r in records(state):
        if who is not None and who not in r['people']:continue
        row=copy.deepcopy(r)
        if who is None and row['seen_phase']!=row['phase']:
            if row['phase'] not in ('feedback','closed','missed'):row['phase']=row['seen_phase']
            row['history']=[];row['contributions']={};row['quality']=None
        rows.append(row)
    return {'events':rows[-6:],'rule':u'Планы не равны выполненным этапам. hero_steps — реальный вклад игрока. Чужую подготовку не приписывать герою. Частные новости известны участникам и сообщаются герою отдельно.'}

def validate(state):
    s=state.get('ensemble')
    if s is None:return
    if not isinstance(s,dict) or type(s.get('sequence')) is not int or not isinstance(s.get('records'),list) or len(s['records'])>24:raise ValueError('Invalid shared events')
    ids=set()
    for r in s['records']:
        if not isinstance(r,dict) or r.get('kind') not in SPECS or r.get('phase') not in PHASES or r.get('seen_phase') not in PHASES or type(r.get('due')) is not int or type(r.get('created')) is not int or r['due']<r['created'] or type(r.get('quality')) is not int or not 0<=r['quality']<=10 or type(r.get('progress')) is not int or not 0<=r['progress']<=30 or not isinstance(r.get('people'),list) or r['people']!=SPECS[r['kind']]['people'] or not isinstance(r.get('history'),list) or len(r['history'])>12 or not isinstance(r.get('hero_steps'),list) or len(r['hero_steps'])>5 or not isinstance(r.get('contributions'),dict) or not isinstance(r.get('id'),(str,type(u''))) or r['id'] in ids:raise ValueError('Invalid shared event record')
        ids.add(r['id'])
        if r.get('variant') is not None and r['variant'] not in SPECS[r['kind']]['variants']:raise ValueError('Invalid shared event variant')
