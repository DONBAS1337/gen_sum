# -*- coding: utf-8 -*-
"""Per-shift pacing; reading time never advances the game clock."""
from __future__ import unicode_literals
def dialogue_minutes(state):return state.get('pacing',{}).get('dialogue_minutes',5)
def visit_gap(state,personal=False):
    value=state.get('pacing',{}).get('visits','normal')
    return {'rare':12,'normal':4,'often':3}[value] if personal else {'rare':6,'normal':2,'often':1}[value]
def validate(state):
    s=state.get('pacing')
    if s is None:return
    if not isinstance(s,dict) or set(s)-set(('dialogue_minutes','visits')) or type(s.get('dialogue_minutes',5)) is not int or dialogue_minutes(state) not in (3,5,8) or s.get('visits','normal') not in ('rare','normal','often'):raise ValueError('Invalid pacing settings')
