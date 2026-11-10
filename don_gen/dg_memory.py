# -*- coding: utf-8 -*-
"""Durable scene memory and actionable follow-ups, independent of prose cache."""
from __future__ import unicode_literals
import copy
import hashlib
import re

TOPICS = {
    'music': (u'репет', u'музык', u'гитар', u'песн', u'выступ', u'играть'),
    'trust': (u'обещ', u'довер', u'извин', u'секрет', u'благодар'),
    'explore': (u'исслед', u'провер', u'узнать', u'найти', u'поиск'),
    'help': (u'помоч', u'помог', u'почин', u'подготов', u'помощ')}
LABELS = {'music':u'Продолжение репетиции', 'trust':u'Вернуться к важному разговору',
          'explore':u'Проверить прежнюю находку', 'help':u'Продолжить общее дело'}


def topic(text):
    text = text.lower()
    return next((key for key in ('music', 'trust', 'explore', 'help')
                 if any(word in text for word in TOPICS[key])), None)


def record(state, key, action, result, scene, who=None, origin=None, spawn_thread=True, deferred=None, private=None):
    import dg_stage
    origin = origin or state
    memory = state.setdefault('story_memory', {'episodes':[], 'threads':[], 'people':{}})
    for name, value in (('episodes',[]), ('threads',[]), ('people',{})):
        memory.setdefault(name, value)
    memory.setdefault('milestones', [])
    if any(row['id'] == key for row in memory['episodes']):
        return
    row = {'id':key, 'day':origin['day'], 'slot':origin['slot'], 'place':origin['place'],
           'who':who, 'intention':action[:500], 'confirmed_result':result[:700],
           'narrated_scene':dg_stage.readable(scene)[:900]}
    private=private if private is not None else bool(re.search(u'наедине|ш[её]потом|личн|не рассказывай|между нами',action.lower()))
    row['witnesses']=([who] if who else []) if private else [code for code,name in __import__('dg_rpg').at_place(origin)]
    if who and who not in row['witnesses']:row['witnesses'].append(who)
    row['public']=False if private else (origin['place'] in ('stage','radio','square') and (state.get('world',{}).get('decisions')!=origin.get('world',{}).get('decisions') or any(record['stage']==4 and origin.get('projects',{}).get('records',{}).get(key,{}).get('stage',0)<4 for key,record in state.get('projects',{}).get('records',{}).items())))
    row['deferred'] = list(deferred or [])
    memory['episodes'].append(row)
    memory['episodes'] = memory['episodes'][-96:]
    if who:
        person = memory['people'].setdefault(who, {'meetings':0, 'last':None})
        person.setdefault('first_meeting', copy.deepcopy(row))
        person['meetings'] += 1
        person['last'] = copy.deepcopy(row)
    if (state.get('world', {}).get('decisions') != origin.get('world', {}).get('decisions')
            or state.get('quests_done') != origin.get('quests_done')
            or state.get('route_events_done') != origin.get('route_events_done')):
        memory['milestones'].append(copy.deepcopy(row))
        memory['milestones'] = memory['milestones'][-24:]
    subject = topic(action)
    folded = action.lower()
    intended = any(word in folded for word in (u'хочу',u'давай',u'предлага',u'предлож',u'продолж',
                   u'попроб',u'обещ',u'собира',u'завтра',u'начать',u'науч',u'провер',u'найти',
                   u'исслед',u'помочь',u'помог',u'обсуд'))
    refusal = re.search(u'\\bне\\b.{0,20}(?:хоч|буд|обещ|собира|предла|продолж|репет|помо)', folded)
    if spawn_thread and subject and intended and not refusal and not any(t['topic'] == subject and t.get('who') == who and t['status'] == 'open'
                           for t in memory['threads']):
        ident = hashlib.sha1((key + ':' + subject).encode('utf-8')).hexdigest()[:16]
        memory['threads'].append({'id':ident, 'topic':subject, 'who':who,
                                  'place':origin['place'], 'day':origin['day'],
                                  'title':LABELS[subject], 'intention':action[:300],
                                  'status':'open', 'attempts':0,'witnesses':copy.deepcopy(row['witnesses']),'public':row['public']})
        memory['threads'] = memory['threads'][-48:]


def recall(state, who=None):
    memory = state.get('story_memory', {})
    known=lambda row:who is None or row.get('who')==who or who in row.get('witnesses',[]) or row.get('public',False)
    episodes = [row for row in memory.get('episodes',[]) if known(row)]
    relevant = [row for row in episodes if (who and row.get('who') == who)
                or row['place'] == state['place']]
    rows = relevant[-5:] + episodes[-3:]
    unique = []
    for row in rows:
        if row['id'] not in [item['id'] for item in unique]:
            unique.append(copy.deepcopy(row))
    return {'relevant_episodes':unique, 'people':copy.deepcopy(dict((code,person) for code,person in memory.get('people',{}).items() if who is None or code==who)),
            'milestones':copy.deepcopy([row for row in memory.get('milestones',[]) if known(row)][-8:]),
            'open_threads':copy.deepcopy([row for row in memory.get('threads', [])
                                         if row['status'] == 'open' and known(row)][-8:]),
            'knowledge_owner':who,
            'rule':u'Личная память отфильтрована по свидетелям и публичным фактам. Отсутствующий NPC не знает частного разговора. Намерения и реплики не доказывают достижения. Только confirmed_result — механический исход; narrated_scene — запись прежнего рассказа.'}


def validate(state):
    memory = state.get('story_memory')
    if memory is None:
        return
    if not isinstance(memory, dict):
        raise ValueError('Invalid story memory')
    for name, limit in (('episodes',96), ('threads',48), ('milestones',24)):
        rows = memory.get(name, [])
        if not isinstance(rows, list) or len(rows) > limit or not all(isinstance(row, dict) for row in rows):
            raise ValueError('Invalid story memory collection')
    if not isinstance(memory.get('people', {}), dict) or len(memory.get('people', {})) > 11:
        raise ValueError('Invalid character memories')
    import dg_rpg
    for row in memory.get('episodes', []) + memory.get('milestones', []):
        if (not isinstance(row.get('id'), (str, type(u''))) or row.get('place') not in dg_rpg.PLACE_NAMES
                or row.get('slot') not in (0,1,2,3) or not isinstance(row.get('day'), int)
                or row['day'] < 1 or row.get('who') not in tuple(dg_rpg.NPC_NAMES) + (None,)):
            raise ValueError('Invalid episode memory')
        for field, limit in (('intention',500), ('confirmed_result',700), ('narrated_scene',900)):
            if not isinstance(row.get(field), (str, type(u''))) or len(row[field]) > limit:
                raise ValueError('Invalid remembered text')
        if not isinstance(row.get('witnesses',[]),list) or len(row.get('witnesses',[]))>11 or any(code not in dg_rpg.NPC_NAMES for code in row.get('witnesses',[])) or not isinstance(row.get('public',False),bool):raise ValueError('Invalid memory witnesses')
        deferred = row.get('deferred', [])
        if not isinstance(deferred,list) or len(deferred)>3 or any(not isinstance(item,(str,type(u''))) or len(item)>250 for item in deferred):
            raise ValueError('Invalid deferred intentions')
    for row in memory.get('threads', []):
        if (row.get('topic') not in TOPICS or row.get('status') not in ('open','resolved','abandoned')
                or row.get('place') not in dg_rpg.PLACE_NAMES or not isinstance(row.get('day'), int)
                or not isinstance(row.get('id'), (str, type(u'')))):
            raise ValueError('Invalid unfinished story thread')
    for who, person in memory.get('people', {}).items():
        if (who not in dg_rpg.NPC_NAMES or not isinstance(person, dict)
                or not isinstance(person.get('meetings'), int) or person['meetings'] < 0):
            raise ValueError('Invalid remembered participant')


def opportunity(state):
    """A prior action can create tomorrow's situation, never an instant reward."""
    import dg_rpg
    candidates = [t for t in state.get('story_memory', {}).get('threads', [])
                  if t['status'] == 'open' and t['day'] < state['day']
                  and t.get('attempts', 0) < 2
                  and (t.get('who') != 'uv' or (state['slot'] == 3 and
                       state.get('mystery', {}).get('yulia_discovered')))]
    if not candidates:
        return None
    seed = int(hashlib.sha1((state['id'] + str(state['day'])).encode('ascii')).hexdigest()[:8], 16)
    thread = candidates[seed % len(candidates)]
    who = thread.get('who') or ('mi' if thread['topic'] == 'music' else 'sl')
    place = thread['place']
    import dg_world
    moved = u''
    if dg_world.weather(state)[0] == 'rain' and place in ('stage','square','gate','beach','lake','forest','forest_path','sports','campfire','outdoor_stage') and who != 'uv':
        place = 'music' if who in ('mi','dv','us') else 'library' if who in ('un','mz') else 'canteen'
        moved = u' Из-за дождя встречу перенесли под крышу: %s.' % dg_rpg.PLACE_NAMES[place]
    introduction=(u' Подробности личной инициативы героя ещё не известны собеседнику; сначала герой должен рассказать о ней.' if not (thread.get('who')==who or who in thread.get('witnesses',[]) or thread.get('public')) else u'')
    return {'id':'%d:thread:%s' % (state['day'], thread['id']), 'day':state['day'],
            'arc':'daily', 'stage':0, 'place':place, 'npc':who, 'thread_id':thread['id'],
            'title':thread['title'],
            'story':(u'Продолжение твоего поступка из дня %d: «%s». %s готовит следующий шаг. '
                     u'Предыдущий разговор не решил всё за один раз: теперь можно продолжить дело, '
                     u'разобраться в затруднении или предложить другой путь. Не считай прежнее намерение уже выполненной работой.') %
                    (thread['day'], thread['intention'], dg_rpg.NPC_NAMES[who]) + moved + introduction}


def resolve(state, event, choice):
    for row in state.get('story_memory', {}).get('threads', []):
        if row['id'] == event.get('thread_id'):
            if choice == 'missed':
                row['attempts'] = row.get('attempts', 0) + 1
                row['day'] = state['day']
                if row['attempts'] >= 2:
                    row['status'] = 'abandoned'
            else:
                row['status'] = 'resolved'
                row['resolution'] = choice
                row['resolved_day'] = state['day']
