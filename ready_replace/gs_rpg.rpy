# -*- coding: utf-8 -*-
# RPG sandbox. Loaded alongside generative_summer.rpy; does not change classic stories.
init 1001 python:
    import json
    import os
    import gs_rpg
    import gs_backend

    def gs_rpg_root():
        return gs_runtime.app.library.root

    def gs_rpg_start(name, age, days, history, source):
        state = gs_rpg.new_game(name, age, days, history, source)
        gs_rpg.save(gs_rpg_root(), state)
        store.gs_rpg_state = state
        renpy.block_rollback()

    def gs_rpg_open(game_id):
        store.gs_rpg_state = gs_rpg.load(gs_rpg_root(), game_id)
        renpy.block_rollback()

    def gs_rpg_apply(action, arg=None):
        state = gs_rpg.load(gs_rpg_root(), gs_rpg_state["id"])
        if action == "move":
            gs_rpg.move(state, arg)
        elif action == "talk":
            gs_rpg.activity(state, "talk", arg)
        elif action == "route":
            gs_rpg.route_event(state, arg[0], arg[1])
        else:
            gs_rpg.activity(state, action)
        gs_rpg.save(gs_rpg_root(), state)
        store.gs_rpg_state = state
        renpy.block_rollback()

    GS_RPG_SPRITE_HINTS = {
        "sl": u"blonde girl, long braids, blue eyes, red pioneer neckerchief",
        "dv": u"red-haired girl, short unruly hair, amber eyes, mischievous expression",
        "un": u"shy violet-haired girl, thoughtful expression",
        "mi": u"Japanese girl, very long turquoise twin tails, gentle smile",
        "us": u"short red-haired energetic girl",
        "mt": u"adult counselor, long brown hair, confident expression",
        "cs": u"adult nurse, short violet hair, white medical coat",
        "mz": u"short dark hair, glasses, reserved expression",
        "el": u"light-haired boy with glasses, cheerful expression",
        "sh": u"dark-haired boy with glasses, curious expression",
        "uv": u"mysterious cat-eared girl, long lilac hair"
    }

    GS_RPG_BG = {
        "square": "bg ext_square_day",
        "gate": "bg ext_camp_entrance_day",
        "cabins": "bg ext_houses_day",
        "canteen": "bg int_dining_hall_people_day",
        "library": "bg int_library_day",
        "clubs": "bg ext_clubs_day",
        "stage": "bg ext_stage_normal_day",
        "beach": "bg ext_beach_day",
        "lake": "bg ext_boathouse_day",
        "forest": "bg ext_path_day",
        "infirmary": "bg int_aidpost_day",
        "sports": "bg ext_playground_day"
    }

    def gs_rpg_bg():
        place = gs_rpg_state["place"]
        custom = gs_rpg.asset_path(gs_rpg_root(), gs_rpg_state["id"], "background", place)
        if custom and renpy.loadable(custom):
            return Image(custom)
        name = GS_RPG_BG.get(place)
        if name in gs_runtime.original_images:
            return gs_runtime.original_images[name]
        return Solid("#173039")

    def gs_rpg_sprite(who):
        custom = gs_rpg.asset_path(gs_rpg_root(), gs_rpg_state["id"], "sprite", who)
        if custom and renpy.loadable(custom):
            return Image(custom)
        # Native Ren'Py displayables are already resolved in the private vanilla archive.
        candidates = sorted(name for name in gs_runtime.original_images
                            if name.startswith(who + " ") and " pioneer " in (" " + name + " "))
        if not candidates:
            candidates = sorted(name for name in gs_runtime.original_images if name.startswith(who + " "))
        return gs_runtime.original_images[candidates[0]] if candidates else None

    def gs_rpg_scene_generate(who, intent):
        # Called via gs_runtime.app.start(), never on the screen rendering thread.
        state = gs_rpg.load(gs_rpg_root(), gs_rpg_state["id"])
        context = gs_rpg.summary_for_ai(state, who, intent)
        app = gs_runtime.app
        if state["source"].startswith("7dl:"):
            root = (app.catalog.get("source_roots") or {}).get("7dl")
            if root and os.path.isdir(root):
                try:
                    import gs_source_7dl
                    context["source_reference"] = gs_source_7dl.source_context(
                        root, os.path.join(gs_rpg_root(), "_source_cache"),
                        state["source"].split(":", 1)[1],
                        gs_rpg.NPC_NAMES[who] + u" " + intent,
                        mode="divergent", day=min(state["day"], 7),
                        limit=3, max_chars=7000)
                except (IOError, OSError, ValueError, TypeError):
                    pass
        if not app.models:
            app.refresh_models()
        model = gs_backend.default_model(app.models, persistent.gs_model)
        instructions = (
            u"Ты литературный рассказчик игры-песочницы в мире «Бесконечного лета». "
            u"Напиши ОДНУ выразительную сцену на русском, 300–650 слов, с диалогом и реакциями. "
            u"Учитывай имя, возраст, предысторию, время, место, очки отношений, поступок игрока и журнал. "
            u"Не превращай сцену в жёсткий рут, не решай за игрока его действия, "
            u"не перескакивай во времени и не переписывай факты. "
            u"Не выдумывай новые цифры характеристик, награды или местонахождение персонажей. "
            u"Верни только текст сцены без Markdown, программного кода и меню."
        )
        app.set_status(u"Создаём особую сцену…")
        story_text = app.client.generate(instructions, json.dumps(context, ensure_ascii=False),
                                         model=model, effort=gs_backend.DEFAULT_EFFORT,
                                         fast_mode=persistent.gs_fast_mode)
        gs_rpg.append_ai_scene(state, who, story_text)
        gs_rpg.save(gs_rpg_root(), state)
        return story_text

    def gs_rpg_art_generate(kind, key):
        state = gs_rpg.load(gs_rpg_root(), gs_rpg_state["id"])
        if kind == "background":
            if key not in gs_rpg.PLACE_NAMES:
                raise ValueError("Unknown location")
            label = gs_rpg.PLACE_NAMES[key]
            prompt = (
                u"Wide anime background in the hand-painted visual novel style of Everlasting Summer, "
                u"the Sovyonok summer camp, warm 1980s summer aesthetic, no text, no people, "
                u"no UI, composition suitable for dialogue and sprites, daytime. "
                u"Location: " + label + u"."
            )
            transparent = False
        elif kind == "sprite":
            if key not in gs_rpg.NPC_NAMES:
                raise ValueError("Unknown character")
            label = gs_rpg.NPC_NAMES[key]
            prompt = (
                u"FULL BODY character sprite for a 2D anime visual novel in the hand-drawn "
                u"Everlasting Summer summer camp style. Character: " + label + u". "
                u"Appearance: " + GS_RPG_SPRITE_HINTS.get(key, u"expressive anime features") + u". "
                u"Recognizable consistent hair, face and pioneer outfit, neutral standing pose, "
                u"single centered character, clear outline, fully visible head and feet, "
                u"NO scenery, NO props, NO text, transparent alpha background."
            )
            transparent = True
        else:
            raise ValueError("Unknown asset type")
        app = gs_runtime.app
        app.set_status(u"Рисуем %s…" % (u"фон" if kind == "background" else u"спрайт"))
        data = app.client.generate_background(prompt,
                                              references=app.catalog.get("background_references") if kind == "background" else None,
                                              transparent=transparent)
        return gs_rpg.save_asset(gs_rpg_root(), state["id"], kind, key, data)

default gs_rpg_state = None
default gs_rpg_focus = None

screen gs_rpg_picker:
    modal True
    add Solid("#11262c")
    use gs_chrome(u"ОТКРЫТЫЙ МИР", Return(("back", None)))
    text u"Совёнок · свободная смена" style "gs_title" xpos 120 ypos 145 size 65
    text u"Передвижение, распорядок, очки отношений и занятия без обязательных AI-запросов." style "gs_sub" xpos 120 ypos 230 size 31
    frame:
        style "gs_box"
        xpos 120 ypos 325 xsize 1680 ysize 570
        hbox:
            spacing 65
            vbox:
                xsize 1000 spacing 14
                text u"СОХРАНЁННЫЕ СМЕНЫ" style "gs_meta"
                viewport:
                    mousewheel True
                    scrollbars "vertical"
                    ysize 400
                    vbox:
                        spacing 12
                        for game in gs_rpg.list_games(gs_rpg_root()):
                            textbutton (u"%s · день %d/%d%s" % (game["name"], game["day"], game["duration"], u" · завершена" if game["finished"] else u"")) style "gs_row" action Return(("load", game["id"]))
            vbox:
                spacing 20
                textbutton u"Создать персонажа" style "gs_primary" action Return(("new", None))
                textbutton u"Назад" style "gs_act" action Return(("back", None))

screen gs_rpg_setup:
    modal True
    default name = u"Семён"
    default age = "18"
    default days = "14"
    default history = u"Новичок в лагере"
    default source = "vanilla"
    add Solid("#152c34")
    use gs_chrome(u"СОЗДАНИЕ ПЕРСОНАЖА", Return(None))
    text u"Ваша история начинается здесь" style "gs_title" xpos 120 ypos 135 size 68
    frame:
        background GS_PAPER
        padding (60, 45)
        xpos 330 ypos 270 xsize 1260 ysize 630
        vbox:
            spacing 22
            hbox:
                spacing 50
                vbox:
                    xsize 490
                    text u"ИМЯ" style "gs_ink_label"
                    input value ScreenVariableInputValue("name") length 35 style "gs_ink_input" xmaximum 480
                    null height 15
                    text u"ВОЗРАСТ (14–80)" style "gs_ink_label"
                    input value ScreenVariableInputValue("age") length 3 style "gs_ink_input"
                    null height 15
                    text u"ДНЕЙ В СМЕНЕ (1–120)" style "gs_ink_label"
                    input value ScreenVariableInputValue("days") length 3 style "gs_ink_input"
                vbox:
                    xsize 550
                    text u"ПРЕДЫСТОРИЯ" style "gs_ink_label"
                    input value ScreenVariableInputValue("history") length 120 style "gs_ink_input" xmaximum 520
                    null height 18
                    text u"МИР И ХАРАКТЕРЫ" style "gs_ink_label"
                    textbutton u"Оригинальный Совёнок" style "gs_ink_act" action SetScreenVariable("source", "vanilla") selected source == "vanilla"
                    if gs_detect_7dl_root():
                        textbutton u"7ДЛ · Мику" style "gs_ink_act" action SetScreenVariable("source", "7dl:mi_7dl") selected source == "7dl:mi_7dl"
            null height 6
            text u"В этом режиме возраст и имя задаются игроком. Персонажи остаются в рамках своего характера, а сюжетная генерация доступна отдельно." style "gs_ink_small" size 22
            $ valid = bool(name.strip() and history.strip() and age.isdigit() and days.isdigit() and 14 <= int(age) <= 80 and 1 <= int(days) <= 120)
            hbox:
                spacing 34
                textbutton u"Начать смену" style "gs_ink_act" sensitive valid action Return((name.strip(), age, days, history.strip(), source))
                textbutton u"Отмена" style "gs_ink_act" action Return(None)

screen gs_rpg_map:
    modal True
    add Solid("#122c31")
    use gs_chrome(u"КАРТА СОВЁНКА", Return(None))
    text u"Карта лагеря" style "gs_title" xpos 120 ypos 120 size 70
    text (u"Вы находитесь: " + gs_rpg.PLACE_NAMES[gs_rpg_state["place"]]) style "gs_sub" xpos 120 ypos 205
    # Schematic clickable map, not an assertion about canonical geography.
    frame:
        background Solid("#24473c")
        xpos 90 ypos 280 xsize 1740 ysize 645
    for slug, place_name, x, y in gs_rpg.PLACES:
        $ inhabitants = gs_rpg.at_place(gs_rpg_state, slug)
        vbox:
            xpos 100 + int(x * 16.5)
            ypos 250 + int(y * 6.0)
            spacing 2
            textbutton (u"● " + place_name if gs_rpg_state["place"] == slug else place_name) style "gs_navlink" action Return(slug)
            if inhabitants:
                text (u", ".join(n[1] for n in inhabitants)) style "gs_small" size 20 color "#f8d88f" xmaximum 235
    text u"Схематичная карта · персонажи перемещаются по распорядку дня." style "gs_small" xpos 150 ypos 970

screen gs_rpg_hub:
    modal True
    add gs_rpg_bg()
    add Solid("#051014b0")
    $ nearby_sprites = gs_rpg.at_place(gs_rpg_state)
    if nearby_sprites:
        $ portrait = gs_rpg_sprite(nearby_sprites[0][0])
        if portrait is not None:
            add portrait at gs_rpg_portrait_transform xpos 1000 ypos 160
    use gs_chrome(gs_rpg.PLACE_NAMES[gs_rpg_state["place"]])
    vbox:
        xpos 100 ypos 135 spacing 12 xsize 920
        text gs_rpg.camp_time(gs_rpg_state) style "gs_title" size 59
        text (u"%s, %d лет · %s" % (gs_rpg_state["hero"]["name"], gs_rpg_state["hero"]["age"], gs_rpg_state["hero"]["background"])) style "gs_sub" size 28
        text (u"Энергия: %d/100   ·   Любознательность: %d   ·   Доброта: %d   ·   Навык: %d" %
              (gs_rpg_state["energy"], gs_rpg_state["stats"]["curiosity"], gs_rpg_state["stats"]["kindness"], gs_rpg_state["stats"]["skill"])) style "gs_small"
        null height 5
        frame:
            background Solid("#172b32e0")
            padding (20, 18)
            xsize 850
            text gs_literal(gs_rpg_state["event"]) style "gs_text" size 29 xmaximum 800
        null height 20
        textbutton u"Открыть карту" style "gs_primary" action Return(("map", None)) sensitive not gs_rpg_state["finished"]
        if not gs_rpg_state["finished"]:
            text u"ПОВСЕДНЕВНЫЕ ЗАНЯТИЯ" style "gs_meta"
            hbox:
                spacing 23
                textbutton u"Осмотреться" style "gs_act" action Return(("activity", "explore"))
                textbutton u"Помочь" style "gs_act" action Return(("activity", "help"))
                textbutton u"Заняться делом" style "gs_act" action Return(("activity", "practice"))
            textbutton u"Отдохнуть / пропустить время" style "gs_act" action Return(("activity", "rest"))
        textbutton u"Дневник, характеристики и руты" style "gs_act" action Return(("journal", None))
        if not gs_rpg_state["finished"]:
            textbutton u"Создать фон локации (AI)" style "gs_act" action Return(("background", gs_rpg_state["place"]))
        textbutton u"Вернуться к выбору смены" style "gs_act" action Return(("exit", None))
    frame:
        background Solid("#11232ce0")
        padding (30, 24)
        xpos 1090 ypos 155 xsize 730 ysize 790
        vbox:
            spacing 16
            text u"КТО СЕЙЧАС РЯДОМ" style "gs_meta"
            $ inhabitants = gs_rpg.at_place(gs_rpg_state)
            if not inhabitants:
                text u"Пока никого. Посмотрите карту или дождитесь другого времени." style "gs_text" size 26
            viewport:
                ysize 570 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 17
                    for who, person in inhabitants:
                        vbox:
                            spacing 5
                            text (person + u" · %d/100 · %s" % (gs_rpg_state["affinity"][who], gs_rpg.route_label(gs_rpg_state["affinity"][who]))) style "gs_text" size 30
                            hbox:
                                spacing 16
                                textbutton u"Поговорить" style "gs_navlink" action Return(("talk", who)) sensitive not gs_rpg_state["finished"]
                                textbutton u"AI-сцена" style "gs_navlink" action Return(("ai", who)) sensitive not gs_rpg_state["finished"]
                                textbutton u"Спрайт" style "gs_navlink" action Return(("sprite", who)) sensitive not gs_rpg_state["finished"]
                            if gs_rpg.available_route_events(gs_rpg_state, who) and not gs_rpg_state["finished"]:
                                textbutton u"Сюжетный этап рута" style "gs_navlink" action Return(("route", who))
            text u"Разговоры и активности меняют время и отношения локально. AI-сцены вызываются только вручную." style "gs_small" size 23

screen gs_rpg_journal:
    modal True
    add Solid("#172a32")
    use gs_chrome(u"ДНЕВНИК", Return())
    text u"Дневник смены и руты" style "gs_title" xpos 120 ypos 135 size 65
    hbox:
        xpos 110 ypos 270 spacing 65
        frame:
            background Solid("#091a24")
            padding (25, 20)
            xsize 850 ysize 680
            viewport:
                mousewheel True scrollbars "vertical" ysize 620
                vbox:
                    spacing 16
                    for row in reversed(gs_rpg_state["journal"]):
                        text (u"День %d · %s" % (row["day"], gs_rpg.SLOTS[row["slot"]])) style "gs_meta"
                        text gs_literal(row["text"]) style "gs_text" size 26 xmaximum 740
        frame:
            background Solid("#091a24")
            padding (25, 20)
            xsize 780 ysize 680
            viewport:
                mousewheel True scrollbars "vertical" ysize 620
                vbox:
                    spacing 13
                    for who, name in sorted(gs_rpg.NPC_NAMES.items()):
                        text (u"%s: %d/100 · %s" % (name, gs_rpg_state["affinity"][who], gs_rpg.route_label(gs_rpg_state["affinity"][who]))) style "gs_text" size 26
                    null height 25
                    text u"ЗАДАНИЯ" style "gs_meta"
                    for key, title, progress, goal in gs_rpg.quest_progress(gs_rpg_state):
                        text (u"%s: %d/%d%s" % (title, min(progress, goal), goal, u" ✓" if key in gs_rpg_state["quests_done"] else u"")) style "gs_text" size 25

screen gs_rpg_route_choice(who):
    modal True
    add Solid("#0c1823ed")
    frame:
        background GS_PAPER padding (55, 45)
        align (0.5, 0.5) xsize 1100
        vbox:
            spacing 24
            text (u"Сюжетный этап: " + gs_rpg.NPC_NAMES[who]) style "gs_ink_title"
            $ stage = gs_rpg.available_route_events(gs_rpg_state, who)[0]
            text (u"%s · порог %d очков" % (stage[1], stage[0])) style "gs_ink_small"
            textbutton u"Поддержать персонажа" style "gs_ink_act" action Return("support")
            textbutton u"Высказать свою точку зрения" style "gs_ink_act" action Return("honest")
            textbutton u"Сохранить дистанцию" style "gs_ink_act" action Return("leave")
            textbutton u"Не сейчас" style "gs_ink_act" action Return(None)

transform gs_rpg_portrait_transform:
    zoom 0.56
    alpha 0.7

screen gs_rpg_ai_input(who):
    modal True
    default intent = u"Хочу побеседовать и узнать персонажа получше"
    add Solid("#0a1823d9")
    frame:
        background GS_PAPER padding (60, 50)
        align (0.5, 0.5) xsize 1100
        vbox:
            spacing 22
            text (u"Особая сцена: " + gs_rpg.NPC_NAMES[who]) style "gs_ink_title"
            text u"Опишите действие или тему разговора. Только этот запрос вызовет LLM." style "gs_ink_small"
            input value ScreenVariableInputValue("intent") style "gs_ink_input" length 500 xmaximum 940
            hbox:
                spacing 35
                textbutton u"Сгенерировать" style "gs_ink_act" sensitive bool(intent.strip()) action Return(intent.strip())
                textbutton u"Отмена" style "gs_ink_act" action Return("")

screen gs_rpg_read_scene(scene_text):
    modal True
    add Solid("#091827")
    use gs_chrome(u"ОСОБАЯ СЦЕНА", Return())
    frame:
        background GS_PAPER
        padding (55, 45)
        xpos 270 ypos 175 xsize 1380 ysize 740
        viewport:
            ysize 640
            mousewheel True scrollbars "vertical"
            text gs_literal(scene_text) style "gs_ink_small" size 30 xmaximum 1240

label gs_rpg_main:
    $ gs_setup()
    $ gs_place("gate")
label gs_rpg_picker_label:
    call screen gs_rpg_picker
    $ gs_rpg_cmd, gs_rpg_value = _return
    if gs_rpg_cmd == "back":
        jump gs_menu
    if gs_rpg_cmd == "new":
        call screen gs_rpg_setup
        if not _return:
            jump gs_rpg_picker_label
        $ gs_rpg_name, gs_rpg_age, gs_rpg_days, gs_rpg_history, gs_rpg_source = _return
        $ gs_rpg_start(gs_rpg_name, gs_rpg_age, gs_rpg_days, gs_rpg_history, gs_rpg_source)
    else:
        $ gs_rpg_open(gs_rpg_value)
    jump gs_rpg_loop

label gs_rpg_loop:
    call screen gs_rpg_hub
    $ gs_rpg_cmd, gs_rpg_value = _return
    if gs_rpg_cmd == "exit":
        jump gs_rpg_picker_label
    if gs_rpg_cmd == "journal":
        call screen gs_rpg_journal
        jump gs_rpg_loop
    if gs_rpg_cmd == "map":
        call screen gs_rpg_map
        if _return:
            $ gs_rpg_apply("move", _return)
        jump gs_rpg_loop
    if gs_rpg_cmd == "activity":
        $ gs_rpg_apply(gs_rpg_value)
        jump gs_rpg_loop
    if gs_rpg_cmd == "talk":
        $ gs_rpg_apply("talk", gs_rpg_value)
        jump gs_rpg_loop
    if gs_rpg_cmd == "route":
        $ gs_rpg_focus = gs_rpg_value
        call screen gs_rpg_route_choice(gs_rpg_focus)
        if _return:
            $ gs_rpg_apply("route", (gs_rpg_focus, _return))
        jump gs_rpg_loop
    if gs_rpg_cmd == "ai":
        if not gs_runtime.app.client.authenticated():
            call gs_connect
            if not gs_runtime.app.client.authenticated():
                jump gs_rpg_loop
        $ gs_rpg_focus = gs_rpg_value
        call screen gs_rpg_ai_input(gs_rpg_focus)
        if not _return:
            jump gs_rpg_loop
        $ gs_rpg_intent = _return
        $ gs_run("chapter", gs_rpg_scene_generate, gs_rpg_focus, gs_rpg_intent)
        if gs_runtime.app.error:
            call screen gs_error
        else:
            $ gs_rpg_open(gs_rpg_state["id"])
            call screen gs_rpg_read_scene(gs_runtime.app.result)
        jump gs_rpg_loop
    if gs_rpg_cmd == "background" or gs_rpg_cmd == "sprite":
        if not gs_runtime.app.client.authenticated():
            call gs_connect
            if not gs_runtime.app.client.authenticated():
                jump gs_rpg_loop
        $ gs_rpg_art_kind = "background" if gs_rpg_cmd == "background" else "sprite"
        $ gs_run("chapter", gs_rpg_art_generate, gs_rpg_art_kind, gs_rpg_value)
        if gs_runtime.app.error:
            call screen gs_error
        jump gs_rpg_loop
    jump gs_rpg_loop
