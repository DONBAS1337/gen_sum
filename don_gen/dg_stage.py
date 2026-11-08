# -*- coding: utf-8 -*-
"""Scene presentation data only: speakers, cast, pages and map geometry.

Never executes model text or applies game effects. Python 2.7/3 compatible.
"""
from __future__ import unicode_literals
import re

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
    return {"day": state["day"], "slot": state["slot"], "place": state["place"],
            "present": present, "hero_name": state["hero"]["name"]}


def validate_speakers(text, present):
    """Reject new generated speech from absent actors before committing a turn."""
    speakers = set(re.findall(r"\[(" + "|".join(sorted(NAMES)) + r")\]", _text(text)))
    if speakers.difference(present):
        raise ValueError("Narrator introduced an absent speaker; regenerate the scene")
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


def parse(scene_text, present=(), focus=None):
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


def cast(turns, present=(), focus=None):
    allowed = set(present)
    result = []
    for turn in turns:
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
    return result


def readable(text):
    """Keep presentation tags out of diaries and other plain-text views."""
    def replace(match):
        who = match.group(1)
        if who == "narrator":
            return ""
        return (u"Герой" if who == "hero" else NAMES[who]) + ": "
    return re.sub(r"\[(narrator|hero|" + "|".join(sorted(NAMES)) + r")\]\s*", replace, _text(text))


def positions(cast_ids, speaker=None):
    # Keep the active speaker in frame even in a crowded scene.
    visible = list(cast_ids[:4])
    if speaker in cast_ids and speaker not in visible:
        visible[-1] = speaker
    places = {0: (), 1: (.5,), 2: (.28, .72), 3: (.17, .5, .83),
              4: (.13, .37, .63, .87)}[len(visible)]
    return list(zip(visible, places))

