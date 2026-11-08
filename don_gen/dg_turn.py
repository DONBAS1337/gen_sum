# -*- coding: utf-8 -*-
"""Uncommitted ordinary turns. The narrator must succeed before saving."""
from __future__ import unicode_literals
import copy
import dg_hybrid
import dg_narrative
import dg_rpg


def begin(state):
    return {"before": dg_hybrid.fingerprint(state),
            "state": copy.deepcopy(state)}


def finish(root, pending, scene_key, text):
    candidate = copy.deepcopy(pending["state"])
    current = dg_rpg.load(root, candidate["id"])
    if dg_hybrid.fingerprint(current) != pending["before"]:
        raise ValueError("The saved game changed while generating this scene")
    if not isinstance(text, type(u"")) or not 100 <= len(text.strip()) <= 12000:
        raise ValueError("Narrator returned invalid scene text")
    dg_narrative.remember_scene(candidate, scene_key, text.strip())
    dg_rpg.save(root, candidate)
    return candidate
