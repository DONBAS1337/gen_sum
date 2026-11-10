# -*- coding: utf-8 -*-
"""Conservative background tags: modest abilities, never invented achievements."""
from __future__ import unicode_literals
import re
TAGS={'music':(u'Музыка',u'играю на гитар|умею играть|занимаюсь музык|музыкант|пианист|гитарист'),
      'sport':(u'Спорт',u'занимаюсь спорт|спортсмен|легкоатлет|занимаюсь гимнаст|хорошо плаваю'),
      'technical':(u'Техника',u'радиолюбител|инженер|умею паять|занимаюсь электроник|ремонтирую'),
      'cards':(u'Карточные игры',u'играю в карты|карточные игры|карточный игрок'),
      'height_fear':(u'Боязнь высоты',u'боюсь высоты|боязнь высоты|акрофоб'),
      'shy':(u'Застенчивость',u'стеснител|застенчив|трудно знакомиться')}

def profile(state):
    text=state['hero'].get('background','').lower();found=[]
    for key,(label,pattern) in sorted(TAGS.items()):
        for match in re.finditer(pattern,text):
            prefix=text[max(0,match.start()-30):match.start()]
            if not re.search(u'\\b(?:не|никогда не|не являюсь|не считаю себя)(?:\\s+\\w+){0,2}\\s*$',prefix):
                found.append(key);break
    return {'tags':found,'labels':[TAGS[k][0] for k in found],
            'rule':u'Предыстория задаёт речь, интересы и небольшой навык. Не даёт предметов, чужого согласия, дружбы, власти или прошлых лагерных достижений. Не объявляй NPC осведомлённым о личном описании до разговора.'}

def has(state,key):return key in profile(state)['tags']
