# -*- coding: utf-8 -*-
"""Player-selected cabin and roommate; no relationship rewards or story overrides."""
from __future__ import unicode_literals
import copy
CABINS=tuple('cabin_%02d' % n for n in range(1,32))
RESERVED_CABINS = {'cabin_13': ('un', 'mi')}
AVAILABLE_CABINS = tuple(cabin for cabin in CABINS if cabin not in RESERVED_CABINS)
FEMALE_ROOMMATES = ('mi', 'dv', 'un', 'sl', 'us', 'mz', 'mt', 'cs')
ROOMMATES=('mi','dv','un','sl','us','mz','el','sh','mt','cs')

def assign(state,cabin='cabin_01',roommate='mt'):
    if cabin not in AVAILABLE_CABINS or roommate not in ROOMMATES+(None,):
        raise ValueError('Invalid housing choice')
    state['housing']={'cabin':cabin,'roommate':roommate}
    return state['housing']

def validate(state):
    value=state.get('housing')
    if value is not None and (not isinstance(value,dict) or value.get('cabin') not in CABINS or value.get('roommate') not in ROOMMATES+(None,)):
        raise ValueError('Invalid housing record')

def report(state):
    return copy.deepcopy(state.get('housing'))

def location(state,who):
    value=state.get('housing')
    if state['slot'] != 3:
        return None
    if value and value['roommate'] == who:
        return value['cabin']
    if who in RESERVED_CABINS['cabin_13']:
        return 'cabin_13'
    return None


def at_own_cabin(state):
    return state.get('place') == (state.get('housing') or {}).get('cabin')


def door(state, inside):
    if not at_own_cabin(state) or state.get('finished') or type(inside) is not bool:
        raise ValueError(u'Войти можно только в свой домик в активной смене.')
    if state.get('cabin_inside', False) == inside:
        return {'status': 'done', 'text': u'Ты уже здесь.', 'kind': 'door', 'who': None}
    import dg_rpg, dg_clock
    state['cabin_inside'] = inside
    if dg_clock.enabled(state):
        dg_rpg._tick(state, 1)
    text = u'Ты вошёл в свой домик.' if inside else u'Ты вышел из домика на крыльцо.'
    dg_rpg._journal(state, text)
    return {'status': 'done', 'text': text, 'kind': 'door', 'who': None}


def door_intent(state, text):
    if not at_own_cabin(state):
        return None
    text = text.lower().strip().rstrip('.!')
    if text in (u'войти в свой домик', u'зайти в свой домик', u'зайти в домик', u'войти в домик', u'иду в свой домик'):
        return True
    if text in (u'выйти из домика', u'выйти на крыльцо', u'выхожу из домика'):
        return False
    return None
