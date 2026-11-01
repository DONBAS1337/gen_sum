# -*- coding: utf-8 -*-
# RPG sandbox. Loaded alongside don_gen.rpy; does not change classic stories.
init 1001 python:
    import json
    import os
    import logging
    import dg_rpg
    import dg_backend

    def dg_rpg_root():
        return dg_runtime.app.library.root

    def dg_rpg_start(name, age, days, history, source, pronouns):
        state = dg_rpg.new_game(name, age, days, history, source, pronouns)
        dg_rpg.save(dg_rpg_root(), state)
        store.dg_rpg_state = state
        logging.getLogger("don_gen").info("RPG created id=%s days=%s", state["id"], state["duration"])
        renpy.block_rollback()

    def dg_rpg_open(game_id):
        store.dg_rpg_state = dg_rpg.load(dg_rpg_root(), game_id)
        logging.getLogger("don_gen").info("RPG opened id=%s", game_id)
        renpy.block_rollback()

    def dg_rpg_apply(action, arg=None):
        state = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        if action == "move":
            dg_rpg.move(state, arg)
        elif action == "talk":
            dg_rpg.activity(state, "talk", arg)
        elif action == "route":
            dg_rpg.route_event(state, arg[0], arg[1])
        else:
            dg_rpg.activity(state, action)
        dg_rpg.save(dg_rpg_root(), state)
        store.dg_rpg_state = state
        logging.getLogger("don_gen").info("RPG action=%s day=%d slot=%d place=%s", action, state["day"], state["slot"], state["place"])
        renpy.block_rollback()

    DG_RPG_SPRITE_HINTS = {
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

    DG_RPG_BG = {
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

    def dg_rpg_bg():
        place = dg_rpg_state["place"]
        custom = dg_rpg.asset_path(dg_rpg_root(), dg_rpg_state["id"], "background", place)
        if custom and renpy.loadable(custom):
            return Image(custom)
        name = DG_RPG_BG.get(place)
        if name in dg_runtime.original_images:
            return dg_runtime.original_images[name]
        return Solid("#173039")

    def dg_rpg_sprite(who):
        custom = dg_rpg.asset_path(dg_rpg_root(), dg_rpg_state["id"], "sprite", who)
        if custom and renpy.loadable(custom):
            return Image(custom)
        # Native Ren'Py displayables are already resolved in the private vanilla archive.
        candidates = sorted(name for name in dg_runtime.original_images
                            if name.startswith(who + " ") and " pioneer " in (" " + name + " "))
        if not candidates:
            candidates = sorted(name for name in dg_runtime.original_images if name.startswith(who + " "))
        return dg_runtime.original_images[candidates[0]] if candidates else None

    def dg_rpg_scene_generate(who, intent):
        # Called via dg_runtime.app.start(), never on the screen rendering thread.
        state = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        context = dg_rpg.summary_for_ai(state, who, intent)
        app = dg_runtime.app
        if state["source"].startswith("7dl:"):
            root = (app.catalog.get("source_roots") or {}).get("7dl")
            if root and os.path.isdir(root):
                try:
                    import dg_source_7dl
                    context["source_reference"] = dg_source_7dl.source_context(
                        root, os.path.join(dg_rpg_root(), "_source_cache"),
                        state["source"].split(":", 1)[1],
                        dg_rpg.NPC_NAMES[who] + u" " + intent,
                        mode="divergent", day=min(state["day"], 7),
                        limit=3, max_chars=7000)
                except (IOError, OSError, ValueError, TypeError):
                    pass
        if not app.models:
            app.refresh_models()
        model = dg_backend.default_model(app.models, persistent.dg_model)
        instructions = (
            u"Ты литературный рассказчик игры-песочницы в мире «Бесконечного лета». "
            u"Напиши ОДНУ выразительную сцену на русском, 300–650 слов, с диалогом и реакциями. "
            u"Учитывай имя, возраст, предысторию, время, место, очки отношений, поступок игрока и журнал. "
            u"Не превращай сцену в жёсткий рут, не решай за игрока его действия, "
            u"не перескакивай во времени и не переписывай факты. "
            u"Не выдумывай новые цифры характеристик, награды или местонахождение персонажей. "
            u"Верни только текст сцены без Markdown, программного кода и меню."
        )
        logging.getLogger("don_gen").info("AI scene request npc=%s day=%d", who, state["day"])
        app.set_status(u"Создаём особую сцену…")
        story_text = app.client.generate(instructions, json.dumps(context, ensure_ascii=False),
                                         model=model, effort=dg_backend.DEFAULT_EFFORT,
                                         fast_mode=persistent.dg_fast_mode)
        dg_rpg.append_ai_scene(state, who, story_text)
        dg_rpg.save(dg_rpg_root(), state)
        logging.getLogger("don_gen").info("AI scene committed npc=%s", who)
        return story_text

    def dg_rpg_art_generate(kind, key):
        state = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        if kind == "background":
            if key not in dg_rpg.PLACE_NAMES:
                raise ValueError("Unknown location")
            label = dg_rpg.PLACE_NAMES[key]
            prompt = (
                u"Wide anime background in the hand-painted visual novel style of Everlasting Summer, "
                u"the Sovyonok summer camp, warm 1980s summer aesthetic, no text, no people, "
                u"no UI, composition suitable for dialogue and sprites, daytime. "
                u"Location: " + label + u"."
            )
            transparent = False
        elif kind == "sprite":
            if key not in dg_rpg.NPC_NAMES:
                raise ValueError("Unknown character")
            label = dg_rpg.NPC_NAMES[key]
            prompt = (
                u"FULL BODY character sprite for a 2D anime visual novel in the hand-drawn "
                u"Everlasting Summer summer camp style. Character: " + label + u". "
                u"Appearance: " + DG_RPG_SPRITE_HINTS.get(key, u"expressive anime features") + u". "
                u"Recognizable consistent hair, face and pioneer outfit, neutral standing pose, "
                u"single centered character, clear outline, fully visible head and feet, "
                u"NO scenery, NO props, NO text, transparent alpha background."
            )
            transparent = True
        else:
            raise ValueError("Unknown asset type")
        app = dg_runtime.app
        logging.getLogger("don_gen").info("AI image request kind=%s key=%s", kind, key)
        app.set_status(u"Рисуем %s…" % (u"фон" if kind == "background" else u"спрайт"))
        data = app.client.generate_background(prompt,
                                              references=app.catalog.get("background_references") if kind == "background" else None,
                                              transparent=transparent)
        return dg_rpg.save_asset(dg_rpg_root(), state["id"], kind, key, data)

default dg_rpg_state = None
default dg_rpg_focus = None

screen dg_rpg_picker:
    modal True
    add Solid("#11262c")
    use dg_chrome(u"ОТКРЫТЫЙ МИР", Return(("back", None)))
    text u"Совёнок · свободная смена" style "dg_title" xpos 120 ypos 145 size 65
    text u"Передвижение, распорядок, очки отношений и занятия без обязательных AI-запросов." style "dg_sub" xpos 120 ypos 230 size 31
    frame:
        style "dg_box"
        xpos 120 ypos 325 xsize 1680 ysize 570
        hbox:
            spacing 65
            vbox:
                xsize 1000 spacing 14
                text u"СОХРАНЁННЫЕ СМЕНЫ" style "dg_meta"
                viewport:
                    mousewheel True
                    scrollbars "vertical"
                    ysize 400
                    vbox:
                        spacing 12
                        for game in dg_rpg.list_games(dg_rpg_root()):
                            textbutton dg_literal(u"%s · день %d/%d%s" % (game["name"], game["day"], game["duration"], u" · завершена" if game["finished"] else u"")) style "dg_row" action Return(("load", game["id"]))
            vbox:
                spacing 20
                textbutton u"Создать персонажа" style "dg_primary" action Return(("new", None))
                textbutton u"Назад" style "dg_act" action Return(("back", None))

screen dg_rpg_setup:
    modal True
    add Solid("#152c34")
    use dg_chrome(u"СОЗДАНИЕ ПЕРСОНАЖА", Return(("cancel",)))
    text u"Ваша история начинается здесь" style "dg_title" xpos 120 ypos 120 size 67
    frame:
        background DG_PAPER
        padding (50, 32)
        xpos 300 ypos 250 xsize 1320 ysize 715
        vbox:
            spacing 15
            hbox:
                spacing 65
                vbox:
                    xsize 520
                    spacing 9
                    text u"ИМЯ" style "dg_ink_label"
                    textbutton (dg_literal(dg_create_name) + u"  · ИЗМЕНИТЬ") style "dg_ink_act" action Return(("edit", "name"))
                    null height 11
                    text u"ВОЗРАСТ (14–80)" style "dg_ink_label"
                    textbutton (dg_create_age + u"  · ИЗМЕНИТЬ") style "dg_ink_act" action Return(("edit", "age"))
                    null height 11
                    text u"ДНЕЙ В СМЕНЕ (1–120)" style "dg_ink_label"
                    textbutton (dg_create_days + u"  · ИЗМЕНИТЬ") style "dg_ink_act" action Return(("edit", "days"))
                    null height 5
                    text u"Нажмите «изменить», чтобы ввести значение." style "dg_ink_small" size 21
                vbox:
                    xsize 590
                    spacing 10
                    text u"ПРЕДЫСТОРИЯ" style "dg_ink_label"
                    textbutton (dg_literal(dg_create_history) + u"  · ИЗМЕНИТЬ") style "dg_ink_act" action Return(("edit", "history")) xmaximum 565
                    null height 9
                    text u"МИР И ХАРАКТЕРЫ" style "dg_ink_label"
                    textbutton u"Оригинальный Совёнок" style "dg_ink_act" action SetVariable("dg_create_source", "vanilla") selected dg_create_source == "vanilla"
                    if dg_detect_7dl_root():
                        textbutton u"7ДЛ · Мику" style "dg_ink_act" action SetVariable("dg_create_source", "7dl:mi_7dl") selected dg_create_source == "7dl:mi_7dl"
                        textbutton u"7ДЛ · DJ" style "dg_ink_act" action SetVariable("dg_create_source", "7dl:mi_dj") selected dg_create_source == "7dl:mi_dj"
                        textbutton u"7ДЛ · Классика" style "dg_ink_act" action SetVariable("dg_create_source", "7dl:mi_cl") selected dg_create_source == "7dl:mi_cl"
            text u"ОБРАЩЕНИЕ" style "dg_ink_label"
            hbox:
                spacing 36
                for choice in (u"он/его", u"она/её", u"они/их"):
                    textbutton choice style "dg_ink_act" selected dg_create_pronouns == choice action SetVariable("dg_create_pronouns", choice)
            null height 8
            text u"Имя, возраст и длительность можно изменить до начала смены. Режим RPG работает и без генерации." style "dg_ink_small" size 22
            $ dg_valid = bool(dg_create_name.strip() and dg_create_history.strip() and dg_create_age.isdigit() and dg_create_days.isdigit() and 14 <= int(dg_create_age) <= 80 and 1 <= int(dg_create_days) <= 120)
            hbox:
                spacing 44
                textbutton u"Начать смену" style "dg_ink_act" sensitive dg_valid action Return(("start",))
                textbutton u"Отмена" style "dg_ink_act" action Return(("cancel",))
            if not dg_valid:
                text u"Заполните имя/предысторию, возраст 14–80, смена 1–120 дней." style "dg_ink_small" size 20 color "#b22e1f"

screen dg_rpg_map:
    modal True
    add Solid("#122c31")
    use dg_chrome(u"КАРТА СОВЁНКА", Return(None))
    text u"Карта лагеря" style "dg_title" xpos 120 ypos 120 size 70
    text (u"Вы находитесь: " + dg_rpg.PLACE_NAMES[dg_rpg_state["place"]]) style "dg_sub" xpos 120 ypos 205
    # Schematic clickable map, not an assertion about canonical geography.
    frame:
        background Solid("#24473c")
        xpos 90 ypos 280 xsize 1740 ysize 645
    for slug, place_name, x, y in dg_rpg.PLACES:
        $ inhabitants = dg_rpg.at_place(dg_rpg_state, slug)
        vbox:
            xpos 100 + int(x * 16.5)
            ypos 250 + int(y * 6.0)
            spacing 2
            textbutton (u"● " + place_name if dg_rpg_state["place"] == slug else place_name) style "dg_navlink" action Return(slug)
            if inhabitants:
                text (u", ".join(n[1] for n in inhabitants)) style "dg_small" size 20 color "#f8d88f" xmaximum 235
    text u"Схематичная карта · персонажи перемещаются по распорядку дня." style "dg_small" xpos 150 ypos 970

screen dg_rpg_hub:
    modal True
    add dg_rpg_bg()
    add Solid("#051014b0")
    $ nearby_sprites = dg_rpg.at_place(dg_rpg_state)
    if nearby_sprites:
        $ portrait = dg_rpg_sprite(nearby_sprites[0][0])
        if portrait is not None:
            add portrait at dg_rpg_portrait_transform xpos 1000 ypos 160
    use dg_chrome(dg_rpg.PLACE_NAMES[dg_rpg_state["place"]])
    vbox:
        xpos 100 ypos 135 spacing 12 xsize 920
        text dg_rpg.camp_time(dg_rpg_state) style "dg_title" size 59
        text dg_literal(u"%s, %d лет · %s" % (dg_rpg_state["hero"]["name"], dg_rpg_state["hero"]["age"], dg_rpg_state["hero"]["background"])) style "dg_sub" size 28
        text (u"Энергия: %d/100   ·   Любознательность: %d   ·   Доброта: %d   ·   Навык: %d" %
              (dg_rpg_state["energy"], dg_rpg_state["stats"]["curiosity"], dg_rpg_state["stats"]["kindness"], dg_rpg_state["stats"]["skill"])) style "dg_small"
        null height 5
        frame:
            background Solid("#172b32e0")
            padding (20, 18)
            xsize 850
            text dg_literal(dg_rpg_state["event"]) style "dg_text" size 29 xmaximum 800
        null height 20
        textbutton u"Открыть карту" style "dg_primary" action Return(("map", None)) sensitive not dg_rpg_state["finished"]
        if not dg_rpg_state["finished"]:
            text u"ПОВСЕДНЕВНЫЕ ЗАНЯТИЯ" style "dg_meta"
            hbox:
                spacing 23
                textbutton u"Осмотреться" style "dg_act" action Return(("activity", "explore"))
                textbutton u"Помочь" style "dg_act" action Return(("activity", "help"))
                textbutton u"Заняться делом" style "dg_act" action Return(("activity", "practice"))
            textbutton u"Отдохнуть / пропустить время" style "dg_act" action Return(("activity", "rest"))
        textbutton u"Дневник, характеристики и руты" style "dg_act" action Return(("journal", None))
        textbutton u"Диагностика DON-GEN" style "dg_act" action Return(("diag", None))
        if not dg_rpg_state["finished"]:
            textbutton u"Создать фон локации (AI)" style "dg_act" action Return(("background", dg_rpg_state["place"]))
        textbutton u"Вернуться к выбору смены" style "dg_act" action Return(("exit", None))
    frame:
        background Solid("#11232ce0")
        padding (30, 24)
        xpos 1090 ypos 155 xsize 730 ysize 790
        vbox:
            spacing 16
            text u"КТО СЕЙЧАС РЯДОМ" style "dg_meta"
            $ inhabitants = dg_rpg.at_place(dg_rpg_state)
            if not inhabitants:
                text u"Пока никого. Посмотрите карту или дождитесь другого времени." style "dg_text" size 26
            viewport:
                ysize 570 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 17
                    for who, person in inhabitants:
                        vbox:
                            spacing 5
                            text (person + u" · %d/100 · %s" % (dg_rpg_state["affinity"][who], dg_rpg.route_label(dg_rpg_state["affinity"][who]))) style "dg_text" size 30
                            hbox:
                                spacing 16
                                textbutton u"Поговорить" style "dg_navlink" action Return(("talk", who)) sensitive not dg_rpg_state["finished"]
                                textbutton u"AI-сцена" style "dg_navlink" action Return(("ai", who)) sensitive not dg_rpg_state["finished"]
                                textbutton u"Спрайт" style "dg_navlink" action Return(("sprite", who)) sensitive not dg_rpg_state["finished"]
                            if dg_rpg.available_route_events(dg_rpg_state, who) and not dg_rpg_state["finished"]:
                                textbutton u"Сюжетный этап рута" style "dg_navlink" action Return(("route", who))
            text u"Разговоры и активности меняют время и отношения локально. AI-сцены вызываются только вручную." style "dg_small" size 23

screen dg_rpg_journal:
    modal True
    add Solid("#172a32")
    use dg_chrome(u"ДНЕВНИК", Return())
    text u"Дневник смены и руты" style "dg_title" xpos 120 ypos 135 size 65
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
                    for row in reversed(dg_rpg_state["journal"]):
                        text (u"День %d · %s" % (row["day"], dg_rpg.SLOTS[row["slot"]])) style "dg_meta"
                        text dg_literal(row["text"]) style "dg_text" size 26 xmaximum 740
        frame:
            background Solid("#091a24")
            padding (25, 20)
            xsize 780 ysize 680
            viewport:
                mousewheel True scrollbars "vertical" ysize 620
                vbox:
                    spacing 13
                    for who, name in sorted(dg_rpg.NPC_NAMES.items()):
                        text (u"%s: %d/100 · %s" % (name, dg_rpg_state["affinity"][who], dg_rpg.route_label(dg_rpg_state["affinity"][who]))) style "dg_text" size 26
                    null height 25
                    text u"ЗАДАНИЯ" style "dg_meta"
                    for key, title, progress, goal in dg_rpg.quest_progress(dg_rpg_state):
                        text (u"%s: %d/%d%s" % (title, min(progress, goal), goal, u" ✓" if key in dg_rpg_state["quests_done"] else u"")) style "dg_text" size 25

screen dg_rpg_route_choice(who):
    modal True
    add Solid("#0c1823ed")
    frame:
        background DG_PAPER padding (55, 45)
        align (0.5, 0.5) xsize 1100
        vbox:
            spacing 24
            text (u"Сюжетный этап: " + dg_rpg.NPC_NAMES[who]) style "dg_ink_title"
            $ stage = dg_rpg.available_route_events(dg_rpg_state, who)[0]
            text (u"%s · порог %d очков" % (stage[1], stage[0])) style "dg_ink_small"
            textbutton u"Поддержать персонажа" style "dg_ink_act" action Return("support")
            textbutton u"Высказать свою точку зрения" style "dg_ink_act" action Return("honest")
            textbutton u"Сохранить дистанцию" style "dg_ink_act" action Return("leave")
            textbutton u"Не сейчас" style "dg_ink_act" action Return(None)

transform dg_rpg_portrait_transform:
    zoom 0.56
    alpha 0.7

screen dg_rpg_ai_input(who):
    modal True
    default intent = u"Хочу побеседовать и узнать персонажа получше"
    add Solid("#0a1823d9")
    frame:
        background DG_PAPER padding (60, 50)
        align (0.5, 0.5) xsize 1100
        vbox:
            spacing 22
            text (u"Особая сцена: " + dg_rpg.NPC_NAMES[who]) style "dg_ink_title"
            text u"Опишите действие или тему разговора. Только этот запрос вызовет LLM." style "dg_ink_small"
            input value ScreenVariableInputValue("intent") style "dg_ink_input" length 500 xmaximum 940
            hbox:
                spacing 35
                textbutton u"Сгенерировать" style "dg_ink_act" sensitive bool(intent.strip()) action Return(intent.strip())
                textbutton u"Отмена" style "dg_ink_act" action Return("")

screen dg_rpg_read_scene(scene_text):
    modal True
    add Solid("#091827")
    use dg_chrome(u"ОСОБАЯ СЦЕНА", Return())
    frame:
        background DG_PAPER
        padding (55, 45)
        xpos 270 ypos 175 xsize 1380 ysize 740
        viewport:
            ysize 640
            mousewheel True scrollbars "vertical"
            text dg_literal(scene_text) style "dg_ink_small" size 30 xmaximum 1240

label dg_rpg_main:
    $ dg_setup()
    $ dg_place("gate")
label dg_rpg_picker_label:
    call screen dg_rpg_picker
    $ dg_rpg_cmd, dg_rpg_value = _return
    if dg_rpg_cmd == "back":
        jump dg_menu
    if dg_rpg_cmd == "new":
        $ dg_create_name = u"Семён"
        $ dg_create_age = u"18"
        $ dg_create_days = u"14"
        $ dg_create_history = u"Новичок в лагере"
        $ dg_create_source = "vanilla"
        $ dg_create_pronouns = u"он/его"
        jump dg_rpg_create_loop
    $ dg_rpg_open(dg_rpg_value)
    jump dg_rpg_loop

label dg_rpg_create_loop:
    call screen dg_rpg_setup
    $ dg_create_cmd = _return
    if not dg_create_cmd or dg_create_cmd[0] == "cancel":
        jump dg_rpg_picker_label
    if dg_create_cmd[0] == "edit":
        if dg_create_cmd[1] == "name":
            $ dg_create_name = renpy.input(u"Имя персонажа:", default=dg_create_name, length=35).strip()
        elif dg_create_cmd[1] == "age":
            $ dg_create_age = renpy.input(u"Возраст персонажа (14–80):", default=dg_create_age, length=3, allow="0123456789").strip()
        elif dg_create_cmd[1] == "days":
            $ dg_create_days = renpy.input(u"Продолжительность смены (1–120 дней):", default=dg_create_days, length=3, allow="0123456789").strip()
        elif dg_create_cmd[1] == "history":
            $ dg_create_history = renpy.input(u"Предыстория персонажа:", default=dg_create_history, length=120).strip()
        jump dg_rpg_create_loop
    if dg_create_cmd[0] == "start":
        $ dg_rpg_start(dg_create_name.strip(), dg_create_age, dg_create_days, dg_create_history.strip(), dg_create_source, dg_create_pronouns)
        jump dg_rpg_loop
    jump dg_rpg_create_loop

label dg_rpg_loop:
    call screen dg_rpg_hub
    $ dg_rpg_cmd, dg_rpg_value = _return
    if dg_rpg_cmd == "exit":
        jump dg_rpg_picker_label
    if dg_rpg_cmd == "journal":
        call screen dg_rpg_journal
        jump dg_rpg_loop
    if dg_rpg_cmd == "diag":
        call screen dg_diagnostics
        jump dg_rpg_loop
    if dg_rpg_cmd == "map":
        call screen dg_rpg_map
        if _return:
            $ dg_rpg_apply("move", _return)
        jump dg_rpg_loop
    if dg_rpg_cmd == "activity":
        $ dg_rpg_apply(dg_rpg_value)
        jump dg_rpg_loop
    if dg_rpg_cmd == "talk":
        $ dg_rpg_apply("talk", dg_rpg_value)
        jump dg_rpg_loop
    if dg_rpg_cmd == "route":
        $ dg_rpg_focus = dg_rpg_value
        call screen dg_rpg_route_choice(dg_rpg_focus)
        if _return:
            $ dg_rpg_apply("route", (dg_rpg_focus, _return))
        jump dg_rpg_loop
    if dg_rpg_cmd == "ai":
        if not dg_runtime.app.client.authenticated():
            call dg_connect
            if not dg_runtime.app.client.authenticated():
                jump dg_rpg_loop
        $ dg_rpg_focus = dg_rpg_value
        call screen dg_rpg_ai_input(dg_rpg_focus)
        if not _return:
            jump dg_rpg_loop
        $ dg_rpg_intent = _return
        $ dg_run("chapter", dg_rpg_scene_generate, dg_rpg_focus, dg_rpg_intent)
        if dg_runtime.app.error:
            call screen dg_error
        else:
            $ dg_rpg_open(dg_rpg_state["id"])
            call screen dg_rpg_read_scene(dg_runtime.app.result)
        jump dg_rpg_loop
    if dg_rpg_cmd == "background" or dg_rpg_cmd == "sprite":
        if not dg_runtime.app.client.authenticated():
            call dg_connect
            if not dg_runtime.app.client.authenticated():
                jump dg_rpg_loop
        $ dg_rpg_art_kind = "background" if dg_rpg_cmd == "background" else "sprite"
        $ dg_run("chapter", dg_rpg_art_generate, dg_rpg_art_kind, dg_rpg_value)
        if dg_runtime.app.error:
            call screen dg_error
        jump dg_rpg_loop
    jump dg_rpg_loop
