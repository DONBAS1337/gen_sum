# -*- coding: utf-8 -*-
"""Deterministic checks for explicit facts extracted from generated prose."""
from __future__ import unicode_literals
import copy

def contract(context):
    import dg_rpg
    inner=context.get('scene_identity') or context.get('narrative_direction') or context
    anchor=context.get('scene_anchor') or inner
    place=anchor.get('place');day=anchor.get('day',inner.get('day'))
    reverse=dict((name,code) for code,name in dg_rpg.PLACE_NAMES.items())
    place=reverse.get(place,place)
    time=anchor.get('slot',anchor.get('time',inner.get('slot')))
    if time in dg_rpg.SLOTS:time=dg_rpg.SLOTS.index(time)
    people=context.get('present_people',inner.get('present_people',[]));codes=['hero']
    for person in people:
        who=person[0] if isinstance(person,(list,tuple)) and len(person)==2 else person
        if who in dg_rpg.NPC_NAMES:codes.append(who)
        else:
            codes.extend(code for code,name in dg_rpg.NPC_NAMES.items() if name==who)
    after=context.get('confirmed_after_state') or {}
    projects=after.get('shared_projects',context.get('shared_projects',inner.get('shared_projects',{})))
    inventory=after.get('inventory',context.get('inventory',inner.get('inventory',{})))
    bags={'hero':copy.deepcopy(projects.get('inventory',inventory.get('player',{})))}
    bags.update(copy.deepcopy(projects.get('npc_inventory',inventory.get('people',{}))))
    owners=copy.deepcopy(bags)
    for loan in inventory.get('world',{}).get('loans',[]):
        if loan.get('status')=='open':
            item=loan['item'];holder=loan['holder'];owner=loan['owner']
            owners.setdefault(holder,{})[item]=max(0,owners.get(holder,{}).get(item,0)-1)
            owners.setdefault(owner,{})[item]=owners.get(owner,{}).get(item,0)+1
    return {'actor_codes':copy.deepcopy(dg_rpg.NPC_NAMES),'item_codes':__import__('dg_inventory').CATALOG,'day':day,'slot':time,'place':place,'people':sorted(set(codes)), 'bags':bags,'owners':owners,'projects':dict((key,row['stage']) for key,row in projects.get('records',{}).items())}

def check(claims,facts):
    import dg_rpg,dg_inventory
    if not isinstance(claims,list) or len(claims)>32:raise ValueError('Invalid extracted facts')
    issues=[]
    for row in claims:
        if not isinstance(row,dict) or not isinstance(row.get('kind'),(str,type(u''))) or row.get('kind') not in ('presence','place','slot','day','owns','holds','project_stage'):raise ValueError('Unknown extracted fact')
        kind=row['kind'];mismatch=False;code='continuity'
        if kind=='presence':
            if set(row)!=set(('kind','actor')) or row['actor'] not in tuple(dg_rpg.NPC_NAMES)+('hero',):raise ValueError('Invalid actor fact')
            mismatch=row['actor'] not in facts['people'];code='people'
        elif kind in ('place','slot','day'):
            if set(row)!=set(('kind','value')):raise ValueError('Invalid scene anchor fact')
            if kind=='place' and (not isinstance(row['value'],(str,type(u''))) or row['value'] not in dg_rpg.PLACE_NAMES):raise ValueError('Invalid place fact')
            if kind in ('slot','day') and (not isinstance(row['value'],int) or isinstance(row['value'],bool)):raise ValueError('Invalid time fact')
            mismatch=facts[kind] is not None and row['value']!=facts[kind];code='place' if kind=='place' else 'time'
        elif kind in ('owns','holds'):
            if set(row)!=set(('kind','actor','item','count')) or row['actor'] not in tuple(dg_rpg.NPC_NAMES)+('hero',) or not isinstance(row['item'],(str,type(u''))) or row['item'] not in dg_inventory.CATALOG or not isinstance(row['count'],int) or isinstance(row['count'],bool) or not 1<=row['count']<=3:raise ValueError('Invalid ownership fact')
            mismatch=facts['owners' if kind=='owns' else 'bags'].get(row['actor'],{}).get(row['item'],0)<row['count'];code='items'
        else:
            if set(row)!=set(('kind','project','value')) or not isinstance(row['project'],(str,type(u''))) or not isinstance(row['value'],int) or isinstance(row['value'],bool) or not 0<=row['value']<=4:raise ValueError('Invalid project fact')
            mismatch=facts['projects'].get(row['project'],0)!=row['value'];code='effects'
        if mismatch:issues.append({'code':code,'text':u'Факт сцены не подтверждён движком: '+type(u'')(row)[:450]})
    return issues
