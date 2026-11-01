# -*- coding: utf-8 -*-
"""Explicit opt-in 18+ alternate universe for DON-GEN, Python 2.7 friendly.

Canonical vanilla ages are NOT silently rewritten. Only a separately
acknowledged adult AU can use mature romantic narration, and no intimate
content is permitted with child-coded characters, regardless of mode.
"""
from __future__ import unicode_literals
import re

# Fictional adult alternate-universe ages; do NOT alter underlying vanilla canon.
ADULT_AU_AGES = {
    "mi": 19, "sl": 19, "dv": 19, "un": 19, "mz": 20,
    "el": 19, "sh": 19, "mt": 29, "cs": 28
}
INELIGIBLE = ("us", "uv")  # Ulyana and Yulia stay outside adult content.
ADULT_STEMS = (u"секс",u"эрот",u"интим",u"голый",u"голая",u"голые",u"голыш",u"раздев",u"постел",
               u"обнаж",u"порно",u"nsfw",u"sex",u"nude",u"naked")
YOUNG_STEMS = (u"ульян",u"юл",u"ulyana",u"yulia",u"uliana")
SAFE_NOTICE = (
    u"Обычный режим: не вводить эротические события. "
    u"Взрослые романтические темы только в явно включённой альтернативной вселенной 18+."
)

def ensure(state):
    adult = state.setdefault("adult_mode", {
        "enabled": False, "confirmed": False, "setting": "adult_alternate_universe"})
    return adult

def enabled(state):
    flag = ensure(state)
    return (bool(flag.get("enabled")) and bool(flag.get("confirmed"))
            and int(state["hero"]["age"]) >= 18)

def set_enabled(state, value, confirmed=False):
    if not isinstance(value, bool):
        raise ValueError("Adult mode requires a boolean")
    if value and (int(state["hero"]["age"]) < 18 or not confirmed):
        raise ValueError("Adult AU requires an adult protagonist and explicit confirmation")
    info = ensure(state)
    info["enabled"] = value
    info["confirmed"] = bool(value and confirmed)
    return info

def can_romance(state, who):
    return bool(enabled(state) and who in ADULT_AU_AGES)

def classify_sensitive(text):
    lowered = text.lower()
    return any(stem in lowered for stem in ADULT_STEMS)

def validate_action(state, text, target=None):
    if not classify_sensitive(text):
        return None
    if target in INELIGIBLE or any(stem in text.lower() for stem in YOUNG_STEMS):
        return u"Эротические действия с несовершеннолетними или детски изображёнными героями недопустимы."
    if not enabled(state):
        return u"Для взрослой романтической темы требуется включённый режим альтернативной вселенной 18+."
    if target is not None and target not in ADULT_AU_AGES:
        return u"Этот персонаж недоступен для взрослого контента."
    return None

def scene_policy(state, who=None):
    if not enabled(state) or (who is not None and who not in ADULT_AU_AGES):
        return u"Только обычная драматическая, дружеская и неэротическая романтическая проза; никакого сексуализированного описания несовершеннолетних."
    return (u"Режим отдельной взрослой AU: все участники возможных интимных отношений "
            u"это явно совершеннолетние самостоятельные персонажи. "
            u"Взрослые версии: " +
            u", ".join(u"%s — %d лет" % (who,age) for who,age in sorted(ADULT_AU_AGES.items())) +
            u". Исключить Ульяну и Юлю из любой эротики независимо от контекста. "
            u"Только добровольные и взаимные отношения с явным согласием, "
            u"без принуждения; сохранять инициативу игрока. "
            u"Допустимы зрелая романтика и чувственное напряжение между взрослыми, "
            u"но не добавляй такой контент автоматически, если действие игрока его не предполагает.")
