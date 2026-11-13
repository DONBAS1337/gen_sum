# -*- coding: utf-8 -*-
"""Contextual antenna work and player-authored physical risks."""
from __future__ import unicode_literals
import re

def injured(state):
    h=state.get('health',{})
    return bool(isinstance(h,dict) and h and __import__('dg_clock').absolute(state)<h.get('until',0))

def impaired(state):return __import__('dg_clock').absolute(state)<state.get('impaired_until',0)

def encounter(state):
    import dg_world,dg_camp
    return ('camp_life' in state and not dg_camp.in_intro(state) and not injured(state) and not state['finished']
            and 600<=state['camp_life']['minute']<1080 and not dg_camp._done(state,'roof_encounter')
            and dg_world._seed(state['id'],state['day'],'encounter')%3==0)

def location(state,who):
    if who=='el' and encounter(state):return 'square' if state['place']=='square' else 'clubs'
    return None

def cards(state):
    if not encounter(state):return []
    if __import__('dg_rpg').where_is(state,'el') not in ('clubs','square'):return []
    place='square' if state['place']=='square' else 'clubs'
    story=u'Электроник просит помочь с антенной на крыше здания клубов: они с Шуриком опасаются высоты. Согласие ещё не дано. Работать можно только у клубов; можно позвать взрослого или отказаться.'
    rows=[dict(key='risk:'+kind,title=title,place='clubs' if kind!='decline' else place,who='el',minutes=cost,story=story,ready=state['place']==('clubs' if kind!='decline' else place))
          for kind,title,cost in (('safe',u'Антенна клубов: позвать взрослого с оборудованием',15),('decline',u'Антенна клубов: отказаться от подъёма',5),('climb',u'Починить антенну на крыше самому — риск травмы',20))]
    return rows

def intent(text):
    text=text.lower()
    if re.search(u'\\b(?:не|если|вчера|завтра|потом)\\b',text):return None
    climbing=re.search(u'(?:лезу|залез|лезть|поднимаюсь|забираюсь|взбираюсь|полез).{0,35}',text)
    if climbing and re.search(u'дерев|сосну|сосне|берёз|берез',climbing.group()+text[climbing.end():climbing.end()+15]):return 'risk:tree'
    if climbing and u'крыш' in text:return 'risk:climb'
    if re.search(u'плыву|плавать|переплы|купаюсь',text):return 'risk:swim'
    if re.search(u'бегу|побежал|бежать|пробежк',text):return 'risk:run'
    if re.search(u'напился|выпил.{0,15}(?:алкогол|водк|вин[ао]|пив)',text):return 'risk:drink'
    return None

def resolve(state,key,action=None):
    import dg_camp,dg_world,dg_hero,dg_clock,dg_rpg
    if state['finished'] or 'camp_life' not in state or injured(state):raise ValueError(u'После травмы рискованные действия недоступны.')
    custom=key in ('risk:tree','risk:drink','risk:swim','risk:run')
    if custom:
        if key=='risk:drink':
            if int(state['hero']['age'])<18:raise ValueError(u'Для несовершеннолетнего героя это действие недоступно.')
            state['impaired_until']=dg_clock.absolute(state)+180;state['energy']=max(0,state['energy']-5);dg_clock.advance(state,10)
            text=u'Ты описал употребление алкоголя: временно нарушена координация, физический риск повышен. Это не выдаёт герою алкоголь или другие предметы.'
            dg_rpg._journal(state,text);return dict(who=None,title=u'Ухудшение координации',text=text)
        if key=='risk:swim' and state['place'] not in ('lake','beach','pier'):raise ValueError(u'Здесь нет подходящего места для плавания.')
        if state['place'] not in ('square','forest','forest_path','cabins','lake','beach','campfire','old_camp','pier','sports','forest_path','football','volleyball'):
            raise ValueError(u'В текущем месте нет условий для такого физического занятия. Выбери подходящую локацию.')
        if dg_camp._done(state,key.split(':')[1]+'_risk'):raise ValueError(u'Повторный подъём сегодня отложен.')
        if action and re.search(u'напился|пьяный|выпил.{0,15}(?:алкогол|водк|вин[ао]|пив)',action.lower()):
            if int(state['hero']['age'])<18:raise ValueError(u'Это действие недоступно для несовершеннолетнего героя.')
        row=dict(who=None,title={'risk:tree':u'Подняться на дерево','risk:swim':u'Поплавать','risk:run':u'Пробежаться'}[key],minutes=20);kind='climb';marker=key.split(':')[1]+'_risk'
    else:
        rows=[r for r in cards(state) if r['key']==key and r['ready']]
        if not rows:raise ValueError(u'Нужно быть у клубов и иметь текущую просьбу об антенне; чужую задачу нельзя завершить задним числом.')
        row=rows[0];kind=key.split(':')[1];marker='roof_encounter'
    if kind=='climb' and state['energy']<10:raise ValueError(u'Недостаточно сил для рискованного подъёма.')
    if custom and action and re.search(u'напился|пьяный|выпил.{0,15}(?:алкогол|водк|вин[ао]|пив)',action.lower()):state['impaired_until']=dg_clock.absolute(state)+180
    dg_camp._mark(state,marker)
    if kind=='safe':text=u'Ты позвал взрослого. Антенну на здании клубов проверили с подходящим оборудованием; ты не поднимался на крышу.'
    elif kind=='decline':text=u'Ты отказался лезть на крышу. Электроник принял отказ; отношения не ухудшились.'
    else:
        chance=(35 if key=='risk:tree' else 5 if custom else 55)+(25 if impaired(state) else 0)+(20 if dg_world.weather(state)[0]=='rain' else 0)+(10 if dg_hero.has(state,'height_fear') else 0)-(15 if dg_hero.has(state,'sport') else 0)
        hurt=dg_world._seed(state['id'],state['day'],key.split(':')[1]+'_fall' if custom else 'roof_fall')%100<min(95,chance)
        if hurt:
            state['health']={'kind':'strain' if key in ('risk:run','risk:swim') else 'fall','until':dg_clock.absolute(state)+1440,'treated':False,'day':state['day']}
            state['place']='infirmary';state['energy']=max(0,state['energy']-25)
            text=(row['title'] if custom else u'Попытка добраться до антенны на крыше')+(u' закончилась перенапряжением. Ты добрался до медпункта; после осмотра назначен отдых. Нужен повторный осмотр.' if key in ('risk:run','risk:swim') else u' закончился падением. После осмотра в медпункте подтверждён ушиб; примерно сутки без нагрузки. Первая помощь оказана. Нужен повторный осмотр.')
        else:text=(u'Ты поднялся на дерево и спустился без травмы.' if key=='risk:tree' else u'Ты закончил физическое занятие без травмы; силы потрачены.') if custom else u'Ты помог с креплением антенны и вернулся в клубы без травмы. Работа выполнена; это не делает последующие подъёмы безопасными.'
    if row['who']:dg_camp._meet(state,row['who'])
    if custom and key in ('risk:run','risk:swim'):state['energy']=max(0,state['energy']-12)
    dg_clock.advance(state,row['minutes']);dg_rpg._journal(state,text)
    return dict(row,text=text,who='cs' if injured(state) else row['who'])

def treatment(state):
    if state['place']!='infirmary' or not injured(state):raise ValueError(u'Осмотр сейчас недоступен.')
    h=state['health']
    if h['treated']:raise ValueError(u'Повторный осмотр уже пройден; нужно время на восстановление.')
    h['treated']=True;h['until']=max(__import__('dg_clock').absolute(state)+120,h['until']-360)
    return u'Виола провела повторный осмотр и уточнила режим восстановления. Восстановление ускорено, но нагрузка пока ограничена.'

def report(state):
    return {'impaired':impaired(state),'injured':injured(state),'record':dict(state.get('health',{})),
            'rule':u'Травма существует только при injured=true. Нельзя придумывать падение, потерю сознания, лечение или выздоровление. Ушиб ограничивает нагрузку до указанного игрового времени.'}

def validate(state):
    if type(state.get('impaired_until',0)) is not int or not 0<=state.get('impaired_until',0)<=200000:raise ValueError('Invalid impairment')
    h=state.get('health')
    if h is None:return
    if not isinstance(h,dict) or h.get('kind') not in ('fall','strain') or type(h.get('until')) is not int or not 1<=h['until']<=200000 or type(h.get('day')) is not int or not isinstance(h.get('treated'),bool):raise ValueError('Invalid injury record')
