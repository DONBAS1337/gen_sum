# -*- coding: utf-8 -*-
"""Finite world stocks, owned items, loans and explicit crafting recipes."""
from __future__ import unicode_literals
import copy
CATALOG={
 'cigarettes':{'title':u'Пачка сигарет','source':None,'count':0,'restricted':True},
 'beer':{'title':u'Бутылка пива','source':None,'count':0,'restricted':True},
 'guitar':{'title':u'Гитара','source':None,'count':0},
 'jacket':{'title':u'Куртка','source':None,'count':0},
 'shirt':{'title':u'Личная рубашка','source':None,'count':0,'loanable':True},
 'notes':{'title':u'Ноты общего номера','source':'library','count':1},
 'parts':{'title':u'Детали радиооборудования','source':'warehouse','count':1},
 'paper':{'title':u'Бумага','source':'storage','count':4},
 'pencil':{'title':u'Карандаш','source':'library','count':2,'loanable':True},
 'book':{'title':u'Книга','source':'library','count':2,'loanable':True},
 'toolkit':{'title':u'Набор инструментов','source':'clubs','count':1,'loanable':True},
 'tape':{'title':u'Изолента','source':'warehouse','count':2},
 'paint':{'title':u'Краски','source':'storage','count':2},
 'cloth':{'title':u'Ткань','source':'storage','count':2},
 'tea':{'title':u'Чай','source':'canteen','count':3,'energy':8},
 'bun':{'title':u'Булочка','source':'canteen','count':3,'energy':12},
 'water':{'title':u'Вода','source':'canteen','count':3,'energy':10},
 'poster':{'title':u'Самодельный плакат','source':None,'count':0},
 'patch':{'title':u'Ремонтная заплата','source':None,'count':0}}
RECIPES={'poster':{'title':u'Нарисовать плакат','place':'clubs','inputs':{'paper':1,'paint':1},'tools':('pencil',)},
         'patch':{'title':u'Сделать ремонтную заплату','place':'clubs','inputs':{'tape':1,'cloth':1},'tools':('toolkit',)}}

PACKABLE = ('guitar', 'jacket', 'cigarettes', 'beer')
LEGACY_LUGGAGE = ('cigarettes', 'beer')


def suggest_luggage(background):
    import re
    patterns = (u'гитар', u'куртк', u'сигарет', u'пиво|пива')
    return tuple(item for item, pattern in zip(PACKABLE, patterns)
                 if re.search(pattern, background.lower()))


def toggle_luggage(packed, item):
    if item in packed:
        return tuple(key for key in packed if key != item)
    return packed + (item,)


def luggage(state):
    world = state.get('inventory_world', {})
    packed = world.get('packed_luggage', LEGACY_LUGGAGE)
    unpacked = world.get('unpacked_restricted', [])
    return tuple(item for item in packed if item not in unpacked)


def command(value):
    """Decode a screen result; RenPy Return(None) actually produces True."""
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        return None
    operation, item, who = value
    if operation not in ('take','give','lend','return','use','craft','stash','retrieve','unpack','show','play'):
        return None
    if not isinstance(item, (str, type(u''))) or item not in CATALOG:
        return None
    import dg_rpg
    if who is not None and (not isinstance(who, (str, type(u''))) or who not in dg_rpg.NPC_NAMES):
        return None
    return operation, item, who


def ensure(state):
    import dg_projects
    projects=dg_projects.ensure(state)
    if 'inventory_world' not in state:
        stock={}
        # Migration subtracts already owned and committed project materials.
        for item,spec in CATALOG.items():
            if not spec['source']:continue
            held=projects['inventory'].get(item,0)+sum(bag.get(item,0) for bag in projects['npc_inventory'].values())
            committed=sum(row.get('materials',{}).get(item,0) for row in projects['records'].values())
            if item in ('notes','parts'):
                legacy='concert' if item=='notes' else 'radio'
                if projects['records'].get(legacy,{}).get('stage',0)>=2 and not projects['records'][legacy].get('materials'):committed+=1
            stock.setdefault(spec['source'],{})[item]=max(0,spec['count']-held-committed)
        state['inventory_world']={'stock':stock,'loans':[],'ledger':[],'sequence':0,'last_supply_day':state['day']}
    if 'camp_life' in state and not state['inventory_world'].get('personal_gear'):
        held=projects['inventory'].get('shirt',0)+sum(b.get('shirt',0) for b in projects['npc_inventory'].values())
        if not held:projects['inventory']['shirt']=1
        state['inventory_world']['personal_gear']=True
    __import__('dg_instances').ensure(state)
    return state['inventory_world']

def bag(state,actor):
    import dg_projects
    return dg_projects.pouch(dg_projects.ensure(state),actor)

def log(state,operation,item,origin,target):
    world=ensure(state);world['sequence']+=1
    instance=__import__('dg_instances').moved(state,operation,item,origin,target)
    world['ledger'].append({'instance':instance,'id':world['sequence'],'day':state['day'],'slot':state['slot'],'operation':operation,'item':item,'origin':origin,'target':target})
    world['ledger']=world['ledger'][-96:]

def reservation_count(state,actor,item):
    import dg_projects
    return sum(1 for key,row in state.get('projects',{}).get('records',{}).items() if row['stage']==1 and not row.get('cancelled') and actor in row.get('contributions',{}).get('0',[]) and dg_projects.definitions(state)[key]['steps'][0][2]==item )

def reserved(state,actor,item):return reservation_count(state,actor,item)>0

def borrowed_count(state,actor,item):
    return sum(1 for row in state.get('inventory_world',{}).get('loans',[]) if row['status']=='open' and row['holder']==actor and row['item']==item)

def free_count(state,actor,item):
    return max(0,state.get('projects',{}).get('inventory',{}).get(item,0)-reservation_count(state,actor,item)) if actor=='hero' else max(0,state.get('projects',{}).get('npc_inventory',{}).get(actor,{}).get(item,0)-reservation_count(state,actor,item)-borrowed_count(state,actor,item))

def take(state,actor,item,place):
    world=ensure(state);pocket=bag(state,actor)
    count=world['stock'].get(place,{}).get(item,0)
    if count<1 or pocket.get(item,0)>=3:raise ValueError(u'Предмета нет в доступном запасе или сумка уже полна.')
    world['stock'][place][item]-=1;pocket[item]=pocket.get(item,0)+1
    log(state,'take',item,place,actor)

def transfer(state,item,origin,target):
    source=bag(state,origin);dest=bag(state,target)
    if source.get(item,0)<1 or dest.get(item,0)>=3:raise ValueError(u'Передавать нечего или у получателя нет места.')
    source[item]-=1;dest[item]=dest.get(item,0)+1;log(state,'transfer',item,origin,target)

def stock_at(state,place):
    probe=copy.deepcopy(state)
    return copy.deepcopy(ensure(probe)['stock'].get(place,{}))

def report(state):
    return {'world':copy.deepcopy(state.get('inventory_world',{})),
            'player':copy.deepcopy(state.get('projects',{}).get('inventory',{})),
            'people':copy.deepcopy(state.get('projects',{}).get('npc_inventory',{}))}

def act(state,operation,item,who=None):
    import dg_rpg,dg_projects
    if item not in CATALOG or operation not in ('take','give','lend','return','use','craft','stash','retrieve','unpack','show','play'):raise ValueError(u'Неизвестная операция с предметом.')
    if state['finished']:raise ValueError(u'Смена завершена.')
    if who is not None and (who not in dg_rpg.NPC_NAMES or dg_rpg.where_is(state,who)!=state['place']):raise ValueError(u'Собеседника нет рядом.')
    # All mutation is prepared on a copy; failure leaves even a raw caller unchanged.
    shadow=copy.deepcopy(state);world=ensure(shadow);pocket=bag(shadow,'hero')
    cost=6 if operation=='craft' else 3
    if shadow['energy']<cost:raise ValueError(u'Недостаточно сил.')
    if operation == 'unpack':
        import dg_housing
        unpacked = world.setdefault('unpacked_restricted', [])
        if (who is not None or item not in luggage(shadow)
                or not dg_housing.at_own_cabin(shadow) or not shadow.get('cabin_inside')):
            raise ValueError(u'Эту вещь нельзя достать из багажа.')
        if pocket.get(item, 0) >= 3:
            raise ValueError(u'В сумке нет места.')
        unpacked.append(item)
        pocket[item] = pocket.get(item, 0) + 1
        log(shadow, 'unpack', item, 'luggage', 'hero')
        text = u'Ты достал из своего багажа: ' + CATALOG[item]['title'] + u'.'
    elif operation == 'play':
        if who is not None or item != 'guitar' or not pocket.get('guitar', 0):
            raise ValueError(u'Для игры нужна гитара в сумке.')
        present = dict(dg_rpg.at_place(shadow))
        text = u'Ты играешь на своей гитаре.'
        if 'mi' in present:
            text += u' Мику прислушивается к мелодии.'
        elif present:
            text += u' Музыку слышат: ' + u', '.join(present[key] for key in sorted(present)) + u'.'
    elif operation == 'show':
        if not who or not CATALOG[item].get('restricted') or not pocket.get(item, 0):
            raise ValueError(u'Нужен собеседник рядом и предмет в сумке.')
        import dg_epistemic
        subject = 'restricted:' + item
        if dg_epistemic.knows(shadow, who, 'observation', subject):
            raise ValueError(u'Этот персонаж уже видел у тебя эту вещь.')
        dg_epistemic.record(shadow, 'observation', subject, {'item': item, 'holder': 'hero'}, [who, 'hero'])
        reactions = {
            'mt': u'Ольга Дмитриевна делает замечание: на смене таким вещам не место.',
            'cs': u'Виола серьёзнеет и напоминает о правилах лагеря.',
            'mi': u'Мику смущается и просит убрать вещь, пока её не увидела вожатая.',
            'dv': u'Алиса хмыкает и предупреждает, что вожатая такое заметит.',
        }
        text = u'Ты показываешь предмет: ' + CATALOG[item]['title'] + u'. ' + reactions.get(
            who, dg_rpg.NPC_NAMES[who] + u' реагирует настороженно и просит убрать вещь.')
        relationships = __import__('dg_relationships')
        if who in relationships.LIKES:
            person = relationships.person(shadow, who)
            person['tension'] = min(20, person['tension'] + 1)
    elif operation in ('stash', 'retrieve'):
        import dg_housing
        if who is not None or not dg_housing.at_own_cabin(shadow) or not shadow.get('cabin_inside'):
            raise ValueError(u'Тайник доступен внутри своего домика.')
        stash = world.setdefault('cabin_stash', {})
        if operation == 'stash':
            if free_count(shadow, 'hero', item) < 1 or stash.get(item, 0) >= 3:
                raise ValueError(u'Нет свободного предмета или места в тайнике.')
            pocket[item] -= 1
            stash[item] = stash.get(item, 0) + 1
            log(shadow, 'stash', item, 'hero', 'cabin_stash')
            text = u'Ты убрал в тайник: '
        else:
            if stash.get(item, 0) < 1 or pocket.get(item, 0) >= 3:
                raise ValueError(u'Предмета нет в тайнике или сумка полна.')
            stash[item] -= 1
            pocket[item] = pocket.get(item, 0) + 1
            log(shadow, 'retrieve', item, 'cabin_stash', 'hero')
            text = u'Ты забрал из тайника: '
        text += CATALOG[item]['title'] + u'.'
    elif operation=='take':
        take(shadow,'hero',item,shadow['place'])
        dg_projects.claim_resource(shadow,'hero',item,shadow['place'])
        text=u'Ты взял предмет из доступного запаса: '+CATALOG[item]['title']+u'.'
    elif operation in ('give','lend'):
        if CATALOG[item].get('restricted'):
            raise ValueError(u'Этот предмет нельзя передать другому персонажу.')
        if not who:raise ValueError(u'Нужен получатель.')
        if shadow.get('relationships',{}).get('people',{}).get(who,{}).get('tension',0)>=8:raise ValueError(u'Собеседник сейчас не хочет принимать вещи. Сначала стоит разобраться в конфликте.')
        if pocket.get(item,0)<=reservation_count(shadow,'hero',item):raise ValueError(u'Предмет подготовлен для общего дела. Передай его на этапе проекта или сначала отмени проект.')
        if operation=='lend' and not CATALOG[item].get('loanable'):raise ValueError(u'Этот предмет не выдаётся во временное пользование.')
        transfer(shadow,item,'hero',who)
        if operation=='lend':
            if len([r for r in world['loans'] if r['status']=='open'])>=12:raise ValueError(u'Слишком много открытых займов.')
            world['loans'].append({'id':world['sequence'],'item':item,'owner':'hero','holder':who,'deadline':shadow['day']+3,'status':'open','witnesses':[p for p,n in dg_rpg.at_place(shadow)],'instance':world['ledger'][-1].get('instance')})
            for instance in world.get('instances',[]):
                if instance['id']==world['loans'][-1]['instance']:instance['owner']='hero'
            opened=[r for r in world['loans'] if r['status']=='open']
            closed=[r for r in world['loans'] if r['status']!='open'][-(48-len(opened)):]
            world['loans']=sorted(opened+closed,key=lambda r:r['id'])
        appreciated=__import__('dg_relationships').received(shadow,who,item) if operation=='give' else False
        text=u'Предмет '+CATALOG[item]['title']+(u' передан во временное пользование.' if operation=='lend' else u' передан другому владельцу.')
        if appreciated:text+=u' Это соответствует интересам собеседника; доверие немного укрепилось.'
    elif operation=='return':
        loan=next((r for r in world['loans'] if r['item']==item and r['holder']==who and r['status']=='open'),None)
        if not loan:raise ValueError(u'Открытого займа нет.')
        transfer(shadow,item,who,'hero');loan['status']='returned'
        text=u'Одолженный предмет возвращён тебе: '+CATALOG[item]['title']+u'.'
    elif operation=='use':
        if pocket.get(item,0)<1:raise ValueError(u'Предмета нет при себе.')
        if free_count(shadow,'hero',item)<1:raise ValueError(u'Предмет закреплён за общим делом. Сначала заверши или отмени проект.')
        if CATALOG[item].get('energy'):
            shadow['energy']=min(100,shadow['energy']+CATALOG[item]['energy'])
            text=u'Ты использовал предмет: '+CATALOG[item]['title']+u'. Силы немного восстановились.'
        elif item=='poster' and shadow['place'] in ('square','stage','music','canteen'):
            import dg_world
            camp=dg_world.ensure(shadow);camp['morale']=dg_world.clamp(camp['morale']+2)
            text=u'Ты разместил готовый плакат в подходящем месте. Оформление немного подняло настроение лагеря.'
        elif item=='patch' and shadow['place'] in ('clubs','warehouse','boathouse'):
            import dg_world
            camp=dg_world.ensure(shadow);camp['resources']=dg_world.clamp(camp['resources']+2)
            text=u'Заплата использована для мелкого ремонта. Это не завершает автоматически отдельные поручения или большие проекты.'
        else:raise ValueError(u'Для предмета нет подходящего применения здесь.')
        pocket[item]-=1;log(shadow,'use',item,'hero',shadow['place'])
    else:
        recipe=RECIPES.get(item)
        if not recipe or shadow['place']!=recipe['place'] or pocket.get(item,0)>=3:raise ValueError(u'Здесь нет условий для этого рецепта.')
        if any(pocket.get(key,0)<n for key,n in recipe['inputs'].items()) or any(pocket.get(key,0)<1 for key in recipe['tools']):raise ValueError(u'Нужны материалы и инструмент из рецепта.')
        for key,n in recipe['inputs'].items():
            if pocket.get(key,0)-n<reservation_count(shadow,'hero',key):raise ValueError(u'Материал закреплён за общим делом.')
            pocket[key]-=n;log(shadow,'use',key,'hero','craft')
        pocket[item]=pocket.get(item,0)+1;log(shadow,'craft',item,'recipe','hero')
        text=u'По известному рецепту изготовлено: '+CATALOG[item]['title']+u'. Инструмент не израсходован.'
    shadow['energy']-=cost;dg_rpg._journal(shadow,text);dg_rpg._tick(shadow,30 if operation=="craft" else 10 if operation=="play" else 5);dg_rpg.validate(shadow)
    state.clear();state.update(shadow)
    return {'status':'done','title':u'Действие с предметом','text':text,'who':who,'kind':'inventory','private':operation in ('show','unpack','stash','retrieve')}

def validate(state):
    __import__('dg_instances').validate(state)
    world=state.get('inventory_world')
    if world is None:return
    import dg_rpg
    if not isinstance(world,dict) or not isinstance(world.get('stock'),dict) or len(world['stock'])>70 or not isinstance(world.get('loans'),list) or len(world['loans'])>48 or not isinstance(world.get('ledger'),list) or len(world['ledger'])>96 or not isinstance(world.get('sequence'),int) or not 0<=world['sequence']<=1000000:raise ValueError('Invalid inventory world')
    packed = world.get('packed_luggage', list(LEGACY_LUGGAGE))
    if not isinstance(packed, list) or any(item not in PACKABLE for item in packed) or len(set(packed)) != len(packed):
        raise ValueError('Invalid packed luggage')
    unpacked = world.get('unpacked_restricted', [])
    if (not isinstance(unpacked, list) or any(item not in packed for item in unpacked)
            or len(unpacked) != len(set(unpacked))):
        raise ValueError('Invalid unpacked items')
    stash = world.get('cabin_stash', {})
    if not isinstance(stash, dict) or any(item not in CATALOG or type(count) is not int
                                          or not 0 <= count <= 3 for item, count in stash.items()):
        raise ValueError('Invalid cabin stash')
    for place,items in world['stock'].items():
        if place not in dg_rpg.PLACE_NAMES or not isinstance(items,dict) or any(item not in CATALOG or not isinstance(n,int) or isinstance(n,bool) or not 0<=n<=20 for item,n in items.items()):raise ValueError('Invalid stock')
    for loan in world['loans']:
        if not isinstance(loan,dict):raise ValueError('Invalid loan')
        if not isinstance(loan.get('witnesses',[]),list) or len(loan.get('witnesses',[]))>11 or any(w not in dg_rpg.NPC_NAMES for w in loan.get('witnesses',[])):raise ValueError('Invalid loan witnesses')
        if not isinstance(loan,dict) or loan.get('item') not in CATALOG or not CATALOG[loan['item']].get('loanable') or loan.get('owner')!='hero' or loan.get('holder') not in dg_rpg.NPC_NAMES or loan.get('status') not in ('open','returned') or not isinstance(loan.get('deadline'),int) or not 1<=loan['deadline']<=50000:raise ValueError('Invalid loan')
    for row in world['ledger']:
        if not isinstance(row,dict) or row.get('item') not in CATALOG or row.get('operation') not in ('take','transfer','use','craft','commit','restock','stash','retrieve','unpack') or not isinstance(row.get('id'),int) or not isinstance(row.get('day'),int) or row.get('slot') not in (0,1,2,3):raise ValueError('Invalid inventory ledger')


def actions(state):
    import dg_rpg
    rows=[];pocket=state.get('projects',{}).get('inventory',{});place=state['place'];people=dg_rpg.at_place(state)
    if state['finished']:return rows
    if state['energy']>=3:
        import dg_housing
        if dg_housing.at_own_cabin(state) and state.get('cabin_inside'):
            stash = state.get('inventory_world', {}).get('cabin_stash', {})
            for item in luggage(state):
                if pocket.get(item, 0) < 3:
                    rows.append(('unpack', item, None, u'Достать из багажа: ' + CATALOG[item]['title']))
            for item in sorted(CATALOG):
                if free_count(state, 'hero', item) and stash.get(item, 0) < 3:
                    rows.append(('stash', item, None, u'Спрятать: ' + CATALOG[item]['title']))
                if stash.get(item, 0) and pocket.get(item, 0) < 3:
                    rows.append(('retrieve', item, None, u'Забрать из тайника: ' + CATALOG[item]['title']))
        if pocket.get('guitar', 0):
            rows.append(('play', 'guitar', None, u'Сыграть на гитаре'))
        for item,n in sorted(stock_at(state,place).items()):
            if n and pocket.get(item,0)<3:rows.append(('take',item,None,u'Взять: '+CATALOG[item]['title']))
        for item,n in sorted(pocket.items()):
            if not n:continue
            usable=CATALOG[item].get('energy') or (item=='poster' and place in ('square','stage','music','canteen')) or (item=='patch' and place in ('clubs','warehouse','boathouse'))
            if usable and free_count(state,'hero',item)>0:rows.append(('use',item,None,(u'Разместить: ' if item=='poster' else u'Применить: ' if item=='patch' else u'Использовать: ')+CATALOG[item]['title']))
            if free_count(state,'hero',item)<1:continue
            for who,name in people:
                if (CATALOG[item].get('restricted') and not __import__('dg_epistemic').knows(
                        state, who, 'observation', 'restricted:' + item)):
                    rows.append(('show', item, who, u'Показать ' + name + u': ' + CATALOG[item]['title']))
                if CATALOG[item].get('restricted'):continue
                if state.get('relationships',{}).get('people',{}).get(who,{}).get('tension',0)>=8:continue
                if state.get('projects',{}).get('npc_inventory',{}).get(who,{}).get(item,0)>=3:continue
                rows.append(('give',item,who,u'Передать '+name+u': '+CATALOG[item]['title']))
                if CATALOG[item].get('loanable') and len([r for r in state.get('inventory_world',{}).get('loans',[]) if r['status']=='open'])<12:
                    rows.append(('lend',item,who,u'Одолжить '+name+u': '+CATALOG[item]['title']))
        for loan in state.get('inventory_world',{}).get('loans',[]):
            if loan['status']=='open' and loan['holder'] in [who for who,name in people] and state.get('projects',{}).get('npc_inventory',{}).get(loan['holder'],{}).get(loan['item'],0)>0 and pocket.get(loan['item'],0)<3:
                rows.append(('return',loan['item'],loan['holder'],u'Забрать одолженное: '+CATALOG[loan['item']]['title']))
    if state['energy']>=6:
        for item,recipe in RECIPES.items():
            if place==recipe['place'] and pocket.get(item,0)<3 and all(free_count(state,'hero',key)>=n for key,n in recipe['inputs'].items()) and all(pocket.get(tool,0)>0 for tool in recipe['tools']):rows.append(('craft',item,None,recipe['title']))
    return rows


def parse(state,text):
    if isinstance(text,bytes):text=text.decode('utf-8')
    folded=text.strip().rstrip('.!').lower()
    return next((row for row in actions(state) if row[3].lower()==folded),None)


def daily(state):
    if 'inventory_world' not in state:return
    world=ensure(state)
    if world.get('last_supply_day')==state['day'] or state.get('finished'):return
    world['last_supply_day']=state['day']
    for item in ('tea','bun','water'):
        previous=world['stock'].setdefault('canteen',{}).get(item,0)
        if previous<CATALOG[item]['count']:
            world['stock']['canteen'][item]=CATALOG[item]['count']
            log(state,'restock',item,'camp_meals','canteen')


def nonnegative(value):
    return value if value>0 else 0
