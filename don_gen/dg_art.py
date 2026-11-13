# -*- coding: utf-8 -*-
"""DON-GEN image director: existing assets, session cache, optional CG creation.

Only STATIC backgrounds and full-frame CG can be generated. Character sprites
always use vanilla/gen_assets; RGBA image synthesis is intentionally disabled.
No automatic API calls on normal screen redraws.
"""
from __future__ import unicode_literals
import hashlib
import json
import os
import re
import dg_adult

try:
    text_type=unicode
except NameError:
    text_type=str

KINDS=("background","cg","cg18")
CG_SOURCES=("world","personal","incident","ai","hybrid")
CG_CACHE_LENGTH=40
BACKGROUND_QUALITY=(u"wide landscape scene, 16:9 composition, hand-painted anime "
                    u"visual novel, 1980s Soviet summer pioneer camp, consistent "
                    u"Sovyonok architecture, richly detailed, no lettering, no watermarks")
CG_QUALITY=(u"wide 16:9 cinematic illustration in classic visual novel anime style, "
            u"consistent character designs and clothing, atmospheric lighting, "
            u"one dramatic moment, high-quality scene composition, "
            u"no writing, no captions, no user interface, no watermarks")
NEGATIVE=(u"worst quality, low quality, pixelation, watermark, subtitle, "
          u"UI, text, typography, extra limbs, deformed fingers, distorted faces")
APPEARANCE = {
    'mi':u'Miku: very long turquoise twin tails, turquoise eyes, red hair ties',
    'dv':u'Alisa: orange hair in two short side tails, amber eyes',
    'un':u'Lena: purple hair in two short ponytails, green eyes',
    'sl':u'Slavya: blonde hair in one long braid, blue eyes',
    'us':u'Ulyana: short red hair with small side tails, childlike energetic face',
    'mt':u'Olga: adult camp counsellor, long brown hair, green eyes',
    'cs':u'Viola: adult medical professional, long dark purple hair, white medical coat',
    'mz':u'Zhenya: short dark hair, glasses', 'el':u'Elektronik: blond boy with glasses',
    'sh':u'Shurik: brown-haired boy with glasses', 'uv':u'Yulya: lilac hair, cat ears'}

def _digest(value):
    if isinstance(value,text_type):
        value=value.encode("utf-8")
    return hashlib.sha1(value).hexdigest()

def scene_plan(state, source, title, description, who=None, adult_requested=False):
    """Attach a deterministic illustration ID to a REAL completed event."""
    import dg_rpg
    dg_rpg.validate(state)
    if isinstance(description, bytes):
        description=description.decode("utf-8")
    if isinstance(title, bytes):
        title=title.decode("utf-8")
    if source not in CG_SOURCES or not isinstance(description,text_type):
        return None
    description=description.strip()
    if len(description)<55:
        return None
    if who is not None and who not in dg_rpg.NPC_NAMES:
        return None
    if adult_requested:
        if not dg_adult.enabled(state) or who not in dg_adult.ADULT_AU_AGES:
            return None
        if dg_adult.validate_action(state,u"интим",who) is not None:
            return None
        if any(stem in description.lower() for stem in dg_adult.YOUNG_STEMS):
            return None
    kind="cg18" if adult_requested else "cg"
    stable=u"|".join([text_type(state["id"]),source,text_type(state["day"]),
                     text_type(state["place"]),text_type(who or ""),
                     text_type(title),description,kind])
    return {"key":_digest(stable),"kind":kind,"title":title[:170],
            "description":description[:2500],"who":who,"source":source,
            "day":state["day"],"place":state["place"]}

def is_cg_worthy(state, source, text, who=None, adult_requested=False):
    return scene_plan(state,source,u"Сцена",text,who,adult_requested) is not None

def background_prompt(state, place):
    import dg_rpg
    import dg_world
    if place not in dg_rpg.PLACE_NAMES:
        raise ValueError("Unknown background location")
    phase=dg_rpg.SLOTS[state["slot"]]
    return (BACKGROUND_QUALITY + u". Location: " +
            dg_rpg.PLACE_NAMES[place] + u". Time: " + phase +
            u". Weather: " + dg_world.weather(state)[1] +
            u". Empty environment without people or text.")

def cg_prompt(state, plan):
    import dg_rpg
    dg_rpg.validate(state)
    if plan is None or plan.get("kind") not in ("cg","cg18"):
        raise ValueError("Invalid CG plan")
    who=plan.get("who")
    if who is not None and who not in dg_rpg.NPC_NAMES:
        raise ValueError("Unknown scene protagonist")
    if plan["kind"]=="cg18":
        if (not dg_adult.enabled(state) or who not in dg_adult.ADULT_AU_AGES or
                any(stem in plan["description"].lower() for stem in dg_adult.YOUNG_STEMS)):
            raise ValueError("Adult CG is not permitted for these participants")
        romance=(u"An alternative-universe scene between clearly adult "
                 u"consenting characters, tasteful intimate romantic atmosphere, "
                 u"all characters 18+, no childlike appearance. ")
    else:
        romance=u"General-audience scene, avoid nudity and sexualized imagery. "
    import dg_stage
    scene=dg_stage.readable(plan["description"])[:2000]
    person=u" Featuring %s. " % dg_rpg.NPC_NAMES[who] if who else u""
    cast = list(plan.get('cast') or ([who] if who else []))
    if plan['kind'] == 'cg18' and any(actor not in dg_adult.ADULT_AU_AGES for actor in cast):
        raise ValueError('Adult CG cast contains a protected character')
    identities = u'; '.join(APPEARANCE[actor] for actor in cast if actor in APPEARANCE)
    place = plan.get('scene_place', plan['place'])
    moment = plan.get('scene_slot', state['slot'])
    return (CG_QUALITY + u". " + romance + person + u"Character identities: " + identities +
            u". Keep the listed cast and consistent original pioneer uniforms. Location: " +
            dg_rpg.PLACE_NAMES[place] + u". Setting: " + (plan.get('setting') or 'as described') +
            u". Time: " + dg_rpg.SLOTS[moment] + u". Scene: " + scene)

def asset_location(root, game_id, kind, key):
    import dg_rpg
    if kind not in KINDS:
        raise ValueError("Only backgrounds and full-frame CG are generated")
    return dg_rpg.asset_path(root,game_id,kind,key)

def resolve(root, game_id, kind, key, built_in=None, prefer_generated=True):
    """Return asset availability without generating, mutating or network calls.

    Built-in is a verified filename/asset ref supplied by caller.
    """
    generated=asset_location(root,game_id,kind,key)
    exists=os.path.isfile(os.path.join(root,*generated.split("/")))
    if exists and (prefer_generated or not built_in):
        return {"status":"generated","path":generated,"generate":False}
    if built_in:
        return {"status":"builtin","path":built_in,"generate":False}
    if exists:
        return {"status":"generated","path":generated,"generate":False}
    return {"status":"missing","path":None,"generate":True}

def approve_cg_lookup(root, index, key):
    """Explicit curated map: scene key -> local game-relative path.

    A file with an arbitrary name is not assumed to match a story scene.
    """
    if not isinstance(index,dict):
        return None
    rel=index.get(key)
    if not isinstance(rel,text_type) or not re.match(
            r"^mods/don_gen/images/gen_assets/cg/[a-zA-Z0-9_./-]+\.(?:png|jpg|jpeg)$",rel):
        return None
    if ".." in rel.split("/") or "\\" in rel:
        return None
    return rel

def marker(state, plan):
    if plan is None: return None
    if plan.get("kind")=="cg18" and (not dg_adult.enabled(state) or
                                     plan.get("who") not in dg_adult.ADULT_AU_AGES):
        return None
    return plan["key"]


def freeze_scene_request(plan):
    """Snapshot the CG request before the Ren'Py worker-thread handoff."""
    if not isinstance(plan, dict):
        raise ValueError("CG scene is not a dictionary")
    return json.dumps(plan, ensure_ascii=False, sort_keys=True)


def validate_scene_request(state, kind, payload):
    """Decode a frozen request and guard against stale/mismatched CG plans."""
    import dg_rpg
    dg_rpg.validate(state)
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    if isinstance(payload, text_type):
        try:
            plan = json.loads(payload)
        except (TypeError, ValueError):
            raise ValueError("CG request could not be decoded")
    else:
        plan = payload  # compatibility with older caller, not used by new UI
    if not isinstance(plan, dict):
        raise ValueError("CG request must be a dictionary")
    if kind not in ("cg", "cg18") or plan.get("kind") != kind:
        raise ValueError("CG type changed while preparing the image")
    if plan.get("source") not in CG_SOURCES:
        raise ValueError("Unknown cinematic scene source")
    who = plan.get("who")
    if who is not None and who not in dg_rpg.NPC_NAMES:
        raise ValueError("Unknown CG character")
    if plan.get("day") != state["day"] or plan.get("place") != state["place"]:
        raise ValueError("CG belongs to an earlier moment of the shift")
    key = plan.get("key")
    if not isinstance(key, (str, text_type)) or not re.match(r"^[a-f0-9]{40}$", key):
        raise ValueError("Invalid CG cache identifier")
    title, desc = plan.get("title"), plan.get("description")
    if not isinstance(title, (str, text_type)) or not isinstance(desc, (str, text_type)):
        raise ValueError("CG lacks its scene text")
    if len(title) > 170 or not (55 <= len(desc) <= 2500):
        raise ValueError("CG scene text length is invalid")
    if marker(state, plan) is None:
        raise ValueError("CG disabled for this character or adult setting")
    return plan

