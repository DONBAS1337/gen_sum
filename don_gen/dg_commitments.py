# -*- coding: utf-8 -*-
"""Explicit future meetings and concrete promises, fulfilled by real evidence."""
from __future__ import unicode_literals
import copy

def ensure(state):return state.setdefault('commitments',{'sequence':0,'records':[]})
def rows(state):return state.get('commitments',{}).get('records',[])
def _now(state):return __import__('dg_clock').absolute(state)
def _relation(state,who):return __import__('dg_relationships').person(state,who)
def _hold(state,who,minutes):state['interaction']={'who':who,'until':_now(state)+minutes}
def _capacity(state):return sum(r['status'] in ('open','performed') for r in rows(state))+min(24,sum(r['status'] not in ('open','performed') for r in rows(state)))<48

MEETING_PLACES=('square','music','clubs','library','canteen','beach','lake','campfire','sports','stage')

def meeting_reason(state,who,day,minute,place):
    import dg_rpg,dg_camp
    if 'camp_life' not in state or state['finished'] or dg_camp.in_intro(state):return u'Сначала нужно освоиться в лагере.'
    if not _capacity(state):return u'Сначала разберись с прежними договорённостями.'
    if who not in __import__('dg_life').PEERS or who not in state['met'] or dg_rpg.where_is(state,who)!=state['place']:return u'Нужно обсудить встречу с присутствующим знакомым.'
    if dg_camp.stage(state,who) not in ('friend','close','romance'):return u'Для личной встречи сначала нужно развить дружбу.'
    if type(day) is not int or type(minute) is not int or not state['day']<=day<=min(state['duration'],state['day']+7) or not 600<=minute<=1260 or minute%5 or (day-1)*1440+minute<_now(state)+40:return u'Выбери время с шагом пять минут, с 10:00 до 21:00, в ближайшие семь дней и не раньше чем через 40 минут.'
    if place not in MEETING_PLACES:return u'Выбери общественное место лагеря.'
    due=(day-1)*1440+minute
    if any(r['kind']=='meeting' and r['status']=='open' and abs(r['due']-due)<60 for r in rows(state)):return u'Рядом с этим временем уже есть назначенная встреча.'
    if any(r['kind']=='meeting' and r['who']==who and r['status']!='cancelled' and r['created']//1440==_now(state)//1440 for r in rows(state)):return u'Сегодня с этим собеседником уже обсуждали личную встречу.'
    future=copy.deepcopy(state);future['day']=day;future['slot']=0 if minute<720 else 1 if minute<1080 else 2;future['camp_life']['minute']=minute
    imposed=dg_camp.location(future,who)
    if imposed and imposed!=place:return u'У собеседника в это время обязательное дело в другом месте.'
    if __import__('dg_world').weather(future)[0]=='rain' and place in ('beach','lake','campfire','sports','stage'):return u'Для такой встречи под дождём выбери помещение.'
    return None

def schedule(state,who,day,minute,place):
    why=meeting_reason(state,who,day,minute,place)
    if why:raise ValueError(why)
    if state['energy']<3:raise ValueError(u'Недостаточно сил для разговора.')
    import dg_rpg,dg_clock,dg_epistemic
    title=u'Встреча: день %d, %02d:%02d'%(day,minute//60,minute%60)
    r=_append(state,{'kind':'meeting','who':who,'place':place,'due':(day-1)*1440+minute,'status':'open','title':title,'arrived':False,'progress':0,'last':None})
    text=u'Вы договорились о встрече: '+title+u' · '+dg_rpg.PLACE_NAMES[place]+u'. Можно заранее предупредить об отмене. Встреча пока не состоялась; приход и совместное время проверяются отдельно.'
    dg_epistemic.record(state,'account','commitment:'+r['id']+':invite',{'status':'open','kind':'meeting','title':title},['hero',who])
    state['energy']-=3;_hold(state,who,5);dg_clock.advance(state,5);dg_rpg._journal(state,text)
    return {'status':'done','kind':'commitment','title':title,'text':text,'who':who,'private':True}

def options(state):
    import dg_rpg,dg_camp,dg_actions
    if 'camp_life' not in state or state['finished'] or dg_camp.in_intro(state):return []
    result=[];now=_now(state)
    def add(key,title,who,place,minutes=5):
        result.append({'key':key,'title':title,'who':who,'place':place,'minutes':minutes,'story':u'Явная договорённость, срок и фактическое выполнение; слова не заменяют поступок.','ready':state['place']==place and dg_rpg.where_is(state,who)==place})
    for who,name in dg_rpg.at_place(state):
        if who not in __import__('dg_life').PEERS or who not in state['met']:continue
        openrows=[r for r in rows(state) if r['who']==who and r['status'] in ('open','performed')]
        if meeting_reason(state,who,state['day']+1,1095,state['place']) is None:
            add('invite:'+who,u'Договориться о встрече завтра в 18:15 здесь · '+name,who,state['place'])
        for action in dg_actions.available(state):
            if not _capacity(state) or action['verb'] not in ('clean','repair','organize') or any(r.get('action')==action['key'] for r in openrows):continue
            add('pledge:'+who+':'+action['key'],u'Обещать до завтра 20:00: '+action['title']+u' · '+name,who,state['place'])
        for r in openrows:
            if r['status']=='performed':add('report:'+r['id'],u'Рассказать о выполненном обещании · '+r['title'],who,state['place'])
            elif now<r['due']:add('cancel:'+r['id'],u'Заранее отменить: '+r['title'],who,state['place'])
    for r in rows(state):
        if r['kind']=='meeting' and r['status']=='open' and r['due']<=now<r['due']+30:
            add('attend:'+r['id'],u'Провести время на назначенной встрече · '+dg_rpg.NPC_NAMES[r['who']],r['who'],r['place'],10)
    return result

def _append(state,row):
    s=ensure(state);s['records']=[r for r in s['records'] if r['status'] in ('open','performed')]+[r for r in s['records'] if r['status'] not in ('open','performed')][-24:]
    if len(s['records'])>=48:raise ValueError(u'Сначала разберись с прежними договорённостями.')
    s['sequence']+=1;row['id']=str(s['sequence']);row['created']=_now(state);s['records'].append(row)
    return row

def act(state,key):
    import dg_rpg,dg_clock,dg_epistemic
    option=next((r for r in options(state) if r['key']==key and r['ready']),None)
    if not option:raise ValueError(u'Для договорённости нужен присутствующий собеседник и доступный шаг.')
    who=option['who'];now=_now(state)
    if state['energy']<3:raise ValueError(u'Недостаточно сил для разговора.')
    verb,arg=key.split(':',1)
    if verb=='invite':
        return schedule(state,who,state['day']+1,1095,state['place'])
    elif verb=='pledge':
        who,action=arg.split(':',1);spec=next(r for r in __import__('dg_actions').available(state) if r['key']==action)
        r=_append(state,{'kind':'task','who':who,'place':state['place'],'action':action,'due':state['day']*1440+1200,'status':'open','title':spec['title']})
        text=u'Ты пообещал выполнить конкретное дело до завтра 20:00: '+spec['title']+u'. Обещание принято, но работа пока не выполнена. Если собеседник не увидит работу, о результате нужно рассказать лично.'
    else:
        r=next(r for r in rows(state) if r['id']==arg)
        if verb=='cancel':r['status']='cancelled';text=u'Ты заранее предупредил об отмене. Обещание не считается выполненным; штрафа за честное предупреждение нет.'
        elif verb=='report':
            r['status']='fulfilled';p=_relation(state,who);p['trust']=min(20,p['trust']+2)
            text=u'Ты рассказал о выполненной работе. Запись реального поступка подтверждена; собеседник теперь знает о результате.'
        elif verb=='attend':
            tick(state)
            text=u'Вы проводите десять минут вместе на назначенной встрече. Выполнение зависит от реального совместного присутствия.'
        else:raise ValueError('Unknown commitment')
    dg_epistemic.record(state,'account','commitment:'+r['id']+':'+verb,{'status':r['status'],'kind':r['kind'],'title':r['title']},['hero',who])
    state['energy']-=3;_hold(state,who,option['minutes'])
    dg_clock.advance(state,option['minutes']);dg_rpg._journal(state,text)
    return {'status':'done','kind':'commitment','title':option['title'],'text':text,'who':who,'private':True}

def performed(state,key,at,witnesses):
    for r in rows(state):
        if r['kind']=='task' and r['status']=='open' and r['action']==key and at<=r['due']:
            r['evidence']={'key':key,'at':at,'witnesses':list(witnesses)};r['status']='performed'
            if r['who'] in witnesses:
                r['status']='fulfilled';p=_relation(state,r['who']);p['trust']=min(20,p['trust']+2)

def destination(state,who):
    now=_now(state)
    r=next((r for r in rows(state) if r['kind']=='meeting' and r['who']==who and r['status']=='open' and r['due']-35<=now<r['due']+30),None)
    return r['place'] if r else None

def tick(state):
    import dg_rpg
    if 'camp_life' not in state:return
    now=_now(state)
    for r in rows(state):
        if r['status']!='open':continue
        if not r.get('reminded') and r['due']-30<=now<=r['due']:
            r['reminded']=True;dg_rpg._journal(state,u'Скоро срок: '+r['title']+u' · '+dg_rpg.NPC_NAMES[r['who']])
        if r['kind']=='meeting' and r['due']<=now<r['due']+30:
            here=dg_rpg.where_is(state,r['who'])==r['place']
            if here:r['arrived']=True
            if here and state['place']==r['place']:
                r['progress']+=max(0,min(5,now-(r['last'] if r['last'] is not None else now)))
                if r['progress']>=10:
                    r['status']='fulfilled';p=_relation(state,r['who']);p['trust']=min(20,p['trust']+2)
                    __import__('dg_epistemic').record(state,'meeting','hero:'+r['id'],{'place':r['place'],'minutes':r['progress']},['hero',r['who']])
                    dg_rpg._journal(state,u'Назначенная встреча состоялась: '+dg_rpg.NPC_NAMES[r['who']])
            r['last']=now if here and state['place']==r['place'] else None
        if now>=(r['due']+30 if r['kind']=='meeting' else r['due']+1) and r['status']=='open':
            r['status']='missed' if r['kind']=='task' or r['arrived'] else 'excused'
            if r['status']=='missed':
                p=_relation(state,r['who']);p['trust']=max(-20,p['trust']-2);p['tension']=min(20,p['tension']+2)
            dg_rpg._journal(state,(u'Договорённость не выполнена: ' if r['status']=='missed' else u'Встреча сорвалась из-за занятости собеседника: ')+r['title'])

def report(state,who=None):
    visible=[copy.deepcopy(r) for r in rows(state) if who is None or r['who']==who]
    if who is not None:
        for r in visible:
            if r['status']=='performed':r['status']='open'
            r.pop('evidence',None)
    return {'records':visible[-24:],'rule':u'open — только договорённость; performed — дело выполнено, но собеседник ещё не осведомлён; fulfilled — подтверждено. Чужие личные договорённости не известны NPC.'}

def validate(state):
    s=state.get('commitments')
    if s is None:return
    import dg_rpg
    if not isinstance(s,dict) or type(s.get('sequence')) is not int or not isinstance(s.get('records'),list) or len(s['records'])>48:raise ValueError('Invalid commitments')
    ids=set()
    for r in s['records']:
        if not isinstance(r,dict) or r.get('kind') not in ('task','meeting') or r.get('who') not in __import__('dg_life').PEERS or r.get('place') not in dg_rpg.PLACE_NAMES or r.get('status') not in ('open','performed','fulfilled','cancelled','missed','excused') or type(r.get('due')) is not int or type(r.get('created')) is not int or not 0<=r['created']<r['due']<=122*1440 or not isinstance(r.get('id'),(str,type(u''))) or not r['id'].isdigit() or r['id'] in ids or int(r['id'])>s['sequence'] or not isinstance(r.get('title'),(str,type(u''))) or len(r['title'])>300:raise ValueError('Invalid commitment record')
        ids.add(r['id'])
        if r['kind']=='task' and (not isinstance(r.get('action'),(str,type(u''))) or (r['status'] in ('performed','fulfilled') and not isinstance(r.get('evidence'),dict))):raise ValueError('Missing commitment evidence')
        if r['kind']=='meeting' and (type(r.get('progress')) is not int or not 0<=r['progress']<=20 or type(r.get('arrived')) is not bool or r['status']=='performed'):raise ValueError('Invalid meeting progress')
