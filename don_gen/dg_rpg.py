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
import dg_dialogue
import dg_world
import dg_social

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
    ("parking", u"Стоянка", 6, 48),
    ("music", u"Музыкальный кружок", 30, 19),
    ("clubhouse", u"Общие кружки", 32, 38),
    ("administration", u"Административный корпус", 43, 36),
    ("showers", u"Душевые", 37, 45),
    ("washrooms", u"Умывальники", 35, 43),
    ("kitchen", u"Кухня", 64, 46),
    ("storage", u"Склад", 73, 48),
    ("gym", u"Спортзал", 79, 49),
    ("volleyball", u"Волейбольная площадка", 78, 57),
    ("football", u"Футбольное поле", 86, 57),
    ("badminton", u"Бадминтон", 82, 37),
    ("canteen_veranda", u"Веранда столовой", 68, 52),
    ("cabins_south", u"Южные домики", 30, 56),
    ("boathouse", u"Лодочная станция", 49, 73),
    ("pier", u"Причал", 52, 76),
    ("beachhouse", u"Пляжные раздевалки", 75, 70),
    ("island", u"Ближний остров", 36, 91),
    ("island_far", u"Дальний остров", 73, 94),
    ("old_camp", u"Старый корпус", 16, 78),
    ("campfire", u"Костровая площадка", 31, 65),
    ("forest_path", u"Лесная тропа", 22, 24),
    ("radio", u"Радиорубка", 52, 25),
    ("headquarters", u"Штаб отряда", 48, 44),
    ("laundry", u"Прачечная", 35, 50),
    ("outdoor_stage", u"Кулисы", 53, 21),
    ("warehouse", u"Хозяйственный двор", 72, 55),
)
# Each of the 31 numbered pioneer cabins is a real visitable location.
# Existing save IDs keep their meaning; no random per-load remapping.
PLACES = PLACES + tuple(("cabin_%02d" % i, u"Домик №%d" % i, 24 + (i % 9) * 5, 22 + (i // 9) * 8)
                        for i in range(1, 32))
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
ROUTE_TITLES = { "sl": u"Общий труд", "dv": u"Вечер у сцены", "un": u"Тихая прогулка",
                 "mi": u"Репетиция", "us": u"Спортивный спор", "mt": u"Серьёзный разговор",
                 "cs": u"Визит в медпункт", "mz": u"Книжная находка", "el": u"Клубная идея",
                 "sh": u"Эксперимент", "uv": u"Тайна леса" }
QUESTS = (("friends", u"Знакомства", 3), ("help", u"Помощь лагерю", 3), ("explore", u"Исследователь", 5))
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


def new_game(name, age, days, background=u"Обычный пионер", source="vanilla", pronouns=u"он/его"):
    name = _clean(name, 100)
    background = _clean(background, 8000)
    age, days = int(age), int(days)
    if age < 1 or age > 999999999 or days < 1 or days > 120:
        raise ValueError("Age must be 1..999999999 and duration 1..120")
    if pronouns not in (u"он/его", u"она/её", u"они/их"):
        raise ValueError("Unknown pronouns")
    if source not in ("vanilla", "7dl:mi_7dl", "7dl:mi_dj", "7dl:mi_cl"):
        raise ValueError("Unknown world profile")
    state = {
        "version": 1, "id": uuid.uuid4().hex,
        "hero": {"name": name, "age": age, "background": background, "pronouns": pronouns},
        "source": source, "duration": days, "day": 1, "slot": 0,
        "place": "gate", "energy": 100, "stats": {"curiosity": 0, "kindness": 0, "skill": 0},
        "affinity": dict((npc[0], 0) for npc in NPCS),
        "met": [], "milestones": [], "journal": [], "event": u"Вы приехали в Совёнок. Впереди целая смена.",
        "visits": {}, "finished": False, "ai_scenes": [],
        "mystery": {"yulia_discovered": False},
        "activity_counts": {"help": 0, "explore": 0}, "quests_done": [], "route_events_done": [],
        "dialogue_history": [], "dialogue_counts": {}
    }
    dg_world.prepare(state)
    dg_social.ensure(state)
    dg_social.prepare_incident(state)
    return state


def validate(state):
    if not isinstance(state, dict) or state.get("version") != 1:
        raise ValueError("Unsupported save format")
    state.setdefault("mystery", {"yulia_discovered": False})
    if not re.match(r"^[a-f0-9]{32}$", state.get("id", "")):
        raise ValueError("Invalid save ID")
    _clean(state["hero"]["name"], 100)
    _clean(state["hero"]["background"], 8000)
    if not (1 <= int(state["hero"]["age"]) <= 999999999):
        raise ValueError("Invalid age")
    state["hero"].setdefault("pronouns", u"он/его")
    if state["place"] not in PLACE_NAMES:
        raise ValueError("Invalid location")
    if not (1 <= int(state["day"]) <= int(state["duration"]) + 1):
        raise ValueError("Invalid camp day")
    if state["slot"] not in range(4):
        raise ValueError("Invalid time of day")
    state.setdefault("activity_counts", {"help": 0, "explore": 0})
    state.setdefault("quests_done", [])
    state.setdefault("route_events_done", [])
    state.setdefault("dialogue_history", [])
    state.setdefault("dialogue_counts", {})
    dg_world.ensure(state)
    dg_social.ensure(state)
    if not state.get("finished"):
        dg_social.prepare_incident(state)
    if len(state.get("journal", [])) > 500 or len(state.get("ai_scenes", [])) > 80 or len(state["dialogue_history"]) > 100:
        raise ValueError("Oversized save")
    return state


def camp_time(state):
    return u"День %d/%d · %s" % (state["day"], state["duration"], SLOTS[state["slot"]])


def where_is(state, who):
    if who not in NPC_NAMES or state["finished"]:
        return None
    # Yulia is a secret encounter, never part of routine public schedules.
    if who == "uv":
        secret = state.get("mystery", {})
        return "forest_path" if secret.get("yulia_discovered") and state["slot"] == 3 else None
    schedule = next(n for n in NPCS if n[0] == who)
    # A shared event temporarily brings two NPCs to one real map location.
    incident = dg_social.incident(state)
    if incident and who in incident["pair"]:
        return incident["place"]
    # Deterministic day-specific schedule variation; no random rolls on screen redraw.
    slot = state["slot"]
    if slot == 2 and state["day"] % 3 == 0 and who in ("sl", "un", "mi"):
        return "square"
    if slot == 1 and state["day"] % 4 == 0 and who in ("dv", "us"):
        return "sports"
    target = schedule[slot + 2]
    # Weather may change plans of NPCs; only on days after arrival and in daylight.
    if state["day"] > 1 and slot in (1, 2):
        conditions = dg_world.weather(state)[0]
        if conditions == "rain" and target in ("beach", "lake", "sports", "stage", "forest"):
            if who in ("mi", "el", "sh"):
                return "clubs"
            if who in ("un", "mz"):
                return "library"
            return "canteen"
        if conditions == "heat" and target == "sports":
            return "beach"
    return target


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


def quest_progress(state):
    return [
        ("friends", u"Знакомства", len(state["met"]), 3),
        ("help", u"Помощь лагерю", state["activity_counts"].get("help", 0), 3),
        ("explore", u"Исследовать места", len(state["visits"]), 5)
    ]


def _check_quests(state):
    for key, title, done, goal in quest_progress(state):
        if done >= goal and key not in state["quests_done"]:
            state["quests_done"].append(key)
            state["stats"]["kindness"] += 3
            _journal(state, u"Задание выполнено: %s. Награда: +3 доброты." % title)


def available_route_events(state, who):
    if who not in NPC_NAMES:
        return []
    score = state["affinity"][who]
    return [(level, ROUTE_TITLES[who]) for level in MILESTONES
            if score >= level and who + ":" + str(level) not in state["route_events_done"]]


def route_event(state, who, approach):
    validate(state)
    if state["finished"] or where_is(state, who) != state["place"]:
        raise ValueError("Character not available")
    options = available_route_events(state, who)
    if not options or approach not in ("support", "honest", "leave"):
        raise ValueError("No available route milestone")
    if state["energy"] < 12:
        _journal(state, u"Для личной встречи нужно немного сил. Отдохните.")
        return state
    level, title = options[0]
    state["route_events_done"].append(who + ":" + str(level))
    state["energy"] -= 12
    if approach == "support":
        state["affinity"][who] = min(100, state["affinity"][who] + 4)
        conclusion = u"Вы поддержали собеседника."
    elif approach == "honest":
        state["stats"]["curiosity"] += 3
        conclusion = u"Вы высказали свою позицию и узнали новое."
    else:
        conclusion = u"Вы предпочли сохранить дистанцию."
    _journal(state, u"Рут %s, этап %d: %s. %s" %
             (NPC_NAMES[who], level, title, conclusion))
    _tick(state)
    return state


def _tick(state):
    if state["slot"] == 3:
        expired = dg_world.missed(state)
        if expired:
            _journal(state, expired)
        unseen = dg_social.missed_incident(state)
        if unseen:
            _journal(state, unseen)
    state["slot"] += 1
    if state["slot"] >= 4:
        state["slot"] = 0
        state["day"] += 1
        state["energy"] = min(100, state["energy"] + 65)
        if state["day"] > state["duration"]:
            state["finished"] = True
            _journal(state, u"Смена закончилась. Все встречи и достижения сохранились в дневнике.")
        else:
            # World ticks happen on turn advance, not during screen redraw.
            interaction = dg_social.npc_daily(state)
            if interaction:
                _journal(state, interaction)
            for notice in dg_social.expire_quests(state):
                _journal(state, notice)
            dg_world.prepare(state)
            dg_social.prepare_incident(state)


def move(state, place):
    validate(state)
    if state["finished"]:
        return state
    if place not in PLACE_NAMES:
        raise ValueError("Unknown destination")
    state["place"] = place
    state["visits"][place] = state["visits"].get(place, 0) + 1
    _check_quests(state)
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
        _check_quests(state)
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
        if action in ("explore", "help"):
            state["activity_counts"][action] = state["activity_counts"].get(action, 0) + 1
    _check_quests(state)
    _journal(state, label + u" — " + PLACE_NAMES[state["place"]] + u".")
    _tick(state)
    return state



def conversation(state, who, topic_index, stance):
    """One full two-choice, no-network dialogue with a meaningful outcome."""
    validate(state)
    if state["finished"] or who not in NPC_NAMES or where_is(state, who) != state["place"]:
        raise ValueError("Character is not here")
    if state["energy"] < 8:
        _journal(state, u"Вы устали. Сначала отдохните, а потом продолжите беседу.")
        return None
    outcome = dg_dialogue.outcome(state, who, topic_index, stance)
    day_key = "%d:%s" % (state["day"], who)
    repeated = state["dialogue_counts"].get(day_key, 0)
    first_meeting = who not in state["met"]
    if first_meeting:
        state["met"].append(who)
    # Prevent farming unlimited reputation without stopping roleplay.
    gain = outcome["affinity"] if repeated == 0 else 1
    if first_meeting:
        gain += 2
    stat_gain = 2 if repeated == 0 else 0
    state["affinity"][who] = min(100, state["affinity"][who] + gain)
    state["stats"][outcome["stat"]] += stat_gain
    state["energy"] -= 8
    state["dialogue_counts"][day_key] = repeated + 1
    scene = {
        "day": state["day"], "slot": state["slot"], "who": who,
        "topic": outcome["topic"], "stance": stance,
        "text": outcome["text"], "affinity_gain": gain
    }
    state["dialogue_history"].append(scene)
    state["dialogue_history"] = state["dialogue_history"][-80:]
    score = state["affinity"][who]
    new_milestones = []
    for threshold in MILESTONES:
        key = who + ":" + str(threshold)
        if score >= threshold and key not in state["milestones"]:
            state["milestones"].append(key)
            new_milestones.append(threshold)
    event = u"%s · %s. Отношения: +%d (всего %d/100). %s: +%d." % (
        NPC_NAMES[who], outcome["topic"], gain, score,
        {"kindness": u"Доброта", "curiosity": u"Любознательность", "skill": u"Навык"}[outcome["stat"]], stat_gain
    )
    if new_milestones:
        event += u" Открыта веха рута (%s)." % u", ".join(str(x) for x in new_milestones)
    _journal(state, event)
    _check_quests(state)
    _tick(state)
    return scene



def story_choice(state, key):
    """Persistent, offline nonlinear event. Effects apply exactly once."""
    validate(state)
    if state["finished"]:
        raise ValueError("The camp shift has ended")
    outcome = dg_world.choose(state, key)
    if outcome["npc"] not in state["met"]:
        state["met"].append(outcome["npc"])
    _journal(state, u"Сюжет: %s. %s" % (outcome["title"], outcome["text"][:360]))
    score = state["affinity"][outcome["npc"]]
    for threshold in MILESTONES:
        marker = outcome["npc"] + ":" + str(threshold)
        if score >= threshold and marker not in state["milestones"]:
            state["milestones"].append(marker)
    _check_quests(state)
    _tick(state)
    return outcome



def free_action(state, requested):
    """Player types a concrete Russian action. No AI / no false success."""
    validate(state)
    if state["finished"]:
        return {"status":"unknown","text":u"Смена уже завершена."}
    nearby=[who for who, name in at_place(state)]
    result=dg_social.action(state, requested, nearby)
    if result["status"] != "done":
        return result
    _journal(state, result["text"])
    for who, score in state["affinity"].items():
        for threshold in MILESTONES:
            token = who + ":" + str(threshold)
            if score >= threshold and token not in state["milestones"]:
                state["milestones"].append(token)
    if result["intent"] == "help":
        state["activity_counts"]["help"] = state["activity_counts"].get("help", 0) + 1
    if result["intent"] == "search":
        state["activity_counts"]["explore"] = state["activity_counts"].get("explore", 0) + 1
    _check_quests(state)
    _tick(state)
    return result


def personal_choice(state, who, stance):
    validate(state)
    if state["finished"] or where_is(state,who)!=state["place"]:
        raise ValueError("Character not at this location")
    result=dg_social.resolve_personal(state,who,stance)
    _journal(state, u"Личная история %s: %s. %s" % (
        NPC_NAMES[who],result["title"],result["text"][-350:]))
    for threshold in MILESTONES:
        token = who + ":" + str(threshold)
        if state["affinity"][who] >= threshold and token not in state["milestones"]:
            state["milestones"].append(token)
    _check_quests(state)
    _tick(state)
    return result


def accept_contract(state, ident):
    validate(state)
    result=dg_social.accept(state,ident)
    _journal(state,result)
    return result



def social_encounter(state, stance):
    validate(state)
    if state["finished"]:
        raise ValueError("The camp shift has ended")
    outcome=dg_social.resolve_incident(state,stance)
    _journal(state,u"Встреча персонажей: " + outcome["text"][-360:])
    _tick(state)
    return outcome


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
        "recent_scenes": state["ai_scenes"][-3:],
        "recent_dialogue": state["dialogue_history"][-6:],
        "world_state": dg_world.world_report(state),
        "recent_world_decisions": state["world"]["decisions"][-7:],
        "social_world": dg_social.report(state),
        "active_social_incident": dg_social.incident(state),
        "route_milestones": available_route_events(state, who),
        "completed_route_events": [v for v in state["route_events_done"] if v.startswith(who + ":")]
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


def asset_path(root, game_id, kind, key):
    """Ren'Py-loadable path beneath the DON-GEN save search root."""
    _path(root, game_id)
    if kind == "background":
        if key not in PLACE_NAMES:
            raise ValueError("Unknown location")
    elif kind == "sprite":
        if key not in NPC_NAMES:
            raise ValueError("Unknown character")
    else:
        raise ValueError("Unknown asset type")
    return "_rpg/assets/%s/%s_%s.png" % (game_id, kind, key)


def save_asset(root, game_id, kind, key, data):
    """Publish a validated PNG; sprite assets need an alpha channel."""
    import struct
    relative = asset_path(root, game_id, kind, key)
    if not isinstance(data, bytes) or len(data) < 100 or len(data) > 32 * 1024 * 1024:
        raise ValueError("Invalid image data")
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("Image service did not return PNG")
    width, height = struct.unpack(">II", data[16:24])
    if not (256 <= width <= 4096 and 256 <= height <= 4096):
        raise ValueError("Unexpected image dimensions")
    color_type = data[25] if isinstance(data[25], int) else ord(data[25])
    if kind == "sprite" and color_type not in (4, 6):
        raise ValueError("The sprite PNG has no alpha channel; retry generation")
    target = os.path.join(root, *relative.split("/"))
    folder = os.path.dirname(target)
    if not os.path.isdir(folder):
        try:
            os.makedirs(folder)
        except OSError:
            if not os.path.isdir(folder):
                raise
    temporary = target + "." + uuid.uuid4().hex + ".tmp"
    try:
        with open(temporary, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if os.name == "nt":
            import ctypes
            if not ctypes.windll.kernel32.MoveFileExW(text_type(temporary), text_type(target), 9):
                raise OSError("Could not publish generated image")
        else:
            os.rename(temporary, target)
    finally:
        if os.path.isfile(temporary):
            os.unlink(temporary)
    return relative
