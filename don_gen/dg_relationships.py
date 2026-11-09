# -*- coding: utf-8 -*-
"""Explicit promises, preferences, boundaries and reversible social choices."""
from __future__ import unicode_literals
import copy
LIKES={'mi':'concert','dv':'concert','us':'concert','sl':'concert','un':'concert','mz':'radio','el':'radio','sh':'radio','mt':'concert','cs':'radio'}

def ensure(state): return state.setdefault('relationships',{'people':{},'promises':[]})
def person(state,who): return ensure(state)['people'].setdefault(who,{'trust':0,'tension':0,'home_visits':True,'invitations':True,'last_apology':None})
def report(state):
    result=copy.deepcopy(state.get('relationships',{}));result['preferences']=copy.deepcopy(LIKES)
    return result

def promise(state,who,key):
    import dg_projects,dg_rpg
    if who not in LIKES or key not in dg_projects.DEFINITIONS or dg_rpg.where_is(state,who)!=state['place']: raise ValueError(u'Обещание требует присутствующего собеседника и известного проекта.')
    index,spec=dg_projects.step(state,key)
    rows=ensure(state)['promises']
    if not spec or any(r['who']==who and r['project']==key and r['status']=='open' for r in rows): raise ValueError(u'Такое обещание уже дано или проект завершён.')
    row={'who':who,'project':key,'stage':index,'deadline':state['day']+3,'status':'open','day':state['day']}
    rows.append(row);ensure(state)['promises']=rows[-48:]
    return u'Ты обещал внести личный вклад в текущий этап проекта в течение трёх дней. Само дело ещё не выполнено.'

def contributed(state,key,index):
    import dg_world
    system=ensure(state)
    for row in system['promises']:
        if row['project']==key and row['stage']==index and row['status']=='open':
            row['status']='fulfilled';p=person(state,row['who']);p['trust']=min(20,p['trust']+3);p['tension']=max(0,p['tension']-2)
    # A deed matching someone's interests improves trust only once per project stage.
    for who,p in system['people'].items():
        if LIKES.get(who)==key: p['tension']=max(0,p['tension']-1)

def tick(state):
    system=state.get('relationships',{})
    for row in system.get('promises',[]):
        if row['status']=='open' and state['day']>row['deadline']:
            row['status']='broken';p=person(state,row['who']);p['trust']=max(-20,p['trust']-4);p['tension']=min(20,p['tension']+4)
            __import__('dg_rpg')._journal(state,u'Срок обещания прошёл: '+__import__('dg_rpg').NPC_NAMES[row['who']]+u' ждал твоего участия.')

def act(state,who,action,key=None):
    import dg_rpg
    if who not in LIKES or dg_rpg.where_is(state,who)!=state['place'] or state['finished']: raise ValueError(u'Собеседника нет рядом.')
    if action not in ('promise','home_visits','invitations','end_romance','apologize'):raise ValueError('Unknown relationship action')
    if action=='promise': return promise(state,who,key)
    p=person(state,who)
    if action in ('home_visits','invitations'):
        p[action]=not p[action]
        active=state.get('npc_visits',{}).get('active')
        if not p[action] and active and active['who']==who and (action=='invitations' or active.get('place')==(state.get('housing') or {}).get('cabin')):
            active['status']='departing' if active.get('place') else 'travelling'
            if not active.get('place'):state['npc_visits']['active']=None
        return u'Ты обозначил личную границу. Настройка сохранена; отношения не оштрафованы.'
    if action=='end_romance':
        romance=state.get('npc_visits',{}).get('romance',[])
        if who not in romance: raise ValueError(u'Романтические отношения не начинались.')
        romance.remove(who);return u'Вы завершили романтические отношения. Обычное общение остаётся доступным.'
    if action=='apologize':
        if p['tension']==0 or p['last_apology']==state['day'] or state['energy']<6: raise ValueError(u'Сейчас такой разговор недоступен.')
        p['tension']=max(0,p['tension']-2);p['last_apology']=state['day'];state['energy']-=6
        dg_rpg._tick(state)
        return u'Ты извинился и выслушал собеседника. Напряжение уменьшилось, но нарушенные обещания не стали выполненными.'
    raise ValueError('Unknown relationship action')

def validate(state):
    system=state.get('relationships')
    if system is None:return
    if not isinstance(system,dict) or not isinstance(system.get('people'),dict) or len(system['people'])>10 or not isinstance(system.get('promises'),list) or len(system['promises'])>48: raise ValueError('Invalid relationship state')
    for who,p in system['people'].items():
        if who not in LIKES or not isinstance(p,dict) or not isinstance(p.get('trust'),int) or isinstance(p['trust'],bool) or not -20<=p['trust']<=20 or not isinstance(p.get('tension'),int) or isinstance(p['tension'],bool) or not 0<=p['tension']<=20 or not isinstance(p.get('home_visits'),bool) or not isinstance(p.get('invitations'),bool) or (p.get('last_apology') is not None and not isinstance(p['last_apology'],int)):raise ValueError('Invalid relationship record')
    for row in system['promises']:
        if not isinstance(row,dict) or row.get('who') not in LIKES or row.get('project') not in ('concert','radio') or row.get('stage') not in (0,1,2,3) or row.get('status') not in ('open','fulfilled','broken') or not isinstance(row.get('deadline'),int) or not 1<=row['deadline']<=50000:raise ValueError('Invalid promise')


def available_promises(state):
    import dg_rpg,dg_projects
    result=[]
    for who,name in dg_rpg.at_place(state):
        if who not in LIKES:continue
        for key in sorted(dg_projects.DEFINITIONS):
            index,spec=dg_projects.step(state,key)
            if spec and not any(row['who']==who and row['project']==key and row['status']=='open' for row in state.get('relationships',{}).get('promises',[])):
                result.append({'target':who,'project':key,'caption':u'Дать обещание: '+name+u' · '+dg_projects.DEFINITIONS[key]['title']})
    return result

def parse_promise(state,text):
    folded=text.strip().rstrip('.!').lower()
    return next((row for row in available_promises(state) if row['caption'].lower()==folded),None)
