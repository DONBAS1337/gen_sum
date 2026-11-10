# -*- coding: utf-8 -*-
"""Bounded dialogue exchanges within a period; mutations occur only on commit."""
from __future__ import unicode_literals
EXCHANGES = 6

def rounds(state):
    return state.get('dialogue_clock', {}).get('rounds', 0)

def consume(state, who):
    import dg_rpg
    count = rounds(state) + 1
    state['dialogue_clock'] = {'rounds':count, 'who':who}
    if __import__('dg_clock').enabled(state):
        __import__('dg_clock').advance(state,__import__('dg_pacing').dialogue_minutes(state))
        return
    if count >= EXCHANGES:
        dg_rpg._tick(state)

def end(state):
    if rounds(state):
        import dg_rpg
        if __import__('dg_clock').enabled(state):
            state.pop('dialogue_clock',None)
            dg_rpg._journal(state,u'Беседа завершена. Потраченное на реплики время уже учтено.')
            return True
        dg_rpg._journal(state, u'Беседа завершена. Прошёл один период дня.')
        dg_rpg._tick(state)
        return True
    return False

def validate(state):
    clock = state.get('dialogue_clock')
    if clock is None: return
    import dg_rpg
    if (not isinstance(clock, dict) or type(clock.get('rounds')) is not int
            or not 1 <= clock['rounds'] < (145 if __import__('dg_clock').enabled(state) else EXCHANGES) or clock.get('who') not in dg_rpg.NPC_NAMES):
        raise ValueError('Invalid dialogue clock')
