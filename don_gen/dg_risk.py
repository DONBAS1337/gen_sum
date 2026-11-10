# -*- coding: utf-8 -*-
"""Optional risky encounters; reproducible rolls and committed injury outcomes."""
from __future__ import unicode_literals
import re

def injured(state):
    h=state.get('health',{})
    return bool(h and __import__('dg_clock').absolute(state)<h.get('until',0))

def cards(state):
    import dg_world,dg_camp,dg_rpg
    if 'camp_life' not in state or dg_camp.in_intro(state) or injured(state) or state['finished']:return []
    c=state['camp_life'];minute=c['minute']
    if not 600<=minute<1080 or dg_camp._done(state,'roof_encounter'):return []
    if dg_world._seed(state['id'],state['day'],'encounter')%3:return []
    who=('mi','dv','el')[dg_world._seed(state['id'],state['day'],'requester')%3]
    place=dg_rpg.where_is(state,who)
    if place not in ('music','clubs','stage','square'):return []
    story=u'На крыше застрял лёгкий реквизит. '+dg_rpg.NPC_NAMES[who]+u' просит помочь его достать. Согласие ещё не дано; можно отказаться или позвать взрослого с оборудованием.'
    return [dict(key='risk:'+kind,title=title,place=place,who=who,minutes=cost,story=story,ready=state['place']==place)
            for kind,title,cost in (('safe',u'Реквизит на крыше: позвать взрослого',15),('decline',u'Реквизит на крыше: отказаться',5),('climb',u'Полезть на крышу самому — риск травмы',20))]

def resolve(state,key):
    import dg_camp,dg_world,dg_hero,dg_clock,dg_rpg
    rows=[r for r in cards(state) if r['key']==key and r['ready']]
    if not rows:raise ValueError(u'Сейчас такой встречи нет; опасный поступок нельзя выполнить задним числом.')
    row=rows[0];kind=key.split(':')[1]
    if kind=='climb' and state['energy']<10:raise ValueError(u'Недостаточно сил для рискованного подъёма.')
    dg_camp._mark(state,'roof_encounter')
    if kind=='safe':text=u'Ты позвал взрослого. Реквизит достали подходящим оборудованием; ты не поднимался на крышу.'
    elif kind=='decline':text=u'Ты отказался лезть на крышу. Собеседник принял отказ; отношения не ухудшились.'
    else:
        chance=55+(20 if dg_world.weather(state)[0]=='rain' else 0)+(10 if dg_hero.has(state,'height_fear') else 0)-(15 if dg_hero.has(state,'sport') else 0)
        hurt=dg_world._seed(state['id'],state['day'],'roof_fall')%100<chance
        if hurt:
            state['health']={'kind':'fall','until':dg_clock.absolute(state)+1440,'treated':False,'day':state['day']}
            state['place']='infirmary';state['energy']=max(0,state['energy']-25)
            text=u'Попытка залезть на крышу закончилась падением. После осмотра в медпункте у тебя ушиб и запрет на нагрузку примерно на сутки. Первая помощь оказана; активные дела временно недоступны. Нужен повторный осмотр.'
        else:text=u'Ты рискнул и достал реквизит с крыши без травмы. Это не делает последующие подъёмы безопасными.'
    dg_camp._meet(state,row['who'])
    dg_clock.advance(state,row['minutes']);dg_rpg._journal(state,text)
    return dict(row,text=text,title=row['title'],who='cs' if injured(state) else row['who'])

def intent(text):
    text=text.lower()
    if re.search(u'\\b(?:не|если|вчера|завтра|потом)\\b',text):return None
    return 'risk:climb' if re.search(u'(?:лезу|залез|лезть|поднимаюсь|забираюсь).{0,30}крыш',text) else None

def treatment(state):
    if state['place']!='infirmary' or not injured(state):raise ValueError(u'Осмотр сейчас недоступен.')
    h=state['health']
    if h['treated']:raise ValueError(u'Повторный осмотр уже пройден; нужно время на восстановление.')
    h['treated']=True;h['until']=max(__import__('dg_clock').absolute(state)+120,h['until']-360)
    return u'Виола провела повторный осмотр и уточнила режим. Восстановление ускорено, но нагрузка пока ограничена.'

def report(state):
    return {'injured':injured(state),'record':dict(state.get('health',{})),
            'rule':u'Травма существует только при injured=true. Нельзя придумывать падение, потерю сознания, лечение или выздоровление. Ушиб ограничивает нагрузку до указанного игрового времени.'}

def validate(state):
    h=state.get('health')
    if h is None:return
    if not isinstance(h,dict) or h.get('kind')!='fall' or type(h.get('until')) is not int or not 1<=h['until']<=200000 or type(h.get('day')) is not int or not isinstance(h.get('treated'),bool):raise ValueError('Invalid injury record')
