# -*- coding: utf-8 -*-
"""Locate installed Workshop resources without importing another mod's scripts."""
from __future__ import unicode_literals
import io
import json
import os

try:
    text_type = unicode
except NameError:
    text_type = str

WORKSHOP_ID = "3266357374"
MAP_ICONS = {"hero": "n01", "mi": "n02", "sh": "n03", "el": "n04", "mz": "n05",
             "mt": "n06", "uv": "n07", "un": "n08", "us": "n09", "dv": "n10",
             "sl": "n11", "cs": "n12"}
EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".ogg", ".mp3", ".wav", ".opus")


def valid_root(path):
    if not isinstance(path, (str, text_type)) or not path.strip():
        return None
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.basename(path).lower() == "scenario_alt":
        path = os.path.dirname(path)
    return path if os.path.isdir(os.path.join(path, "scenario_alt", "Pics")) else None


def detect_root(game_dir, config_path=None, environ=None):
    environ = os.environ if environ is None else environ
    candidates = [environ.get("DON_GEN_7DL_ROOT")]
    if config_path:
        try:
            with io.open(config_path, "r", encoding="utf-8") as stream:
                config = json.loads(stream.read().lstrip(u"\ufeff"))
            if isinstance(config, dict):
                candidates.append(config.get("seven_dl_root"))
        except (IOError, OSError, ValueError, TypeError):
            pass
    steamapps = os.path.abspath(os.path.join(game_dir, "..", "..", ".."))
    candidates.extend([os.path.join(steamapps, "workshop", "content", "331470", WORKSHOP_ID),
                       os.path.join(game_dir, "mods", "7dl"), os.path.join(game_dir, "mods", "7dl_ce")])
    for path in candidates:
        root = valid_root(path)
        if root:
            return root
    return None


def asset(root, relative):
    """Return an existing media file under this resource root, never a script."""
    if not root or not isinstance(relative, (str, text_type)) or os.path.isabs(relative):
        return None
    if os.path.splitext(relative)[1].lower() not in EXTENSIONS:
        return None
    base = os.path.realpath(root)
    path = os.path.realpath(os.path.join(base, *relative.replace("\\", "/").split("/")))
    if not os.path.normcase(path).startswith(os.path.normcase(base + os.sep)):
        return None
    # Ren'Py's loader rejects backslashes, including in absolute Windows paths.
    return path.replace("\\", "/") if os.path.isfile(path) else None


def map_asset(root, filename):
    if filename not in ("map_bg.jpg", "map_avaliable.jpg", "map_selected.jpg"):
        return None
    return asset(root, "scenario_alt/Pics/gui/maps/" + filename)


def map_icon(root, who):
    code = MAP_ICONS.get(who)
    return asset(root, "scenario_alt/Pics/gui/maps/map_icon_%s.png" % code) if code else None


def absolute_assets(root, manifest):
    """Keep the donor root out of Ren'Py's script search path."""
    if isinstance(manifest, dict):
        return dict((key, absolute_assets(root, value)) for key, value in manifest.items())
    if isinstance(manifest, (str, text_type)):
        return asset(root, manifest)
    return manifest


BACKGROUND_STEMS = {
    "administration": ("ext_admins",), "headquarters": ("int_admin_empty", "int_admin"),
    "showers": ("ext_bathhouse",), "washrooms": ("ext_washstands",),
    "storage": ("int_warehouse",), "warehouse": ("ext_warehouse",),
    "gym": ("int_sporthall",), "sports": ("ext_sport",),
    "volleyball": ("ext_sport",), "football": ("ext_sport",), "badminton": ("ext_sport",),
    "old_camp": ("ext_old_building",), "library": ("int_library",),
    "infirmary": ("int_medbay",), "canteen": ("int_dinningroom_full", "int_dinningroom_half"),
    "boathouse": ("ext_boathouse_alt2", "ext_boathouse_alt"),
    "island": ("ext_island",), "island_far": ("ext_island",),
}


def background(manifest, place, slot):
    stems = BACKGROUND_STEMS.get(place, ("ext_house",) if place.startswith("cabin_") else ())
    suffix = "day" if slot in (0, 1) else "sunset" if slot == 2 else "night"
    backgrounds = manifest.get("backgrounds", {})
    for stem in stems:
        path = backgrounds.get("bg %s_%s_7dl" % (stem, suffix))
        if path:
            return path
    return None
