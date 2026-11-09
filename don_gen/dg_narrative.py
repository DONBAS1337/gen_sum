# -*- coding: utf-8 -*-
"""DON-GEN narrative director.

Offline variation is deterministic per save, time, route and scene; LLM can
replace prose (never world mechanics) on demand. No network, filesystem,
or Ren'Py dependency in this module. Python 2.7 + 3.
"""
from __future__ import unicode_literals
import copy
import hashlib
import json
import dg_bkrr

try:
    text_type=unicode
except NameError:
    text_type=str

STYLE_PROFILES={
 "bkrr:mi": dg_bkrr.PROFILE,
 "vanilla": (u"летний лагерь, будни, лёгкая ностальгия, юмор и честные чувства",
             u"Внешний мир и необычные события вводить только при поддержке истории"),
 "7dl:mi_7dl": (u"7ДЛ: Мику как самостоятельная личность: сцена, музыка, отношения, "
                u"несказанное, страх быть неуслышанной, сложные личные решения",
                u"Не делай Мику однообразно болтливой или бесконечно восторженной. "
                u"Разделяй искреннюю лёгкость и внутреннее напряжение"),
 "7dl:mi_dj": (u"7ДЛ DJ: самостоятельный музыкальный мир, ритм, аппаратура, "
               u"радио, работа со звуком, публичный образ и частная сторона",
               u"Не смешивай DJ-ветку с канонической Мику 7ДЛ/классикой; "
               u"музыкальные знания должны влиять на конфликт"),
 "7dl:mi_cl": (u"7ДЛ классика: романтика, тихие встречи, личное доверие, "
               u"простые лагерные будни, музыка как способ понять человека",
               u"Не превращай каждую встречу в концерт и не смешивай "
               u"характерные события других двух маршрутов")
}
PERSONA={
 "mi":(u"Мику",u"внешняя разговорчивость и наблюдательность; может быть серьёзной, "
       u"уязвимой, инициативной и спорить о профессиональной музыке",
       (u"собирает разрозненные мелодии на слух",u"пытается сохранить собственную идею без чужой помощи",
        u"переживает из-за чужой оценки выступления",u"предлагает неожиданную творческую сделку",
        u"спорит о темпе и том, кому принадлежит право принимать решение",
        u"вспоминает то, что обычно не рассказывает",u"ищет момент без зрителей",
        u"пытается понять, почему герой интересуется музыкой")),
 "dv":(u"Алиса",u"дерзость и проверка границ, не путать с бездумной агрессией",
       (u"сомневается в честности обещания",u"испытывает чужую идею на прочность",
        u"репетирует без свидетелей",u"пытается скрыть свою уязвимость")),
 "un":(u"Лена",u"наблюдательность и глубина, тихость не равна пассивности",
       (u"замечает неожиданную деталь",u"раздумывает о чужом секрете",
        u"предлагает сделать трудный выбор",u"проверяет, услышат ли её")),
 "sl":(u"Славя",u"ответственность и собственные желания, не своди к образу помощницы",
       (u"устала решать всё за остальных",u"сомневается в правилах",
        u"организует инициативу без вожатой",u"пытается научиться говорить нет")),
 "mz":(u"Женя",u"резкость, книги, чувство личного пространства и острый юмор",
       (u"находит странную пометку в каталоге",u"отказывается соглашаться с догадкой",
        u"проверяет память собеседника",u"неожиданно предлагает помощь")),
 "mt":(u"Ольга Дмитриевна",u"вожатая, усталость и ответственность за безопасность",
       (u"срывается расписание",u"нужно вмешаться в спор старших",
        u"сомневается, стоит ли доверить подросткам инициативу")),
 "cs":(u"Виола",u"взрослый медработник; юмор, профессионализм, уважение границ",
       (u"встречает неожиданную просьбу",u"пытается остановить нелепый слух",
        u"расспрашивает о привычках отдыха")),
 "us":(u"Ульяна",u"энергия и детские шалости, никакой сексуализации",
       (u"спорит о справедливых правилах",u"устраивает невинный розыгрыш",
        u"просит сохранить безобидный секрет")),
 "el":(u"Электроник",u"весёлый изобретатель со своими страхами и приоритетами",
       (u"спорит о схеме",u"проверяет рискованный проект",
        u"защищает идею перед товарищем")),
 "sh":(u"Шурик",u"погружённость в дело, критическое мышление и живое любопытство",
       (u"получил неожиданный результат",u"сомневается в измерении",
        u"делит работу и ответственность")),
 "uv":(u"Юля",u"редкая таинственная встреча, не обычная соседка по лагерю",
       (u"замечает странный звук ночью",u"связывает два забытых следа"))
}
MOTIVES=(
 u"стремление сохранить независимость",u"напряжение между честностью и заботой",
 u"желание быть услышанным",u"неожиданная дружеская ревность",
 u"срыв давно согласованного плана",u"сомнение в чужом обещании",
 u"спор о пределах допустимого риска",u"желание исправить старую ошибку",
 u"необходимость выбрать, кому довериться",u"потребность оказаться полезным",
 u"попытка не повторить вчерашнюю неудачу",u"столкновение личного и общего интереса",
 u"любопытство, ведущее к неудобному вопросу",u"неожиданная просьба о времени",
 u"разница между публичным образом и личной жизнью",u"отложенный разговор",
 u"подозрение, которое нельзя доказать",u"страх потерять контроль над ситуацией",
 u"жест уважения, который неверно поняли",u"секрет, раскрытый слишком рано"
)
DETAILS=(
 u"незакрытая тетрадь",u"забытый термос",u"неисправная лампа",
 u"случайно услышанная фраза",u"след мокрой обуви",u"письмо без подписи",
 u"список с зачёркнутой фамилией",u"лишний билет на мероприятие",
 u"расписание с исправлениями",u"обрывок мелодии",
 u"чужой значок",u"незаписанное обещание",u"вещь из прошлой смены",
 u"неподписанная фотография",u"песок на полу",u"запах сырой древесины",
 u"неожиданная тишина",u"потерянная закладка",u"пустая коробка",
 u"бумажная схема неизвестного происхождения"
)
TWISTS=(
 u"второй участник понимает всё иначе",u"истинная причина не совпадает с первой догадкой",
 u"времени на решение меньше, чем казалось",u"свидетель просит не называть его",
 u"прежний выбор игрока неожиданно всплывает",u"кто-то предлагает рискованный компромисс",
 u"событие мешает другому важному делу",u"полезное открытие создаёт новую моральную дилемму",
 u"обещанная помощь задерживается",u"внешняя случайность меняет настроение разговора",
 u"неожиданно появляется человек с иной точкой зрения",u"один персонаж меняет прежнюю позицию"
)
MI_7DL={
 "7dl:mi_7dl": (u"личный авторский замысел Мику",u"выступление, за которым скрыта частная история",
                 u"музыкальная идея, не получившая признания",u"разговор о выборе своего пути",
                 u"сложное отношение к вниманию окружающих"),
 "7dl:mi_dj": (u"эксперимент с записью звука",u"спор о стиле и публичном образе",
                u"необычная находка в эфире",u"новая аранжировка",u"желание решить всё самостоятельно"),
 "7dl:mi_cl": (u"обыкновенная прогулка с важным разговором",u"неуверенность перед репетицией",
                u"доверительная история без свидетелей",u"музыка для одного слушателя",
                u"неожиданное чувство к старому знакомому")
}

def _u(value):
    if isinstance(value,bytes):
        return value.decode("utf-8")
    if isinstance(value,text_type):
        return value
    return text_type(value)

def _pick(values, *parts):
    seed=u"|".join([_u(p) for p in parts]).encode("utf-8")
    index=int(hashlib.sha256(seed).hexdigest()[:16],16)%len(values)
    return values[index]

def event_fingerprint(state, kind, who, identity, moment=None):
    parts=[_u(state["id"]),kind,who or "-",_u(identity),_u(state["day"]),
           _u(state.get("source","vanilla"))]
    if moment is not None:
        parts.append(_u(moment))
    return hashlib.sha256(u"|".join(parts).encode("utf-8")).hexdigest()

def context(state, kind, who=None, identity=None, moment=None):
    """Unique, grounded palette. No mutating game state and no random global PRNG."""
    import dg_rpg
    import dg_world
    source=state.get("source","vanilla")
    time=state["slot"] if moment is None else moment
    key=event_fingerprint(state,kind,who,identity or "",time)
    persona=PERSONA.get(who)
    # Shuffle motif/prop/twist choices independently. Keep the actual game
    # state in the brief, so each turn can develop previously established facts.
    motif=_pick(MOTIVES,key,"motive")
    detail=_pick(DETAILS,key,"prop")
    twist=_pick(TWISTS,key,"twist")
    hook=_pick(persona[2],key,"hook") if persona else u"жизнь лагеря требует участия"
    if who=="mi" and source in MI_7DL:
        hook=_pick(MI_7DL[source],key,"mi_route")
    if source == dg_bkrr.SOURCE:
        motif=_pick((u"доверие через совместное дело", u"дружба и чувство меры",
                     u"умение посмеяться над собственной неудачей",
                     u"уважение к чужой инициативе"), key, "bkrr_motive")
        if who == "mi":
            hook=_pick(dg_bkrr.HOOKS, key, "bkrr_hook")
    recent=state.get("journal",[])[-5:]
    recent_decisions=state.get("world",{}).get("decisions",[])[-6:]
    return {
        "scene_id":key, "kind":kind, "hero":copy.deepcopy(state["hero"]),
        "day":state["day"],"slot":time,"time_of_day":dg_rpg.SLOTS[time],
        "place":dg_rpg.PLACE_NAMES[state["place"]],
        "source":source,"route_style":STYLE_PROFILES.get(source,STYLE_PROFILES["vanilla"]),
        "who":who,"persona":(persona[:2] if persona else None),
        "present_people": [(code, name) for code, name in dg_rpg.at_place(state)],
        "relationship":state["affinity"].get(who,0) if who else None,
        "motivation":motif,"physical_detail":detail,"unexpected_twist":twist,
        "character_hook":hook,"recent_journal":copy.deepcopy(recent),
        "recent_decisions":copy.deepcopy(recent_decisions),
        "recent_conversations":copy.deepcopy(state.get("dialogue_history",[])[-4:]),
        "world":copy.deepcopy(state.get("world",{}).get("preparations",{})),
        "social_bonds":copy.deepcopy(state.get("social",{}).get("bonds",{})),
        "long_term_memory":__import__('dg_memory').recall(state, who),
        "npc_agendas":__import__('dg_agents').report(state),
        "housing":__import__("dg_housing").report(state),
        "weather":dg_world.weather(state)[1]
    }

def decorate_event(state,event):
    """Reframe a world event without changing its ID, choices or mechanics."""
    c=context(state,"world",event["npc"],event["id"],0)
    scene=copy.deepcopy(event)
    prefix=(u"На первый взгляд всё началось с привычного лагерного дела, "
            u"но рядом обнаружилась новая подробность: %s. " %
            c["physical_detail"])
    focus=(u"%s %s. За внешним поводом скрывается %s.") % (
           PERSONA[event["npc"]][0],c["character_hook"],c["motivation"])
    tension=u"Неожиданное осложнение: %s. " % c["unexpected_twist"]
    if event["npc"]=="mi" and state.get("source") in MI_7DL:
        focus+=u" Эта ситуация развивается по выбранному профилю Мику 7ДЛ, не смешивая его с остальными ветками. "
    scene["story"]=prefix+focus+u"\n\n"+event["story"]+u"\n\n"+tension
    scene["narrative"]={"motivation":c["motivation"],"detail":c["physical_detail"],
                        "twist":c["unexpected_twist"],"hook":c["character_hook"],
                        "profile":state.get("source","vanilla")}
    return scene

def decorate_outcome(state,event,choice_key,text):
    """Varied epilogue; original mechanically authoritative outcome remains."""
    c=context(state,"world_outcome",event["npc"],event["id"]+":"+choice_key,0)
    who=PERSONA[event["npc"]][0]
    addition=(u"\n\nПосле принятого решения %s не возвращается сразу к привычным "
              u"делам. Её или его беспокоит %s; в разговоре снова появляется "
              u"такая подробность, как %s. Становится заметно, что %s. "
              u"Это повод для следующей встречи, а не готовый исход истории.") % (
             who,c["motivation"],c["physical_detail"],c["unexpected_twist"])
    return text+addition

def decorate_dialogue(state,who,phase,scene,topic_index=0,stance=None):
    c=context(state,"npc_"+phase,who,str(topic_index)+u":"+_u(stance or ""),
              state["slot"]+state.get("dialogue_counts",{}).get(
                  "%d:%s" % (state["day"],who),0)*4)
    updated=copy.deepcopy(scene)
    intro=(u"В разговор вмешивается маленькая деталь: %s. %s "
           u"Сегодня собеседник пытается разобраться с тем, что %s. "
           u"Неожиданный поворот: %s.") % (
           c["physical_detail"],PERSONA[who][0],c["character_hook"],
           c["unexpected_twist"])
    updated["text"]=intro+u"\n\n"+updated["text"]
    updated["narrative"]=c
    return updated

def spontaneous(state,who=None):
    """One freeform encounter at the current location, before any player choice.

    It is safe to present without changing the simulation. A separate action
    in the RPG engine spends time only after the player participates.
    """
    import dg_rpg
    dg_rpg.validate(state)
    if state["finished"]:
        raise ValueError("The camp shift is complete")
    if who is not None:
        if who not in dg_rpg.NPC_NAMES or dg_rpg.where_is(state,who)!=state["place"]:
            raise ValueError("NPC is no longer here")
    count=state.get("surprise_counts",{}).get(
        "%d:%d:%s:%s" % (state["day"],state["slot"],state["place"],who or "-"),0)
    identity="spontaneous:%s:%d" % (who or "place",count)
    c=context(state,"spontaneous",who,identity)
    name=PERSONA[who][0] if who else dg_rpg.PLACE_NAMES[state["place"]]
    if who:
        lead=(u"Случайная встреча с %s. %s %s. " %
              (name,name,c["character_hook"]))
    else:
        lead=(u"На территории «%s» происходит что-то, что не входит в обычный распорядок. " %
              name)
    body=(u"Всё начинается с небольшой подробности: %s. "
          u"За событием скрывается %s. "
          u"Но затем оказывается, что %s. "
          u"Ситуация не решена: герой может выслушать, вмешаться своим действием "
          u"или оставить развитие событий другим.") % (
           c["physical_detail"],c["motivation"],c["unexpected_twist"])
    return {"id":identity,"who":who,"text":lead+body,
            "title":u"Неожиданная встреча" if who else u"Неожиданность в лагере",
            "narrative":c}

def memo(state):
    return state.setdefault("narrative_cache",{})

def read_scene(state,key):
    return state.get("narrative_cache",{}).get(key)

def remember_scene(state,key,text):
    if not isinstance(text,text_type) or not (100<=len(text)<=12000):
        raise ValueError("Generated narration must be 100..12000 characters")
    if not isinstance(key,(str,text_type)) or len(key)!=64:
        raise ValueError("Invalid scene key")
    import re
    if not re.match(r"^[0-9a-f]{64}$",key):
        raise ValueError("Invalid scene key")
    scenes=memo(state)
    scenes[key]={"text":text,"day":state["day"]}
    # Maintain a chronological LRU list; same-day entries must never be
    # evicted according to their hash order.
    order=state.setdefault("narrative_order",[])
    order[:]=[item for item in order if item in scenes and item!=key]
    order.append(key)
    while len(order)>48:
        oldest=order.pop(0)
        if oldest in scenes:
            del scenes[oldest]
    # Migrate old saves which only contain the dictionary.
    if len(scenes)>48:
        for stale in sorted(scenes, key=lambda k:(scenes[k]["day"],k))[:len(scenes)-48]:
            del scenes[stale]
    return text

def request(state,kind,who,identity,source_text,choices=None,moment=None,source_reference=None):
    c=context(state,kind,who,identity,moment)
    brief={
       "anchor_scene":_u(source_text)[:5000],
       "scene_identity":c,"permitted_existing_options":copy.deepcopy(choices or []),
       "source_reference":_u(source_reference or "")[:5800],
       "world_facts_are_locked":True
    }
    rules=(u"Ты пишешь ОРИГИНАЛЬНУЮ сцену визуальной новеллы «Бесконечное лето» "
           u"на русском, 300–650 слов, с живыми репликами, действиями, паузами "
           u"и собственными голосами участников. В каждой сцене используй "
           u"отличающийся конфликт и несколько значимых деталей из scene_identity. "
           u"Избегай штампов вроде «собеседник внимательно посмотрел» и "
           u"повторения текста вчерашнего разговора. "
           u"УЧИТЫВАЙ указанные различия профилей 7ДЛ Мику, не перемешивай "
           u"маршруты mi_7dl, mi_dj, mi_cl. "
           u"Если предоставлен исходный контекст 7ДЛ, используй только "
           u"факты и характер, НЕ цитируй и не пересказывай близко оригинальные реплики. "
           u"Важно: локальный движок уже закрепил персонажей, локацию, время, "
           u"события прошлого и возможные варианты выбора. "
           u"НЕ придумывай завершённые действия игрока, последствия, очки отношений, "
           u"новые квесты, награды, дополнительные варианты меню и не переписывай "
           u"известный игровой мир. Остановись непосредственно перед выбором "
           u"или после зафиксированного исхода. Не перемещай героев в новое место "
           u"без разрешения. Верни только повествовательный текст без Markdown.")
    return rules,json.dumps(brief,ensure_ascii=False,sort_keys=True)

