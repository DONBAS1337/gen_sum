# -*- coding: utf-8 -*-
# RPG sandbox. Loaded alongside don_gen.rpy; does not change classic stories.
init 1001 python:
    import json
    import os
    import logging
    import dg_rpg
    import dg_dialogue
    import dg_world
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
        elif action == "conversation":
            store.dg_rpg_last_scene = dg_rpg.conversation(state, arg[0], arg[1], arg[2])
        elif action == "world":
            store.dg_rpg_last_world = dg_rpg.story_choice(state, arg)
        else:
            dg_rpg.activity(state, action)
        dg_rpg.save(dg_rpg_root(), state)
        store.dg_rpg_state = state
        logging.getLogger("don_gen").info("RPG action=%s day=%d slot=%d place=%s", action, state["day"], state["slot"], state["place"])
        renpy.block_rollback()

    DG_RPG_MAP_IMAGE = "mods/don_gen/images/camp_map.png"
    # Coordinates grounded in the supplied 1920 x 1080 Sovyonok top-down map.
    DG_RPG_MAP_PINS = (
        ("gate", 382, 392), ("square", 855, 395),
        ("cabins", 733, 190), ("canteen", 885, 496),
        ("library", 1080, 270), ("clubs", 454, 485),
        ("stage", 905, 110), ("beach", 1170, 720),
        ("lake", 1010, 897), ("forest", 506, 135),
        ("infirmary", 880, 337), ("sports", 1310, 515)
    )

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
        candidates = [name for name in dg_runtime.original_images
                      if name.startswith(who + " ") and " pioneer " in (" " + name + " ")]
        if not candidates:
            candidates = [name for name in dg_runtime.original_images if name.startswith(who + " ")]
        candidates.sort()
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
                        mode="divergent", day=(state["day"] if state["day"] <= 7 else 7),
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

# Contrast-focused modal editor; avoids the tiny global Ren'Py input overlay.
style dg_rpg_edit_input is dg_ink_input:
    size 46
    color "#fff5d8"
    outlines []
    kerning 1

screen dg_rpg_edit_field(field, current):
    modal True
    default editor_text = current
    $ title = {"name": u"Имя героя", "age": u"Возраст героя", "days": u"Дней в смене", "history": u"Предыстория героя"}[field]
    $ tip = {"name": u"Как к тебе будут обращаться другие пионеры?",
             "age": u"Укажи число от 14 до 80.",
             "days": u"Укажи длину смены от 1 до 120 дней.",
             "history": u"Кто ты и как оказался в лагере? Эти сведения используются в сюжетных сценах."}[field]
    $ valid_edit = bool(editor_text.strip()) and (
        ((editor_text.isdigit() and 14 <= int(editor_text) <= 80) if field == "age"
         else (editor_text.isdigit() and 1 <= int(editor_text) <= 120) if field == "days"
         else True))
    add Solid("#061522f5")
    frame:
        background Solid("#18343ff8")
        padding (45, 37)
        align (0.5, 0.5)
        xsize 1110 ysize 510
        vbox:
            spacing 18
            text u"DON-GEN · НАСТРОЙКА ПЕРСОНАЖА" style "dg_meta" size 23
            text title style "dg_title" size 55
            text tip style "dg_text" size 28 xmaximum 995
            null height 11
            frame:
                background Solid("#071b25")
                padding (24, 19)
                xsize 1000 ysize 102
                if field == "age" or field == "days":
                    input:
                        value ScreenVariableInputValue("editor_text")
                        allow "0123456789"
                        length 3
                        xmaximum 925
                        style "dg_rpg_edit_input"
                        default_focus True
                elif field == "name":
                    input:
                        value ScreenVariableInputValue("editor_text")
                        length 35
                        xmaximum 925
                        style "dg_rpg_edit_input"
                        default_focus True
                else:
                    input:
                        value ScreenVariableInputValue("editor_text")
                        length 120
                        xmaximum 925
                        style "dg_rpg_edit_input"
                        default_focus True
            text u"Нажми на светлый текст в поле и введи значение. Применить — только после проверки." style "dg_text" size 22 color "#c9e0d7"
            hbox:
                spacing 48
                textbutton u"ПРИМЕНИТЬ" style "dg_primary" sensitive valid_edit action Return(("save", editor_text.strip()))
                textbutton u"ОТМЕНА" style "dg_act" action Return(("cancel", None))
    key "K_ESCAPE" action Return(("cancel", None))

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

# Map pins are drawn over the actual user-provided camp plan when installed.
# This layout also works without the PNG: the legend remains navigable.
style dg_map_pin is dg_act:
    background Solid("#102932ee")
    hover_background Solid("#466755f5")
    selected_background Solid("#ad8034e8")
    padding (10, 6)
style dg_map_pin_text is dg_text:
    size 23
    color "#f8eed1"
    hover_color "#ffe899"
    outlines [(1, "#051119", 0, 1)]

screen dg_rpg_map:
    modal True
    if renpy.loadable(DG_RPG_MAP_IMAGE):
        add DG_RPG_MAP_IMAGE
    else:
        add Solid("#94a65d")
        text u"Для красивой карты добавьте файл: game/mods/don_gen/images/camp_map.png" style "dg_text" xpos 350 ypos 800 size 25
    # Translucent header keeps the original map clearly visible.
    frame:
        background Solid("#10252de9")
        xpos 0 ypos 0 xsize 1920 ysize 108
        hbox:
            xpos 95 ypos 22 spacing 36
            text u"DON-GEN · СОВЁНОК" style "dg_meta" size 26
            text (u"День %d/%d · %s" % (dg_rpg_state["day"], dg_rpg_state["duration"], dg_rpg.SLOTS[dg_rpg_state["slot"]])) style "dg_text" size 27
            text (u"Вы сейчас: " + dg_rpg.PLACE_NAMES[dg_rpg_state["place"]]) style "dg_text" size 27 color "#ffe8a1"
    textbutton u"ЗАКРЫТЬ КАРТУ" style "dg_map_pin" xpos 1620 ypos 25 action Return(None)
    # Geographic points match the supplied map. Click any point for free travel.
    for slug, px, py in DG_RPG_MAP_PINS:
        $ loc_name = dg_rpg.PLACE_NAMES[slug]
        $ story_here = dg_world.event_at(dg_rpg_state, slug)
        $ others = dg_rpg.at_place(dg_rpg_state, slug)
        vbox:
            xpos px
            ypos py
            spacing 3
            textbutton (u"◆ " + loc_name if dg_rpg_state["place"] == slug else u"● " + loc_name) style "dg_map_pin" action Return(slug)
            if story_here:
                textbutton u"★ СЮЖЕТ" style "dg_map_pin" text_color "#ffdd88" action Return(slug)
            if others:
                frame:
                    background Solid("#10252dc9")
                    padding (8, 3)
                    text (u", ".join(person for who, person in others)) style "dg_text" size 18 color "#ffe8a1" xmaximum 240
    frame:
        background Solid("#10252de0")
        xpos 30 ypos 1010 xsize 1860 ysize 64
        hbox:
            xpos 30 ypos 14 spacing 30
            text u"● Выберите место: переход не расходует время" style "dg_text" size 22
            text u"◆ — ваше местоположение" style "dg_text" size 22 color "#ffe8a1"
            text u"★ Активный сюжет; выбери точку для встречи" style "dg_text" size 22 color "#ffe19b"

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
        $ day_event = dg_world.current(dg_rpg_state)
        if day_event:
            frame:
                background Solid("#1e3240ef")
                padding (22, 14)
                xsize 855
                vbox:
                    spacing 8
                    text (u"★ СЕГОДНЯ: " + day_event["title"]) style "dg_text" size 29 color "#ffe5a0"
                    text (u"Место события: " + dg_rpg.PLACE_NAMES[day_event["place"]] + u" · линия: " +
                          (dg_world.PLOTS[day_event["arc"]]["name"] if day_event["arc"] != "daily" else u"лагерные истории")) style "dg_text" size 22
                    textbutton (u"НАЧАТЬ СОБЫТИЕ" if dg_rpg_state["place"] == day_event["place"] else u"ОТПРАВИТЬСЯ К СОБЫТИЮ") style "dg_navlink" action Return(("world", None) if dg_rpg_state["place"] == day_event["place"] else ("world_travel", day_event["place"]))
        else:
            frame:
                background Solid("#172b32df")
                padding (20, 15)
                xsize 855
                text (u"Событие дня завершено. Можно исследовать лагерь и общаться с ребятами." if not dg_rpg_state["finished"] else u"Смена завершена. Итоги приключений доступны в хронике.") style "dg_text" size 25
        text dg_literal(dg_rpg_state["event"]) style "dg_small" size 22 xmaximum 850
        if dg_rpg_state["finished"]:
            textbutton u"ИТОГИ МОЕЙ СМЕНЫ" style "dg_primary" action Return(("finale", None))
        else:
            textbutton u"Открыть карту" style "dg_primary" action Return(("map", None))
        if not dg_rpg_state["finished"]:
            text u"ПОВСЕДНЕВНЫЕ ЗАНЯТИЯ" style "dg_meta"
            hbox:
                spacing 23
                textbutton u"Осмотреться" style "dg_act" action Return(("activity", "explore"))
                textbutton u"Помочь" style "dg_act" action Return(("activity", "help"))
                textbutton u"Заняться делом" style "dg_act" action Return(("activity", "practice"))
            textbutton u"Отдохнуть / пропустить время" style "dg_act" action Return(("activity", "rest"))
        textbutton u"Дневник, отношения и хроника" style "dg_act" action Return(("journal", None))
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
                                textbutton u"Диалог · выборы" style "dg_navlink" action Return(("talk", who)) sensitive (not dg_rpg_state["finished"] and dg_rpg_state["energy"] >= 8)
                                textbutton u"AI-сцена" style "dg_navlink" action Return(("ai", who)) sensitive not dg_rpg_state["finished"]
                                textbutton u"Спрайт" style "dg_navlink" action Return(("sprite", who)) sensitive not dg_rpg_state["finished"]
                            if dg_rpg.available_route_events(dg_rpg_state, who) and not dg_rpg_state["finished"]:
                                textbutton u"Сюжетный этап рута" style "dg_navlink" action Return(("route", who))
            text u"Разговоры и активности меняют время и отношения локально. AI-сцены вызываются только вручную." style "dg_small" size 23


screen dg_rpg_dialogue(who, phase, topic_index=0, stance="support"):
    modal True
    add dg_rpg_bg()
    add Solid("#07121add")
    $ speaking = dg_rpg.NPC_NAMES[who]
    $ portrait = dg_rpg_sprite(who)
    if portrait is not None:
        add portrait at dg_rpg_portrait_transform xpos 70 ypos 130
    if phase == "topics":
        $ scene = dg_dialogue.opening(dg_rpg_state, who)
    elif phase == "choice":
        $ scene = dg_dialogue.topic(dg_rpg_state, who, topic_index)
    else:
        $ scene = dg_dialogue.outcome(dg_rpg_state, who, topic_index, stance)
    frame:
        background Solid("#102530f4")
        xpos 530 ypos 115 xsize 1320 ysize 860
        padding (43, 35)
        vbox:
            spacing 11
            hbox:
                spacing 32
                text speaking style "dg_title" size 50 color "#ffe19b"
                text (u"ДЕНЬ %d · %s" % (dg_rpg_state["day"], dg_rpg.PLACE_NAMES[dg_rpg_state["place"]])) style "dg_meta" size 23
            text (scene.get("title", u"Разговор с " + speaking)) style "dg_sub" size 32
            frame:
                background Solid("#061824b7")
                padding (24, 18)
                xsize 1212 ysize 310
                viewport:
                    mousewheel True
                    scrollbars "vertical"
                    ysize 270
                    text dg_literal(scene["text"]) style "dg_text" size 29 xmaximum 1145
            if phase == "topics":
                text u"О ЧЁМ ПОГОВОРИТЬ?" style "dg_meta" size 23
            elif phase == "choice":
                text u"ЧТО ВЫ ОТВЕТИТЕ?" style "dg_meta" size 23
            else:
                text (u"Изменение отношений: +%d · %s: +%d" %
                      (dg_rpg_last_scene["affinity_gain"] if dg_rpg_last_scene else 0,
                       {"support": u"Доброта", "curious": u"Любознательность", "bold": u"Навык"}[stance],
                       2 if dg_rpg_last_scene and dg_rpg_last_scene["affinity_gain"] > 1 else 0)) style "dg_text" size 25 color "#ffe2a1"
            if phase != "result":
                for choice_id, caption in scene["options"]:
                    textbutton dg_literal(caption) style "dg_navlink" text_size 27 action Return(choice_id)
                textbutton u"Завершить разговор без выбора" style "dg_navlink" text_size 24 action Return(None)
            else:
                textbutton u"Закончить встречу" style "dg_primary" text_size 33 action Return("done")

screen dg_rpg_finale:
    modal True
    add Solid("#0e252f")
    use dg_chrome(u"ИТОГИ СМЕНЫ", Return(None))
    frame:
        background DG_PAPER
        xpos 260 ypos 175 xsize 1400 ysize 785
        padding (58, 39)
        vbox:
            spacing 16
            text u"Твоя история в Совёнке" style "dg_ink_title" size 50
            viewport:
                mousewheel True
                scrollbars "vertical"
                ysize 570
                text dg_literal(dg_world.finale(dg_rpg_state)) style "dg_ink_small" size 30 xmaximum 1260
            textbutton u"Вернуться к дневнику" style "dg_ink_act" action Return(None)

screen dg_rpg_world_event:
    modal True
    add dg_rpg_bg()
    add Solid("#081826d9")
    $ active = dg_world.event_at(dg_rpg_state, dg_rpg_state["place"])
    if active:
        $ nearby = dg_rpg_sprite(active["npc"])
        if nearby is not None:
            add nearby at dg_rpg_portrait_transform xpos 50 ypos 145
        frame:
            background Solid("#102831f4")
            xpos 505 ypos 110 xsize 1340 ysize 865
            padding (43, 32)
            vbox:
                spacing 13
                text (u"★ ЖИВОЙ СЮЖЕТ · ДЕНЬ %d" % dg_rpg_state["day"]) style "dg_meta" size 24 color "#ffdd98"
                text dg_literal(active["title"]) style "dg_title" size 48
                text (dg_rpg.PLACE_NAMES[active["place"]] + u" · " +
                      (dg_world.PLOTS[active["arc"]]["name"] if active["arc"] != "daily" else u"Повседневная история")) style "dg_sub" size 27
                frame:
                    background Solid("#061b26e5")
                    padding (22, 15)
                    xsize 1230 ysize 328
                    viewport:
                        ysize 288
                        mousewheel True
                        scrollbars "vertical"
                        text dg_literal(active["story"]) style "dg_text" size 29 xmaximum 1168
                text u"КАК ТЫ ПОСТУПИШЬ? РЕШЕНИЕ ИЗМЕНИТ СЛЕДУЮЩИЕ ДНИ" style "dg_meta" size 22 color "#ffda91"
                if dg_rpg_state["energy"] >= 8:
                    viewport:
                        ysize 225
                        mousewheel True
                        scrollbars "vertical"
                        vbox:
                            spacing 9
                            for choice in active["choices"]:
                                textbutton dg_literal(choice["text"]) style "dg_navlink" text_size 26 xmaximum 1165 action Return(choice["key"])
                else:
                    text u"Для сюжетного выбора нужно 8 энергии. Сначала отдохни." style "dg_text" size 27 color "#ffe19b"
                textbutton u"Вернуться в лагерь (решение можно принять позже)" style "dg_navlink" text_size 24 action Return(None)
    else:
        text u"На этом месте сегодня больше нет активных событий." style "dg_text" xpos 500 ypos 500
        textbutton u"Назад" style "dg_primary" xpos 1000 ypos 800 action Return(None)

screen dg_rpg_world_result(result):
    modal True
    add dg_rpg_bg()
    add Solid("#0a1b27ee")
    frame:
        background Solid("#122f3bef")
        align (0.5, 0.5)
        xsize 1470 ysize 875
        padding (54, 35)
        vbox:
            spacing 18
            text u"ПОСЛЕДСТВИЯ РЕШЕНИЯ" style "dg_meta" size 24 color "#ffe19b"
            text dg_literal(result["title"]) style "dg_title" size 49
            frame:
                background Solid("#081923e8")
                padding (25, 20)
                xsize 1360 ysize 435
                viewport:
                    ysize 390
                    mousewheel True scrollbars "vertical"
                    text dg_literal(result["text"]) style "dg_text" size 31 xmaximum 1290
            text (u"Лагерь: сплочённость %d · знания %d · свобода %d · ресурсы %d" %
                  (dg_rpg_state["world"]["morale"], dg_rpg_state["world"]["knowledge"],
                   dg_rpg_state["world"]["freedom"], dg_rpg_state["world"]["resources"])) style "dg_text" size 26 color "#ffe19b"
            textbutton u"Продолжить историю" style "dg_primary" action Return(None)

screen dg_rpg_journal:
    modal True
    default view = "timeline"
    add Solid("#142832")
    use dg_chrome(u"ДНЕВНИК", Return())
    text u"Дневник смены" style "dg_title" xpos 100 ypos 115 size 65
    hbox:
        xpos 100 ypos 215 spacing 28
        textbutton u"События" style "dg_navlink" selected view == "timeline" action SetScreenVariable("view", "timeline")
        textbutton u"Разговоры" style "dg_navlink" selected view == "talks" action SetScreenVariable("view", "talks")
        textbutton u"AI-сцены" style "dg_navlink" selected view == "ai" action SetScreenVariable("view", "ai")
        textbutton u"Хроника мира" style "dg_navlink" selected view == "world" action SetScreenVariable("view", "world")
    hbox:
        xpos 95 ypos 295 spacing 45
        frame:
            background Solid("#091a24")
            padding (23, 21)
            xsize 970 ysize 660
            viewport:
                mousewheel True
                scrollbars "vertical"
                ysize 610
                vbox:
                    spacing 16
                    if view == "timeline":
                        for row in dg_rpg_state["journal"][::-1]:
                            text (u"День %d · %s" % (row["day"], dg_rpg.SLOTS[row["slot"]])) style "dg_meta" size 20
                            text dg_literal(row["text"]) style "dg_text" size 26 xmaximum 855
                    elif view == "talks":
                        if not dg_rpg_state.get("dialogue_history"):
                            text u"Вы ещё не вели подробных разговоров. Встретьте персонажа и выберите тему беседы." style "dg_text" size 28 xmaximum 850
                        for item in dg_rpg_state.get("dialogue_history", [])[::-1]:
                            text (u"День %d · %s · %s" % (item["day"], dg_rpg.NPC_NAMES[item["who"]], item["topic"])) style "dg_meta" size 23
                            text dg_literal(item["text"]) style "dg_text" size 26 xmaximum 855
                            text (u"Отношения +%d" % item["affinity_gain"]) style "dg_text" size 22 color "#ffe19b"
                            null height 12
                    elif view == "world":
                        if not dg_rpg_state["world"]["chronicle"]:
                            text u"Лагерные истории только начинаются. Посетите место события дня и примите решение." style "dg_text" size 28 xmaximum 850
                        for item in dg_rpg_state["world"]["chronicle"][::-1]:
                            text (u"День %d · %s · %s" % (item["day"], item["title"],
                                  u"Пропущено" if item["status"] == "missed" else u"Событие сыграно")) style "dg_meta" size 23
                            text dg_literal(item["text"]) style "dg_text" size 26 xmaximum 855
                            null height 12
                    else:
                        if not dg_rpg_state["ai_scenes"]:
                            text u"Пока нет AI-сцен. Они создаются вручную через кнопку персонажа." style "dg_text" size 28
                        for item in dg_rpg_state["ai_scenes"][::-1]:
                            text (u"День %d · %s" % (item["day"], dg_rpg.NPC_NAMES[item["who"]])) style "dg_meta" size 23
                            text dg_literal(item["text"]) style "dg_text" size 26 xmaximum 855
                            null height 13
        frame:
            background Solid("#091a24")
            padding (24, 19)
            xsize 760 ysize 660
            viewport:
                mousewheel True scrollbars "vertical" ysize 610
                vbox:
                    spacing 13
                    text u"ХАРАКТЕРИСТИКИ" style "dg_meta" size 25
                    text (u"Энергия: %d/100" % dg_rpg_state["energy"]) style "dg_text" size 26
                    text (u"Любознательность: %d · Доброта: %d · Навык: %d" %
                          (dg_rpg_state["stats"]["curiosity"], dg_rpg_state["stats"]["kindness"],
                           dg_rpg_state["stats"]["skill"])) style "dg_text" size 23 xmaximum 680
                    null height 12
                    text u"СОСТОЯНИЕ ЛАГЕРЯ" style "dg_meta" size 25 color "#ffdf98"
                    text (u"Сплочённость: %d/100 · Знания: %d/100" %
                          (dg_rpg_state["world"]["morale"], dg_rpg_state["world"]["knowledge"])) style "dg_text" size 23
                    text (u"Свобода: %d/100 · Ресурсы: %d/100" %
                          (dg_rpg_state["world"]["freedom"], dg_rpg_state["world"]["resources"])) style "dg_text" size 23
                    null height 12
                    text u"СЮЖЕТНЫЕ ЛИНИИ" style "dg_meta" size 25
                    for plot in dg_world.PLOT_ORDER:
                        text (dg_world.PLOTS[plot]["name"] + u" · " +
                              str(dg_rpg_state["world"]["tracks"][plot]["stage"]) + u"/5") style "dg_text" size 25 color "#ffe4a1"
                        text dg_world.story_status(dg_rpg_state, plot) style "dg_text" size 21 xmaximum 680
                    null height 15
                    text u"ОТНОШЕНИЯ" style "dg_meta"
                    for who, name, morning, daytime, evening, night in dg_rpg.NPCS:
                        text (u"%s: %d/100 · %s" % (name, dg_rpg_state["affinity"][who], dg_rpg.route_label(dg_rpg_state["affinity"][who]))) style "dg_text" size 25
                    null height 18
                    text u"ЗАДАНИЯ" style "dg_meta"
                    for key, title, progress, goal in dg_rpg.quest_progress(dg_rpg_state):
                        text (u"%s: %d/%d%s" % (title, (progress if progress <= goal else goal), goal, u" ✓" if key in dg_rpg_state["quests_done"] else u"")) style "dg_text" size 24

screen dg_rpg_route_choice(who):
    modal True
    add dg_rpg_bg()
    add Solid("#071520e7")
    $ portrait = dg_rpg_sprite(who)
    if portrait is not None:
        add portrait at dg_rpg_portrait_transform xpos 65 ypos 125
    $ stage = dg_rpg.available_route_events(dg_rpg_state, who)[0]
    $ situation = dg_dialogue.route_intro(dg_rpg_state, who, stage[0])
    frame:
        background Solid("#102530f4")
        xpos 515 ypos 115 xsize 1320 ysize 865
        padding (40, 32)
        vbox:
            spacing 17
            text (u"РУТ: " + dg_rpg.NPC_NAMES[who] + u" · ЭТАП " + str(stage[0])) style "dg_title" size 46 color "#ffe19b"
            text dg_literal(situation["title"] + u" · " + stage[1]) style "dg_sub" size 30
            frame:
                background Solid("#071923dd")
                padding (23, 17)
                xsize 1210 ysize 345
                viewport:
                    mousewheel True scrollbars "vertical"
                    ysize 303
                    text dg_literal(situation["text"]) style "dg_text" size 28 xmaximum 1140
            text u"КАК ОТВЕТИТЬ?" style "dg_meta" size 24
            for choice, caption in situation["options"]:
                textbutton caption style "dg_navlink" text_size 28 sensitive (dg_rpg_state["energy"] >= 12) action Return(choice)
            if dg_rpg_state["energy"] < 12:
                text u"Для сюжетного события нужно 12 энергии." style "dg_text" size 24 color "#ffe19b"
            textbutton u"Вернуться позже" style "dg_navlink" text_size 25 action Return(None)

screen dg_rpg_route_result(who, level, stance):
    modal True
    add dg_rpg_bg()
    add Solid("#081a25e8")
    frame:
        background DG_PAPER
        padding (65, 52)
        align (0.5, 0.5) xsize 1250 ysize 670
        vbox:
            spacing 29
            text (u"Событие рута: " + dg_rpg.NPC_NAMES[who]) style "dg_ink_title"
            text dg_literal(dg_dialogue.route_conclusion(who, level, stance)) style "dg_ink_small" size 33 xmaximum 1100
            textbutton u"Продолжить смену" style "dg_ink_act" action Return(None)

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
        $ dg_edit_name = dg_create_cmd[1]
        if dg_edit_name == "name":
            $ dg_edit_current = dg_create_name
        elif dg_edit_name == "age":
            $ dg_edit_current = dg_create_age
        elif dg_edit_name == "days":
            $ dg_edit_current = dg_create_days
        else:
            $ dg_edit_current = dg_create_history
        call screen dg_rpg_edit_field(dg_edit_name, dg_edit_current)
        $ dg_edit_result = _return
        if dg_edit_result and dg_edit_result[0] == "save":
            if dg_edit_name == "name":
                $ dg_create_name = dg_edit_result[1]
            elif dg_edit_name == "age":
                $ dg_create_age = dg_edit_result[1]
            elif dg_edit_name == "days":
                $ dg_create_days = dg_edit_result[1]
            elif dg_edit_name == "history":
                $ dg_create_history = dg_edit_result[1]
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
    if dg_rpg_cmd == "finale":
        call screen dg_rpg_finale
        jump dg_rpg_loop
    if dg_rpg_cmd == "diag":
        call screen dg_diagnostics
        jump dg_rpg_loop
    if dg_rpg_cmd == "map":
        call screen dg_rpg_map
        if _return:
            $ dg_rpg_apply("move", _return)
            if dg_world.event_at(dg_rpg_state, dg_rpg_state["place"]):
                jump dg_rpg_world_label
        jump dg_rpg_loop
    if dg_rpg_cmd == "world_travel":
        $ dg_rpg_apply("move", dg_rpg_value)
        jump dg_rpg_world_label
    if dg_rpg_cmd == "world":
        jump dg_rpg_world_label
    if dg_rpg_cmd == "activity":
        $ dg_rpg_apply(dg_rpg_value)
        jump dg_rpg_loop
    if dg_rpg_cmd == "talk":
        $ dg_rpg_focus = dg_rpg_value
        if dg_rpg_state["energy"] < 8:
            jump dg_rpg_loop
        call screen dg_rpg_dialogue(dg_rpg_focus, "topics")
        if _return is None:
            jump dg_rpg_loop
        $ dg_rpg_talk_topic = int(_return)
        call screen dg_rpg_dialogue(dg_rpg_focus, "choice", dg_rpg_talk_topic)
        if _return is None:
            jump dg_rpg_loop
        $ dg_rpg_talk_stance = _return
        $ dg_rpg_apply("conversation", (dg_rpg_focus, dg_rpg_talk_topic, dg_rpg_talk_stance))
        call screen dg_rpg_dialogue(dg_rpg_focus, "result", dg_rpg_talk_topic, dg_rpg_talk_stance)
        jump dg_rpg_loop
    if dg_rpg_cmd == "route":
        $ dg_rpg_focus = dg_rpg_value
        $ dg_rpg_route_level = dg_rpg.available_route_events(dg_rpg_state, dg_rpg_focus)[0][0]
        call screen dg_rpg_route_choice(dg_rpg_focus)
        if _return:
            $ dg_rpg_route_stance = _return
            $ dg_rpg_apply("route", (dg_rpg_focus, dg_rpg_route_stance))
            call screen dg_rpg_route_result(dg_rpg_focus, dg_rpg_route_level, dg_rpg_route_stance)
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

label dg_rpg_world_label:
    if dg_rpg_state["finished"]:
        jump dg_rpg_loop
    if not dg_world.event_at(dg_rpg_state, dg_rpg_state["place"]):
        jump dg_rpg_loop
    call screen dg_rpg_world_event
    if _return:
        $ dg_rpg_world_stance = _return
        $ dg_rpg_apply("world", dg_rpg_world_stance)
        call screen dg_rpg_world_result(dg_rpg_last_world)
    jump dg_rpg_loop
