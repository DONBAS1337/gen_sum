# -*- coding: utf-8 -*-
"""Scene presentation data only: speakers, cast, pages and map geometry.

Never executes model text or applies game effects. Python 2.7/3 compatible.
"""
from __future__ import unicode_literals
import re
import copy

EMOTIONS = ('normal', 'smile', 'laugh', 'sad', 'cry', 'angry', 'surprise', 'shy', 'serious')
STAGING = re.compile(r'\[stage ([a-z]+) ([a-z]+) ([a-z]+) (auto|[1-6])\]')

try:
    text_type = unicode
except NameError:
    text_type = str

NAMES = {"sl": u"Славя", "dv": u"Алиса", "un": u"Лена", "mi": u"Мику",
         "us": u"Ульяна", "mt": u"Ольга Дмитриевна", "cs": u"Виола",
         "mz": u"Женя", "el": u"Электроник", "sh": u"Шурик", "uv": u"Юля"}
COLORS = {"sl": "#ffd86a", "dv": "#ffaa00", "un": "#b595ef", "mi": "#6ce6df",
          "us": "#ff7777", "mt": "#64d68a", "cs": "#bba6ed", "mz": "#d5b1ed",
          "el": "#efdb88", "sh": "#efdb88", "uv": "#ddbcff", "hero": "#eeeeee"}
FORMATTING = (
    u"Формат сцены: каждый абзац начинай с метки говорящего: "
    u"[narrator] описание и действия; [hero] слова героя; "
    u"[mi], [dv], [un], [sl], [us], [mt], [cs], [mz], [el], [sh], [uv] — реплика "
    u"соответствующего присутствующего персонажа. Одна метка — один абзац. "
    u"Не включай авторские описания в реплику: выноси их в [narrator]. "
    u"Не добавляй отсутствующих участников. Это только разметка текста, не команды игры."
    u" Перед изменением выражения/позы вставь отдельную режиссёрскую метку, например "
    u"[stage mi smile normal 2]. Поля: код присутствующего персонажа; эмоция "
    u"normal/smile/laugh/sad/cry/angry/surprise/shy/serious; дистанция normal/close/far; "
    u"номер позы 1–6 или auto. Не чаще одного изменения за смысловой момент. "
    u"Не описывай эту техническую метку словами в реплике."
)


def _text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value if isinstance(value, text_type) else text_type(value or "")


def freeze(state, focus=None):
    import dg_rpg
    present = [who for who, name in dg_rpg.at_place(state)]
    if focus in NAMES and focus not in present:
        present.append(focus)
    return {"music_inside":state.get("music_inside",False), "day": state["day"], "slot": state["slot"], "place": state["place"],
            "weather":__import__("dg_world").weather(state)[0], "present": present, "hero_name": state["hero"]["name"],
            "minute":__import__("dg_clock").minute(state) if __import__("dg_clock").enabled(state) else None}


def validate_speakers(text, present):
    """Reject new generated speech from absent actors before committing a turn."""
    speakers = set(re.findall(r"\[(" + "|".join(sorted(NAMES)) + r")\]", _text(text)))
    if speakers.difference(present):
        raise ValueError("Narrator introduced an absent speaker; regenerate the scene")
    if len(re.findall(r'\[stage\b', _text(text), re.I)) != len(STAGING.findall(_text(text))):
        raise ValueError('Malformed scene direction; regenerate the scene')
    for match in re.finditer(r'\[stage[^\]]*\]', _text(text)):
        directive = STAGING.match(match.group(0))
        if (not directive or directive.end() != len(match.group(0))
                or directive.group(1) not in present or directive.group(2) not in EMOTIONS
                or directive.group(3) not in ('normal', 'close', 'far')):
            raise ValueError('Invalid scene direction; regenerate the scene')
    return text


def _pages(value, limit=240):
    # Split overlong tokens too; a URL or an unspaced model output cannot overflow.
    pieces = []
    line = ""
    for word in value.split():
        while len(word) > limit:
            if line:
                pieces.append(line)
                line = ""
            pieces.append(word[:limit])
            word = word[limit:]
        if not word:
            continue
        if line and len(line) + len(word) + 1 > limit:
            pieces.append(line)
            line = ""
        line += (" " if line else "") + word
    if line:
        pieces.append(line)
    return pieces


def _parse_text(scene_text, present=(), focus=None):
    """Parse safe text labels; legacy unmarked prose remains narrator prose."""
    text = _text(scene_text).replace("\r\n", "\n")
    # Tagged turns may share a paragraph, but ordinary inline [brackets] are data.
    text = re.sub(r"(?<!\n)(\[(?:narrator|hero|" + "|".join(sorted(NAMES)) + r")\])", r"\n\1", text)
    allowed = set(present)
    result = []
    for block in re.split(r"\n\s*\n|\n(?=\[)", text):
        block = block.strip()
        if not block:
            continue
        speaker = None
        match = re.match(r"^\[([a-z_]+)\]\s*(.*)$", block, re.S)
        if match:
            token, body = match.groups()
            if token in ("hero", "narrator") or token in allowed:
                speaker = None if token == "narrator" else token
                block = body.strip()
            elif token in NAMES:
                block = NAMES[token] + ": " + body.strip()
        else:
            # Support old scenes with explicit names without guessing from a mention.
            for who, name in list(NAMES.items()) + [("hero", u"Герой")]:
                prefix = name + ":"
                if block.startswith(prefix) and (who in allowed or who == "hero"):
                    speaker, block = who, block[len(prefix):].strip()
                    break
            # A standalone quoted answer in the old single-NPC format is unambiguous.
            if speaker is None and focus in allowed and block.startswith(u"«") and block.endswith(u"»") and block.count(u"«") == 1:
                speaker = focus
        for page in _pages(block):
            result.append({"who": speaker, "text": page})
    return result


def parse(scene_text, present=(), focus=None):
    """Directions are inert, whitelisted data; only existing actors can change."""
    text = _text(scene_text)
    result, staging, cursor = [], {}, 0
    for directive in STAGING.finditer(text):
        for turn in _parse_text(text[cursor:directive.start()], present, focus):
            turn['stage'] = copy.deepcopy(staging)
            result.append(turn)
        who, emotion, distance, pose = directive.groups()
        if who in present and emotion in EMOTIONS and distance in ('normal', 'close', 'far'):
            staging[who] = {'emotion':emotion, 'distance':distance, 'pose':None if pose == 'auto' else pose}
        cursor = directive.end()
    for turn in _parse_text(text[cursor:], present, focus):
        turn['stage'] = copy.deepcopy(staging)
        result.append(turn)
    return result


def cast(turns, present=(), focus=None):
    allowed = set(present)
    result = []
    for turn in turns:
        for actor in turn.get('stage', {}):
            if actor in allowed and actor not in result:
                result.append(actor)
        who = turn["who"]
        if who in allowed and who in NAMES and who not in result:
            result.append(who)
    if focus in allowed and focus in NAMES and focus not in result:
        result.insert(0, focus)
    # Mentioned characters in legacy narrator prose can still be in the shot.
    text = " ".join(turn["text"] for turn in turns)
    for who in present:
        if who in NAMES and who not in result and re.search(r"(?<!\w)" + NAMES[who] + r"(?!\w)", text):
            result.append(who)
    # Everyone physically present remains visible, including silent listeners.
    for who in present:
        if who in NAMES and who not in result:
            result.append(who)
    return result


def readable(text):
    """Keep presentation tags out of diaries and other plain-text views."""
    def replace(match):
        who = match.group(1)
        if who == "narrator":
            return ""
        return (u"Герой" if who == "hero" else NAMES[who]) + ": "
    return re.sub(r"\[(narrator|hero|" + "|".join(sorted(NAMES)) + r")\]\s*", replace, STAGING.sub('', _text(text)))


def positions(cast_ids, speaker=None):
    # Keep the active speaker in frame even in a crowded scene.
    visible = list(cast_ids[:4])
    if speaker in cast_ids and speaker not in visible:
        visible[-1] = speaker
    places = {0: (), 1: (.5,), 2: (.28, .72), 3: (.17, .5, .83),
              4: (.13, .37, .63, .87)}[len(visible)]
    return list(zip(visible, places))

