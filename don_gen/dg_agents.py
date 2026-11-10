# -*- coding: utf-8 -*-
"""Persistent NPC agendas, advanced by game turns, never by screen redraws."""
from __future__ import unicode_literals
import copy
import hashlib

PROFILES = {
 'mi':('music','help'), 'dv':('music','repair'), 'us':('music','help'),
 'sl':('help','organize'), 'un':('read','explore'), 'mz':('read','organize'),
 'el':('repair','explore'), 'sh':('repair','explore'),
 'mt':('organize','help'), 'cs':('help','organize'), 'uv':('explore',)}
TASKS = {
 'music':(u'Подготовить свой фрагмент репетиции','music','festival'),
 'repair':(u'Разобраться с оборудованием кружка','clubs','radio'),
 'help':(u'Закончить общее лагерное поручение','canteen','council'),
 'organize':(u'Согласовать дела и распределить работу','square','council'),
 'read':(u'Разобрать записи и найти нужные сведения','library','radio'),
 'explore':(u'Проверить маршрут и отметить наблюдения','forest_path','lake')}


def _number(state, who, cycle):
    return int(hashlib.sha1(('%s:%s:%s' % (state['id'],who,cycle)).encode('ascii')).hexdigest()[:8],16)


def _new_goal(state, who, cycle):
    kind = PROFILES[who][_number(state,who,cycle) % len(PROFILES[who])]
    title, place, arc = TASKS[kind]
    project=__import__('dg_projects').offer_goal(state,who) if cycle>0 else None
    goal={'id':'%s:%d' % (who,cycle), 'kind':kind, 'title':title,
            'place':place, 'arc':arc, 'progress':0, 'required':3,
            'status':'working', 'deadline':state['day']+5, 'blocked_turns':0}
    if project:goal.update(project)
    return goal


def ensure(state):
    system = state.setdefault('npc_agendas', {'people':{}, 'history':[], 'last_turn':None})
    for who in sorted(PROFILES):
        if who == 'uv' and not state.get('mystery',{}).get('yulia_discovered'):
            continue
        system['people'].setdefault(who, {'energy':80, 'cycle':0, 'active':False,
            'goal':_new_goal(state,who,0)})
    return system


def _log(state, who, text, status):
    system = ensure(state)
    system['history'].append({'day':state['day'],'slot':state['slot'],
                              'who':who,'text':text,'status':status})
    system['history'] = system['history'][-64:]


def _complete(state, who, person):
    import dg_world
    goal = person['goal']
    if not __import__('dg_projects').npc_complete(state,who,goal):
        goal.update(status='blocked',progress=goal['required']-1,blocked_turns=min(3,goal['blocked_turns']+1))
        _log(state,who,u'Ждёт участника или предмет для совместного дела.','blocked')
        return
    goal['status'] = 'completed'
    world = dg_world.ensure(state)
    world['preparations'][goal['arc']] = dg_world.clamp(world['preparations'].get(goal['arc'],0)+2)
    _log(state,who,u'Завершено собственное дело: ' + goal['title'], 'completed')


def tick(state):
    if state.get('finished'):
        return []
    system = ensure(state)
    moment = (state['day']-1)*4+state['slot']
    if system['last_turn'] == moment:
        return []
    previous = copy.deepcopy(system['history'][-1:])
    system['last_turn'] = moment
    people = sorted(who for who in system['people'] if (who == 'uv') == (state['slot'] == 3))
    for who, person in system['people'].items():
        if state['slot'] == 0:
            person['energy'] = min(100,person['energy']+40)
        if state['slot'] == 3 and who != 'uv':
            person['active'] = False
    if not people:
        return []
    # Two autonomous decisions per turn keep global effects bounded.
    offset = moment*2 % len(people)
    for who in (people[offset:] + people[:offset])[:2]:
        if (who == 'uv' and state['slot'] != 3) or (who != 'uv' and state['slot'] == 3):
            continue
        person = system['people'][who]
        goal = person['goal']
        if goal['status'] in ('completed','abandoned'):
            person['cycle'] += 1
            person['goal'] = goal = _new_goal(state,who,person['cycle'])
        person['active'] = True
        if state['day'] > goal['deadline']:
            goal['status'] = 'abandoned'
            person['active'] = False
            _log(state,who,u'Пересматривает просроченный план: ' + goal['title'], 'abandoned')
            continue
        import dg_rpg
        if dg_rpg.where_is(state,who) != goal['place']:
            person['active'] = False
            _log(state,who,u'Пока откладывает своё дело из-за других обстоятельств.', 'occupied')
            continue
        if person['energy'] < 15:
            person['energy'] = min(100,person['energy']+25)
            person['active'] = False
            _log(state,who,u'Отдыхает перед продолжением своего дела.', 'rest')
            continue
        person['energy'] -= 12
        obstacle = (_number(state,who,moment) % 5 == 0 and goal['progress'] < 2)
        if obstacle:
            goal['status'] = 'blocked'
            goal['blocked_turns'] += 1
            _log(state,who,u'Нужна помощь: ' + goal['title'], 'blocked')
            if goal['blocked_turns'] >= 3 or state['day'] > goal['deadline']:
                goal['status'] = 'abandoned'
                _log(state,who,u'Меняет план после затруднений: ' + goal['title'], 'abandoned')
        else:
            goal['status'] = 'working'
            goal['progress'] += 1
            _log(state,who,u'Самостоятельно продвигает дело: ' + goal['title'], 'working')
            if goal['progress'] >= goal['required']:
                _complete(state,who,person)
    __import__('dg_projects').meetings(state)
    return copy.deepcopy(system['history'][-4:]) if system['history'][-1:] != previous else []


def location(state, who):
    if __import__("dg_camp").in_intro(state):return None
    person = state.get('npc_agendas',{}).get('people',{}).get(who)
    if not person or not person.get('active') or person['goal']['status'] not in ('working','blocked'):
        return None
    if who == 'uv' and state['slot'] != 3:
        return None
    if who != 'uv' and state['slot'] == 3:
        return None
    import dg_world
    place = person['goal']['place']
    if dg_world.weather(state)[0] == 'rain' and place in ('square','forest_path'):
        return 'library' if who in ('un','mz') else 'clubs'
    return place


def assist(state, who, intent):
    person = state.get('npc_agendas',{}).get('people',{}).get(who)
    if not person or person['goal']['status'] not in ('working','blocked') or intent not in ('help','create','practice','search','mediate'):
        return None
    import dg_rpg
    if dg_rpg.where_is(state,who) != state['place']:
        return None
    goal = person['goal']
    if state['place'] != goal['place']:
        return None
    applicable = {'music':('help','practice','create'), 'repair':('help','create','search'),
                  'help':('help','mediate'), 'organize':('help','mediate','create'),
                  'read':('help','search'), 'explore':('help','search')}
    if intent not in applicable[goal['kind']]:
        return None
    goal['progress'] = min(goal['required'],goal['progress']+1)
    goal['status'] = 'working'
    goal['blocked_turns'] = 0
    _log(state,who,u'Получена помощь игрока: ' + goal['title'], 'helped')
    if goal['progress'] >= goal['required']:
        _complete(state,who,person)
    return u'Продвинуто дело %s: %s (%d/%d).' % (dg_rpg.NPC_NAMES[who],goal['title'],goal['progress'],goal['required'])


def report(state):
    system = state.get('npc_agendas',{})
    return copy.deepcopy({'people':system.get('people',{}),'recent_actions':system.get('history',[])[-8:]})


def validate(state):
    system = state.get('npc_agendas')
    if system is None:
        return
    if not isinstance(system,dict) or not isinstance(system.get('people'),dict) or len(system['people']) > 11:
        raise ValueError('Invalid NPC agendas')
    if not isinstance(system.get('history'),list) or len(system['history']) > 64:
        raise ValueError('Invalid NPC action history')
    import dg_rpg
    def integer(value, low, high):
        return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    if system.get('last_turn') is not None and not integer(system['last_turn'],0,50000):
        raise ValueError('Invalid NPC clock')
    for who, person in system['people'].items():
        if not isinstance(person,dict) or not isinstance(person.get('goal'),dict):
            raise ValueError('Invalid NPC record')
        goal = person['goal']
        if (who not in PROFILES or goal.get('kind') not in TASKS
                or goal.get('status') not in ('working','blocked','completed','abandoned')
                or not integer(person.get('energy'),0,100) or not integer(person.get('cycle'),0,50000)
                or not isinstance(person.get('active'),bool)
                or not integer(goal.get('required'),1,10) or not integer(goal.get('progress'),0,goal['required'])
                or not integer(goal.get('blocked_turns'),0,3) or not integer(goal.get('deadline'),1,50000)
                or goal.get('place') not in dg_rpg.PLACE_NAMES or goal.get('arc') not in ('festival','radio','council','lake')
                or not isinstance(goal.get('title'),type(u'')) or len(goal['title']) > 200
                or not isinstance(goal.get('id'),type(u'')) or len(goal['id']) > 100):
            raise ValueError('Invalid NPC goal')
        if 'project' in goal:
            projects=__import__('dg_projects')
            if (not isinstance(goal.get('project'),type(u'')) or goal.get('project') not in projects.definitions(state) or goal.get('project_stage') not in (0,1,2,3) or goal.get('project_role') not in (None,'recipient') or goal['place']!=projects.definitions(state)[goal['project']]['steps'][goal['project_stage']][1]):
                raise ValueError('Invalid project goal')
    for row in system['history']:
        if (not isinstance(row,dict) or row.get('who') not in PROFILES
                or not integer(row.get('day'),1,50000) or not integer(row.get('slot'),0,3)
                or row.get('status') not in ('working','blocked','completed','abandoned','occupied','rest','helped')
                or not isinstance(row.get('text'),type(u'')) or len(row['text']) > 400):
            raise ValueError('Invalid NPC history row')
