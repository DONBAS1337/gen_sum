# -*- coding: utf-8 -*-
"""Contextual invitations with per-action consent, never forced physical contact."""
from __future__ import unicode_literals
import re
LABELS={'walk':u'Предложить прогулку','hug':u'Предложить объятие','hand':u'Предложить взяться за руки','dance':u'Пригласить на танец'}

def intent(text):
    text=text.lower()
    if re.search(u'\\b(?:не|нет|вчера|помню|вспоминаю|если|потом|завтра)\\b',text):return None
    if re.search(u'обня|обним|объяти',text):return 'hug'
    if re.search(u'за рук|взяться.{0,15}рук',text):return 'hand'
    if re.search(u'потанц|приглас.{0,25}танец',text):return 'dance'
    if re.search(u'погуля|предлож.{0,20}прогул',text):return 'walk'
    return None

def options(state,who):
    import dg_camp,dg_rpg,dg_relationships
    if who not in dg_relationships.LIKES or who not in state['met'] or state['finished'] or dg_rpg.where_is(state,who)!=state['place']:return []
    stage=dg_camp.stage(state,who);relation=state.get('relationships',{}).get('people',{}).get(who,{})
    if not relation.get('invitations',True) or relation.get('tension',0)>=4:return []
    disco=dg_camp.enabled(state) and state['place']=='square' and state['day']%3==0 and 1200<=state['camp_life']['minute']<1290
    rows=[];used=state.get('affection',{}).get('cooldowns',{})
    for kind,ready in (('dance',disco),('walk',stage in ('friend','close','romance')),('hug',stage in ('close','romance') and relation.get('trust',0)>=3),('hand',stage=='romance' and relation.get('trust',0)>=4)):
        if ready and used.get(who+':'+kind)!=state['day']:rows.append((kind,LABELS[kind]))
    return rows

def act(state,who,kind):
    import dg_rpg,dg_clock,dg_camp,dg_visits
    if (kind,LABELS.get(kind)) not in options(state,who):raise ValueError(u'Для такого предложения пока недостаточно знакомства, доверия или согласованных границ.')
    if state['energy']<3:raise ValueError(u'Недостаточно сил.')
    goal=state.get('npc_agendas',{}).get('people',{}).get(who,{})
    minute=dg_clock.minute(state)
    routine=dg_camp.enabled(state) and (510<=minute<570 or 780<=minute<840 or 1140<=minute<1200)
    consent=not routine and not dg_visits.busy(state,who) and goal.get('energy',80)>=20
    system=state.setdefault('affection',{'history':[],'cooldowns':{}})
    system['cooldowns'][who+':'+kind]=state['day']
    system['history'].append({'who':who,'kind':kind,'consent':consent,'day':state['day']})
    system['history']=system['history'][-64:]
    state['energy']-=3
    if consent:
        text={'dance':u'Собеседник явно согласился на один танец. Вы потанцевали на лагерной дискотеке. Это не объявление романтических отношений.','walk':u'Собеседник согласился прогуляться вместе.','hug':u'Собеседник явно согласился на объятие. Вы ненадолго обнялись. Это не начало романа и не согласие на другие прикосновения.',
              'hand':u'Собеседник явно согласился взять тебя за руку. Это согласие только на данный жест.'}[kind]
        state['affinity'][who]=min(100,state['affinity'][who]+1)
        if kind=='walk' and dg_camp.enabled(state):state['camp_life']['companion']={'who':who,'until':dg_clock.absolute(state)+35}
    else:text=u'Собеседник сейчас занят или устал и вежливо отказался. Прикосновения не произошло; отношения не оштрафованы.'
    dg_rpg._tick(state,10 if kind=='dance' else 5)
    dg_rpg._journal(state,LABELS[kind]+u': '+text)
    return {'who':who,'title':LABELS[kind],'text':text,'consent':consent}

def validate(state):
    value=state.get('affection')
    if value is None:return
    import dg_rpg
    if not isinstance(value,dict) or not isinstance(value.get('history'),list) or len(value['history'])>64 or not isinstance(value.get('cooldowns'),dict) or len(value['cooldowns'])>44:raise ValueError('Invalid affection history')
    for row in value['history']:
        if not isinstance(row,dict) or row.get('who') not in dg_rpg.NPC_NAMES or row.get('kind') not in LABELS or not isinstance(row.get('consent'),bool) or type(row.get('day')) is not int:raise ValueError('Invalid consent record')
