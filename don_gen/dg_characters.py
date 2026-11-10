# -*- coding: utf-8 -*-
"""Character identity and reactions grounded in the current saved state."""
from __future__ import unicode_literals
import copy
VOICES={
 'mi':u'Музыкальная компетентность, увлечённость и наблюдательность. Разговорчивость не означает бесконечного потока слов; умеет быть краткой, серьёзной и возражать.',
 'dv':u'Прямота, ирония, защита самостоятельности и скрытая уязвимость. Не превращать каждую реплику в оскорбление или ревность.',
 'un':u'Тихая внимательная речь, собственное мнение и инициатива. Смущение не отменяет самостоятельности; не назначать патологическую ревность по умолчанию.',
 'sl':u'Ответственность, забота и собственные желания. Может устать, отказаться от дополнительного поручения и попросить помощи.',
 'us':u'Энергия, детское любопытство, шутки и чувство справедливости. Дружеское общение без романтических и взрослых ролей.',
 'mz':u'Книги, точность, резкость и личное пространство. Неприветливость не равна постоянной враждебности.',
 'el':u'Технический интерес, энтузиазм и потребность быть полезным. Не всезнайка и не универсальный источник чужих секретов.',
 'sh':u'Техника, сосредоточенность и последовательность. Проверяет гипотезы; не объявляет неподтверждённую догадку знанием.',
 'mt':u'Ответственность вожатой, забота, усталость и правила лагеря. Не сводить к наказаниям и не объявлять постоянное кокетство.',
 'cs':u'Профессиональная забота, спокойствие, юмор и границы. Не превращать медицинскую роль в автоматический флирт.',
 'uv':u'Скрытность и любопытство. Не знает автоматически тайны и внутренние мысли героя; появляется только при подтверждённых условиях.'}

def cards(state,people):
    import dg_relationships
    result=[]
    for who in people[:4]:
        if who not in VOICES:continue
        relation=state.get('relationships',{}).get('people',{}).get(who,{})
        agent=state.get('npc_agendas',{}).get('people',{}).get(who,{})
        memory=__import__('dg_memory').recall(state,who)
        result.append({'allowed_proposals':[kind for kind,label in __import__('dg_affection').options(state,who)],'last_contact':[row for row in state.get('affection',{}).get('history',[]) if row['who']==who][-1:],'confirmed_knowledge':__import__('dg_epistemic').recall(state,who),'own_appointments':__import__('dg_life').report(state,who),'private_observation':__import__('dg_clues').known(state,who),'knowledge':{'episodes':memory['relevant_episodes'][-3:],'milestones':memory['milestones'][-3:],'threads':memory['open_threads'][-3:]},'relationship_stage':__import__('dg_camp').stage(state,who),'who':who,'voice':VOICES[who],'source_profile':state['source'],
          'familiarity':state['affinity'][who],'met':who in state['met'],
          'romance_confirmed':who in state.get('npc_visits',{}).get('romance',[]),
          'trust':relation.get('trust',0),'tension':relation.get('tension',0),
          'tired':agent.get('energy',80)<25,'current_goal':copy.deepcopy(agent.get('goal')),
          'preferences':copy.deepcopy(dg_relationships.PREFERENCES.get(who,{})),
          'boundaries':{'invitations':relation.get('invitations',True),'home_visits':relation.get('home_visits',True)},
          'rule':u'Характер устойчив, реакция зависит от отношений, усталости, границ и текущего дела. Близость не подтверждает роман; примеры исходника не являются личными воспоминаниями.'})
    return result
