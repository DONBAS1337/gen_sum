# -*- coding: utf-8 -*-
"""Pure presentation helpers and bounded dialogue history."""
from __future__ import unicode_literals
import copy,hashlib,json

def record(state,key,text):
    import dg_stage
    ui=state.setdefault('presentation',{'lines':[],'seen_events':None})
    if any(row['scene']==key for row in ui['lines']):return
    present=list(dg_stage.NAMES)
    for turn in dg_stage.parse(text,present):
        ui['lines'].append({'scene':key,'who':turn['who'],'text':turn['text'][:700],'day':state['day'],'slot':state['slot'],'place':state['place']})
    ui['lines']=ui['lines'][-180:]

def history(state):return copy.deepcopy(state.get('presentation',{}).get('lines',[]))

def history_display(state):
    # Reverse scenes, never the pages/words within a scene.
    groups=[]
    for row in history(state):
        if not groups or groups[-1][0]['scene']!=row['scene']:groups.append([])
        group=groups[-1]
        if group and group[-1]['who']==row['who'] and len(group[-1]['text'])+len(row['text'])+1<=700:
            group[-1]['text']+=' '+row['text']
        else:group.append(row)
    return [row for group in reversed(groups) for row in group]

def command(value, fallback='back'):
    if not isinstance(value,(tuple,list)) or len(value)!=2 or not isinstance(value[0],(str,type(u''))):
        import logging
        logging.getLogger('don_gen').warning('Invalid screen result type=%s; returning safely',type(value).__name__)
        return (fallback,None)
    return tuple(value)

def event_token(state):
    data={'event':state.get('world',{}).get('event'),'incident':state.get('social',{}).get('incident'),'visit':state.get('npc_visits',{}).get('active'),'projects':state.get('projects',{}).get('records',{}),'day':state['day']}
    return hashlib.sha1(json.dumps(data,ensure_ascii=True,sort_keys=True).encode('utf-8')).hexdigest()

def unread(state):return state.get('presentation',{}).get('seen_events')!=event_token(state)
def seen(state):state.setdefault('presentation',{'lines':[],'seen_events':None})['seen_events']=event_token(state)

def status(state,who):
    import dg_rpg
    if __import__('dg_clues').known(state,who):return u'Хочет разобраться в личном вопросе'
    if who=='el' and __import__('dg_risk').encounter(state):return u'Просит помочь с антенной клубов'
    person=state.get('npc_agendas',{}).get('people',{}).get(who,{})
    relation=state.get('relationships',{}).get('people',{}).get(who,{})
    text=dg_rpg.relationship_label(state,who)
    if relation.get('tension',0)>=4:text+=u' · есть напряжение'
    elif person.get('goal',{}).get('status')=='blocked':text+=u' · нужна помощь'
    elif person.get('active'):text+=u' · занят своим делом'
    return text

def validate(state):
    ui=state.get('presentation')
    if ui is None:return
    import dg_rpg,dg_stage
    if not isinstance(ui,dict) or not isinstance(ui.get('lines'),list) or len(ui['lines'])>180:raise ValueError('Invalid presentation history')
    if ui.get('seen_events') is not None and (not isinstance(ui['seen_events'],(str,type(u''))) or len(ui['seen_events'])!=40):raise ValueError('Invalid event marker')
    for row in ui['lines']:
        if not isinstance(row,dict) or row.get('who') not in tuple(dg_stage.NAMES)+('hero',None) or not isinstance(row.get('text'),(str,type(u''))) or len(row['text'])>700 or row.get('place') not in dg_rpg.PLACE_NAMES or row.get('slot') not in (0,1,2,3) or not isinstance(row.get('day'),int) or not isinstance(row.get('scene'),(str,type(u''))):raise ValueError('Invalid dialogue history row')


def recent_scenes(state, who=None):
    rows=history(state);keys=[]
    for row in rows:
        if (who is None or row['who']==who) and row['scene'] not in keys:keys.append(row['scene'])
    return [' '.join(r['text'] for r in rows if r['scene']==key)[-3500:] for key in keys[-3:]]

def repeats_scene(text, previous):
    import re,dg_stage
    def shingles(value):
        words=re.findall(r'\w+',dg_stage.readable(value).lower(),re.UNICODE)
        return set(tuple(words[i:i+8]) for i in range(len(words)-7))
    current=shingles(text)
    if len(current)<40:return False
    for old in previous:
        old=shingles(old)
        if len(old)>=40 and len(current & old)/float(len(current))>=0.65:return True
    return False


def creation_command(value):
    if isinstance(value,(tuple,list)) and len(value)==1:value=(value[0],None)
    return command(value,'cancel')
