# -*- coding: utf-8 -*-
"""Minute clock for the camp-life mode. Legacy saves retain their old clock."""
from __future__ import unicode_literals
BOUNDARIES=(720,1080,1320,1440)

def enabled(state): return 'camp_life' in state

def minute(state): return state.get('camp_life',{}).get('minute',(540,780,1140,1350)[state['slot']])

def absolute(state): return (state['day']-1)*1440+minute(state)

def text(state):
    value=minute(state)
    return '%02d:%02d'%(value//60,value%60)

def advance(state,minutes):
    import dg_rpg
    validate(state)
    if type(minutes) is not int or not 0<=minutes<=1440: raise ValueError('Invalid action duration')
    while minutes and not state['finished']:
        current=minute(state);boundary=BOUNDARIES[state['slot']]
        spend=min(minutes,boundary-current)
        state['camp_life']['minute']=current+spend;minutes-=spend
        if current+spend==boundary:
            dg_rpg._period_tick(state)
            state['camp_life']['minute']=420 if state['slot']==0 else BOUNDARIES[state['slot']-1]
    __import__('dg_camp').refresh(state)

def validate(state):
    if not enabled(state):return
    value=minute(state);low=(420,720,1080,1320)[state['slot']]
    if type(value) is not int or not low<=value<BOUNDARIES[state['slot']]:raise ValueError('Clock and period disagree')
