# -*- coding: utf-8 -*-
"""DON-GEN social simulation: free-form intent commands, NPC arcs, quests, and social ties.

Pure Python 2.7/3, no Ren'Py and no network. Commands use a transparent
intent classifier, not an LLM; unrecognized requests never silently succeed.
"""
from __future__ import unicode_literals
import re
import dg_world

NAMES = {
    "mi": u"Мику", "dv": u"Алиса", "un": u"Лена", "sl": u"Славя",
    "us": u"Ульяна", "sh": u"Шурик", "el": u"Электроник",
    "mz": u"Женя", "mt": u"Ольга Дмитриевна", "cs": u"Виола",
    "uv": u"Юля"
}
# Match inflected names as whole words, not arbitrary words sharing a prefix.
TARGET_PATTERNS = {
    "mi": u"мику", "dv": u"алис(?:а|ы|е|у|ой|ою)",
    "un": u"лен(?:а|ы|е|у|ой|ою)", "sl": u"слав(?:я|и|е|ю|ей|ею)",
    "us": u"ульян(?:а|ы|е|у|ой|ою)", "sh": u"шурик(?:а|у|ом|е)?",
    "el": u"электроник(?:а|у|ом|е)?", "mz": u"жен(?:я|и|е|ю|ей|ею)",
    "mt": u"(?:ольг(?:а|и|е|у|ой|ою)|вожат(?:ая|ой|ую))",
    "cs": u"виол(?:а|ы|е|у|ой|ою)", "uv": u"юл(?:я|и|е|ю|ей|ею)"
}
VERBS = (
    ("mediate", (u"помир",u"договор",u"примир",u"обсуд",u"уговор",u"поговор",u"разговор",u"подруж")),
    ("create", (u"почин",u"собра",u"сдела",u"созда",u"постро",u"написа",u"организ",u"придум",u"подготов",u"отрепетир")),
    ("help", (u"помог",u"помоч",u"помощ",u"подсоб",u"поддерж",u"выручи",u"убра",u"убор",u"отнес",u"отнести")),
    ("search", (u"изуч",u"осмотр",u"исслед",u"провери",u"найти",u"поиск",u"искать",u"расслед",u"узна")),
    ("practice", (u"трениров",u"репетир",u"потренир",u"упражн",u"учить",u"науч",u"занят")),
    ("rest", (u"отдох",u"отдых",u"поспа",u"вздрем",u"прилеч"))
)
ACTION_LABELS = {"mediate":u"переговоры", "create":u"новое дело", "help":u"помощь",
                 "search":u"исследование", "practice":u"тренировка", "rest":u"отдых"}
ACTION_STATS = {"mediate":"kindness","create":"skill","help":"kindness",
                "search":"curiosity","practice":"skill","rest":None}
PAIR_DEFS = (
    ("mi", "dv", -12, u"Мику и Алиса", u"Мику предлагает совместную репетицию, но Алисе не нравятся правила. Их разговор слышат у сцены."),
    ("el", "sh", 35, u"Шурик и Электроник", u"Шурик и Электроник спорят над схемой: один хочет проверить теорию, другой — собрать работающий прототип."),
    ("sl", "mt", 28, u"Славя и Ольга Дмитриевна", u"Славя обсуждает с вожатой распределение дел. Спор идёт о том, кому нужна помощь."),
    ("un", "dv", -5, u"Лена и Алиса", u"Алиса и Лена никак не решат, стоит ли рассказывать остальным об их старой договорённости."),
    ("us", "sl", 8, u"Ульяна и Славя", u"Ульяна спорит со Славей о правилах игры; ребята собираются вокруг."),
    ("mz", "mi", 7, u"Женя и Мику", u"Мику принесла в библиотеку ноты, и Женя хочет аккуратно их каталогизировать."),
    ("cs", "mt", 20, u"Виола и Ольга Дмитриевна", u"Виола напоминает вожатой, что даже ответственным ребятам необходим отдых."),
    ("uv", "un", 13, u"Юля и Лена", u"Юля задаёт Лене неожиданный вопрос о тропинке возле озера.")
)

# Three personal chapters for every NPC, with relationship gates.
PERSONAL = {
    "mi": ((u"Неоконченная песня",u"Мику прячет лист с мелодией: она боится, что никто не воспримет её собственную музыку всерьёз."),
           (u"Репетиция вдвоём",u"Мику признаётся, что с кем-то рядом легче играть, но страшнее ошибаться. Нужно решить, как проводить репетицию."),
           (u"Свой голос",u"Мику готова впервые исполнить собственную вещь перед другими. Она спрашивает, какой риск ты готов разделить с ней.")),
    "dv": ((u"Тайный аккорд",u"Алиса не хочет объяснять, почему старая песня так много для неё значит. С ней можно говорить без давления."),
           (u"Ссора у сцены",u"Алиса спорит с Мику, но за резкими словами скрывается страх проиграть."),
           (u"Без маски",u"Алиса просит высказать мнение о её музыке без привычных шуток и поддевок.")),
    "un": ((u"Рисунок у озера",u"Лена держит при себе незаконченный альбом; один рисунок явно связан с лагерем."),
           (u"Доверить секрет",u"Лена хочет рассказать о найденной записке, но не уверена, что ты умеешь хранить чужие тайны."),
           (u"Разговор без страха",u"Лена предлагает вместе закончить рисунок, который долго не решалась показывать.")),
    "sl": ((u"Слишком много дел",u"Славя скрывает усталость за улыбкой: на неё опять легла половина лагерных обязанностей."),
           (u"Собственное решение",u"Славе впервые предлагают отказаться от поручения. Она не знает, как это сделать без чувства вины."),
           (u"День для себя",u"Славя решается выделить время для собственных желаний. Ты можешь поддержать этот выбор.")),
    "us": ((u"Не просто шалость",u"Ульяна придумывает новую игру, но остальные считают её очередной проделкой."),
           (u"Честный спор",u"Ульяна хочет выиграть соревнование без поблажек. Ей важнее уважение, чем приз."),
           (u"Ответственность",u"Ульяне доверяют важное поручение, и она не хочет всех подвести.")),
    "sh": ((u"Гипотеза",u"Шурик из-за ошибки в схеме сомневается, способен ли вообще довести свой проект до конца."),
           (u"Цена эксперимента",u"Новый опыт может повредить оборудование, но обещает важное открытие."),
           (u"Готовый прибор",u"Шурик может показать результат всем или оставить работу закрытой.")),
    "el": ((u"Мастерская для всех",u"Электроник хочет, чтобы клубы были интересны не только тем, кто уже разбирается в технике."),
           (u"Друг или соперник",u"Между Электроником и Шуриком возник спор о приоритете новой идеи."),
           (u"Общее изобретение",u"Электроник готов отказаться от личной славы ради командной работы.")),
    "mz": ((u"Забытый сборник",u"Женя нашла книгу без карточки и подозревает, что она связана с прошлой сменой."),
           (u"Доверить архив",u"Женя просит тебя самостоятельно разобраться с несколькими ценными записями."),
           (u"Книга с продолжением",u"Женя хочет сохранить новую историю лагеря для тех, кто приедет позже.")),
    "mt": ((u"Трудное дежурство",u"Ольга Дмитриевна должна решить, как быть с конфликтом внутри отряда."),
           (u"Цена ответственности",u"Вожатая впервые спрашивает твоё мнение о том, как дать ребятам больше свободы."),
           (u"Лагерь завтра",u"Ольга Дмитриевна собирает предложения, которые могут изменить следующую смену.")),
    "cs": ((u"Забота без приказа",u"Виола знает, что многие пионеры стесняются рассказывать о своих трудностях."),
           (u"Неочевидная помощь",u"Виола просит придумать, как вовлечь отряд в заботу друг о друге."),
           (u"Выслушать взрослого",u"Виола делится своей усталостью от нескончаемых забот и впервые ждёт ответа.")),
    "uv": ((u"Лесной знак",u"Юля показывает необычный знак на старом дереве и спрашивает, что он может означать."),
           (u"Обещание у тропы",u"Юля просит никому не рассказывать о месте, которое она нашла."),
           (u"Тайна или дружба",u"Юля готова доверить тебе часть загадки Совёнка, если ты не станешь требовать полного ответа."))
}
GATES = (6, 20, 38)
ANSWERS = (("support",u"Поддержать и разделить ответственность"),
           ("question",u"Задать трудный вопрос и разобраться в причинах"),
           ("initiative",u"Предложить собственный, смелый выход"))

# Quest is accepted explicitly and advanced by the *same* free-form action system.
QUESTS = {
    "rehearsal": (u"Подготовить выступление Мику", "mi", "festival", 9,
                  (("clubs","help",u"Помочь Мику с репетицией в клубах"),
                   ("stage","search",u"Проверить оборудование сцены"),
                   ("stage","create",u"Организовать концертную площадку"))),
    "archive": (u"Восстановить старые записи", "mz", "radio", 11,
                (("library","search",u"Исследовать записи библиотеки"),
                 ("clubs","create",u"Собрать устройство для чтения записей"),
                 ("lake","search",u"Найти недостающую подсказку у озера"))),
    "shore": (u"Помочь исследовать тропу", "un", "lake", 8,
              (("lake","search",u"Изучить берег озера"),
               ("forest","help",u"Помочь расчистить безопасный путь"),
               ("lake","mediate",u"Договориться о правилах прогулки"))),
    "team": (u"Собрать команду отряда", "sl", "council", 10,
             (("square","mediate",u"Обсудить задачи на площади"),
              ("canteen","help",u"Помочь на дежурстве в столовой"),
              ("sports","create",u"Организовать общую игру"))),
}


# Steps require place + action TYPE + contextual words; generic "Помочь" is not enough.
QUEST_HINTS = {
    "rehearsal": ((u"репет",u"музык",u"мику"),(u"оборуд",u"сцен",u"свет",u"аппарат"),(u"концерт",u"сцен",u"площад")),
    "archive": ((u"запис",u"архив",u"книг"),(u"устрой",u"прибор",u"запис"),(u"подсказ",u"озер",u"след")),
    "shore": ((u"берег",u"озер",u"троп"),(u"путь",u"расчист",u"троп"),(u"прогул",u"правил",u"троп")),
    "team": ((u"задач",u"отряд",u"дежур"),(u"дежур",u"обед",u"столов"),(u"игр",u"соревн",u"спорт"))
}


def _pair(a, b):
    return ":".join(sorted((a, b)))


def ensure(state):
    social = state.setdefault("social", {})
    bonds = social.setdefault("bonds", {})
    for a, b, score, title, description in PAIR_DEFS:
        bonds.setdefault(_pair(a, b), score)
    social.setdefault("personal", {})
    social.setdefault("personal_choices", {})
    social.setdefault("quests", {})
    social.setdefault("actions", [])
    social.setdefault("last_interactions", [])
    social.setdefault("daily_seen", [])
    social.setdefault("rumours", [])
    social.setdefault("last_day_processed", state["day"])
    social.setdefault("incident", None)
    return social


def clamp(score):
    return 0 if score < 0 else 100 if score > 100 else score


def bond(state, a, b):
    return ensure(state)["bonds"].get(_pair(a, b), 0)


def personal_scene(state, who):
    social = ensure(state)
    if who not in PERSONAL or state.get("finished"):
        return None
    if who == "uv" and not state.get("mystery", {}).get("yulia_discovered", False):
        return None
    stage = social["personal"].get(who, 0)
    if stage >= 3 or state["affinity"].get(who, 0) < GATES[stage]:
        return None
    chapter = PERSONAL[who][stage]
    history = social["personal_choices"].get(who, [])
    memory = u""
    if history:
        previous = history[-1]
        memory = {
            "support":u"После предыдущей встречи герой помнит, что ты предпочёл поддержать собеседника. Теперь ему легче попросить тебя о помощи.",
            "question":u"Твои прежние прямые вопросы заставили собеседника переосмыслить свои мотивы. Сегодня прежний разговор получает продолжение.",
            "initiative":u"О твоём неожиданном предложении ещё вспоминают в лагере. Собеседник хочет понять, готов ли ты снова рискнуть."
        }[previous]
    social_bonds = social["bonds"]
    if who in ("mi","dv") and social_bonds.get(_pair("mi","dv"),0)<-10:
        memory += u" Отношения Мику и Алисы сейчас напряжённые, и это влияет на их решения."
    if who in ("sh","el") and social_bonds.get(_pair("sh","el"),0)>=45:
        memory += u" Шурик и Электроник уже научились лучше понимать друг друга; теперь они обсуждают общие решения."
    if state["world"]["morale"]<30:
        memory += u" Неудачи последних дней сделали настроение лагеря тревожнее."
    return {"npc":who,"stage":stage,"title":chapter[0],
            "text":chapter[1]+(u"\n\n"+memory if memory else u""),
            "choices":ANSWERS,"affinity":state["affinity"][who]}


def resolve_personal(state, who, approach):
    scene = personal_scene(state, who)
    if scene is None or approach not in dict(ANSWERS):
        raise ValueError("No personal scene or unsupported approach")
    if state["energy"] < 12:
        raise ValueError("Not enough energy")
    social = ensure(state)
    state["energy"] -= 12
    stage = scene["stage"]
    social["personal"][who] = stage + 1
    social["personal_choices"].setdefault(who, []).append(approach)
    scores = {"support":(8,"kindness"),"question":(5,"curiosity"),"initiative":(4,"skill")}
    reward, stat = scores[approach]
    state["stats"][stat] += 2
    state["affinity"][who] = clamp(state["affinity"][who] + reward)
    world = dg_world.ensure(state)
    if approach == "support":
        world["morale"] = clamp(world["morale"] + 2)
    elif approach == "question":
        world["knowledge"] = clamp(world["knowledge"] + 3)
    else:
        world["freedom"] = clamp(world["freedom"] + 3)
    arc = {"mi":"festival","dv":"festival","sh":"radio","el":"radio","mz":"radio",
           "un":"lake","uv":"lake","sl":"council","mt":"council","us":"council","cs":"council"}[who]
    prep = world.setdefault("preparations",{})
    prep[arc] = clamp(prep.get(arc, 0) + 6)
    consequence = (
        u"Вы выслушали друг друга и вместе придумали следующий шаг." if approach == "support" else
        u"Ты заметил важную деталь. Собеседник не сразу согласился, но разговор открыл новое направление." if approach == "question" else
        u"Вы решили попробовать непривычный вариант. Он потребует смелости и не всем понравится."
    )
    if stage == 2:
        consequence += u" Личная история завершена; это решение останется в памяти персонажа."
    result = {"who":who,"stage":stage+1,"title":scene["title"],
              "text":scene["text"] + u"\n\n" + consequence,
              "affinity_gain":reward,"approach":approach}
    social["last_interactions"].append({"day":state["day"],"who":who,"kind":"personal",
                                         "title":scene["title"],"text":result["text"]})
    social["last_interactions"] = social["last_interactions"][-80:]
    dg_world.refresh_open_event(state)
    return result


def quest_list(state):
    social = ensure(state)
    rows = []
    for ident in ("rehearsal","archive","shore","team"):
        title, who, arc, limit, steps = QUESTS[ident]
        record = social["quests"].get(ident, {})
        index = record.get("step", 0)
        status = record.get("status", "available")
        rows.append({"id":ident,"title":title,"who":who,"arc":arc,"status":status,
                     "step":index,"total":len(steps),
                     "task":steps[index][2] if index < len(steps) else u"Всё сделано",
                     "deadline":record.get("deadline"),"limit":limit})
    return rows


def accept(state, ident):
    social = ensure(state)
    if ident not in QUESTS or state.get("finished"):
        raise ValueError("Unknown quest")
    existing = social["quests"].get(ident)
    if existing:
        raise ValueError("Quest already accepted or resolved")
    title, who, arc, limit, steps = QUESTS[ident]
    social["quests"][ident] = {"status":"active", "step":0, "started":state["day"],
                               "deadline":min(state["duration"], state["day"]+limit)}
    return u"Задание принято: %s. Первый шаг: %s." % (title, steps[0][2])


def quest_steps(state, place, action, description):
    social = ensure(state)
    feedback = []
    for ident, record in social["quests"].items():
        if record["status"] != "active":
            continue
        title, who, arc, limit, steps = QUESTS[ident]
        index = record["step"]
        if index >= len(steps):
            continue
        needed_place, needed_action, objective = steps[index]
        if place != needed_place or action != needed_action:
            continue
        if not any(keyword in description.lower() for keyword in QUEST_HINTS[ident][index]):
            continue
        record["step"] += 1
        if record["step"] == len(steps):
            record["status"] = "completed"
            state["affinity"][who] = clamp(state["affinity"][who] + 8)
            state["stats"]["kindness"] += 3
            world = dg_world.ensure(state)
            world["resources"] = clamp(world["resources"] + 7)
            prep = world.setdefault("preparations", {})
            prep[arc] = clamp(prep.get(arc, 0) + 15)
            feedback.append(u"Задание завершено: %s. Награда: отношения +8, доброта +3, ресурсы +7." % title)
        else:
            feedback.append(u"Шаг выполнен: %s. Дальше: %s." % (title, steps[record["step"]][2]))
    return feedback


def npc_daily(state):
    """Run ONCE for each crossed day, never on screen redraw."""
    social = ensure(state)
    day = state["day"]
    if day in social["daily_seen"]:
        return None
    # A deterministic pair interacts without waiting for the player.
    index = (day + int(state["id"][:4], 16)) % len(PAIR_DEFS)
    if "uv" in PAIR_DEFS[index][:2]:
        index = (index + 1) % len(PAIR_DEFS)
    a,b,baseline,title,story = PAIR_DEFS[index]
    key = _pair(a,b)
    old = social["bonds"][key]
    is_tense = old < 0
    change = -2 if is_tense and day % 3 == 0 else 2
    new = max(-100, min(100, old + change))
    social["bonds"][key] = new
    dg_world.ensure(state)["morale"] = clamp(state["world"]["morale"] + (-1 if change < 0 else 1))
    report = u"За твоими делами продолжается жизнь лагеря. %s %s Отношения между ними: %s%d." % (
        title, story, u"+" if new > 0 else u"", new)
    social["rumours"].append({"day":day,"a":a,"b":b,"text":report,"delta":change})
    social["rumours"] = social["rumours"][-90:]
    social["daily_seen"].append(day)
    social["daily_seen"] = social["daily_seen"][-130:]
    return report


def expire_quests(state):
    social = ensure(state)
    notes = []
    for ident, record in social["quests"].items():
        if record["status"] == "active" and state["day"] > record["deadline"]:
            record["status"] = "failed"
            title, who, arc, limit, steps = QUESTS[ident]
            dg_world.ensure(state)["morale"] = clamp(state["world"]["morale"] - 3)
            notes.append(u"Срок поручения истёк: %s. Другие ребята продолжат без тебя." % title)
    return notes


def parse(text):
    """Transparent intent recognition; no implicit LLM and no silent guess."""
    if not isinstance(text, type(u"")):
        try:
            text = text.decode("utf-8")
        except (AttributeError, UnicodeError):
            return None
    text = text.strip()[:4000]
    if len(text) < 5:
        return None
    lowered = text.lower()
    # Explicit refusal should not accidentally count as performing the action.
    if re.search(u"(?<!\\w)не\\s+(?:хочу|буду|стану|могу)\\b", lowered, re.UNICODE):
        return None
    selected = None
    earliest = len(lowered) + 1
    # Choose the FIRST actual action verb, not the first category in a fixed list.
    # "Помочь организаторам" means help, not "organize" due to the noun.
    for key, stems in VERBS:
        for stem in stems:
            match = re.search(r"(?<!\w)" + re.escape(stem), lowered, re.UNICODE)
            if match is not None and match.start() < earliest:
                # A directly negated verb is a refusal, not a performed act.
                # Be conservative with compound refusals rather than rewarding them.
                if re.search(u"(?<!\\w)не\\s+$", lowered[:match.start()], re.UNICODE):
                    return None
                selected = key
                earliest = match.start()
    if selected is None:
        return None
    targets = [who for who, pattern in TARGET_PATTERNS.items()
               if re.search(r"(?<!\w)(?:" + pattern + r")(?!\w)", lowered, re.UNICODE)]
    if len(targets) > 1:
        targets = sorted(targets)
    # Do not pretend an unknown *named* interlocutor is a known camp NPC.
    # Generic "с ребятами" remains valid, but "с Марсианами" will not.
    if not targets and selected == "mediate" and re.search(
            u"(?<!\\w)[сС]\\s+([А-ЯЁ][а-яёА-ЯЁ-]+)", text, re.UNICODE):
        return None
    return {"intent":selected,"target":targets[0] if len(targets)==1 else None,
            "ambiguous":len(targets)>1,"original":text}


def _prepared_arc(state, intent, target):
    place = state["place"]
    if target in ("mi","dv") or place == "stage":return "festival"
    if target in ("el","sh","mz") or place in ("library","clubs"):return "radio"
    if target in ("un","uv") or place in ("lake","forest","beach"):return "lake"
    return "council"


def action(state, text, nearby):
    """Validate, then mutate; returns None if command is unrecognized/ambiguous.

    Caller must advance time ONCE only when status is 'done'.
    """
    parsed = parse(text)
    if parsed is None:
        return {"status":"unknown","text":u"Не понял действие. Попробуй описать, что ты хочешь сделать: помочь, исследовать, организовать, договориться, потренироваться или отдохнуть. Время не потрачено."}
    if parsed["ambiguous"]:
        return {"status":"unknown","text":u"Указано несколько персонажей. Пока действие адресуется одному собеседнику; уточни, кому хочешь помочь. Время не потрачено."}
    intent,target = parsed["intent"],parsed["target"]
    if target and target not in nearby:
        return {"status":"unknown","text":u"Сейчас %s нет рядом. Посмотри карту или выбери другое действие. Время не потрачено." % NAMES[target]}
    cost = 0 if intent=="rest" else 10
    if state["energy"] < cost:
        return {"status":"unknown","text":u"Для этого действия нужно хотя бы 10 энергии. Отдохни. Время не потрачено."}
    import dg_rpg
    place = state["place"]
    location = dg_rpg.PLACE_NAMES[place]
    social=ensure(state)
    world=dg_world.ensure(state)
    state["energy"]=min(100,state["energy"]+35) if intent=="rest" else state["energy"]-cost
    arc=_prepared_arc(state,intent,target)
    world.setdefault("preparations",{})
    counter_key="%d:%s:%s:%s" % (state["day"],state["place"],intent,target or "-")
    seen=len([a for a in social["actions"] if a["key"]==counter_key])
    impact=0 if intent=="rest" else (4 if seen==0 else 0)
    world["preparations"][arc]=clamp(world["preparations"].get(arc,0)+impact)
    if impact and intent in ("mediate","help"):
        world["morale"]=clamp(world["morale"]+2)
    elif impact and intent=="search":
        world["knowledge"]=clamp(world["knowledge"]+2)
    elif impact and intent=="create":
        world["resources"]=clamp(world["resources"]+2)
    elif impact and intent=="practice":
        world["freedom"]=clamp(world["freedom"]+2)
    if intent!="rest":
        state["stats"][ACTION_STATS[intent]]+=1 if impact else 0
    if target and impact:
        state["affinity"][target]=clamp(state["affinity"][target]+3)
    if intent=="mediate" and impact:
        pairs=[(a,b) for a,b,value,title,story in PAIR_DEFS if a==target or b==target] if target else []
        if not pairs:
            # Free mediation at a place influences an actual local incident,
            # rather than mysteriously changing Miku/Alice from anywhere.
            active=incident_at(state,state["place"])
            if active:
                pairs=[tuple(active["pair"])]
        if pairs:
            a,b=pairs[0]
            social["bonds"][_pair(a,b)]=max(-100,min(100,social["bonds"][_pair(a,b)]+7))
    person=u" вместе с "+NAMES[target] if target else u""
    if intent=="rest":
        narration=u"Ты находишь спокойное место: %s и немного восстанавливаешь силы. Лагерь тем временем продолжает жить своей жизнью." % location
    else:
        narration=(u"Место действия: %s. Здесь ты берёшься за дело%s. Ты описал своё намерение так: «%s». "
                   u"Поступок меняет подготовку к следующему лагерному событию%s.") % (
                   location,person,parsed["original"],
                   u" (+%d)" % impact if impact else u", но повторение уже не даёт награды")
    notes=quest_steps(state,place,intent,parsed["original"])
    if notes:
        narration+=u"\n\n"+u"\n".join(notes)
    dg_world.refresh_open_event(state)
    social["actions"].append({"day":state["day"],"slot":state["slot"],"key":counter_key,
                              "intent":intent,"target":target,"place":place,
                              "text":parsed["original"],"impact":impact})
    social["actions"]=social["actions"][-80:]
    return {"status":"done","text":narration,"intent":intent,"target":target,
            "quest_updates":notes,"arc":arc,"impact":impact}




# Simultaneous, observable NPC-vs-NPC situations. An incident affects
# where both characters are currently visible on the camp map.
INCIDENT_PLACES=("stage","clubs","square","library","sports",
                 "library","infirmary","lake")
INCIDENT_CHOICES=(
    ("mediate",u"Выслушать обоих и помочь договориться"),
    ("support_a",u"Поддержать первого участника"),
    ("support_b",u"Поддержать второго участника")
)


def prepare_incident(state):
    social=ensure(state)
    current=social.get("incident")
    if state.get("finished"):
        return None
    if current is None or current["day"]!=state["day"]:
        index=(state["day"]+int(state["id"][4:8],16))%len(PAIR_DEFS)
        if "uv" in PAIR_DEFS[index][:2]:
            index=(index+1)%len(PAIR_DEFS)
        a,b,score,title,description=PAIR_DEFS[index]
        social["incident"]={"day":state["day"],"pair":[a,b],
                            "place":INCIDENT_PLACES[index],"title":title,
                            "text":description,"status":"open"}
    return social["incident"]


def incident(state):
    current=ensure(state).get("incident")
    return current if current and current["day"]==state["day"] and current["status"]=="open" and not state.get("finished") else None


def incident_at(state, place):
    current=incident(state)
    return current if current and current["place"]==place else None


def resolve_incident(state, choice):
    current=incident_at(state, state["place"])
    if not current or choice not in dict(INCIDENT_CHOICES):
        raise ValueError("No encounter or unsupported choice")
    if state["energy"]<9:
        raise ValueError("Not enough energy")
    social=ensure(state)
    world=dg_world.ensure(state)
    a,b=current["pair"]
    key=_pair(a,b)
    state["energy"]-=9
    if choice=="mediate":
        bond_gain=10
        world["morale"]=clamp(world["morale"]+4)
        state["stats"]["kindness"]+=2
        state["affinity"][a]=clamp(state["affinity"][a]+4)
        state["affinity"][b]=clamp(state["affinity"][b]+4)
        outcome=u"Ты даёшь каждому высказаться и находишь общее решение. Они не обязаны стать лучшими друзьями, но теперь способны работать вместе."
    else:
        preferred=a if choice=="support_a" else b
        other=b if preferred==a else a
        bond_gain=-5
        state["affinity"][preferred]=clamp(state["affinity"][preferred]+7)
        state["affinity"][other]=clamp(state["affinity"][other]-2)
        world["freedom"]=clamp(world["freedom"]+2)
        outcome=u"Ты открыто поддерживаешь %s. %s благодарит тебя, а %s чувствует себя оставленным без поддержки. Этот спор ещё даст о себе знать." % (
            NAMES[preferred], NAMES[preferred], NAMES[other])
    social["bonds"][key]=max(-100,min(100,social["bonds"][key]+bond_gain))
    current["status"]="resolved"
    current["choice"]=choice
    current["bond_delta"]=bond_gain
    arc="festival" if _pair(a,b)==_pair("dv","mi") else "radio" if _pair(a,b)==_pair("el","sh") else "council"
    preps=world.setdefault("preparations",{})
    preps[arc]=clamp(preps.get(arc,0)+4)
    dg_world.refresh_open_event(state)
    narrative=u"%s\n\n%s\n\nОтношения между персонажами: %+d, теперь %+d." % (
        current["text"],outcome,bond_gain,social["bonds"][key])
    social["rumours"].append({"day":state["day"],"a":a,"b":b,
                             "text":narrative,"delta":bond_gain})
    social["rumours"]=social["rumours"][-90:]
    return {"title":current["title"],"text":narrative,"pair":current["pair"],"delta":bond_gain}


def missed_incident(state):
    current=incident(state)
    if not current:
        return None
    social=ensure(state)
    a,b=current["pair"]
    key=_pair(a,b)
    delta = -3 if social["bonds"][key]<0 else 1
    social["bonds"][key]=max(-100,min(100,social["bonds"][key]+delta))
    current["status"]="missed"
    text=u"Пока ты был занят, %s и %s решили вопрос самостоятельно. Ты не повлиял на их спор; их отношения изменились на %+d." % (
        NAMES[a],NAMES[b],delta)
    social["rumours"].append({"day":state["day"],"a":a,"b":b,"text":text,"delta":delta})
    social["rumours"]=social["rumours"][-90:]
    return text


def quest_at(state, place):
    return [entry for entry in quest_list(state)
            if entry["status"]=="active" and
            QUESTS[entry["id"]][4][entry["step"]][0]==place]


def report(state):
    social=ensure(state)
    return {"bonds":[{"a":a,"b":b,"title":title,
                       "score":bond(state,a,b)} for a,b,value,title,desc in PAIR_DEFS
                      if state.get("mystery",{}).get("yulia_discovered") or "uv" not in (a,b)],
            "personal":social["personal"],
            "quests":quest_list(state),
            "rumours":social["rumours"][-8:],
            "recent_actions":social["actions"][-8:]}

