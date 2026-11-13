# -*- coding: utf-8 -*-
"""Private observations and bounded disputes; clues are not omniscient verdicts."""
from __future__ import unicode_literals
import copy

def ensure(state):
    c=state.setdefault('clues',{'active':None,'history':[],'last_day':-20,'exclusive':[]})
    if c.get('active'):
        r=c['active'];r.setdefault('phase','noticed');r.setdefault('proof',[]);r.setdefault('last_penalty',r['day']);r.setdefault('penalties',0)
    return c


def _evolve(state,c):
    r=c['active']
    if not r:return
    import dg_rpg,dg_epistemic
    if r['phase']=='acknowledged' and state['day']>r.get('answered_day',state['day']):r['phase']='repair'
    if r['phase']=='false_account' and state['day']>r.get('answered_day',state['day']):
        if dg_rpg.where_is(state,r['who'])==dg_rpg.where_is(state,r['holder']):
            r['phase']='lie_discovered';r['proof'].append('independent_testimony')
            relation=__import__('dg_relationships').person(state,r['who']);relation['trust']=max(0,relation['trust']-3);relation['tension']=min(20,relation['tension']+3)
            dg_epistemic.record(state,'testimony','case:%d'%r['day'],{'loan':r['loan'],'kind':'independent_confirmation'},[r['who'],r['holder']])
            dg_epistemic.believe(state,r['who'],'case:%d'%r['day'],u'Объяснение героя расходится с подтверждённой передачей вещи',90,'supported')
    if r['phase'] in ('noticed','deferred','questioned') and state['day']>r['last_penalty']+1 and r['penalties']<3:
        r['last_penalty']=state['day'];r['penalties']+=1
        relation=__import__('dg_relationships').person(state,r['who']);relation['tension']=min(20,relation['tension']+1)


def refresh(state):
    import dg_rpg,dg_world,dg_social
    if 'camp_life' not in state or state['finished']:return
    c=ensure(state)
    _evolve(state,c)
    if c['active'] or state['day']-c['last_day']<7:return
    partners=state.get('npc_visits',{}).get('romance',[])
    # Only a witnessed intimate gesture contradicting an EXPLICIT agreement.
    for row in reversed(state.get('affection',{}).get('history',[])):
        if row['day']!=state['day'] or not row['consent'] or row['kind']!='hand':continue
        for observer in c['exclusive']:
            if observer!=row['who'] and observer in partners and observer in row.get('witnesses',[]):
                c['active']={'who':observer,'cause':'agreement','holder':row['who'],'loan':None,'day':state['day'],
                             'observation':u'Ты лично видел, как герой согласованно держался за руки с другим романтическим партнёром, хотя с тобой была явная договорённость об исключительности.'}
                c['last_day']=state['day'];return
    # A borrowed unique garment is evidence of ownership, not identity.
    for loan in state.get('inventory_world',{}).get('loans',[]):
        if loan['holder'] not in ('sh','el') or loan['status']!='open' or loan['item']!='shirt' or dg_rpg.where_is(state,loan['holder'])!='showers':continue
        for observer in partners:
            if observer not in ('mi','dv','sl','un','mz') or observer in loan.get('witnesses',[]) or dg_rpg.where_is(state,observer)!='showers':continue
            if dg_world._seed(state['id'],state['day'],loan['id'],'clue')%8:continue
            # Do not invent another couple or sex from a shirt alone.
            close=[p for p in ('mi','dv','sl','un','mz') if p!=observer and dg_rpg.where_is(state,p)=='showers' and dg_social.bond(state,loan['holder'],p)>=60]
            if not close:continue
            subject=loan.get('instance') or 'shirt:'+state['id']
            if not __import__('dg_epistemic').knows(state,observer,'recognition',subject):continue
            if any(r.get('loan')==loan['id'] for r in c['history']):continue
            c['active']={'who':observer,'cause':'garment','holder':loan['holder'],'loan':loan['id'],'day':state['day'],
                         'observation':u'У банных раздевалок ты увидел неразличимую пару близко друг к другу и узнал знакомую рубашку героя. Личность владельца одежды в этот момент не установлена. О передаче рубашки тебе неизвестно. Это повод спросить, а не доказательство измены или секса.'}
            c['last_day']=state['day'];ensure(state)
            __import__('dg_epistemic').record(state,'meeting','bath:%d:%s'%(state['day'],loan['holder']),{'pair':[loan['holder'],close[0]],'place':'showers','kind':'private_meeting'},[loan['holder'],close[0]])
            __import__('dg_epistemic').believe(state,observer,'case:%d'%state['day'],u'Возможно, герой был участником неоднозначной встречи',40)
            return

def known(state,who):
    row=state.get('clues',{}).get('active')
    return {'phase':row.get('phase','noticed'),'observation':(u'Получено независимое подтверждение передачи вещи; прежнее отрицание героя оказалось ложью.' if row.get('phase')=='lie_discovered' else row['observation']),'certainty':'question_not_verdict','rule':u'Общий реестр вещей — сведения движка, не твои знания. Не узнавай передачу вещи из реестра до объяснения героя. Обычный разговор с другой девушкой не повод для ревности.'} if row and row['who']==who else None

def cards(state):
    import dg_rpg
    rows=[];c=state.get('clues',{});r=c.get('active');people=[p for p,n in dg_rpg.at_place(state)]
    def add(key,title,who):rows.append(dict(key=key,title=title,who=who,place=dg_rpg.where_is(state,who),minutes=10,story=u'Личный разговор на основании подтверждённых фактов.',ready=who in people))
    for who in state.get('npc_visits',{}).get('romance',[]):
        if who in people and who not in c.get('exclusive',[]):add('clue:exclusive:'+who,u'Обсудить исключительность отношений',who)
    if not r:return rows
    phase=r.get('phase','noticed');who=r['who']
    add('clue:listen',u'Наедине спросить, что тревожит собеседника',who)
    if phase in ('noticed','questioned','deferred'):
        if phase!='noticed':add('clue:explain',u'Честно изложить свою версию',who)
        add('clue:defer',u'Попросить время на разговор',who)
        if r['cause']=='garment' and phase!='noticed':add('clue:lie',u'Солгать, что никому не передавал вещь',who)
    if phase in ('account','checking'):
        if 'record' not in r.get('proof',[]):add('clue:record',u'Показать запись о передаче вещи',who)
        if 'testimony' not in r.get('proof',[]):add('clue:witness',u'Подтверждение передачи · '+dg_rpg.NPC_NAMES[r['holder']],r['holder'])
        if len(set(r.get('proof',[])))>=2:add('clue:resolve',u'Сопоставить подтверждения и закончить разговор',who)
    if phase=='lie_discovered':add('clue:admit',u'Признать ложь и объяснить настоящий ход событий',who)
    if phase=='repair':add('clue:repair',u'Вернуться к разговору после паузы',who)
    return rows


def act(state,key):
    import dg_rpg,dg_clock,dg_relationships,dg_epistemic
    rows=[r for r in cards(state) if r['key']==key and r['ready']]
    if not rows:raise ValueError(u'Для этого шага нужны собеседник, время и предшествующий разговор.')
    row=rows[0];c=ensure(state);who=row['who'];r=c.get('active');done=False
    subject='case:%d'%r['day'] if r else ''
    if key.startswith('clue:exclusive:'):
        c['exclusive'].append(who);text=u'Вы прямо договорились об исключительности романтических отношений. Дружеское общение с другими не нарушает договорённость.'
    elif key=='clue:listen':
        if r['phase']=='noticed':r['phase']='questioned'
        text=r['observation']+u' Собеседник рассказал только увиденное; обвинение в доказанной измене не прозвучало. Теперь можно объясниться или попросить время.'
    elif key=='clue:defer':
        r['phase']='deferred';r['last_penalty']=state['day'];text=u'Ты попросил время. Вопрос остаётся открытым; немедленного штрафа и расставания нет.'
    elif key=='clue:explain':
        r['answered_day']=state['day']
        if r['cause']=='garment':
            r['phase']='account';text=u'Ты рассказал, что вещь одалживал '+dg_rpg.NPC_NAMES[r['holder']]+u'. Пока собеседник услышал твою версию; запись и подтверждение получателя можно проверить отдельно.'
            dg_epistemic.record(state,'account',subject,{'claim':'loan','holder':r['holder'],'truth_confirmed_to_listener':False},['hero',who])
        else:
            r['phase']='acknowledged';relation=dg_relationships.person(state,who);relation['trust']=max(0,relation['trust']-2);relation['tension']=min(20,relation['tension']+2)
            text=u'Ты признал конкретное нарушение договорённости. Доверие снизилось на два пункта; мгновенного расставания или прощения нет. Собеседнику нужно время до следующего дня.'
    elif key=='clue:lie':
        r.update(phase='false_account',answered_day=state['day'])
        text=u'Ты солгал, будто не передавал вещь. Собеседник услышал эту версию, но факт передачи от этого не изменился. Независимые сведения могут позже обнаружить ложь.'
        dg_epistemic.believe(state,who,subject,u'Герой отрицает передачу вещи; это пока только его слова',35)
    elif key in ('clue:record','clue:witness'):
        loan=next((l for l in state.get('inventory_world',{}).get('loans',[]) if l['id']==r['loan'] and l['holder']==r['holder']),None)
        if not loan:raise ValueError(u'Подтверждённую передачу не удалось найти.')
        proof='record' if key=='clue:record' else 'testimony';r['proof'].append(proof);r['phase']='checking'
        text=u'Ты показал сделанную при передаче запись. Для полного объяснения осталось подтверждение получателя.' if proof=='record' else u'Получатель подтвердил, что брал именно эту вещь. Теперь это можно сообщить собеседнику и сопоставить с записью.'
        dg_epistemic.record(state,'testimony',subject,{'loan':r['loan'],'type':proof},['hero',who])
    elif key=='clue:resolve':
        text=u'Запись и подтверждение получателя согласуются. Собеседник узнал недостающие факты и отказался от ошибочного предположения о личности человека. Штрафа за неподтверждённую измену нет.';done=True
        dg_epistemic.believe(state,who,subject,u'Одежда принадлежала герою, но была одолжена другому человеку',100,'refuted')
        dg_epistemic.record(state,'resolution',subject,{'result':'misunderstanding_cleared'},['hero',who])
    elif key=='clue:admit':
        r.update(phase='acknowledged',answered_day=state['day']);relation=dg_relationships.person(state,who)
        text=u'Ты признал ложь после независимого подтверждения. Исходное подозрение могло быть ошибочным, но теперь доверие пострадало от самого обмана. Нужна пауза и дальнейший разговор.'
    else:
        relation=dg_relationships.person(state,who);relation['tension']=max(0,relation['tension']-1)
        text=u'После паузы вы вернулись к разговору. Напряжение немного снизилось. Согласие продолжать отношения не стирает прошлое и не восстанавливает доверие мгновенно.';done=True
    if done:
        c['history'].append(dict(r,resolution=text));c['history']=c['history'][-24:];c['active']=None
    state['interaction']={'who':who,'until':dg_clock.absolute(state)+10}
    try:dg_clock.advance(state,10)
    finally:state.pop('interaction',None)
    dg_rpg._journal(state,text)
    text=u'Вы отошли в сторону и говорите вдвоём. Публичных обвинений не было. '+text
    return dict(row,text=text,private=True)


def validate(state):
    c=state.get('clues')
    if c is None:return
    import dg_rpg
    if not isinstance(c,dict) or not isinstance(c.get('history'),list) or len(c['history'])>24 or not isinstance(c.get('exclusive'),list) or len(set(c['exclusive']))!=len(c['exclusive']) or any(w not in dg_rpg.NPC_NAMES for w in c['exclusive']) or type(c.get('last_day')) is not int:raise ValueError('Invalid clue state')
    for row in c['history']+([c['active']] if c.get('active') else []):
        if isinstance(row,dict) and (row.get('phase','noticed') not in ('noticed','questioned','deferred','account','checking','false_account','lie_discovered','acknowledged','repair') or not isinstance(row.get('proof',[]),list) or len(row.get('proof',[]))>8):raise ValueError('Invalid investigation phase')
        if not isinstance(row,dict) or row.get('who') not in dg_rpg.NPC_NAMES or row.get('holder') not in dg_rpg.NPC_NAMES or row.get('cause') not in ('garment','agreement') or type(row.get('day')) is not int or not isinstance(row.get('observation'),(str,type(u''))) or len(row['observation'])>2000:raise ValueError('Invalid observation')
