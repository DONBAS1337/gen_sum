# -*- coding: utf-8 -*-
"""Identity and bounded custody records for actual loanable inventory units."""
from __future__ import unicode_literals

def ensure(state):
    import dg_inventory
    world=state['inventory_world'];bags={'hero':state['projects']['inventory']};bags.update(state['projects']['npc_inventory'])
    if 'instances' not in world:
        rows=[]
        for item,spec in sorted(dg_inventory.CATALOG.items()):
            if not spec.get('loanable'):continue
            number=0
            for actor,bag in sorted(bags.items()):
                for n in range(bag.get(item,0)):
                    number+=1;rows.append({'id':('%s:%s'%(item,state['id'])) if item=='shirt' else '%s:%d'%(item,number),'item':item,'owner':actor,'holder':actor,'marker':u'контрастный шов' if item=='shirt' else spec['title']+u' №%d'%number,'custody':[]})
            for place,stock in sorted(world['stock'].items()):
                for n in range(stock.get(item,0)):
                    number+=1;rows.append({'id':'%s:%d'%(item,number),'item':item,'owner':'camp','holder':'stock:'+place,'marker':spec['title']+u' №%d'%number,'custody':[]})
        world['instances']=rows
        for loan in world['loans']:
            instance=next((r for r in rows if r['item']==loan['item'] and r['holder']==loan['holder']),None)
            if instance:instance['owner']=loan['owner'];loan['instance']=instance['id']
    return world['instances']

def moved(state,operation,item,origin,target):
    import dg_inventory,dg_rpg,dg_clock,dg_epistemic
    if not dg_inventory.CATALOG[item].get('loanable') or operation not in ('take','transfer'):return None
    rows=ensure(state);source='stock:'+origin if operation=='take' else origin
    instance=next((r for r in rows if r['item']==item and r['holder']==source),None)
    if not instance:raise ValueError('Physical item instance is missing')
    place=origin if origin in dg_rpg.PLACE_NAMES else state['place'] if origin=='hero' else dg_rpg.where_is(state,origin)
    witnesses=[w for w,n in dg_rpg.at_place(state,place)]
    if state['place']==place:witnesses.append('hero')
    witnesses=list(set(witnesses+[p for p in (origin,target) if p in tuple(dg_rpg.NPC_NAMES)+('hero',)]))
    instance['holder']=target;instance['owner']=target
    instance['custody'].append({'at':dg_clock.absolute(state),'origin':origin,'target':target,'witnesses':witnesses})
    instance['custody']=instance['custody'][-32:]
    dg_epistemic.record(state,'transfer',instance['id'],{'origin':origin,'target':target,'item':item},witnesses)
    return instance['id']

def validate(state):
    rows=state.get('inventory_world',{}).get('instances')
    if rows is None:return
    import dg_inventory,dg_rpg
    if not isinstance(rows,list) or len(rows)>128:raise ValueError('Invalid item instances')
    keys=[]
    for r in rows:
        if not isinstance(r,dict) or r.get('item') not in dg_inventory.CATALOG or not isinstance(r.get('id'),(str,type(u''))) or len(r['id'])>100 or r['id'] in keys or not isinstance(r.get('marker'),(str,type(u''))) or len(r['marker'])>200 or not isinstance(r.get('custody'),list) or len(r['custody'])>32:raise ValueError('Invalid physical item')
        keys.append(r['id'])
        for who in (r.get('owner'),r.get('holder')):
            if who not in ('camp','hero')+tuple(dg_rpg.NPC_NAMES) and who not in ['stock:'+p for p in dg_rpg.PLACE_NAMES]:raise ValueError('Invalid custody actor')
