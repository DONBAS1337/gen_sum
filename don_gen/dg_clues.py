# -*- coding: utf-8 -*-
"""Private observations and bounded disputes; clues are not omniscient verdicts."""
from __future__ import unicode_literals
import copy

def ensure(state):return state.setdefault('clues',{'active':None,'history':[],'last_day':-20,'exclusive':[]})

def refresh(state):
    import dg_rpg,dg_world,dg_social
    if 'camp_life' not in state or state['finished']:return
    c=ensure(state)
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
            if any(r.get('loan')==loan['id'] for r in c['history']):continue
            c['active']={'who':observer,'cause':'garment','holder':loan['holder'],'loan':loan['id'],'day':state['day'],
                         'observation':u'У банных раздевалок ты увидел неразличимую пару близко друг к другу и узнал рубашку героя по контрастному шву. Личность владельца одежды в этот момент не установлена. О передаче рубашки тебе неизвестно. Это повод спросить, а не доказательство измены или секса.'}
            c['last_day']=state['day'];return

def known(state,who):
    row=state.get('clues',{}).get('active')
    return {'observation':row['observation'],'certainty':'question_not_verdict','rule':u'Общий реестр вещей — сведения движка, не твои знания. Не узнавай передачу вещи из реестра до объяснения героя. Обычный разговор с другой девушкой не повод для ревности.'} if row and row['who']==who else None

def cards(state):
    import dg_rpg
    rows=[];c=state.get('clues',{});row=c.get('active');people=[p for p,n in dg_rpg.at_place(state)]
    def add(key,title,who):rows.append(dict(key=key,title=title,who=who,place=dg_rpg.where_is(state,who),minutes=10,story=u'Личный разговор на основании подтверждённых фактов.',ready=who in people))
    for who in state.get('npc_visits',{}).get('romance',[]):
        if who in people and who not in c.get('exclusive',[]):add('clue:exclusive:'+who,u'Обсудить и подтвердить исключительность отношений',who)
    if row:
        add('clue:listen',u'Выслушать, что именно вызвало сомнения',row['who'])
        add('clue:explain',u'Разобраться в фактах и объясниться',row['who'])
    return rows

def act(state,key):
    import dg_rpg,dg_clock,dg_relationships
    rows=[r for r in cards(state) if r['key']==key and r['ready']]
    if not rows:raise ValueError(u'Для этого разговора нет подходящего собеседника или подтверждённой ситуации.')
    row=rows[0];c=ensure(state);who=row['who']
    if key.startswith('clue:exclusive:'):
        c['exclusive'].append(who);text=u'Вы прямо договорились об исключительности романтических отношений. Дружеское общение с другими не нарушает эту договорённость.'
    elif key=='clue:listen':text=c['active']['observation']+u' Ты выслушал сомнения; вывод ещё не сделан и отношения автоматически не оштрафованы.'
    else:
        evidence=c['active'];relation=dg_relationships.person(state,who)
        if evidence['cause']=='garment':
            loan=next((l for l in state.get('inventory_world',{}).get('loans',[]) if l['id']==evidence['loan']),None)
            if not loan or loan['holder']!=evidence['holder']:raise ValueError(u'Подтверждения передачи вещи недостаточно.')
            text=u'Ты объяснил: рубашку брал '+dg_rpg.NPC_NAMES[evidence['holder']]+u'. Запись передачи подтверждает объяснение: одежда не доказывала твоего присутствия. Собеседник получил недостающую информацию; обвинение в измене не подтверждено.'
        else:
            relation['trust']=max(0,relation['trust']-2);relation['tension']=min(20,relation['tension']+2)
            text=u'Ты признал конкретное нарушение договорённости. Доверие немного снизилось; мгновенного расставания или автоматического прощения нет. Разговор о дальнейшем остаётся открытым.'
        c['history'].append(dict(evidence,resolution=text));c['history']=c['history'][-24:];c['active']=None
    dg_clock.advance(state,10);dg_rpg._journal(state,text)
    text=u'Вы отошли в сторону и говорите вдвоём. До этого публичных обвинений не было. '+text
    return dict(row,text=text,private=True)

def validate(state):
    c=state.get('clues')
    if c is None:return
    import dg_rpg
    if not isinstance(c,dict) or not isinstance(c.get('history'),list) or len(c['history'])>24 or not isinstance(c.get('exclusive'),list) or len(set(c['exclusive']))!=len(c['exclusive']) or any(w not in dg_rpg.NPC_NAMES for w in c['exclusive']) or type(c.get('last_day')) is not int:raise ValueError('Invalid clue state')
    for row in c['history']+([c['active']] if c.get('active') else []):
        if not isinstance(row,dict) or row.get('who') not in dg_rpg.NPC_NAMES or row.get('holder') not in dg_rpg.NPC_NAMES or row.get('cause') not in ('garment','agreement') or type(row.get('day')) is not int or not isinstance(row.get('observation'),(str,type(u''))) or len(row['observation'])>2000:raise ValueError('Invalid observation')
