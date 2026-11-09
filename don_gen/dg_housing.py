# -*- coding: utf-8 -*-
"""Player-selected cabin and roommate; no relationship rewards or story overrides."""
from __future__ import unicode_literals
import copy
CABINS=tuple('cabin_%02d' % n for n in range(1,32))
ROOMMATES=('mi','dv','un','sl','us','mz','el','sh','mt','cs')

def assign(state,cabin='cabin_01',roommate='mt'):
    if cabin not in CABINS or roommate not in ROOMMATES+(None,):
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
    return value['cabin'] if value and value['roommate']==who and state['slot']==3 else None
