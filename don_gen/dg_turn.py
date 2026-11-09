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
    import dg_stage
    if not isinstance(text, type(u"")) or len(text) > 12000 or len(dg_stage.readable(text).strip()) < 100:
        raise ValueError("Narrator returned invalid scene text")
    dg_narrative.remember_scene(candidate, scene_key, text.strip())
    import dg_memory
    dg_memory.record(candidate, scene_key, pending.get('intention', u'Завершённый ход'),
                     pending.get('result', candidate.get('event', u'')), text.strip(),
                     pending.get('who'), origin=current,
                     spawn_thread=bool(pending.get('intention')) and not (current.get('world', {}).get('event') or {}).get('thread_id'))
    dg_rpg.save(root, candidate)
    return candidate
