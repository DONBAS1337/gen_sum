# -*- coding: utf-8 -*-
"""DON-GEN world director. Pure Python 2.7/3, deterministic, offline.

Four persistent, branching storylines + context-driven daily interludes.
One opportunity per game day. Missing an opportunity has a consequence.
The world reacts to earlier choices, hero skills, NPC relations, and other arcs.
"""
from __future__ import unicode_literals

import hashlib

PLOT_ORDER = ("festival", "radio", "lake", "council")
PLOTS = {
    "festival": {
        "name": u"Фестиваль Совёнка", "place": "stage", "npc": "mi",
        "chapters": (
            (u"Заявка на концерт", u"Мику показывает список номеров. Заведующий клубами сомневается, что ребята успеют подготовиться. Ей нужна не похвала, а решение, с чего начинать.",
             u"Вы собираете команду для первой репетиции.",
             u"Ты разбираешься с расписанием и находишь свободные часы.",
             u"Ты предлагаешь независимый камерный концерт вместо общего смотра."),
            (u"Неожиданный соперник", u"Алиса заявляет, что музыка должна быть живой, а не составленной по отчётам. Мику растеряна. Концерт рискует превратиться в соревнование.",
             u"Ты предлагаешь Мику и Алисе сыграть вместе.",
             u"Ты находишь способ объединить два стиля в программе.",
             u"Ты позволяешь Алисе выступить отдельно, чтобы не раздувать конфликт."),
            (u"Пропавшие ноты", u"Перед репетицией исчезает папка с набросками. В кружке тихо: никто не хочет обвинять другого, но время идёт.",
             u"Вы обходите лагерь и спокойно расспрашиваете ребят.",
             u"Ты проверяешь последние места, где могли остаться записи.",
             u"Ты предлагаешь восстановить музыку по памяти и не зависеть от папки."),
            (u"Генеральная репетиция", u"Сцена готова, но света и времени не хватает. Один неверный выбор испортит сразу несколько номеров.",
             u"Вы отдаёте часть времени младшему отряду и сокращаете программу.",
             u"Ты изучаешь техническую схему и перестраиваешь свет.",
             u"Ты выбираешь рискованную импровизацию вместо точного расписания."),
            (u"Концерт под звёздами", u"Вечер наступил. На сцене собрались те, кто ещё недавно спорил друг с другом. Мику смотрит на тебя, ожидая последнего решения.",
             u"Ты выходишь помогать за кулисами и поддерживаешь всех.",
             u"Ты оставляешь место для неожиданной музыкальной находки.",
             u"Ты даёшь исполнителям полную свободу, принимая риск."),
        )
    },
    "radio": {
        "name": u"Тайна радиокружка", "place": "clubs", "npc": "sh",
        "chapters": (
            (u"Неизвестная частота", u"Шурик поймал странную последовательность сигналов. Электроник утверждает, что это просто помехи, но совпадения слишком регулярны.",
             u"Ты убеждаешь ребят работать вместе и ничего не скрывать.",
             u"Ты записываешь ритм сигнала и ищешь закономерность.",
             u"Ты предлагаешь провести самостоятельный приём ночью."),
            (u"Шифр на полях", u"В библиотечной книге находятся отметки, напоминающие радиосигнал. Женя уверяет, что никогда их раньше не видела.",
             u"Вы бережно собираете свидетельства, не обвиняя библиотекаря.",
             u"Ты сравниваешь пометки с частотами и расписанием.",
             u"Ты оставляешь шифр при себе, чтобы никто не испортил поиски."),
            (u"Старый передатчик", u"Под крышей клуба находится заброшенный прибор. На нём выцарапаны инициалы, совпадающие с записью в книге.",
             u"Ты зовёшь Шурика и Электроника на совместную проверку.",
             u"Ты проверяешь схему и обнаруживаешь отсутствующую деталь.",
             u"Ты решаешь не ждать разрешения и включить передатчик."),
            (u"Помехи перед концертом", u"Неожиданно передатчик начинает мешать оборудованию на сцене. Решение затронет и исследование, и готовящийся концерт.",
             u"Ты выключаешь прибор на время репетиции Мику.",
             u"Ты рассчитываешь безопасную частоту и перестраиваешь настройку.",
             u"Ты продолжаешь эксперимент, надеясь, что помехи исчезнут."),
            (u"Ответ из прошлого", u"Наконец сигнал складывается в короткое сообщение о старой смене. В нём нет готовых ответов, только направление для дальнейших поисков.",
             u"Ты рассказываешь об открытии друзьям и сохраняешь записи.",
             u"Ты сверяешь дату с историей лагеря и пытаешься понять автора.",
             u"Ты оставляешь сообщение тайной, которую ещё предстоит разгадать."),
        )
    },
    "lake": {
        "name": u"Тропа у озера", "place": "lake", "npc": "un",
        "chapters": (
            (u"Следы на берегу", u"Лена показывает рисунок: старая тропа на нём обрывается в неожиданном месте. У берега видны следы, которых вчера не было.",
             u"Ты предлагаешь идти вместе, не торопясь и не рискуя.",
             u"Ты изучаешь рисунок и берег, замечая необычные детали.",
             u"Ты решаешь пройти тропу самостоятельно и доложить остальным."),
            (u"Забытый указатель", u"За деревьями находится старый столб с выцветшим названием. Юля будто знает, что за ним скрывается, но говорит загадками.",
             u"Ты терпеливо выслушиваешь Юлю и Лену.",
             u"Ты сравниваешь название с найденной схемой лагеря.",
             u"Ты идёшь дальше по указателю, пока другие раздумывают."),
            (u"Письмо без адресата", u"В щели между досками лежит записка о чьём-то давнем обещании вернуться к озеру. Ни имени, ни даты нет.",
             u"Ты предлагаешь сохранить записку и вместе найти владельца.",
             u"Ты ищешь совпадения с архивом библиотеки.",
             u"Ты прячешь письмо, решив, что это слишком личная тайна."),
            (u"Разговор у воды", u"Вечером Лена признаётся, что найденное письмо напомнило ей о собственных страхах. Важнее теперь не загадка, а доверие между вами.",
             u"Ты выслушиваешь её без советов и поспешных обещаний.",
             u"Ты делишься своим опытом и осторожно спрашиваешь о будущем.",
             u"Ты меняешь тему, боясь сделать разговор неловким."),
            (u"Открытая тропа", u"У озера собираются несколько пионеров: тропа снова стала доступна. Вопрос в том, что делать с найденной историей.",
             u"Ты предлагаешь сделать общее памятное место, не раскрывая чужих секретов.",
             u"Ты создаёшь небольшой архив находок, доступный всем желающим.",
             u"Ты оставляешь берег нетронутым, сохраняя его тайну."),
        )
    },
    "council": {
        "name": u"Совет отряда", "place": "square", "npc": "sl",
        "chapters": (
            (u"Новый распорядок", u"Славя замечает, что дежурства распределены несправедливо. Одни ребята устали, а другие почти не участвуют в жизни лагеря.",
             u"Ты предлагаешь обсудить обязанности всем отрядом.",
             u"Ты собираешь сведения и составляешь честный график.",
             u"Ты берёшь трудную часть работы на себя, избегая споров."),
            (u"Ссора у столовой", u"Алиса резко спорит с дежурными. Ульяна подливает масла в огонь, а Славя не знает, с кого начать разговор.",
             u"Ты миришь участников и просишь услышать обе стороны.",
             u"Ты выясняешь, как начался спор и чьи слова были поняты неверно.",
             u"Ты поддерживаешь ребят, которые отказались подчиняться правилу."),
            (u"Новый проект", u"Ольга Дмитриевна даёт отряду возможность самому придумать полезное дело для лагеря. Но каждому хочется своего.",
             u"Ты организуешь совместное голосование.",
             u"Ты предлагаешь объединить идеи в один осуществимый проект.",
             u"Ты берёшь на себя руководство самым смелым вариантом."),
            (u"Проверка доверия", u"Часть отряда уверена, что решения принимают за них. Славя опасается, что всё закончится новым скандалом.",
             u"Ты настаиваешь на открытом обсуждении и выслушиваешь недовольных.",
             u"Ты предъявляешь расчёты и показываешь, почему выбран именно этот план.",
             u"Ты отстаиваешь собственное решение, даже если все не согласны."),
            (u"Итоги смены", u"Отряд собирается на площади обсудить, что удалось изменить. Ольга Дмитриевна не вмешивается: теперь это ваш общий результат.",
             u"Ты отдаёшь слово каждому, кто помогал и сомневался.",
             u"Ты подробно рассказываешь, какие решения оказались удачными.",
             u"Ты призываешь продолжать новые дела без официального руководства."),
        )
    }
}

# Used on long shifts after main arcs are complete, and to keep every day fresh.
DAILY_MOTIFS = (
    ("canteen", "sl", u"Неожиданное дежурство", u"У столовой задержался отряд младших. Повару нужна помощь, иначе обед затянется для всех."),
    ("library", "mz", u"Книга с закладкой", u"На полке обнаружилась книга с неожиданной запиской внутри. Женя хочет узнать, что делать с находкой."),
    ("sports", "us", u"Спор на площадке", u"Ульяна затеяла состязание, но правила оказались слишком выгодными одному участнику."),
    ("stage", "dv", u"Музыка без сцены", u"Алиса пробует новую мелодию и не уверена, стоит ли показывать её остальным."),
    ("infirmary", "cs", u"Разговор о заботе", u"В медпункте не хватает помощников, а одному пионеру неловко попросить о помощи."),
    ("forest", "uv", u"Шорох на тропе", u"Юля уверяет, что в лесу появилась новая тропинка. Она ждёт, доверишься ли ты её словам."),
    ("clubs", "el", u"Техническая находка", u"Электроник принёс коробку деталей: некоторые пригодятся для лагеря, но их нужно распределить."),
    ("beach", "un", u"Записка на песке", u"Лена заметила след от старого костра; рядом кто-то оставил несколько строк."),
    ("gate", "mt", u"Гости лагеря", u"У ворот остановились посетители. Ольге Дмитриевне нужно быстро решить, кто встретит их."),
    ("cabins", "mi", u"Репетиция после отбоя", u"Мику ищет тихое место для репетиции. Другим хочется отдохнуть, но ей важно закончить мелодию."),
    ("lake", "sh", u"Тайна отражений", u"Шурик заметил странный блик у озера и считает его подсказкой к старой схеме."),
    ("square", "dv", u"Незапланированное собрание", u"Алиса считает новый план вожатой несправедливым. Славя зовёт всех поговорить."),
    ("library", "mi", u"Песня из книги", u"Мику нашла в старом сборнике слова неизвестной песни и пытается восстановить мелодию."),
    ("forest", "sl", u"Потерянный маршрут", u"Славя ищет удобную дорогу для прогулки младших, но указатели давно выцвели."),
    ("sports", "el", u"Сломанный секундомер", u"Электроник обещал починить секундомер до соревнований. Шурик предлагает рискованный способ."),
    ("beach", "us", u"Уборка пляжа", u"На берегу обнаружился мусор после вчерашнего мероприятия. Спорят, кто должен убирать."),
)


# Same story can produce different endings, but the decisions are situation-specific.
DAILY_CHOICES = (
    (u"Помочь повару, распределив очередь и подносы", u"Выяснить, где застрял дежурный отряд", u"Самому организовать выдачу обеда без ожидания распоряжений"),
    (u"Вместе с Женей найти хозяина записки", u"Сопоставить почерк с архивными книгами", u"Прочесть записку и решить, стоит ли скрыть находку"),
    (u"Предложить справедливые правила для всех участников", u"Восстановить результаты предыдущих забегов", u"Принять вызов Ульяны по её правилам"),
    (u"Поддержать Алису и предложить сыграть для друзей", u"Разобрать мелодию и подсказать переход", u"Устроить неожиданный концерт прямо здесь"),
    (u"Помочь разнести воду и проверить самочувствие ребят", u"Разобраться, откуда появились жалобы", u"Своими силами устроить временный пункт помощи"),
    (u"Идти вместе с Юлей и не нарушать спокойствие леса", u"Отметить ориентиры и выяснить, действительно ли тропа новая", u"Первым проверить незнакомый поворот"),
    (u"Раздать детали кружкам по общему решению", u"Составить точный перечень и сравнить потребности", u"Собрать что-нибудь полезное прямо из доступных деталей"),
    (u"Выслушать Лену и вместе убрать берег", u"Исследовать следы костра и записку", u"Предложить поискать оставленную кем-то историю"),
    (u"Помочь вожатой встретить гостей", u"Уточнить, зачем они приехали и кого ищут", u"Самостоятельно провести для гостей экскурсию"),
    (u"Найти для Мику подходящее тихое помещение", u"Разобраться в расписании клуба и соседних домиков", u"Предложить смелую ночную импровизацию на сцене"),
    (u"Проверить блик вместе с Шуриком", u"Сравнить направление света с его схемой", u"Проверить место с воды, рискуя промокнуть"),
    (u"Созвать ребят на мирное обсуждение", u"Узнать, почему план кажется несправедливым", u"Поддержать инициативу Алисы без согласования"),
    (u"Помочь Мику разобрать старый сборник", u"Сопоставить текст песни с известными мелодиями", u"Создать собственный вариант исполнения"),
    (u"Пройти путь вместе со Славей и поставить указатели", u"Проверить старые схемы и записи маршрутов", u"Самому найти самый короткий обход"),
    (u"Помочь Электронику с бережной починкой", u"Найти причину поломки в механизме", u"Попробовать экспериментальный способ Шурика"),
    (u"Собрать помощников и организовать уборку", u"Разобраться, кто оставил мусор и почему", u"Первым начать работу и увлечь остальных своим примером"),
)

OPTIONS = (
    ("support", u"Сотрудничать и помочь другим", "morale", 5, "kindness", 2, 6),
    ("investigate", u"Разобраться в причинах и найти решение", "knowledge", 5, "curiosity", 2, 4),
    ("independent", u"Действовать самостоятельно и рискнуть", "freedom", 5, "skill", 2, 1),
)

def _seed(*values):
    raw = u"|".join([unicode_value(v) for v in values]).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:12], 16)


def unicode_value(value):
    try:
        return unicode(value)
    except NameError:
        return str(value)



WEATHER = (
    ("sun", u"Ясное утро", u"Солнечный свет лежит на дорожках лагеря."),
    ("sun", u"Тёплый день", u"На площадке шумно, в тени слышны голоса ребят."),
    ("breeze", u"Ветер с озера", u"Ветер шелестит листьями и мешает репетициям под открытым небом."),
    ("rain", u"Летний дождь", u"Внезапный дождь загоняет ребят под крыши, планы на прогулки меняются."),
    ("heat", u"Жара", u"Солнце сильно греет: многие выбирают пляж вместо спортплощадки."),
    ("cloud", u"Облачный день", u"Лагерь на время затихает, но воздух остаётся тёплым."),
    ("sun", u"Спокойное лето", u"После шумного утра лагерь живёт привычной жизнью."),
)


def weather(state):
    return WEATHER[_seed(state["id"], state["day"], "weather") % len(WEATHER)]


def ensure(state):
    world = state.setdefault("world", {})
    for name in ("morale", "knowledge", "freedom", "resources"):
        world.setdefault(name, 50)
    world.setdefault("tracks", {})
    world.setdefault("chronicle", [])
    world.setdefault("resolved", [])
    world.setdefault("closed_days", [])
    world.setdefault("decisions", [])
    world.setdefault("event", None)
    for plot in PLOT_ORDER:
        track = world["tracks"].setdefault(plot, {})
        track.setdefault("stage", 0)
        track.setdefault("choices", [])
    return world


def _branch_context(state, plot):
    world = ensure(state)
    history = world["tracks"][plot]["choices"]
    if not history:
        lead = u"Ничего ещё не предрешено: от первых шагов будет зависеть дальнейшая история."
    elif history[-1] == "support":
        lead = u"Предыдущая помощь объединила ребят, и теперь они охотнее идут навстречу друг другу."
    elif history[-1] == "investigate":
        lead = u"Твои прошлые наблюдения дали новые зацепки, зато не все довольны долгими обсуждениями."
    else:
        lead = u"После твоего смелого решения в лагере появились как сторонники, так и сомневающиеся."
    connections = []
    if plot == "festival" and world["tracks"]["radio"]["stage"] >= 3:
        connections.append(u"Работающий радиоприёмник может повлиять на сценическое оборудование.")
    if plot == "radio" and world["tracks"]["festival"]["stage"] >= 2:
        connections.append(u"На сцене ждут настройки звука, и времени на эксперименты всё меньше.")
    if plot == "lake" and world["tracks"]["council"]["stage"] >= 2:
        connections.append(u"На совете отряда уже обсуждают безопасность прогулок по лесу.")
    if plot == "council" and world["tracks"]["lake"]["stage"] >= 2:
        connections.append(u"Новости о находках у озера дошли до вожатой.")
    if world["morale"] < 32:
        connections.append(u"В лагере растёт раздражение: люди помнят недавние неудачи.")
    if world["knowledge"] > 70:
        connections.append(u"Накопленные знания позволяют заметить детали, которые раньше ускользали.")
    return lead + u" " + u" ".join(connections)


def _arc(state):
    world = ensure(state)
    unfinished = [key for key in PLOT_ORDER if world["tracks"][key]["stage"] < 5]
    if not unfinished:
        return None
    day = int(state["day"])
    offset = _seed(state["id"], "arc") % len(PLOT_ORDER)
    rotated = PLOT_ORDER[offset:] + PLOT_ORDER[:offset]
    return rotated[(day - 1) % len(rotated)] if rotated[(day - 1) % len(rotated)] in unfinished else unfinished[(day - 1) % len(unfinished)]


def make_event(state):
    world = ensure(state)
    day, duration = int(state["day"]), int(state["duration"])
    if day > duration or state.get("finished"):
        return None
    arc = _arc(state)
    if arc is not None:
        plot = PLOTS[arc]
        stage = world["tracks"][arc]["stage"]
        title, lead, yes, understand, risk = plot["chapters"][stage]
        choices = []
        for index, (key, label, metric, metric_gain, stat, stat_gain, affinity) in enumerate(OPTIONS):
            caption = (yes, understand, risk)[index]
            choices.append({"key": key, "text": caption, "metric": metric,
                            "delta": metric_gain, "stat": stat,
                            "stat_gain": stat_gain, "affinity": affinity})
        situation = (u"День %d смены. %s\n\n%s\n\n%s" %
                     (day, lead, _branch_context(state, arc),
                      u"Это решение останется в памяти лагеря; история продолжится с учётом твоего выбора."))
        event = {"id": "%d:%s:%d" % (day, arc, stage), "day": day,
                 "arc": arc, "stage": stage, "place": plot["place"], "npc": plot["npc"],
                 "title": title, "story": situation, "choices": choices}
    else:
        daily_index = _seed(state["id"], day, "daily") % len(DAILY_MOTIFS)
        selected = DAILY_MOTIFS[daily_index]
        place, who, title, lead = selected
        prior = world["decisions"][-1]["stance"] if world["decisions"] else ""
        callback = ({
            "support": u"В прошлый раз ты помогал окружающим. Некоторые пионеры уже рассчитывают на твою помощь.",
            "investigate": u"Твой интерес к деталям замечают окружающие. Не все согласны, что это всегда помогает.",
            "independent": u"О твоём самостоятельном решении помнят до сих пор.",
        }.get(prior, u"Сегодня новый день, и его исход ещё не определён."))
        event = {"id": "%d:daily:%d" % (day, _seed(state["id"], day) % 100000),
                 "day": day, "arc": "daily", "stage": 0,
                 "place": place, "npc": who, "title": title,
                 "story": u"День %d/%d. %s\n\n%s\n\n%s" %
                          (day, duration, lead, callback, _branch_context(state, "council")),
                 "choices": [{"key": key, "text": DAILY_CHOICES[daily_index][index],
                              "metric": metric, "delta": delta, "stat": stat,
                              "stat_gain": gain, "affinity": affinity}
                             for index, (key, label, metric, delta, stat, gain, affinity) in enumerate(OPTIONS)]}
    # Character identity and selected canon profile enter story context, not only a stat sheet.
    hero = state["hero"]
    if day == 1:
        hero_intro = u"Ты — %s, %d лет. Предыстория: %s. Впервые знакомишься с жизнью Совёнка." % (
            hero["name"], hero["age"], hero["background"])
    else:
        hero_intro = u"%s (%d лет) вспоминает, каким непривычным казался лагерь в первый день. %s" % (
            hero["name"], hero["age"], hero["background"])
    if state.get("source", "vanilla").startswith("7dl:"):
        hero_intro += u" В этой смене отношения с Мику развиваются в варианте 7ДЛ."
    event["story"] = hero_intro + u"\n\nПогода: " + weather(state)[1] + u". " + weather(state)[2] + u"\n\n" + event["story"]
    # Player skills unlock a fourth way to resolve world events.
    if state["stats"]["skill"] >= 12 or state["stats"]["curiosity"] >= 12:
        event["choices"].append({"key": "specialist", "text": u"Использовать свои навыки и найти компромисс",
                                  "metric": "resources", "delta": 7, "stat": "skill",
                                  "stat_gain": 1, "affinity": 5})
    return event


def prepare(state):
    world = ensure(state)
    event = world["event"]
    if state.get("finished") or state["day"] in world["closed_days"]:
        world["event"] = None
        return None
    if event is None or event.get("day") != state["day"]:
        world["event"] = make_event(state)
    return world["event"]


def current(state):
    event = prepare(state)
    if event is None:
        return None
    return event


def event_at(state, place):
    active = current(state)
    return active if active and active["place"] == place else None


def choose(state, choice_key):
    world = ensure(state)
    event = current(state)
    if not event or event["place"] != state["place"]:
        raise ValueError("There is no story opportunity at this location")
    if state["energy"] < 8:
        raise ValueError("Too tired for this story encounter")
    choices = [c for c in event["choices"] if c["key"] == choice_key]
    if not choices:
        raise ValueError("Invalid story choice")
    selected = choices[0]
    state["energy"] -= 8
    world[selected["metric"]] = clamp(world[selected["metric"]] + selected["delta"])
    if choice_key == "independent":
        world["morale"] = clamp(world["morale"] - 3)
    if choice_key == "support":
        world["resources"] = clamp(world["resources"] - 2)
    if choice_key == "investigate":
        world["resources"] = clamp(world["resources"] + 1)
    state["stats"][selected["stat"]] += selected["stat_gain"]
    who = event["npc"]
    state["affinity"][who] = clamp(state["affinity"][who] + selected["affinity"])
    arc = event["arc"]
    if arc != "daily":
        track = world["tracks"][arc]
        track["choices"].append(choice_key)
        track["stage"] += 1
    decision = {"day": state["day"], "id": event["id"], "arc": arc,
                "title": event["title"], "stance": choice_key,
                "place": event["place"], "npc": who}
    world["decisions"].append(decision)
    world["decisions"] = world["decisions"][-130:]
    world["resolved"].append(event["id"])
    world["closed_days"].append(state["day"])
    world["closed_days"] = world["closed_days"][-140:]
    world["resolved"] = world["resolved"][-130:]
    world["event"] = None
    conclusion = _conclusion(state, event, choice_key, selected)
    world["chronicle"].append({"day": state["day"], "title": event["title"],
                                "text": conclusion, "arc": arc, "status": "resolved"})
    world["chronicle"] = world["chronicle"][-150:]
    return {"title": event["title"], "text": conclusion,
            "choice": choice_key, "npc": who, "arc": arc}


def _conclusion(state, event, choice, option):
    person = {
        "mi": u"Мику", "sh": u"Шурик", "un": u"Лена", "sl": u"Славя",
        "mz": u"Женя", "us": u"Ульяна", "dv": u"Алиса", "cs": u"Виола",
        "el": u"Электроник", "mt": u"Ольга Дмитриевна", "uv": u"Юля"
    }[event["npc"]]
    passages = {
        "support": u"Ты не оставляешь никого наедине с проблемой. Вместо спора вы вместе находите первый практический шаг. Не всё решается сразу, зато люди уже готовы продолжать. ",
        "investigate": u"Ты не спешишь соглашаться с самым очевидным объяснением. Находится новая деталь, которая меняет отношение ребят к происходящему. Теперь дальнейшие решения придётся принимать с её учётом. ",
        "independent": u"Ты берёшь ответственность на себя. Не всем нравится твой рискованный метод, но событие сдвигается с места, и об этом ещё будут спорить. ",
        "specialist": u"Ты используешь опыт и находишь неожиданное техническое решение. Оно спасает часть ресурсов и оставляет ребятам возможность договориться. "
    }
    if event["arc"] != "daily" and ensure(state)["tracks"][event["arc"]]["stage"] >= 5:
        ending = story_status(state, event["arc"])
        epilogue = u"\n\nЭТАП ЗАВЕРШЁН. " + ending
    else:
        epilogue = u"\n\nСобытие изменило положение дел в Совёнке. Последствия проявятся в следующих эпизодах."
    return (u"%s\n\n%s замечает, что этот разговор отличается от привычных лагерных поручений. " %
            (passages[choice], person) +
            u"Твой выбор: «" + option["text"] + u"». " +
            u"Отношения с " + person + u": +" + unicode_value(option["affinity"]) +
            u", " + {"support": u"сплочённость лагеря", "investigate": u"знания",
                     "independent": u"свобода инициативы", "specialist": u"ресурсы"}[choice] +
            u": +" + unicode_value(option["delta"]) + u"." + epilogue)


def clamp(value):
    return 0 if value < 0 else 100 if value > 100 else value


def missed(state):
    world = ensure(state)
    event = world["event"]
    if not event or event.get("day") != state["day"]:
        return None
    world["morale"] = clamp(world["morale"] - 2)
    world["resources"] = clamp(world["resources"] - 1)
    text = u"День %d: возможность «%s» упущена. Пионеры справились без твоего участия, но сплочённость и ресурсы лагеря немного снизились." % (state["day"], event["title"])
    world["chronicle"].append({"day": state["day"], "title": event["title"],
                                "text": text, "arc": event["arc"], "status": "missed"})
    world["chronicle"] = world["chronicle"][-150:]
    world["event"] = None
    world["closed_days"].append(state["day"])
    world["closed_days"] = world["closed_days"][-140:]
    return text


def story_status(state, arc):
    world = ensure(state)
    track = world["tracks"][arc]
    stage = track["stage"]
    if stage == 0:
        return u"История ещё не начата."
    if stage < 5:
        return u"Этап %d/5. Ранее принято решений: %d." % (stage, len(track["choices"]))
    support = track["choices"].count("support")
    investigate = track["choices"].count("investigate")
    risky = track["choices"].count("independent")
    if support >= 3:
        return u"Завершено: люди собрались вместе, и даже старые разногласия стали поводом для сотрудничества."
    if investigate >= 3:
        return u"Завершено: разгаданы важные детали; решение получилось осторожным, но прочным."
    if risky >= 3:
        return u"Завершено: выбран дерзкий путь, который часть лагеря запомнит как победу, а часть — как спорный риск."
    return u"Завершено: компромиссный исход. Не все довольны одинаково, но лагерю удалось двигаться дальше."


def world_report(state):
    world = ensure(state)
    return {
        "weather": weather(state)[1],
        "morale": world["morale"], "knowledge": world["knowledge"],
        "freedom": world["freedom"], "resources": world["resources"],
        "tracks": [(PLOTS[key]["name"], story_status(state, key)) for key in PLOT_ORDER],
        "resolved": len(world["resolved"]), "decisions": len(world["decisions"])
    }


def finale(state):
    """Branch-dependent ending, including unresolved storylines and world health."""
    world = ensure(state)
    hero = state["hero"]["name"]
    if world["morale"] >= 70:
        mood = u"Совёнок провожает тебя как своего человека. Друзья собираются на площади, вспоминают общие дела и смеются над прежними спорами."
    elif world["morale"] < 35:
        mood = u"На прощании чувствуется усталость. Некоторые решения оставили между ребятами недосказанность, и далеко не все истории удалось завершить."
    else:
        mood = u"Последнее утро проходит как обычно: знакомые голоса, шаги по дорожкам и ощущение, что лагерь стал немного другим благодаря вашим встречам."
    if world["knowledge"] >= 75:
        discovery = u"Из загадок прошлого удалось извлечь больше ответов, чем ожидалось. Записи и открытия останутся следующей смене."
    elif world["freedom"] >= 75:
        discovery = u"Больше всего будут помнить рискованные, самостоятельные решения, сделавшие эту смену непохожей на другие."
    else:
        discovery = u"Не на каждую загадку найден ответ, но многие прежние вопросы теперь звучат иначе."
    pairs = sorted(state["affinity"].items(), key=lambda pair: pair[1], reverse=True)
    close = [who for who, score in pairs[:3] if score >= 25]
    names = {u"mi": u"Мику", u"sl": u"Славя", u"dv": u"Алиса", u"un": u"Лена",
             u"us": u"Ульяна", u"mt": u"Ольга Дмитриевна", u"cs": u"Виола",
             u"mz": u"Женя", u"el": u"Электроник", u"sh": u"Шурик", u"uv": u"Юля"}
    friendship = (
        u"Особенно близкими стали: " + u", ".join(names[who] for who in close) + u"."
        if close else u"Близких друзей появилось немного, но запомнились даже короткие разговоры."
    )
    epilogues = []
    for plot in PLOT_ORDER:
        epilogues.append(PLOTS[plot]["name"] + u": " + story_status(state, plot))
    return (u"ПОСЛЕДНИЙ ДЕНЬ СМЕНЫ\n\n%s, теперь пришло время уезжать.\n\n%s\n\n%s\n\n%s\n\n" %
            (hero, mood, discovery, friendship) + u"\n\n".join(epilogues) +
            u"\n\nТы можешь вернуться к дневнику и перечитать, какие поступки привели к этому итогу. Каждая новая смена начинается с других событий.")
