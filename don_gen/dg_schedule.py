# -*- coding: utf-8 -*-
"""Stable weekly calendar and optional, save-stable camp encounters."""
from __future__ import unicode_literals
WEEK=(u'Понедельник',u'Вторник',u'Среда',u'Четверг',u'Пятница',u'Суббота',u'Воскресенье')

def weekday(state):return (state['day']-1)%7

def disco(state):return weekday(state)==5 and 1200<=state['camp_life']['minute']<1290

def events(state):
    import dg_world
    if 'camp_life' not in state or state['finished'] or state['camp_life']['arrival']<4:return []
    day=weekday(state);rain=dg_world.weather(state)[0]=='rain';rows=[]
    def add(key,title,place,who,start,end,cost,story):
        rows.append(dict(key='event:'+key,title=title,place=place,who=who,start=start,end=end,minutes=cost,story=story))
    if day==0 and state['day']>1:
        add('science',u'Открытая мастерская Электроника','clubs','el',960,1080,40,u'Электроник показывает простой опыт. Герой может наблюдать и задавать вопросы; участие не завершает проект радио.')
    if day==3:
        add('sports',u'Товарищеские спортивные игры','gym' if rain else 'sports','sl',960,1080,40,u'Командные игры без обязательной победы. При дожде занятие перенесено в зал.')
    if day==6:
        add('campfire',u'Отрядный вечер: истории и песни','clubhouse' if rain else 'campfire','mt',1200,1290,45,u'Отряд собирается на истории и песни у костра; при дожде — без огня в помещении. Рассказанный героем эпизод не становится историческим фактом без подтверждения.')
    if day==1 and state['day']>=2:
        add('cards',u'Карточный турнир Электроника','canteen','el',960,1080,50,u'Электроник проводит товарищеский карточный турнир без денежных ставок. Результат определяют правила движка; знакомства не становятся дружбой автоматически.')
    if day==4:
        add('concert',u'Пятничный концерт', 'clubhouse' if rain else 'stage','mi',1200,1290,60,u'Вечерний концерт лагерных кружков. При дожде выступление перенесено под крышу; герой участвует только в подтверждённом качестве.')
    if day==5:
        add('weekly_disco',u'Субботняя дискотека','clubhouse' if rain else 'square',None,1200,1290,45,u'Субботняя лагерная дискотека; дождь переносит её в помещение. Танец предлагается отдельно.')
    if day in (2,6) and state['day']>=3:
        add('outing',u'Отрядный поход: настольные игры вместо пляжа' if rain else u'Отрядный выход на пляж','clubhouse' if rain else 'beach','mt',900,1020,60,u'Вожатая собирает отряд на спокойные занятия в помещении из-за дождя.' if rain else u'Вожатая ведёт отряд на пляж; купание только под присмотром и по желанию. Герой проводит время с отрядом.')
    return rows

def location(state,who):
    minute=state['camp_life']['minute']
    for row in events(state):
        if row['start']<=minute<row['end'] and (who==row['who'] or (row['key']!='event:cards' and who not in ('uv','cs'))):return row['place']
    return None

def cards(state):
    import dg_camp,dg_rpg
    minute=state['camp_life']['minute'];rows=[]
    for row in events(state):
        if not dg_camp._done(state,row['key']) and row['start']<=minute<row['end']:
            row=dict(row,ready=state['place']==row['place'] and (row['who'] is None or dg_rpg.where_is(state,row['who'])==row['place']))
            rows.append(row)
    return rows

def resolve(state,row):
    import dg_world,dg_hero
    if row['key']=='event:cards':
        score=dg_world._seed(state['id'],state['day'],'cards')%100
        win=score<(65 if dg_hero.has(state,'cards') else 35)
        row=dict(row,story=(u'Ты выиграл товарищеский карточный турнир Электроника.' if win else u'Ты сыграл в турнире Электроника, но не занял первое место.')+u' Денежных ставок и предметного приза не было.')
    elif row['key']=='event:concert':
        member=state['camp_life']['club']=='music' and not __import__('dg_risk').injured(state)
        role=u'Ты сыграл небольшую подготовленную партию с кружком.' if member and dg_hero.has(state,'music') and state.get('activity_counts',{}).get('practice',0)>=2 else u'Ты помог за кулисами как участник кружка.' if member else u'Ты слушал выступление из зрительного зала.'
        row=dict(row,story=row['story']+u' '+role)
    return row

def report(state):
    if 'camp_life' not in state:return None
    return {'weekday':WEEK[weekday(state)],'day_one_weekday':WEEK[0],'today':events(state),
            'rule':u'Мероприятия в today — планы, не уже выполненные действия. Пропущенное мероприятие не переносится задним числом. По пятницам концерт, по субботам дискотека, по вторникам карты, по средам и воскресеньям отрядный выход.'}
