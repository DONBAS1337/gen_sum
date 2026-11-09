# -*- coding: utf-8 -*-
"""Audio direction from authoritative location, weather and relationships."""
from __future__ import unicode_literals
INTERIORS = ('canteen','kitchen','library','infirmary','clubs','clubhouse','administration','headquarters','radio','storage','warehouse','gym','showers','laundry','beachhouse')
WATER = ('lake','beach','pier','boathouse')
FOREST = ('forest','forest_path','old_camp','campfire')

def plan(state, who=None):
    import dg_world
    place, slot = state['place'], state['slot']
    suffix = ('day','day','evening','night')[slot]
    ambience = []
    if place == 'gate': ambience.append('ambience_camp_entrance_'+('night' if slot==3 else 'day'))
    elif place in WATER: ambience.append('ambience_lake_shore_'+('night' if slot==3 else 'day'))
    elif place in FOREST: ambience.append('ambience_forest_'+suffix)
    elif place.startswith('cabin_') or place in ('cabins','cabins_south'):
        if place.startswith('cabin_'): ambience.append('ambience_int_cabin_'+('night' if slot==3 else 'day'))
    elif place=='music': ambience.append('ambience_music_club_'+('night' if slot==3 else 'day'))
    elif place=='infirmary': ambience.append('ambience_medstation_inside_'+('night' if slot==3 else 'day'))
    elif place=='library': ambience.append('ambience_library_day')
    elif place in ('canteen','kitchen'): ambience.append('ambience_dining_hall_full' if slot<2 else 'ambience_dining_hall_empty')
    elif place in INTERIORS: ambience.append('ambience_clubs_inside_day')
    else: ambience.append('ambience_camp_center_'+suffix)
    if place not in INTERIORS and not place.startswith('cabin_'):
        if dg_world.weather(state)[0]=='rain': ambience.insert(0,'ambience_hard_rain_outside')
        ambience.extend(['ambience_camp_center_'+suffix,'ambience_camp_center_day'])
    tension=state.get('relationships',{}).get('people',{}).get(who,{}).get('tension',0)
    if who and tension>=6: music=['reflection_on_water','waltz_of_doubts']
    elif who and who in state.get('npc_visits',{}).get('romance',[]): music=['what_do_you_think_of_me','lets_be_friends']
    elif slot==3: music=['silhouette_in_sunset','reflection_on_water']
    elif slot==2: music=['silhouette_in_sunset','lets_be_friends']
    else: music=['my_daily_life','lets_be_friends']
    return {'music':music,'ambience':ambience}

def movement(before, after):
    if before==after: return []
    if before in INTERIORS or after in INTERIORS or before.startswith('cabin_') or after.startswith('cabin_'):
        return ['sfx_open_door_1','sfx_open_door_2']
    return []

def resolve(catalog, keys, loadable):
    for key in keys:
        path=catalog.get(key)
        if path and loadable(path): return path
    return None
