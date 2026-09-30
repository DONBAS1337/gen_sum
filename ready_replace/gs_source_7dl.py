# -*- coding: utf-8 -*-
"""Safe 7DL source indexer/retriever for Generative Summer.

Python 2.7/3 compatible.  It NEVER imports or executes foreign Ren'Py code.
It treats .rpy files only as text and builds a compact searchable index.

Typical use outside the game:
    python gs_source_7dl.py build --root "D:/.../workshop/content/331470/3266357374" --out 7dl_index.json
    python gs_source_7dl.py query --index 7dl_index.json --route mi_7dl --text "Мику музыкальный клуб репетиция"

The in-game integration can import build_index/query/render_context directly and cache
7dl_index.json under the Generative Summer save directory.
"""
from __future__ import unicode_literals

import argparse
import hashlib
import io
import json
import math
import os
import re
import sys
import time

try:
    text_type = unicode
except NameError:
    text_type = str


INDEX_VERSION = 1

# Canonical filenames.  Complete Edition and Lost Alpha use the same useful
# scenario basenames in their active trees; discovery scores active CE paths
# above Old_Road / unreleased copies.
CANONICAL_FILES = {
    "text_common_day0": "text_common_day0.rpy",
    "text_common_day1": "text_common_day1.rpy",
    "text_common_day2": "text_common_day2.rpy",
    "text_common_day3": "text_common_day3.rpy",
    "text_mi_7dl": "text_mi_7dl.rpy",
    "text_mi_dj": "text_mi_dj.rpy",
    "text_mi_cl": "text_mi_cl.rpy",
    "pls_common_day0": "pls_common_day0.rpy",
    "pls_common_day1": "pls_common_day1.rpy",
    "pls_common_day2": "pls_common_day2.rpy",
    "pls_common_day3": "pls_common_day3.rpy",
    "pls_mi_7dl": "pls_mi_7dl.rpy",
    "pls_mi_dj": "pls_mi_dj.rpy",
    "pls_mi_cl": "pls_mi_cl.rpy",
    "router": "sdl_ce_router.rpy",
    "mi_selector": "sdl_ce_mi_selector.rpy",
    "route_selector": "sdl_ce_route_selector_main.rpy",
    "vars_init": "sdl_ce_vars_init.rpy",
    "define_7dl": "7dl_define.rpy",
    "define_ce": "sdl_ce_define.rpy",
    "sprites": "7dl_sprites.rpy",
    "music": "7dl_music.rpy",
}

ROUTE_PROFILES = {
    "mi_7dl": {
        "title": "Мику — 7ДЛ",
        "entry": "sdl_day4_mi_7dl_start",
        "route_file": "text_mi_7dl",
        "controller_file": "pls_mi_7dl",
        "seed_labels": ["init_mi_7dl_2", "init_sdl_mi_7dl_2"],
    },
    "mi_dj": {
        "title": "Мику — DJ",
        "entry": "sdl_day4_mi_dj_start",
        "route_file": "text_mi_dj",
        "controller_file": "pls_mi_dj",
        "seed_labels": ["init_mi_dj_2", "init_sdl_mi_dj_2"],
    },
    "mi_cl": {
        "title": "Мику — Классика",
        "entry": "sdl_day4_mi_cl_start",
        "route_file": "text_mi_cl",
        "controller_file": "pls_mi_cl",
        "seed_labels": ["init_sdl_mi_cl_2"],
    },
}

SCENARIO_KEYS = [
    "text_common_day0", "text_common_day1", "text_common_day2", "text_common_day3",
    "text_mi_7dl", "text_mi_dj", "text_mi_cl",
]
CONTROLLER_KEYS = [
    "pls_common_day0", "pls_common_day1", "pls_common_day2", "pls_common_day3",
    "pls_mi_7dl", "pls_mi_dj", "pls_mi_cl", "router", "mi_selector", "route_selector",
]
META_KEYS = ["vars_init", "define_7dl", "define_ce", "sprites", "music"]

LABEL_RE = re.compile(r"^\s*label\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\([^)]*\))?\s*:\s*(?:#.*)?$")
CALL_RE = re.compile(r"^\s*(call|jump)\s+([A-Za-z_][A-Za-z0-9_]*)\b")
COND_RE = re.compile(r"^\s*(if|elif)\s+(.+?)\s*:\s*(?:#.*)?$")
ELSE_RE = re.compile(r"^\s*else\s*:\s*(?:#.*)?$")
ASSIGN_RE = re.compile(r"^\s*\$\s*([A-Za-z_][A-Za-z0-9_\.\[\]'\"]*)\s*=\s*(.+?)\s*$")
APPEND_RE = re.compile(r"^\s*\$\s*([A-Za-z_][A-Za-z0-9_]*)\.append\((.+)\)\s*$")
DEFAULT_RE = re.compile(r"^\s*default\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
SCENE_RE = re.compile(r"^\s*scene\s+(.+?)(?:\s+with\s+\S+|\s*:\s*)?$")
SHOW_RE = re.compile(r"^\s*show\s+(.+?)(?:\s+at\s+\S+|\s+with\s+\S+|\s*:\s*)?$")
HIDE_RE = re.compile(r"^\s*hide\s+([A-Za-z_][A-Za-z0-9_]*)")
PLAY_RE = re.compile(r"^\s*play\s+(music|ambience|sound)\s+(.+?)(?:\s+fadein\s+\S+|\s+fadeout\s+\S+|\s+loop\b|\s+noloop\b|\s*$)")
STOP_RE = re.compile(r"^\s*stop\s+(music|ambience|sound)\b")
DAY_RE = re.compile(r"(?:^|_)day([0-9]+)(?:_|$)")
STRING_LINE_RE = re.compile(r"^\s*(?:(?P<who>[A-Za-z_][A-Za-z0-9_]*)\s+)?(?P<literal>[uUrR]{0,2}(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'))\s*(?:#.*)?$")

# Enough for lexical retrieval; source labels/route names still give a strong signal.
STOP_WORDS = set((
    "и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас опять вам ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем сказать всех никогда сегодня можно при наконец два об другой хоть после над больше тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой перед иногда лучше чуть том нельзя такой им более всегда конечно всю между"
).split())


def _u(value):
    if isinstance(value, text_type):
        return value
    return value.decode("utf-8", "replace")


def read_text(path):
    # Ren'Py 7.4 / bundled Python 2.7 can lack the "utf-8-sig" codec alias.
    # Read bytes, strip an optional UTF-8 BOM ourselves, then decode with the
    # plain UTF-8 codec that is guaranteed to exist in the game runtime.
    with open(path, "rb") as source:
        raw = source.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8", "replace")


def _rel(root, path):
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except Exception:
        return os.path.basename(path)


def _path_score(path):
    low = path.replace("\\", "/").lower()
    score = 0
    if "/scenario/ce/" in low:
        score += 100
    if "/config/res/ce/" in low:
        score += 90
    if "/config/res/" in low:
        score += 40
    if "/scenario/" in low:
        score += 35
    if "/old_road/" in low or "/old_ends/" in low:
        score -= 100
    if "/unreleased/" in low:
        score -= 80
    if "/scenario_alt/" in low:
        score -= 50
    if "/backup" in low or "/old/" in low:
        score -= 30
    return score


def discover_sources(root):
    """Locate the active 7DL files without executing the mod."""
    root = os.path.abspath(root)
    wanted = {}
    by_name = {}
    names = set(name.lower() for name in CANONICAL_FILES.values())
    for directory, dirnames, filenames in os.walk(root):
        # Do not descend into obvious caches/build output if present.
        dirnames[:] = [d for d in dirnames if d.lower() not in (".git", "__pycache__", "cache")]
        for filename in filenames:
            low = filename.lower()
            if low in names:
                by_name.setdefault(low, []).append(os.path.join(directory, filename))
    for key, filename in CANONICAL_FILES.items():
        candidates = by_name.get(filename.lower(), [])
        if candidates:
            candidates.sort(key=lambda p: (_path_score(p), -len(p)), reverse=True)
            wanted[key] = candidates[0]
    return wanted


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _literal_text(token):
    token = token.strip()
    # Strip Python's unicode/raw prefixes and parse the quoted body ourselves.
    while token and token[0] in "uUrR":
        token = token[1:]
    if len(token) < 2 or token[0] not in "\"'" or token[-1] != token[0]:
        return ""
    body = token[1:-1]
    # Ren'Py strings here are ordinary escaped literals. unicode_escape would mangle
    # non-ASCII input, so decode only common escaped quote/backslash/newline forms.
    body = body.replace("\\\"", "\"").replace("\\'", "'")
    body = body.replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")
    return body


def tokenize(text):
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9_]+", _u(text).lower(), re.UNICODE)
    result = []
    for word in words:
        if len(word) < 2 or word in STOP_WORDS:
            continue
        result.append(word)
    return result


def split_labels(text):
    lines = text.splitlines()
    starts = []
    for index, line in enumerate(lines):
        match = LABEL_RE.match(line)
        if match:
            starts.append((index, match.group(1)))
    result = []
    for pos, (start, label) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        result.append((label, start + 1, end, lines[start:end]))
    return result


def _route_from_name(key, label):
    value = key + " " + label
    if "mi_dj" in value:
        return "mi_dj"
    if "mi_cl" in value:
        return "mi_cl"
    if "mi_7dl" in value:
        return "mi_7dl"
    return "common"


def _day(label):
    match = DAY_RE.search(label)
    return int(match.group(1)) if match else None


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _conditions_for_lines(lines):
    """Best-effort indentation tracker. Returns active condition text for each line."""
    active = []  # [{indent, expr}]
    out = []
    for line in lines:
        stripped = line.strip()
        indent = _indent(line)
        if stripped:
            # A sibling statement closes conditions at its indent, except elif/else which replaces it.
            is_branch = bool(COND_RE.match(line) or ELSE_RE.match(line))
            while active and active[-1]["indent"] >= indent and not (is_branch and active[-1]["indent"] == indent):
                active.pop()
            cm = COND_RE.match(line)
            if cm:
                while active and active[-1]["indent"] >= indent:
                    active.pop()
                active.append({"indent": indent, "expr": cm.group(2).strip()})
                out.append(" and ".join(x["expr"] for x in active))
                continue
            if ELSE_RE.match(line):
                if active and active[-1]["indent"] == indent:
                    prev = active.pop()["expr"]
                    active.append({"indent": indent, "expr": "not (%s)" % prev})
                else:
                    active.append({"indent": indent, "expr": "else"})
                out.append(" and ".join(x["expr"] for x in active))
                continue
        out.append(" and ".join(x["expr"] for x in active))
    return out


def parse_label(file_key, file_rel, label, start_line, end_line, lines, kind):
    route = _route_from_name(file_key, label)
    conditions = _conditions_for_lines(lines)
    dialogue = []
    characters = set()
    resources = {"backgrounds": set(), "sprites": set(), "music": set(), "ambience": set(), "sounds": set()}
    flow = []
    mutations = []
    story_parts = []

    for offset, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lineno = start_line + offset
        condition = conditions[offset] or None

        sm = STRING_LINE_RE.match(line)
        if sm:
            text = _literal_text(sm.group("literal"))
            if text:
                who = sm.group("who")
                dialogue.append({"who": who, "text": text, "line": lineno})
                if who:
                    characters.add(who)
                    story_parts.append(who + ": " + text)
                else:
                    story_parts.append(text)
            continue

        fm = CALL_RE.match(line)
        if fm:
            flow.append({"op": fm.group(1), "target": fm.group(2), "condition": condition, "line": lineno})

        am = ASSIGN_RE.match(line)
        if am:
            mutations.append({"target": am.group(1), "value": am.group(2).strip(), "condition": condition, "line": lineno})
        else:
            ap = APPEND_RE.match(line)
            if ap:
                mutations.append({"target": ap.group(1), "value": "append(%s)" % ap.group(2).strip(), "condition": condition, "line": lineno})

        sc = SCENE_RE.match(line)
        if sc:
            name = sc.group(1).strip()
            # Keep only plain image names. Expression/ATL scenes remain visible in code but are not catalog candidates.
            if not name.startswith(("expression ", "black")):
                resources["backgrounds"].add(name)
            elif name == "black":
                resources["backgrounds"].add(name)

        sh = SHOW_RE.match(line)
        if sh:
            resources["sprites"].add(sh.group(1).strip())
        hd = HIDE_RE.match(line)
        if hd:
            characters.add(hd.group(1))

        pm = PLAY_RE.match(line)
        if pm:
            group = {"music": "music", "ambience": "ambience", "sound": "sounds"}[pm.group(1)]
            resources[group].add(pm.group(2).strip())

    day = _day(label)
    story_text = "\n".join(story_parts)
    return {
        "id": file_key + ":" + label,
        "label": label,
        "file_key": file_key,
        "file": file_rel,
        "kind": kind,
        "route": route,
        "day": day,
        "start_line": start_line,
        "end_line": end_line,
        "characters": sorted(characters),
        "resources": dict((k, sorted(v)) for k, v in resources.items()),
        "flow": flow,
        "mutations": mutations,
        "dialogue_count": len(dialogue),
        "story_text": story_text,
    }


def parse_file(path, file_key, root, kind):
    text = read_text(path)
    rel = _rel(root, path)
    scenes = []
    for label, start, end, lines in split_labels(text):
        scenes.append(parse_label(file_key, rel, label, start, end, lines, kind))
    return scenes


def parse_defaults(path, root):
    defaults = []
    if not path:
        return defaults
    for lineno, line in enumerate(read_text(path).splitlines(), 1):
        match = DEFAULT_RE.match(line)
        if match:
            defaults.append({"name": match.group(1), "value": match.group(2).strip(), "line": lineno,
                             "file": _rel(root, path)})
    return defaults


def _direct_files(directory, extensions):
    # The active resource roots are safe to traverse recursively (for example
    # Sound/sfx/repl); Old_Road/fanfics are outside these roots.
    if not os.path.isdir(directory):
        return
    for current, dirnames, filenames in os.walk(directory):
        dirnames[:] = [d for d in dirnames if d.lower() not in ("__pycache__", "cache")]
        for name in sorted(filenames):
            path = os.path.join(current, name)
            if os.path.splitext(name)[1].lower() in extensions:
                yield path


def _strip_7dl_suffix(value):
    return value[:-4] if value.lower().endswith("_7dl") else value


def _background_name(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    # Legacy 7DL stores many files as bg_ext_*.jpg while the Ren'Py image is
    # declared as "bg ext_*". CE stores the same class as ext_*.jpg.
    if base.startswith("bg_"):
        base = base[3:]
    return "bg " + base


def _cg_name(filename):
    base = os.path.splitext(os.path.basename(filename))[0]
    if base.startswith("cg_"):
        base = base[3:]
    return "cg " + base


def _audio_key(group, filename):
    base = _strip_7dl_suffix(os.path.splitext(os.path.basename(filename))[0])
    prefix = {"ambience": "ambience_", "sounds": "sfx_", "music": "music_"}[group]
    if base.startswith(prefix):
        base = base[len(prefix):]
    # Keep foreign resources out of the vanilla key namespace. The generated
    # script grammar accepts only identifiers, so use a stable ASCII prefix.
    return {"music": "sdl_music_", "ambience": "sdl_ambience_", "sounds": "sdl_sfx_"}[group] + base


def asset_manifest(root):
    """Return direct 7DL backgrounds/audio without executing any Ren'Py code.

    Only active base + Complete Edition resource folders are scanned. Old_Road,
    fanfics and unreleased trees are deliberately ignored.
    """
    assets = {"backgrounds": {}, "cgs": {}, "music": {}, "ambience": {}, "sounds": {}}
    if not root or not os.path.isdir(root):
        return assets

    # Scan base first and CE second: an active CE file wins on a duplicate key.
    background_dirs = [
        os.path.join(root, "scenario_alt", "Pics", "bg"),
        os.path.join(root, "scenario_alt", "Pics", "CE", "bg"),
    ]
    for directory in background_dirs:
        for path in _direct_files(directory, (".jpg", ".jpeg", ".png", ".webp")):
            assets["backgrounds"][_background_name(path)] = _rel(root, path)

    cg_dirs = [
        os.path.join(root, "scenario_alt", "Pics", "cg"),
        os.path.join(root, "scenario_alt", "Pics", "CE", "cg"),
    ]
    for directory in cg_dirs:
        for path in _direct_files(directory, (".jpg", ".jpeg", ".png", ".webp")):
            assets["cgs"][_cg_name(path)] = _rel(root, path)

    sound_dirs = {
        "music": [
            os.path.join(root, "scenario_alt", "Sound", "music"),
            os.path.join(root, "scenario_alt", "Sound", "CE", "music"),
        ],
        "ambience": [
            os.path.join(root, "scenario_alt", "Sound", "ambience"),
            os.path.join(root, "scenario_alt", "Sound", "CE", "ambience"),
        ],
        "sounds": [
            os.path.join(root, "scenario_alt", "Sound", "sfx"),
            os.path.join(root, "scenario_alt", "Sound", "CE", "sfx"),
        ],
    }
    for group, directories in sound_dirs.items():
        for directory in directories:
            for path in _direct_files(directory, (".ogg", ".mp3", ".wav", ".opus")):
                assets[group][_audio_key(group, path)] = _rel(root, path)
    return assets


def _asset_manifest(root):
    # Backward-compatible internal name used by the standalone build command.
    return asset_manifest(root)


def build_index(root, source_map=None, include_assets=True):
    root = os.path.abspath(root)
    source_map = dict(source_map or discover_sources(root))
    missing = [key for key in (SCENARIO_KEYS + CONTROLLER_KEYS) if key not in source_map]
    scenes = []
    files = {}
    for key in SCENARIO_KEYS + CONTROLLER_KEYS + META_KEYS:
        path = source_map.get(key)
        if not path or not os.path.isfile(path):
            continue
        stat = os.stat(path)
        files[key] = {"path": _rel(root, path), "size": stat.st_size, "sha256": _sha256(path)}
        if key in SCENARIO_KEYS:
            scenes.extend(parse_file(path, key, root, "scenario"))
        elif key in CONTROLLER_KEYS:
            scenes.extend(parse_file(path, key, root, "control"))

    by_label = {}
    for scene in scenes:
        by_label.setdefault(scene["label"], []).append(scene["id"])

    # Explicit route outline from controller call order.  This is not execution:
    # it records edges and conditions for the retriever/model to understand structure.
    outlines = {}
    for route, profile in ROUTE_PROFILES.items():
        controller_key = profile["controller_file"]
        route_scenes = [s for s in scenes if s["file_key"] == controller_key]
        outlines[route] = {
            "entry": profile["entry"],
            "controller_labels": [s["label"] for s in route_scenes],
            "edges": [dict(edge, source=s["label"])
                      for s in route_scenes for edge in s["flow"]],
            "seed_labels": list(profile["seed_labels"]),
        }

    index = {
        "format": "generative_summer_7dl_index",
        "version": INDEX_VERSION,
        "created_at": time.time(),
        "root_hint": root,
        "missing": missing,
        "files": files,
        "profiles": ROUTE_PROFILES,
        "outlines": outlines,
        "defaults": parse_defaults(source_map.get("vars_init"), root),
        "scenes": scenes,
        "by_label": by_label,
        "assets": _asset_manifest(root) if include_assets else {"backgrounds": {}, "cgs": {}, "music": {}, "ambience": {}, "sounds": {}},
    }
    return index


def save_index(index, path):
    # Python 2's json.dump may emit a mixture of str and unicode chunks.
    # codecs/io text writers then fail with:
    #   TypeError: write() argument 1 must be unicode, not str
    # Serialize once, normalize to unicode, and write UTF-8 bytes atomically.
    payload = json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2)
    payload = _u(payload) + u"\n"
    temporary = path + ".tmp"
    with open(temporary, "wb") as output:
        output.write(payload.encode("utf-8"))
        output.flush()
        try:
            os.fsync(output.fileno())
        except (AttributeError, OSError):
            pass
    if os.path.isfile(path):
        os.remove(path)
    os.rename(temporary, path)


def load_index(path):
    with open(path, "rb") as source:
        raw = source.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return json.loads(raw.decode("utf-8", "replace"))


def _query_terms(query):
    terms = tokenize(query)
    # Strong aliases for the user's common Russian wording.
    aliases = {
        "мику": ["mi", "miku"],
        "клуб": ["musclub", "music"],
        "музыка": ["music", "musclub"],
        "репетиция": ["repetition", "rehearsal"],
        "радио": ["radio", "dj"],
        "диджей": ["dj"],
    }
    expanded = []
    seen = set()
    for term in terms:
        for value in [term] + aliases.get(term, []):
            if value not in seen:
                seen.add(value)
                expanded.append(value)
            if len(expanded) >= 160:
                return expanded
    return expanded


def query(index, text, route=None, day=None, characters=None, limit=8, day_window=None):
    terms = _query_terms(text)
    chars = set(characters or [])
    docs = index.get("scenes", [])
    if route and route not in ROUTE_PROFILES:
        raise ValueError("Unknown 7DL route: %s" % route)

    # Cheap IDF over a few hundred labels keeps rare names/events useful.
    df = dict((term, 0) for term in terms)
    token_sets = []
    for scene in docs:
        searchable = " ".join([scene.get("label", "").replace("_", " "), scene.get("route", "").replace("_", " "), scene.get("story_text", "")])
        tokens = set(tokenize(searchable))
        token_sets.append(tokens)
        for term in df:
            if term in tokens:
                df[term] += 1
    total = float(max(1, len(docs)))

    scored = []
    for scene, tokens in zip(docs, token_sets):
        if scene.get("kind") != "scenario":
            continue
        sr = scene.get("route")
        if route and sr not in ("common", route):
            continue
        if day is not None and day_window is not None and scene.get("day") is not None:
            if abs(int(day) - int(scene["day"])) > int(day_window):
                continue
        score = 0.0
        raw = (scene.get("label", "") + " " + scene.get("story_text", "")).lower()
        for term in terms:
            if term in tokens:
                score += 1.0 + math.log((total + 1.0) / (1.0 + df.get(term, 0)))
                # Repetition in actual story prose matters, but cap it.
                score += min(2.0, raw.count(term) * 0.15)
        if route and sr == route:
            score += 4.0
        elif route and sr == "common":
            score -= 0.5
        if day is not None and scene.get("day") is not None:
            distance = abs(int(day) - int(scene["day"]))
            score += max(0.0, 2.0 - 0.6 * distance)
        if chars:
            common = chars.intersection(scene.get("characters", []))
            score += 1.25 * len(common)
        if "mi" in scene.get("characters", []):
            score += 0.2 if route else 0.0
        if score > 0:
            scored.append((score, scene))
    scored.sort(key=lambda item: (-item[0], item[1].get("day") or 99, item[1]["label"]))
    return [{"score": round(score, 3), "scene": scene} for score, scene in scored[:max(1, int(limit))]]


def route_seed(index, route):
    profile = index.get("profiles", {}).get(route) or ROUTE_PROFILES.get(route)
    if not profile:
        return []
    labels = set(profile.get("seed_labels", []))
    return [scene for scene in index.get("scenes", []) if scene.get("label") in labels]


def clean_sprite_name(value):
    value = _u(value).strip()
    for marker in (" at ", " behind ", " zorder ", " with "):
        value = value.split(marker, 1)[0].strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*(?: [A-Za-z0-9_]+){1,4}$", value):
        return None
    tokens = value.split()
    if any(token == "shade" or re.match(r"^tr[0-9]+$", token) for token in tokens):
        return None
    return value


def route_sprite_names(index, route, allowed_tags=None):
    """Sprite names actually referenced by the selected route/common days.

    We do not execute 7DL's dynamic sprite generator. The Ren'Py side resolves
    these safe names into body/clothes/expression/accessory layers at playback.
    """
    if route not in ROUTE_PROFILES:
        raise ValueError("Unknown 7DL route: %s" % route)
    allowed = set(allowed_tags or [])
    result = set()
    for scene in index.get("scenes", []):
        if scene.get("kind") != "scenario" or scene.get("route") not in ("common", route):
            continue
        for raw in scene.get("resources", {}).get("sprites", []):
            name = clean_sprite_name(raw)
            if not name:
                continue
            if allowed and name.split()[0].rstrip("0123456789") not in allowed:
                continue
            result.add(name)
    return sorted(result)


def render_context(index, hits, route=None, mode="anchored", current_day=None, max_chars=30000):
    """Render compact, non-executable source context for an LLM prompt."""
    if mode not in ("anchored", "divergent", "post_source"):
        mode = "anchored"
    parts = []
    if route:
        profile = index.get("profiles", {}).get(route, {})
        outline = index.get("outlines", {}).get(route, {})
        parts.append("ИСТОЧНИК: 7 ДНЕЙ ЛЕТА / %s" % profile.get("title", route))
        parts.append("Точка входа маршрута: %s" % outline.get("entry", profile.get("entry", "?")))
        parts.append("Режим использования источника: %s; текущий день generated-истории: %s" %
                     (mode, current_day if current_day is not None else "?"))
        if mode == "divergent":
            parts.append("ВАЖНО: route уже разошёлся с исходником. События ниже НЕ являются будущими событиями текущей истории; это только примеры речи, характеров, мира и ресурсов.")
        elif mode == "post_source":
            parts.append("ВАЖНО: generated-история уже вышла за пределы семидневной временной линии. События ниже относятся к ПРОШЛОМУ исходного мода и НЕ должны повторяться как новые; используй только характеры, речь, мир и ресурсы.")
        seeds = route_seed(index, route)
        if seeds:
            seed_lines = []
            for seed in seeds:
                for mut in seed.get("mutations", []):
                    if mut.get("target") == "vars":
                        continue
                    seed_lines.append("%s = %s" % (mut["target"], mut["value"]))
            if seed_lines:
                parts.append("Исходное состояние быстрого старта (справочно, не исполнять): " + "; ".join(seed_lines[:24]))

    resource_patterns = (
        ("music", re.compile(r"^music_7dl\[['\"]([^'\"]+)['\"]\]$"), "sdl_music_"),
        ("ambience", re.compile(r"^ambience_7dl\[['\"]([^'\"]+)['\"]\]$"), "sdl_ambience_"),
        ("sounds", re.compile(r"^sfx_7dl\[['\"]([^'\"]+)['\"]\]$"), "sdl_sfx_"),
    )

    for hit in hits:
        scene = hit.get("scene", hit)
        header_kind = "SOURCE SCENE" if mode == "anchored" else "REFERENCE ONLY"
        header = "[%s | %s | day=%s | route=%s | %s:%s-%s]" % (
            header_kind,
            scene.get("label"), scene.get("day"), scene.get("route"), scene.get("file"),
            scene.get("start_line"), scene.get("end_line"))
        body = scene.get("story_text", "").strip()
        if not body:
            continue
        if mode in ("divergent", "post_source"):
            # Reduce event leakage after the generated route leaves the source
            # timeline. Dialogue is useful for voice/character consistency while
            # narration often carries source-specific plot beats.
            dialogue = []
            for line in body.splitlines():
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*:\s+", line):
                    dialogue.append(line)
            if dialogue:
                body = "\n".join(dialogue[:90])
            else:
                body = body[:1800]

        hints = []
        resources = scene.get("resources", {})
        for name in resources.get("backgrounds", []):
            clean = name.split(" at ", 1)[0].strip()
            if clean.startswith(("bg ", "cg ")):
                hints.append(clean)
        for raw in resources.get("sprites", []):
            clean = clean_sprite_name(raw)
            if clean:
                hints.append(clean)
        for group, pattern, prefix in resource_patterns:
            for raw in resources.get(group, []):
                match = pattern.match(raw)
                if match:
                    hints.append(prefix + match.group(1))

        resource_hint = ""
        if hints:
            resource_hint = (
                "\nРесурсы исходной сцены (используй только если они есть в ДОСТУПНЫХ РЕСУРСАХ): "
                + ", ".join(sorted(set(hints))[:32])
            )
        chunk = header + resource_hint + "\n" + body
        combined = "\n\n".join(parts + [chunk])
        if len(combined) > max_chars:
            remaining = max_chars - len("\n\n".join(parts)) - 4
            if remaining > 500:
                parts.append(chunk[:remaining])
            break
        parts.append(chunk)
    return "\n\n".join(parts)

_INDEX_CACHE = {}


def load_or_build(root, cache_dir):
    """Load the cached narrative index, building it once when absent.

    Cache invalidation is intentionally explicit in this first integration:
    delete 7dl_index.json after updating 7DL to force a rebuild.
    """
    root = os.path.abspath(root)
    cache_dir = os.path.abspath(cache_dir)
    if not os.path.isdir(cache_dir):
        try:
            os.makedirs(cache_dir)
        except OSError:
            if not os.path.isdir(cache_dir):
                raise
    path = os.path.join(cache_dir, "7dl_index.json")
    cached = _INDEX_CACHE.get(path)
    if cached is not None:
        return cached
    if os.path.isfile(path):
        try:
            index = load_index(path)
        except (IOError, OSError, ValueError, TypeError):
            # A previous interrupted/failed build may have left a partial cache.
            index = None
        if index is not None:
            cached_root = index.get("root_hint") or ""
            if (index.get("format") == "generative_summer_7dl_index" and
                    index.get("version") == INDEX_VERSION and
                    os.path.normcase(os.path.abspath(cached_root)) == os.path.normcase(root)):
                _INDEX_CACHE[path] = index
                return index
    index = build_index(root, include_assets=False)
    save_index(index, path)
    _INDEX_CACHE[path] = index
    return index


def source_context(root, cache_dir, route, query_text, mode="anchored", day=None, max_chars=24000, limit=8):
    """Return non-executable 7DL reference prose for one GS generation."""
    if route not in ROUTE_PROFILES:
        raise ValueError("Unknown 7DL route: %s" % route)
    if mode not in ("anchored", "divergent", "post_source"):
        mode = "anchored"
    index = load_or_build(root, cache_dir)
    query_day = day if mode == "anchored" else None
    hits = query(index, query_text, route=route, day=query_day, characters=["mi"], limit=limit,
                 day_window=1 if query_day is not None else None)
    return render_context(index, hits, route=route, mode=mode, current_day=day, max_chars=max_chars)


def _cli_build(args):
    source_map = discover_sources(args.root)
    index = build_index(args.root, source_map, include_assets=not args.no_assets)
    save_index(index, args.out)
    print("saved: %s" % args.out)
    print("scenes: %s" % len(index["scenes"]))
    print("missing: %s" % (", ".join(index["missing"]) if index["missing"] else "none"))
    for route in sorted(ROUTE_PROFILES):
        print("route %s: %s" % (route, index["profiles"][route]["entry"]))


def _cli_query(args):
    index = load_index(args.index)
    hits = query(index, args.text, route=args.route, day=args.day, characters=args.character, limit=args.limit)
    print(render_context(index, hits, route=args.route, max_chars=args.max_chars))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Safe 7DL source indexer for Generative Summer")
    sub = parser.add_subparsers(dest="command")

    build = sub.add_parser("build")
    build.add_argument("--root", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--no-assets", action="store_true")
    build.set_defaults(func=_cli_build)

    ask = sub.add_parser("query")
    ask.add_argument("--index", required=True)
    ask.add_argument("--route", choices=sorted(ROUTE_PROFILES))
    ask.add_argument("--day", type=int)
    ask.add_argument("--character", action="append", default=[])
    ask.add_argument("--limit", type=int, default=8)
    ask.add_argument("--max-chars", type=int, default=30000)
    ask.add_argument("--text", required=True)
    ask.set_defaults(func=_cli_query)

    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
