# -*- coding: utf-8 -*-
"""Short, reproducible three-round 21 tournament, without bets or AI rolls."""
from __future__ import unicode_literals
import copy

def score(hand):
    value=sum(hand);aces=hand.count(11)
    while value>21 and aces:value-=10;aces-=1
    return value

def _deal(state,g):
    import dg_world
    deck=[v for v in range(2,12) for _ in range(4)]
    # Stable Fisher-Yates ordering; each round is independent of save/load.
    for i in range(len(deck)-1,0,-1):
        j=dg_world._seed(state['id'],g['day'],g['round'],i,'deck')%(i+1);deck[i],deck[j]=deck[j],deck[i]
    g.update(deck=deck,hero=[deck.pop(),deck.pop()],dealer=[deck.pop(),deck.pop()],phase='playing')

def public(state):
    g=state.get('card_table')
    if not g or g["day"]!=state["day"]:return None
    return {'round':g['round'],'phase':g['phase'],'hero':list(g['hero']),'hero_total':score(g['hero']),
            'dealer':list(g['dealer']) if g['phase']!='playing' else g['dealer'][:1],
            'wins':g['wins'],'losses':g['losses'],'last_result':g.get('last_result',''),
            'rules':u'Турнир «21»: три раунда без ставок. Можно взять карту или остановиться; туз считается 11 или 1. Электроник добирает до 17. Перебор проигрывает; равные суммы — ничья. Закрытую карту до конца раунда не описывать.'}

def cards(state):
    import dg_schedule,dg_camp
    if 'camp_life' not in state or state['finished']:return []
    g=state.get('card_table');rows=[]
    def add(key,title):rows.append(dict(key=key,title=title,who='el',place='canteen',minutes=2,story=u'Карточный турнир по явным правилам.',ready=state['place']=='canteen'))
    if g and g['phase'] in ('playing','round_done') and g['day']==state['day']:
        if g['phase']=='playing':
            add('cards:hit',u'Взять карту · на руках %d'%score(g['hero']));add('cards:stand',u'Остановиться · на руках %d'%score(g['hero']))
        else:add('cards:next',u'Следующий раунд')
        add('cards:leave',u'Закончить турнир досрочно')
    elif not dg_camp._done(state,'event:cards') and any(r['key']=='event:cards' for r in dg_schedule.events(state)) and 960<=state['camp_life']['minute']<1080:
        add('cards:start',u'Сыграть турнир «21» — три раунда')
    return rows

def act(state,key):
    import dg_clock,dg_camp,dg_rpg
    row=next((r for r in cards(state) if r['key']==key and r['ready']),None)
    if not row:raise ValueError(u'Карточный стол сейчас недоступен.')
    if key=='cards:start':
        g={'day':state['day'],'round':1,'wins':0,'losses':0};state['card_table']=g;_deal(state,g)
        text=u'Ты сел за карточный стол. Играете три раунда в «21» без ставок. У тебя %d очков; открытая карта Электроника — %d. Выбор следующего хода остаётся за игроком.'%(score(g['hero']),g['dealer'][0])
    else:
        g=state['card_table']
        if key=='cards:leave':g['phase']='finished';text=u'Ты досрочно закончил турнир. Не доигранные раунды не записаны как победы.'
        elif key=='cards:next':g['round']+=1;_deal(state,g);text=u'Начался новый раунд. Твоя сумма — %d; открытая карта соперника — %d.'%(score(g['hero']),g['dealer'][0])
        else:
            if key=='cards:hit':g['hero'].append(g['deck'].pop())
            if key=='cards:stand' or score(g['hero'])>21:
                while score(g['dealer'])<17:g['dealer'].append(g['deck'].pop())
                a,b=score(g['hero']),score(g['dealer']);win=a<=21 and (b>21 or a>b);lose=a>21 or (b<=21 and b>a)
                g['wins']+=int(win);g['losses']+=int(lose);g['last_result']=u'победа' if win else u'поражение' if lose else u'ничья'
                g['phase']='finished' if g['round']==3 else 'round_done'
                text=u'Раунд завершён: %s. У тебя %d, у Электроника %d. Счёт раундов %d:%d.'%(g['last_result'],a,b,g['wins'],g['losses'])
            else:text=u'Ты взял карту: %d. Теперь у тебя %d очков. Закрытая карта соперника пока неизвестна.'%(g['hero'][-1],score(g['hero']))
        if g['phase']=='finished':dg_camp._mark(state,'event:cards')
    state['interaction']={'who':'el','until':dg_clock.absolute(state)+2}
    try:dg_clock.advance(state,2)
    finally:state.pop('interaction',None)
    dg_camp._meet(state,'el');dg_rpg._journal(state,text)
    return dict(row,text=text)

def validate(state):
    g=state.get('card_table')
    if g is None:return
    if not isinstance(g,dict) or g.get('phase') not in ('playing','round_done','finished') or type(g.get('round')) is not int or not 1<=g['round']<=3 or type(g.get('day')) is not int:raise ValueError('Invalid card game')
    for field in ('hero','dealer','deck'):
        if not isinstance(g.get(field),list) or len(g[field])>40 or any(type(c) is not int or not 2<=c<=11 for c in g[field]):raise ValueError('Invalid card deck')
    cards=g['hero']+g['dealer']+g['deck']
    if len(cards)!=40 or any(cards.count(v)!=4 for v in range(2,12)) or any(type(g.get(k)) is not int or not 0<=g[k]<=3 for k in ('wins','losses')):raise ValueError('Card conservation violated')
