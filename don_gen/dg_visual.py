# -*- coding: utf-8 -*-
"""Pure visual selection for Ren'Py 7: in-scene BG, emotion & real sprite distance.

Works without network/PNG synthesis; all candidates are existing game assets.
"""
from __future__ import unicode_literals
import re

try:
    text_type=unicode
except NameError:
    text_type=str

EMOTION_CUES=(
    ("cry", (u"плачет",u"заплак",u"слёз",u"слез",u"рыда")),
    ("sad", (u"печал",u"груст",u"поник",u"расстро",u"тоску")),
    ("angry", (u"сердит",u"злится",u"разозл",u"возмущ",u"ссор",u"раздраж",u"нахмур")),
    ("surprise", (u"удив",u"ошараш",u"вздрог",u"неожиданн")),
    ("shy", (u"красне",u"смущ",u"застесня")),
    ("laugh", (u"смеёт",u"смеет",u"засмея",u"хохот")),
    ("smile", (u"улыб",u"довольн",u"радост",u"счастлив")),
)
EMOTION_FALLBACK={
    "serious":("serious","normal","sad"),
    "cry":("cry","sad","shy","normal"),
    "sad":("sad","shy","normal","smile"),
    "angry":("angry","rage","serious","normal"),
    "surprise":("surprise","shocked","normal","smile"),
    "shy":("shy","smile","normal"),
    "laugh":("laugh","smile","happy","normal"),
    "smile":("smile","happy","normal"),
    "normal":("normal","smile","happy","serious","shy"),
}
DISTANCE_CUES=(
    ("close",(u"совсем рядом",u"подошла вплотную",u"подошёл вплотную",
              u"наклонилась к",u"наклонился к",u"придвинулась",u"шепчет на ухо")),
    ("far",(u"издалека",u"вдали",u"отступила",u"отступил",
            u"в стороне",u"на другом конце"))
)
DAY_NAMES={"day":"day","evening":"sunset","night":"night"}

def _unicode(value):
    if isinstance(value,bytes):
        return value.decode("utf-8","replace")
    return value if isinstance(value,text_type) else text_type(value)

def mood(text):
    text=_unicode(text or u"").lower()
    for name,stems in EMOTION_CUES:
        for stem in stems:
            for match in re.finditer(re.escape(stem), text):
                prefix = text[max(0, match.start()-24):match.start()]
                if not re.search(u'\\bне(?:\\s+\\w+){0,2}\\s*$', prefix):
                    return name
    return "normal"

def distance(text):
    text=_unicode(text or u"").lower()
    for name,stems in DISTANCE_CUES:
        if any(stem in text for stem in stems):
            return name
    return "normal"

def sprite_names(who, emotion="normal", distance_name="normal", known=(), clothes="pioneer"):
    """Rank actual Ren'Py original sprite names; don't invent unregistered poses."""
    desired=EMOTION_FALLBACK.get(emotion,EMOTION_FALLBACK["normal"])
    names=[x for x in known if x.split(" ")[0] == who]
    if not names:
        return []
    def rank(name):
        parts=name.split(" ")
        if len(parts)<2:
            return (99,99,99,name)
        face=parts[1]
        face_rank=desired.index(face) if face in desired else 30
        last=parts[-1]
        actual_distance=last if last in ("close","far") else "normal"
        # First favor requested distance over requested face for correct size.
        distance_rank=0 if actual_distance==distance_name else (
             1 if actual_distance=="normal" else 2)
        costume_rank=0 if clothes in parts else 1 if "pioneer" in parts else 2
        return distance_rank,costume_rank,face_rank,name
    return sorted(names,key=rank)

def sprite_queries(who, emotion="normal", distance_name="normal", clothes="pioneer"):
    """Known physical layers can provide a sprite even without a registered image."""
    tones=EMOTION_FALLBACK.get(emotion,EMOTION_FALLBACK["normal"])
    distance_suffix=(" "+distance_name) if distance_name!="normal" else ""
    return [(who+" "+face+" "+clothes+distance_suffix) for face in tones]+[
            who+" normal pioneer",who+" smile pioneer"]

def background_names(base, slot):
    """Prefer time-matched original scene when present; don't show gate elsewhere."""
    base=_unicode(base or u"")
    if not base.startswith("bg "):
        return [base] if base else []
    names=[]
    slot=int(slot)
    desired="day" if slot in (0,1) else "sunset" if slot==2 else "night"
    stem=base
    for ending in ("_day","_sunset","_night","_evening"):
        if stem.endswith(ending):
            stem=stem[:-len(ending)]
            break
    for suffix in ([desired,"evening","sunset","day"] if slot==2
                   else [desired,"night","sunset","day"] if slot==3
                   else ["day","sunset","night"]):
        candidate=stem+"_"+suffix
        if candidate not in names:
            names.append(candidate)
    if base not in names:
        names.append(base)
    return names



def background_key(place,slot):
    import dg_rpg
    if place not in dg_rpg.PLACE_NAMES or slot not in (0,1,2,3):
        raise ValueError('Invalid background moment')
    return place + ('_day' if slot in (0,1) else '_sunset' if slot==2 else '_night')


def narrated_moods(text,present):
    import dg_stage
    result={}
    for clause in re.split(u'[.!?;,\n]',_unicode(text)):
        named=[who for who in present if dg_stage.NAMES[who].lower() in clause.lower()]
        if len(named)==1:
            emotion=mood(clause)
            if emotion!='normal':
                result[named[0]]=emotion
    return result


def clothing(state,who,scene=None):
    if scene is not None:
        state=dict(state,**scene)
        if "camp_life" in state:
            state["camp_life"]=dict(state["camp_life"],minute=scene.get("minute") if scene.get("minute") is not None else state["camp_life"]["minute"])
    if who not in ('mi','dv','sl','un','mz','mt','cs'):return 'pioneer'
    if 'camp_life' in state and __import__('dg_schedule').disco(state):
        venue='clubhouse' if __import__('dg_world').weather(state)[0]=='rain' else 'square'
        if state['place']==venue:return 'dress'
    return 'pioneer'


def light_slot(state,scene=None):
    if scene is not None:
        state=dict(state,**scene)
        if 'camp_life' in state:
            state['camp_life']=dict(state['camp_life'],minute=scene.get('minute') if scene.get('minute') is not None else state['camp_life']['minute'])
    if 'camp_life' in state and __import__('dg_schedule').disco(state) and state['place']=='square':return 3
    return state['slot']


def music_door(state, inside):
    """Entering a building is separate from joining its club."""
    import dg_rpg
    if state['place']!='music' or state.get('finished') or type(inside) is not bool:
        raise ValueError(u'Вход в музыкальный кружок сейчас недоступен.')
    if state.get('music_inside',False)==inside:
        return {'status':'done','text':u'Ты уже здесь.','kind':'door','who':None}
    state['music_inside']=inside
    if __import__('dg_clock').enabled(state):dg_rpg._tick(state,1)
    text=u'Ты вошёл в здание музыкального кружка. Членство в кружке от этого не меняется.' if inside else u'Ты вышел на крыльцо музыкального кружка.'
    dg_rpg._journal(state,text)
    return {'status':'done','text':text,'kind':'door','who':None}

def door_intent(state, action):
    if state['place']!='music':return None
    action=action.lower().strip()
    if '?' in action or not re.match(u'^(?:я\s+)?(?:зайти|захожу|войти|вхожу|зайду|выйти|выхожу|выйду)(?:\s|$)',action):return None
    if re.search(u'(?:зайти|захожу|войти|вхожу|зайду|войти внутрь)',action) and re.search(u'(?:муз|круж|внутр)',action):return True
    if re.search(u'(?:выйти|выхожу|выйду)',action) and re.search(u'(?:крыльц|наруж|круж)',action):return False
    return None
