# -*- coding: utf-8 -*-
"""Offline-first, Python 2.7/3-compatible Sovyonok sandbox simulation.

Pure game state. No Ren'Py imports and no network calls: movement, schedules,
activities, relationships and route milestones never require text generation.
"""
from __future__ import unicode_literals

import io
import json
import os
import re
import shutil
import uuid

try:
    text_type = unicode
except NameError:
    text_type = str

SLOTS = (u"Утро", u"День", u"Вечер", u"Ночь")
PLACES = (
    ("square", u"Площадь", 50, 52),
    ("gate", u"Ворота", 9, 56),
    ("cabins", u"Домики", 29, 33),
    ("canteen", u"Столовая", 70, 33),
    ("library", u"Библиотека", 79, 58),
    ("clubs", u"Клубы", 88, 78),
    ("stage", u"Сцена", 52, 15),
    ("beach", u"Пляж", 27, 78),
    ("lake", u"Озеро", 16, 89),
    ("forest", u"Лес", 71, 89),
    ("infirmary", u"Медпункт", 86, 16),
    ("sports", u"Спортплощадка", 42, 88),
)
PLACE_NAMES = dict((p[0], p[1]) for p in PLACES)
NPCS = (
    ("sl", u"Славя", "square", "canteen", "beach", "cabins"),
    ("dv", u"Алиса", "cabins", "stage", "stage", "cabins"),
    ("un", u"Лена", "library", "library", "lake", "cabins"),
    ("mi", u"Мику", "stage", "clubs", "stage", "cabins"),
    ("us", u"Ульяна", "sports", "beach", "square", "cabins"),
    ("mt", u"Ольга Дмитриевна", "square", "cabins", "square", "cabins"),
    ("cs", u"Виола", "infirmary", "infirmary", "infirmary", "infirmary"),
    ("mz", u"Женя", "library", "library", "cabins", "cabins"),
    ("el", u"Электроник", "clubs", "clubs", "square", "cabins"),
    ("sh", u"Шурик", "clubs", "clubs", "forest", "cabins"),
    ("uv", u"Юля", "forest", "forest", "lake", "forest"),
)
NPC_NAMES = dict((n[0], n[1]) for n in NPCS)
MILESTONES = (10, 25, 45, 70)
ACTIONS = {
    "explore": (u"Осмотреться", 12, "curiosity", 2),
    "help": (u"Помочь в лагере", 17, "kindness", 3),
    "practice": (u"Заняться делом", 20, "skill", 4),
    "rest": (u"Отдохнуть", -22, "energy", 0),
}


def _clean(value, maximum):
    if not isinstance(value, text_type):
        raise ValueError("Expected a text value")
    value = value.strip()
    if not value or len(value) > maximum or any(ord(ch) < 32 for ch in value):
        raise ValueError("Invalid text value")
    return value


def new_game(name, age, days, background=u"Обычный пионер", source="vanilla"):
    name = _clean(name, 35)
    background = _clean(background, 120)
    age, days = int(age), int(days)
    if age < 14 or age > 80 or days < 1 or days > 120:
        raise ValueError("Age must be 14..80 and duration 1..120")
    if source not in ("vanilla", "7dl:mi_7dl", "7dl:mi_dj", "7dl:mi_cl"):
        raise ValueError("Unknown world profile")
    state = {
        "version": 1, "id": uuid.uuid4().hex,
        "hero": {"name": name, "age": age, "background": background},
        "source": source, "duration": days, "day": 1, "slot": 0,
        "place": "gate", "energy": 100, "stats": {"curiosity": 0, "kindness": 0, "skill": 0},
        "affinity": dict((npc[0], 0) for npc in NPCS),
        "met": [], "milestones": [], "journal": [], "event": u"Вы приехали в Совёнок. Впереди целая смена.",
        "visits": {}, "finished": False, "ai_scenes": []
    }
    return state


def validate(state):
    if not isinstance(state, dict) or state.get("version") != 1:
        raise ValueError("Unsupported save format")
    if not re.match(r"^[a-f0-9]{32}$", state.get("id", "")):
        raise ValueError("Invalid save ID")
    _clean(state["hero"]["name"], 35)
    if state["place"] not in PLACE_NAMES:
        raise ValueError("Invalid location")
    if not (1 <= int(state["day"]) <= int(state["duration"]) + 1):
        raise ValueError("Invalid camp day")
    if state["slot"] not in range(4):
        raise ValueError("Invalid time of day")
    if len(state.get("journal", [])) > 500 or len(state.get("ai_scenes", [])) > 80:
        raise ValueError("Oversized save")
    return state


def camp_time(state):
    return u"День %d/%d · %s" % (state["day"], state["duration"], SLOTS[state["slot"]])


def where_is(state, who):
    if who not in NPC_NAMES or state["finished"]:
        return None
    schedule = next(n for n in NPCS if n[0] == who)
    # Deterministic day-specific schedule variation; no random rolls on screen redraw.
    slot = state["slot"]
    if slot == 2 and state["day"] % 3 == 0 and who in ("sl", "un", "mi"):
        return "square"
    if slot == 1 and state["day"] % 4 == 0 and who in ("dv", "us"):
        return "sports"
    return schedule[slot + 2]


def at_place(state, place=None):
    place = place or state["place"]
    return [(who, NPC_NAMES[who]) for who in NPC_NAMES if where_is(state, who) == place]


def route_label(score):
    if score >= 70:
        return u"Близость"
    if score >= 45:
        return u"Доверие"
    if score >= 25:
        return u"Дружба"
    if score >= 10:
        return u"Знакомство"
    return u"Незнакомы"


def _journal(state, message):
    state["event"] = message
    state["journal"].append({"day": state["day"], "slot": state["slot"], "text": message})
    state["journal"] = state["journal"][-250:]


def _tick(state):
    state["slot"] += 1
    if state["slot"] >= 4:
        state["slot"] = 0
        state["day"] += 1
        state["energy"] = min(100, state["energy"] + 65)
        if state["day"] > state["duration"]:
            state["finished"] = True
            _journal(state, u"Смена закончилась. Все встречи и достижения сохранились в дневнике.")


def move(state, place):
    validate(state)
    if state["finished"]:
        return state
    if place not in PLACE_NAMES:
        raise ValueError("Unknown destination")
    state["place"] = place
    state["visits"][place] = state["visits"].get(place, 0) + 1
    _journal(state, u"Вы пришли: %s. Здесь сейчас: %s." %
             (PLACE_NAMES[place], u", ".join(n[1] for n in at_place(state)) or u"никого"))
    return state


def activity(state, action, who=None):
    validate(state)
    if state["finished"]:
        return state
    if action == "talk":
        if who not in NPC_NAMES or where_is(state, who) != state["place"]:
            raise ValueError("This character is elsewhere")
        if state["energy"] < 8:
            _journal(state, u"Слишком устали для разговора. Отдохните.")
            return state
        first_meeting = who not in state["met"]
        state["energy"] -= 8
        state["affinity"][who] = min(100, state["affinity"][who] + (8 if first_meeting else 5))
        if first_meeting:
            state["met"].append(who)
        score = state["affinity"][who]
        event = u"Вы поговорили с %s. Отношения: %s (%d/100)." % (NPC_NAMES[who], route_label(score), score)
        if first_meeting:
            event = u"Первое знакомство! " + event
        for threshold in MILESTONES:
            key = who + ":" + str(threshold)
            if score >= threshold and key not in state["milestones"]:
                state["milestones"].append(key)
                event += u" Открыта новая веха рута (%d очков)." % threshold
        _journal(state, event)
        _tick(state)
        return state
    if action not in ACTIONS:
        raise ValueError("Unknown activity")
    label, cost, stat, gain = ACTIONS[action]
    if action != "rest" and state["energy"] < cost:
        _journal(state, u"Недостаточно сил. Можно отдохнуть.")
        return state
    if action == "rest":
        state["energy"] = min(100, state["energy"] + 35)
    else:
        state["energy"] -= cost
        state["stats"][stat] += gain
    _journal(state, label + u" — " + PLACE_NAMES[state["place"]] + u".")
    _tick(state)
    return state


def append_ai_scene(state, who, text):
    if who not in NPC_NAMES:
        raise ValueError("Unknown character")
    if not isinstance(text, text_type) or not text.strip():
        raise ValueError("Empty scene")
    text = text.strip()[:9000]
    state["ai_scenes"].append({"day": state["day"], "who": who, "text": text})
    state["ai_scenes"] = state["ai_scenes"][-60:]
    _journal(state, u"Новая сюжетная сцена с %s добавлена в дневник." % NPC_NAMES[who])
    return state


def summary_for_ai(state, who, intent):
    validate(state)
    intent = _clean(intent, 500)
    if who not in NPC_NAMES or where_is(state, who) != state["place"]:
        raise ValueError("Character is unavailable at the current location")
    return {
        "hero": state["hero"], "profile": state["source"], "day": state["day"],
        "slot": SLOTS[state["slot"]], "place": PLACE_NAMES[state["place"]],
        "speaker": NPC_NAMES[who], "affinity": state["affinity"][who],
        "relation": route_label(state["affinity"][who]), "player_action": intent,
        "recent_journal": state["journal"][-10:],
        "recent_scenes": state["ai_scenes"][-3:]
    }


def _path(root, game_id):
    if not re.match(r"^[a-f0-9]{32}$", game_id):
        raise ValueError("Invalid save identifier")
    return os.path.join(root, "_rpg", game_id + ".json")


def save(root, state):
    validate(state)
    folder = os.path.join(root, "_rpg")
    if not os.path.isdir(folder):
        try:
            os.makedirs(folder)
        except OSError:
            if not os.path.isdir(folder):
                raise
    path = _path(root, state["id"])
    temporary = path + "." + uuid.uuid4().hex + ".tmp"
    try:
        with io.open(temporary, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2))
            stream.flush()
            os.fsync(stream.fileno())
        if os.path.isfile(path):
            shutil.copy2(path, path + ".bak")
        if os.name == "nt":
            import ctypes
            if not ctypes.windll.kernel32.MoveFileExW(text_type(temporary), text_type(path), 9):
                raise OSError("Could not replace RPG save")
        else:
            os.rename(temporary, path)
    finally:
        if os.path.isfile(temporary):
            os.unlink(temporary)
    return state


def load(root, game_id):
    path = _path(root, game_id)
    for candidate in (path, path + ".bak"):
        try:
            with io.open(candidate, "r", encoding="utf-8") as stream:
                return validate(json.load(stream))
        except (IOError, OSError, ValueError, KeyError, TypeError):
            continue
    raise IOError("Could not load RPG save")


def list_games(root):
    folder = os.path.join(root, "_rpg")
    if not os.path.isdir(folder):
        return []
    games = []
    for name in os.listdir(folder):
        if not re.match(r"^[a-f0-9]{32}\.json$", name):
            continue
        try:
            state = load(root, name[:-5])
            games.append({
                "id": state["id"], "name": state["hero"]["name"],
                "day": state["day"], "duration": state["duration"],
                "finished": state["finished"]
            })
        except (IOError, ValueError, KeyError, TypeError):
            continue
    return sorted(games, key=lambda g: g["id"])
