# -*- coding: utf-8 -*-
"""Original arrival, camp routines and acquaintance progression. No donor scripts."""
from __future__ import unicode_literals
import copy
TOUR=(('infirmary','cs'),('library','mz'),('clubs','el'),('music','mi'),('sports','us'))
CLUBS={'music':u'Музыкальный кружок','clubs':u'Технический кружок','library':u'Библиотека','sports':u'Спортивная секция'}
ARRIVAL=(('gate','sl',u'Познакомиться со Славей',u'Славя встречает нового пионера у ворот, представляется и объясняет, как найти вожатую.'),
         ('home','mt',u'Представиться вожатой',u'Ольга Дмитриевна знакомится с новичком, подтверждает выбранное размещение и объясняет распорядок лагеря.'),
         ('square','mt',u'Прийти на линейку приезда',u'Вожатая представляет новичка отряду. Имена услышаны, но личная дружба с каждым ещё не возникла.'),
         ('canteen','sl',u'Освоиться в столовой',u'Славя объясняет порядок в столовой и основные места лагеря. Завтра предстоит обходной лист, а сегодня можно освоиться.'))
JOBS={'canteen':(u'Дежурство в столовой','canteen','mt',35),
      'equipment':(u'Перенести оборудование на сцену','warehouse','mt',45),
      'grounds':(u'Уборка территории','square','sl',30)}

def enabled(state):return 'camp_life' in state

def enable(state,arrival=False):
    if enabled(state):return
    minute=(540,780,1140,1350)[state['slot']]
    state['camp_life']={'version':1,'minute':minute,'arrival':0 if arrival else 4,'tour_issued':False,
                        'stamps':[],'club':None,'done':[],'jobs':{},'contacts':{},'touches':[]}
    __import__('dg_world').ensure(state)
    for who in state.get('met',[]):
        history=[row for row in state.get('dialogue_history',[]) if row.get('who')==who]
        days=sorted(set(row['day'] for row in history if type(row.get('day')) is int and 1<=row['day']<=state['day'])) or [state['day']]
        state['camp_life']['contacts'][who]={'days':days[-120:],'count':len(history) or 1}
    state['world']['event']=None
    if state.get('social',{}).get('incident'):state['social']['incident']['status']='resolved'
    if arrival:
        state['place']='gate';state['world']['event']=None
        if state.get('social',{}).get('incident'):state['social']['incident']['status']='resolved'

def in_intro(state):
    c=state.get('camp_life')
    return bool(c and (c['arrival']<4 or state['day']<3 or c['club'] is None))

def _key(state,name):return '%d:%s'%(state['day'],name)

def _done(state,name):return _key(state,name) in state['camp_life']['done']

def _mark(state,name):
    c=state['camp_life'];c['done'].append(_key(state,name));c['done']=c['done'][-512:]

def record_contact(state,who,trust=True):
    if not enabled(state):return
    c=state['camp_life'];person=c['contacts'].setdefault(who,{'days':[],'count':0})
    if state['day'] not in person['days']:
        person['days'].append(state['day']);person['days']=person['days'][-120:]
        if trust and who in __import__('dg_relationships').LIKES:
            relation=__import__('dg_relationships').person(state,who)
            relation['trust']=min(20,relation['trust']+1)
    person['count']+=1

def stage(state,who):
    if who not in state['met']:return 'stranger'
    days=state.get('camp_life',{}).get('contacts',{}).get(who,{}).get('days',[]) if enabled(state) else [1,2,3]
    if who in state.get('npc_visits',{}).get('romance',[]):return 'romance'
    if state['affinity'][who]>=45 and len(days)>=3:return 'close'
    if state['affinity'][who]>=25 and len(days)>=2:return 'friend'
    return 'acquaintance'

def _meet(state,who):
    if who not in state['met']:state['met'].append(who)
    record_contact(state,who)

def refresh(state):
    if not enabled(state):return
    c=state['camp_life']
    __import__('dg_clues').refresh(state)
    if c['minute']>=720 and c['arrival']==4:
        for name in ('wash','assembly'):
            if not _done(state,name) and not _done(state,'missed_'+name):
                _mark(state,'missed_'+name)
                __import__('dg_rpg')._journal(state,u'Пропущено утреннее дело: '+(u'умывание' if name=='wash' else u'линейка'))
                if name=='assembly':state['world']['morale']=max(0,state['world']['morale']-1)
    companion=c.get('companion')
    if companion and __import__('dg_clock').absolute(state)>=companion['until']:c.pop('companion',None)
    for row in c['jobs'].values():
        if row['status']=='active' and (state['day']>row['deadline'] or state.get('finished')):
            row['status']='missed'
            relation=__import__('dg_relationships').person(state,row['who']);relation['tension']=min(20,relation['tension']+1)
            state['affinity'][row['who']]=max(0,state['affinity'][row['who']]-1)
            __import__('dg_rpg')._journal(state,u'Пропущено поручение: '+row['title'])

def location(state,who):
    if not enabled(state):return None
    c=state['camp_life'];n=c['arrival'];minute=c['minute']
    if n==2 and who not in ('uv','cs'):return 'square'
    if n<4:
        place,actor,title,story=ARRIVAL[n]
        if who==actor:return state['housing']['cabin'] if place=='home' else place
    if 510<=minute<540 and who not in ('uv','cs'):return 'square'
    if (540<=minute<570 or 780<=minute<840 or 1140<=minute<1200) and who not in ('uv','cs'):return 'canteen'
    risk_place=__import__('dg_risk').location(state,who)
    if risk_place:return risk_place
    scheduled=__import__('dg_schedule').location(state,who)
    if scheduled:return scheduled
    if 1290<=minute<1320 and who in ('mi','dv','un','sl','mz','el','sh'):return 'showers'
    companion=c.get('companion')
    if companion and companion['who']==who and __import__('dg_clock').absolute(state)<companion['until']:return state['place']
    if state['day']>=2 and not c['tour_issued'] and who=='mt':return state['housing']['cabin']
    if c['tour_issued'] and c['club'] is None:
        for place,actor in TOUR:
            if who==actor:return place
    return None

def cards(state):
    if not enabled(state) or state['finished']:return []
    c=state['camp_life'];rows=[];minute=c['minute']
    def add(key,title,place,who,minutes,story):rows.append({'key':key,'title':title,'place':place,'who':who,'minutes':minutes,'story':story,'ready':state['place']==place and (who is None or __import__('dg_rpg').where_is(state,who)==place)})
    if c['arrival']<4:
        place,who,title,story=ARRIVAL[c['arrival']]
        if c['arrival']==0 and who in state['met']:story=u'Славя продолжает знакомство с лагерем и объясняет дорогу к вожатой; повторно представляться не нужно.'
        add('arrival',title,state['housing']['cabin'] if place=='home' else place,who,15,story)
    if state['day']>=2 and c['arrival']==4 and not c['tour_issued']:
        add('tour_issue',u'Получить обходной лист',state['housing']['cabin'],'mt',10,u'Вожатая выдаёт обходной лист: медпункт, библиотека, технический и музыкальный кружки, спортплощадка. Кружок выбирает сам игрок после знакомства с местами.')
    if c['tour_issued'] and c['club'] is None:
        for place,who in TOUR:
            if place not in c['stamps']:add('stamp:'+place,u'Обходной лист: '+__import__('dg_rpg').PLACE_NAMES[place],place,who,10,(u'Знакомый ответственный объяснил работу своего места и поставил отметку. Повторное представление не нужно.' if who in state['met'] else u'Короткое личное знакомство с ответственным и отметка о посещении. Это не вступление в кружок и не согласие на совместный проект.'))
        if len(c['stamps'])==len(TOUR):
            for place,title in sorted(CLUBS.items()):add('join:'+place,u'Выбрать: '+title,place,dict(TOUR).get(place,'sl'),15,u'Игрок выбирает направление занятий после обхода лагеря. Членство не означает близких отношений с участниками.')
    if c['arrival']>=2 and minute<720:
        if not _done(state,'wash'):add('wash',u'Умыться','washrooms',None,10,u'Утреннее умывание и подготовка к лагерному дню.')
        if 510<=minute<540 and not _done(state,'assembly') and _done(state,'wash') and c['arrival']==4:add('assembly',u'Утренняя линейка','square','mt',15,u'Построение отряда: объявления, распорядок и поручения на день.')
        if not _done(state,'breakfast') and _done(state,'assembly'):add('breakfast',u'Позавтракать','canteen',None,20,u'Завтрак в столовой.')
    if 720<=minute<1080 and not _done(state,'lunch'):add('lunch',u'Пообедать','canteen',None,25,u'Обед и небольшой перерыв среди дневных дел.')
    if 1080<=minute<1320 and not _done(state,'dinner'):add('dinner',u'Поужинать','canteen',None,25,u'Ужин в столовой перед вечерними занятиями.')
    if c['arrival']==4 and not _done(state,'job_issue'):
        proposed=JOBS[('canteen','equipment','grounds')[(state['day']-1)%3]][0]
        add('job_issue',u'Взять поручение: '+proposed,__import__('dg_rpg').where_is(state,'mt'),'mt',5,u'Вожатая предлагает конкретное лагерное дежурство. Игрок может взять поручение или пока не подходить.')
    for key,row in sorted(c['jobs'].items()):
        if row['status']=='active':add('job:'+key,row['title'],row['place'],None,row['minutes'],u'Выполнить принятое поручение лично в нужном месте. Оборудование — лагерное; оно не становится вещью героя.')
    rows.extend(__import__('dg_schedule').cards(state))
    rows.extend(__import__('dg_risk').cards(state))
    rows.extend(__import__('dg_clues').cards(state))
    if __import__('dg_risk').injured(state) and not state['health']['treated']:
        add('treatment',u'Повторный осмотр после травмы','infirmary','cs',20,u'Повторный осмотр ушиба в медпункте; выздоровление требует времени.')
    if __import__('dg_risk').injured(state):
        rows=[r for r in rows if not r['key'].startswith('job:') and r['key'] not in ('job_issue','event:outing','event:weekly_disco')]
    add('wait',u'Подождать 10 минут',state['place'],None,10,u'Герой ждёт, пока лагерный день идёт своим чередом.')
    if minute>=1260:add('sleep',u'Вернуться в домик и лечь спать',state['housing']['cabin'],None,1440-minute,u'Вечерние дела закончены. Герой ложится спать до утреннего подъёма.')
    return rows

def hint(state):
    if not enabled(state):return u'Можно осмотреться, продолжить своё дело или открыть карту.'
    c=state['camp_life']
    if c['arrival']<4:
        place,who,title,story=ARRIVAL[c['arrival']]
        place=state['housing']['cabin'] if place=='home' else place
        return u'Следующий шаг: '+title+u' — '+__import__('dg_rpg').PLACE_NAMES[place]+u'.'
    if state['day']==1:return u'Сегодня можно освоиться в лагере. Завтра вожатая выдаст обходной лист.'
    if not c['tour_issued']:return u'Вожатая ждёт для выдачи обходного листа. Открой распорядок.'
    if len(c['stamps'])<len(TOUR):return u'Обходной лист: %d/5 отметок. Места и переходы — в распорядке.'%len(c['stamps'])
    if c['club'] is None:return u'Обход закончен. Теперь можно выбрать кружок.'
    return u'Кружок: '+CLUBS[c['club']]+u'. Можно заняться своим делом или посмотреть распорядок.'


def intro_here(state,who):
    for row in cards(state):
        if row['key']=='arrival' and row['ready'] and row['who']==who:return row
    return None


def act(state,key):
    import dg_rpg,dg_clock
    if key.startswith('clue:'):return __import__('dg_clues').act(state,key)
    if key.startswith('risk:'):return __import__('dg_risk').resolve(state,key)
    matches=[row for row in cards(state) if row['key']==key and row['ready']]
    if not matches:raise ValueError(u'Сейчас это лагерное действие недоступно в этом месте.')
    row=matches[0];c=state['camp_life'];who=row['who']
    if key.startswith('job:') and state['energy']<8:raise ValueError(u'Для работы нужно не меньше 8 сил.')
    if key.startswith('event:'):
        row=__import__('dg_schedule').resolve(state,row);_mark(state,key)
    elif key=='treatment':
        row=dict(row,story=__import__('dg_risk').treatment(state))
    elif key=='arrival':
        if c['arrival']==2:_mark(state,'assembly')
        c['arrival']+=1
    elif key=='tour_issue':c['tour_issued']=True
    elif key.startswith('stamp:'):c['stamps'].append(key.split(':',1)[1])
    elif key.startswith('join:'):
        c['club']=key.split(':',1)[1]
        row=dict(row,story=u'Игрок выбрал направление и вступил: '+CLUBS[c['club']]+u'. Отметки обхода сохранены. Это не близость с участниками и не согласие на общий проект.')
    elif key=='job_issue':
        ident=('%d'%state['day']);kind=('canteen','equipment','grounds')[(state['day']-1)%3];title,place,actor,cost=JOBS[kind]
        if kind=='equipment' and __import__('dg_hero').has(state,'technical'):cost-=5
        c['jobs'][ident]={'title':title,'place':place,'who':actor,'minutes':15 if kind=='equipment' and __import__('dg_hero').has(state,'technical') else 20 if kind=='equipment' else cost,'deadline':state['day']+1,'status':'active','kind':kind,'step':0}
        _mark(state,key);row=dict(row,story=u'Получено поручение: '+title+u'. Срок — до конца следующего дня. Работа ещё не выполнена.')
    elif key.startswith('job:'):
        job=c['jobs'][key.split(':',1)[1]]
        if job.get('kind')=='equipment' and job.get('step',0)==0:
            job.update(step=1,place='stage',minutes=25,title=u'Доставить подготовленное оборудование на сцену')
            row=dict(row,minutes=row["minutes"],story=u'Оборудование подготовлено к переноске на хозяйственном дворе. Теперь его нужно доставить на сцену; поручение ещё не закончено.')
        else:
            job['status']='done';credit=job['who']
            row=dict(row,story=(u'Оборудование лично доставлено на сцену. Поручение выполнено.' if job.get('kind')=='equipment' else u'Принятое лагерное дежурство выполнено лично в нужном месте. Новых предметов герой не получил.'))
            state['affinity'][credit]=min(100,state['affinity'][credit]+2);state['stats']['kindness']+=1
            relation=__import__('dg_relationships').person(state,credit);relation['trust']=min(20,relation['trust']+1)
    else:_mark(state,key)
    if who:_meet(state,who)
    if key in ('breakfast','lunch','dinner'):state['energy']=min(100,state['energy']+20)
    elif key not in ('sleep','wash','job_issue'):state['energy']=max(0,state['energy']-(8 if key.startswith('job:') else 3))
    dg_clock.advance(state,row['minutes'])
    dg_rpg._journal(state,row['title']+u'. '+row['story'])
    return {'who':who,'title':row['title'],'text':row['story']}

def report(state):
    if not enabled(state):return None
    return {'calendar':__import__('dg_schedule').report(state),'health':__import__('dg_risk').report(state),'hero_profile':__import__('dg_hero').profile(state),'clock':__import__('dg_clock').text(state),'arrival_step':state['camp_life']['arrival'],
            'tour_issued':state['camp_life']['tour_issued'],'tour_stamps':list(state['camp_life']['stamps']),
            'club':state['camp_life']['club'],'relationship_stages':dict((who,stage(state,who)) for who in state['met']),
            'next_activities':copy.deepcopy(cards(state)),
            'rule':u'Сначала знакомство и обход лагеря. Источник БКРР начинает свою историю на четвёртый день; это не доказательство, что герой текущей смены уже состоит в музклубе. Не назначай совместные проекты незнакомым людям. next_activities — только будущие возможности, не завершённые действия и не состав текущего кадра.'}

def validate(state):
    if not enabled(state):return
    import dg_rpg,dg_clock
    c=state['camp_life']
    if not isinstance(c,dict) or c.get('version')!=1 or type(c.get('arrival')) is not int or not 0<=c['arrival']<=4:raise ValueError('Invalid camp arrival')
    if not isinstance(c.get('tour_issued'),bool) or not isinstance(c.get('stamps'),list) or any(not isinstance(p,(str,type(u''))) for p in c['stamps']) or len(set(c['stamps']))!=len(c['stamps']) or any(p not in dict(TOUR) for p in c['stamps']) or c.get('club') not in tuple(CLUBS)+(None,):raise ValueError('Invalid camp tour')
    if not isinstance(c.get('done'),list) or len(c['done'])>512 or not isinstance(c.get('jobs'),dict) or len(c['jobs'])>120 or not isinstance(c.get('contacts'),dict) or len(c['contacts'])>11:raise ValueError('Invalid camp records')
    if any(not isinstance(row,(str,type(u''))) or len(row)>80 for row in c['done']):raise ValueError('Invalid daily record')
    companion=c.get('companion')
    if companion is not None and (not isinstance(companion,dict) or companion.get('who') not in dg_rpg.NPC_NAMES or type(companion.get('until')) is not int or not 1<=companion['until']<=200000):raise ValueError('Invalid companion')
    for who,p in c['contacts'].items():
        if who not in dg_rpg.NPC_NAMES or not isinstance(p,dict) or not isinstance(p.get('days'),list) or len(p['days'])>120 or any(type(day) is not int or not 1<=day<=121 for day in p['days']) or type(p.get('count')) is not int or not 0<=p['count']<=100000:raise ValueError('Invalid camp contact')
    for row in c['jobs'].values():
        if not isinstance(row,dict) or not isinstance(row.get('title'),(str,type(u''))) or len(row['title'])>200 or row.get('status') not in ('active','done','missed') or row.get('place') not in dg_rpg.PLACE_NAMES or row.get('who') not in dg_rpg.NPC_NAMES or type(row.get('minutes')) is not int or not 1<=row['minutes']<=120 or type(row.get('deadline')) is not int:raise ValueError('Invalid camp job')
    __import__('dg_risk').validate(state)
    __import__('dg_clues').validate(state)
    dg_clock.validate(state)
