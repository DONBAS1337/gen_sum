# -*- coding: utf-8 -*-
"""Stable individual priorities and evidence-backed emotional continuity."""
from __future__ import unicode_literals
import copy,hashlib,re

# Values are bounded conversational preferences, not universal approval rolls.
PROFILES={
 'mi':{'stance':{'support':1,'curious':2,'bold':1},'need':u'быть услышанной как музыкант и человек','conflict':u'сначала объясняет, при давлении становится краткой','repair':u'честное объяснение и совместное спокойное дело','initiative':u'предлагает музыку, но спрашивает, удобно ли сейчас'},
 'dv':{'stance':{'support':0,'curious':1,'bold':2},'need':u'самостоятельность и прямой ответ без покровительства','conflict':u'возражает прямо; не обязана скрывать всё за насмешкой','repair':u'признание ошибки без оправданий и уважение выбора','initiative':u'предлагает смелый вариант и допускает отказ'},
 'un':{'stance':{'support':2,'curious':1,'bold':0},'need':u'время сформулировать мысль и отсутствие публичного давления','conflict':u'берёт паузу, затем обозначает конкретную претензию','repair':u'спокойный личный разговор без требования немедленного прощения','initiative':u'может первой предложить тихое совместное занятие'},
 'sl':{'stance':{'support':2,'curious':1,'bold':0},'need':u'надёжная помощь, которая не создаёт ещё одну обязанность','conflict':u'объясняет последствия и перераспределяет нагрузку','repair':u'выполненное дело и возможность отдохнуть','initiative':u'просит помощи, умеет отказаться от лишней работы'},
 'mz':{'stance':{'support':0,'curious':2,'bold':0},'need':u'точность, тишина и уважение личного пространства','conflict':u'коротко называет нарушение, не изображает постоянную ненависть','repair':u'конкретное исправление вместо многословных комплиментов','initiative':u'предлагает разобраться в интересной записи'},
 'el':{'stance':{'support':1,'curious':1,'bold':2},'need':u'интерес к делу и признание вклада товарищей','conflict':u'пытается найти практический выход, может признать страх','repair':u'проверяемая помощь и разделение ответственности','initiative':u'предлагает опыт, не скрывая возможную неудачу'},
 'sh':{'stance':{'support':0,'curious':2,'bold':1},'need':u'понятные основания и время проверить гипотезу','conflict':u'уточняет факты и отделяет ошибку от умысла','repair':u'доказательства и исправление ошибочного предположения','initiative':u'просит проверить конкретную часть расчёта'},
 'us':{'stance':{'support':1,'curious':0,'bold':2},'need':u'честные правила игры и уважение без снисхождения','conflict':u'спорит о справедливости, учится отвечать за последствия','repair':u'честная договорённость и дружеская игра','initiative':u'предлагает игру; только дружеские отношения'},
 'mt':{'stance':{'support':2,'curious':1,'bold':0},'need':u'надёжность, безопасность отряда и отдых','conflict':u'разбирает поступок и последствия, не наказывает автоматически','repair':u'исправленное нарушение и выполненная обязанность','initiative':u'просит о конкретном посильном поручении'},
 'cs':{'stance':{'support':1,'curious':2,'bold':0},'need':u'честное описание самочувствия и соблюдение рекомендаций','conflict':u'сохраняет профессиональную дистанцию и спокойствие','repair':u'реальное соблюдение рекомендаций','initiative':u'предлагает помощь, уважая медицинские границы'},
 'uv':{'stance':{'support':1,'curious':2,'bold':0},'need':u'уважение тайны и право не отвечать','conflict':u'отходит и ограничивает сведения','repair':u'уважение обозначенной границы','initiative':u'редкая дружеская встреча, без взрослых ролей'}}
KINDS=('support','curious','bold','pressure','insult','honesty','promise_kept','promise_broken','shared_success','setback','apology')

def ensure(state):return state.setdefault('personality',{'people':{},'seen':[]})
def person(state,who):return ensure(state)['people'].setdefault(who,{'stress':0,'last_day':state['day'],'memories':[]})

def tick(state):
    for p in state.get('personality',{}).get('people',{}).values():
        if state['day']>p['last_day']:
            p['stress']=max(0,p['stress']-min(3,state['day']-p['last_day']));p['last_day']=state['day']

def classify(text):
    text=text.lower()
    if re.search(u'\\b(?:не|никогда)\\b',text):return None
    if any(w in text for w in (u'заткни',u'идиот',u'ненавиж',u'дура')):return 'insult'
    if any(w in text for w in (u'ты обязан',u'ты должна',u'немедленно',u'я заставлю')):return 'pressure'
    if any(w in text for w in (u'извини',u'прости за')):return 'apology'
    if any(w in text for w in (u'спасибо',u'благодар',u'я выслушаю',u'я тебя слушаю')):return 'support'
    return None

def react(state,who,kind,key,detail=u''):
    if who not in PROFILES or kind not in KINDS:return {'gain':0,'repeat':False}
    tick(state);s=ensure(state);p=person(state,who)
    ident=hashlib.sha1((who+':'+kind+':'+key).encode('utf-8')).hexdigest()
    if ident in s['seen']:return {'gain':0,'repeat':True}
    s['seen'].append(ident);s['seen']=s['seen'][-256:]
    # Praise/insults cannot be farmed by changing wording within the same day.
    repeated=any(r['kind']==kind and r['day']==state['day'] for r in p['memories'])
    if repeated:return {'gain':0,'repeat':True}
    pressure=2 if who in ('un','mz','dv') else 1
    delta=pressure if kind in ('pressure','insult','promise_broken') else 1 if kind=='setback' else -1
    p['stress']=max(0,min(10,p['stress']+delta))
    gain=-3 if kind=='insult' else -2 if kind=='pressure' else PROFILES[who]['stance'].get(kind,1)
    p['memories'].append({'id':ident,'day':state['day'],'kind':kind,'detail':detail[:300]});p['memories']=p['memories'][-16:]
    return {'gain':gain,'repeat':False,'stress':p['stress']}

def stance(state,who,choice):
    if 'camp_life' not in state:return 0
    result=react(state,who,choice,'dialogue:%d:%s'%(state['day'],choice))
    return result['gain'] if __import__('dg_camp').stage(state,who) in ('friend','close','romance') else 0

def consent(state,who,kind):
    stress=state.get('personality',{}).get('people',{}).get(who,{}).get('stress',0)
    if stress>=7:return False,u'Собеседнику нужна пауза после напряжённых событий.'
    if who in ('un','mz') and kind in ('hug','hand'):
        crowd=len(__import__('dg_rpg').at_place(state))
        if crowd>=4 and stress>=3:return False,u'Сейчас собеседнику некомфортно публичное прикосновение; лучше спокойно поговорить наедине.'
    return True,u''

def brief(state,who):
    if who not in PROFILES:return {}
    p=state.get('personality',{}).get('people',{}).get(who,{})
    stress=max(0,p.get('stress',0)-min(3,max(0,state['day']-p.get('last_day',state['day']))))
    energy=state.get('npc_agendas',{}).get('people',{}).get(who,{}).get('energy',80)
    return {'priorities':copy.deepcopy(PROFILES[who]),'stress':stress,
            'mood':u'нужна пауза' if stress>=7 else u'сдержанность после напряжения' if stress>=3 else u'усталость' if energy<25 else u'обычное состояние',
            'own_experiences':copy.deepcopy(p.get('memories',[])[-5:]),
            'rule':u'Это личные переживания подтверждённых поступков. Различай голос, инициативу и способ решения конфликта. Не превращай черту характера в диагноз; не выдумывай знакомство, роман или новую причину ревности.'}

def validate(state):
    s=state.get('personality')
    if s is None:return
    if not isinstance(s,dict) or not isinstance(s.get('people'),dict) or len(s['people'])>11 or not isinstance(s.get('seen'),list) or len(s['seen'])>256:raise ValueError('Invalid personality memory')
    for who,p in s['people'].items():
        if who not in PROFILES or not isinstance(p,dict) or type(p.get('stress')) is not int or not 0<=p['stress']<=10 or type(p.get('last_day')) is not int or not isinstance(p.get('memories'),list) or len(p['memories'])>16:raise ValueError('Invalid emotional state')
        for r in p['memories']:
            if not isinstance(r,dict) or r.get('kind') not in KINDS or type(r.get('day')) is not int or not isinstance(r.get('detail'),(str,type(u''))) or len(r['detail'])>300:raise ValueError('Invalid personal experience')
