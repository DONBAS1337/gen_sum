# -*- coding: utf-8 -*-
# RPG sandbox. Loaded alongside don_gen.rpy; does not change classic stories.
init 1001 python:
    import json
    import os
    import logging
    import dg_rpg
    import dg_dialogue
    import dg_world
    import dg_social
    import dg_hybrid
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
        elif action == "free":
            store.dg_rpg_last_action = dg_rpg.free_action(state, arg)
        elif action == "personal":
            store.dg_rpg_last_personal = dg_rpg.personal_choice(state, arg[0], arg[1])
        elif action == "incident":
            store.dg_rpg_last_incident = dg_rpg.social_encounter(state, arg)
        elif action == "hybrid":
            store.dg_rpg_hybrid_entry = dg_hybrid.commit(state, arg[0], arg[1])
        elif action == "contract":
            store.dg_rpg_last_contract = dg_rpg.accept_contract(state, arg)
        else:
            dg_rpg.activity(state, action)
        dg_rpg.save(dg_rpg_root(), state)
        store.dg_rpg_state = state
        logging.getLogger("don_gen").info("RPG action=%s day=%d slot=%d place=%s", action, state["day"], state["slot"], state["place"])
        renpy.block_rollback()

    def dg_rpg_hybrid_preview(mode, action, who=None, topic=None):
        current = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        store.dg_rpg_hybrid_plan = dg_hybrid.preview(current, action, mode, who, topic)
        logging.getLogger("don_gen").info(
            "Hybrid preview mode=%s day=%d valid=%s", mode, current["day"],
            store.dg_rpg_hybrid_plan["status"] == "ready")

    def dg_rpg_hybrid_generate(plan):
        # The background worker ONLY generates a text string. No save writes.
        current = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        instructions, prompt = dg_hybrid.build_request(current, plan)
        app = dg_runtime.app
        if not app.models:
            app.refresh_models()
        model = dg_backend.default_model(app.models, persistent.dg_model)
        app.set_status(u"Пишем сцену с зафиксированным игровым исходом…")
        story = app.client.generate(instructions, prompt, model=model,
                                    effort=dg_backend.DEFAULT_EFFORT,
                                    fast_mode=persistent.dg_fast_mode)
        if not isinstance(story, basestring) or len(story.strip()) < 45 or len(story) > dg_hybrid.MAX_SCENE:
            raise ValueError("AI returned invalid scene length")
        return story.strip()

    DG_RPG_MAP_IMAGE = "mods/don_gen/images/camp_map.png"  # legacy optional image
    DG_MAP_ATLAS = "mods/don_gen/images/don_gen_atlas.png"
    DG_MAP_PIN_IDLE = im.Scale("mods/don_gen/images/map_idle.png", 42, 42)
    DG_MAP_PIN_HOVER = im.Scale("mods/don_gen/images/map_hover.png", 53, 53)
    DG_MAP_PIN_SELECTED = im.Scale("mods/don_gen/images/map_selected.png", 47, 47)
    DG_MAP_BADGE_STORY = im.Scale("mods/don_gen/images/map_story.png", 29, 29)
    DG_MAP_BADGE_QUEST = im.Scale("mods/don_gen/images/map_quest.png", 27, 27)
    DG_MAP_BADGE_MEET = im.Scale("mods/don_gen/images/map_encounter.png", 29, 29)
    DG_MAP_BADGE_NPC = im.Scale("mods/don_gen/images/map_character.png", 32, 32)
    # 1920x1080 hot zones matching the new illustrated 16:9 art (not text labels).
    DG_RPG_MAP_PINS = (
        ("gate",175,640), ("parking",85,595), ("square",944,558),
        ("cabins",735,278), ("cabins_south",615,733),
        ("canteen",1302,530), ("canteen_veranda",1283,625),
        ("library",1339,310), ("clubs",472,400), ("clubhouse",388,520),
        ("stage",1048,170), ("outdoor_stage",1108,250),
        ("beach",1425,802), ("lake",1010,928), ("forest",240,190),
        ("forest_path",380,338), ("infirmary",1122,480), ("sports",1570,450),
        ("music",450,225), ("administration",812,488), ("showers",640,572),
        ("washrooms",574,486), ("kitchen",1360,620), ("storage",1490,548),
        ("gym",1528,389), ("volleyball",1685,552), ("football",1812,604),
        ("badminton",1671,305), ("boathouse",1105,815), ("pier",1208,854),
        ("beachhouse",1590,726), ("island",697,949),
        ("island_far",1462,952), ("old_camp",387,853),
        ("campfire",518,790), ("radio",1115,363),
        ("headquarters",943,459), ("laundry",603,639),
        ("warehouse",1524,655)
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
        "sports": "bg ext_playground_day",
        "parking": "bg ext_camp_entrance_day",
        "music": "bg ext_clubs_day",
        "clubhouse": "bg ext_clubs_day",
        "administration": "bg ext_houses_day",
        "showers": "bg ext_houses_day",
        "washrooms": "bg ext_houses_day",
        "kitchen": "bg int_dining_hall_people_day",
        "storage": "bg ext_dining_hall_away_day",
        "gym": "bg ext_playground_day",
        "volleyball": "bg ext_playground_day",
        "football": "bg ext_playground_day",
        "badminton": "bg ext_playground_day",
        "canteen_veranda": "bg ext_dining_hall_away_day",
        "cabins_south": "bg ext_houses_day",
        "boathouse": "bg ext_boathouse_day",
        "pier": "bg ext_boathouse_day",
        "beachhouse": "bg ext_beach_day",
        "island": "bg ext_boathouse_day",
        "island_far": "bg ext_boathouse_day",
        "old_camp": "bg ext_houses_day",
        "campfire": "bg ext_polyana_day",
        "forest_path": "bg ext_path_day",
        "radio": "bg ext_clubs_day",
        "headquarters": "bg ext_square_day",
        "laundry": "bg ext_houses_day",
        "outdoor_stage": "bg ext_stage_normal_day",
        "warehouse": "bg ext_clubs_day"
    }

    def dg_rpg_bg():
        place = dg_rpg_state["place"]
        custom = dg_rpg.asset_path(dg_rpg_root(), dg_rpg_state["id"], "background", place)
        if custom and renpy.loadable(custom):
            return Image(custom)
        name = DG_RPG_BG.get(place)
        if not name and (place.startswith("cabin_") or place == "cabins_south"):
            name = DG_RPG_BG.get("cabins")
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
    if renpy.loadable(DG_MAP_ATLAS):
        add im.Scale(DG_MAP_ATLAS, 1920, 1080)
    else:
        add Solid("#182f34")
    add Solid("#06141dce")
    use dg_chrome(u"РЕЖИМ ПЕСОЧНИЦЫ", Return(("back", None)))
    frame:
        background Solid("#102b37e8")
        xpos 85 ypos 130 xsize 1750 ysize 830
        padding (50, 39)
        hbox:
            spacing 52
            vbox:
                xsize 895 spacing 20
                text u"СОВЁНОК БЕЗ ГРАНИЦ" style "dg_title" size 61 color "#ffe4aa"
                text u"Создай героя, выбирай события, пиши свои действия и наблюдай, как другие пионеры меняют лагерь даже без тебя." style "dg_text" size 30 xmaximum 835
                frame:
                    background Solid("#082330dd")
                    padding (26, 22) xsize 860
                    vbox:
                        spacing 15
                        text u"Новая смена" style "dg_meta" size 26 color "#ffdfaa"
                        text u"Свободная карта, персонажи и их истории, задания, локальные правила и необязательные AI-диалоги." style "dg_text" size 25 xmaximum 790
                        textbutton u"СОЗДАТЬ ПЕРСОНАЖА" style "dg_primary" action Return(("new", None))
                frame:
                    background Solid("#082330c8")
                    padding (26, 17) xsize 860
                    vbox:
                        spacing 10
                        text u"НЕ ТЕРЯЙ СВОЙ ПРОГРЕСС" style "dg_meta" size 24
                        text u"Смены хранятся отдельно от обычных сохранений БЛ. Можно вернуться в любой игровой день." style "dg_text" size 23 xmaximum 780
                textbutton u"ВЕРНУТЬСЯ В МЕНЮ" style "dg_act" action Return(("back", None))
            vbox:
                xsize 690 spacing 19
                text u"ПРОДОЛЖИТЬ ИСТОРИЮ" style "dg_title" size 45
                frame:
                    background Solid("#081f2ae6")
                    padding (22, 22) xsize 685 ysize 635
                    viewport:
                        scrollbars "vertical" mousewheel True ysize 585
                        vbox:
                            spacing 14
                            $ saved = dg_rpg.list_games(dg_rpg_root())
                            if not saved:
                                text u"Пока нет сохранённых смен. Создай первого персонажа." style "dg_text" size 27 xmaximum 600
                            for game in saved:
                                frame:
                                    background Solid("#22404d")
                                    padding (19, 17)
                                    xsize 600
                                    vbox:
                                        spacing 8
                                        text dg_literal(game["name"]) style "dg_text" size 34 color "#ffe5b5"
                                        text (u"День %d / %d  ·  %s" % (game["day"], game["duration"],
                                              u"Смена окончена" if game["finished"] else u"В лагере")) style "dg_text" size 25
                                        textbutton u"ПРОДОЛЖИТЬ" style "dg_navlink" action Return(("load", game["id"]))

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
    $ tip = {"name": u"Как к тебе будут обращаться другие пионеры? До 100 символов.",
             "age": u"Произвольный возраст от 1 до 999 999 999 лет. Игра не навязывает стандартные 14–80.",
             "days": u"Продолжительность от 1 до 120 дней (ограничение симуляции и расписаний).",
             "history": u"Расскажи подробную биографию, цели, вещи, характер и причину попадания в лагерь. До 8000 символов."}[field]
    $ valid_edit = bool(editor_text.strip()) and (
        ((editor_text.isdigit() and 1 <= int(editor_text) <= 999999999) if field == "age"
          else (editor_text.isdigit() and 1 <= int(editor_text) <= 120) if field == "days"
          else (len(editor_text) <= 100) if field == "name"
          else (len(editor_text) <= 8000)))
    add Solid("#07131cf5")
    frame:
        background Solid("#183744fc")
        padding (46, 34)
        align (0.5, 0.5)
        xsize 1440
        ysize (880 if field == "history" else 680)
        vbox:
            spacing 19
            text u"DON-GEN  /  РЕДАКТОР ПЕРСОНАЖА" style "dg_meta" size 24
            text title style "dg_title" size 58 color "#ffe3aa"
            text tip style "dg_text" size 27 xmaximum 1280
            frame:
                background Solid("#071b25")
                padding (25, 22)
                xsize 1310
                ysize (160 if field == "history" else 128)
                if field == "age":
                    input:
                        value ScreenVariableInputValue("editor_text")
                        allow "0123456789"
                        length 9
                        xmaximum 1220
                        style "dg_rpg_edit_input"
                        default_focus True
                elif field == "days":
                    input:
                        value ScreenVariableInputValue("editor_text")
                        allow "0123456789"
                        length 3
                        xmaximum 1220
                        style "dg_rpg_edit_input"
                        default_focus True
                elif field == "name":
                    input:
                        value ScreenVariableInputValue("editor_text")
                        length 100
                        xmaximum 1220
                        style "dg_rpg_edit_input"
                        default_focus True
                else:
                    input:
                        value ScreenVariableInputValue("editor_text")
                        length 8000
                        xmaximum 1220
                        style "dg_rpg_edit_input"
                        default_focus True
            if field == "history":
                text u"ПРЕДПРОСМОТР · текст автоматически переносится по ширине окна" style "dg_meta" size 23
                frame:
                    background Solid("#081e29")
                    padding (22, 19)
                    xsize 1310 ysize (min(365, max(195, 155 + len(editor_text) // 55 * 26)))
                    viewport:
                        mousewheel True
                        scrollbars "vertical"
                        ysize (min(325, max(155, 115 + len(editor_text) // 55 * 26)))
                        text dg_literal(editor_text if editor_text else u"Начни вводить историю — здесь появится читаемый перенос текста.") style "dg_text" size 29 xmaximum 1195
            else:
                text (u"Введено символов: %d" % len(editor_text)) style "dg_text" size 23
            text (u"Использовано: %d / 8000 символов" % len(editor_text) if field == "history"
                  else u"Ввод проверяется перед сохранением") style "dg_text" size 22 color "#b8d9d6"
            hbox:
                spacing 42
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
                    textbutton (dg_literal(dg_create_name[:65]) + (u"…" if len(dg_create_name) > 65 else u"") + u"  · ИЗМЕНИТЬ") style "dg_ink_act" action Return(("edit", "name"))
                    null height 11
                    text u"ВОЗРАСТ ГЕРОЯ" style "dg_ink_label"
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
                    textbutton (dg_literal(dg_create_history[:105]) + (u"…" if len(dg_create_history) > 105 else u"") + u"  · ИЗМЕНИТЬ") style "dg_ink_act" action Return(("edit", "history")) xmaximum 565
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
            $ dg_valid = bool(dg_create_name.strip() and dg_create_history.strip() and dg_create_age.isdigit() and dg_create_days.isdigit() and 1 <= int(dg_create_age) <= 999999999 and 1 <= int(dg_create_days) <= 120)
            hbox:
                spacing 44
                textbutton u"Начать смену" style "dg_ink_act" sensitive dg_valid action Return(("start",))
                textbutton u"Отмена" style "dg_ink_act" action Return(("cancel",))
            if not dg_valid:
                text u"Заполните имя/предысторию, возраст от 1, смена 1–120 дней." style "dg_ink_small" size 20 color "#b22e1f"

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
    default dg_map_hover = None
    # Custom generated DON-GEN map is preferred, legacy supplied map is fallback.
    if renpy.loadable(DG_MAP_ATLAS):
        add im.Scale(DG_MAP_ATLAS, 1920, 1080)
    elif renpy.loadable(DG_RPG_MAP_IMAGE):
        add DG_RPG_MAP_IMAGE
    else:
        add Solid("#78976b")
    add Solid("#10202919")
    # Small graphics are clickable; labels appear ONLY in the hover information card.
    for slug, px, py in DG_RPG_MAP_PINS:
        $ story_here = dg_world.event_at(dg_rpg_state, slug)
        $ quest_here = dg_social.quest_at(dg_rpg_state, slug)
        $ incident_here = dg_social.incident_at(dg_rpg_state, slug)
        $ locals_here = dg_rpg.at_place(dg_rpg_state, slug)
        imagebutton:
            idle (DG_MAP_PIN_SELECTED if dg_rpg_state["place"] == slug else DG_MAP_PIN_IDLE)
            hover DG_MAP_PIN_HOVER
            xpos px ypos py
            focus_mask True
            hovered SetScreenVariable("dg_map_hover", slug)
            unhovered SetScreenVariable("dg_map_hover", None)
            action Return(("cabins", slug) if slug in ("cabins", "cabins_south") else ("go", slug))
        if story_here:
            add DG_MAP_BADGE_STORY xpos (px + 30) ypos (py - 12)
        if quest_here:
            add DG_MAP_BADGE_QUEST xpos (px - 13) ypos (py - 18)
        if incident_here:
            add DG_MAP_BADGE_MEET xpos (px + 26) ypos (py + 28)
        if locals_here:
            # Character illustrations on the atlas, not a string of names.
            for index, pair in enumerate(locals_here[:3]):
                $ who = pair[0]
                $ mini = dg_rpg_sprite(who)
                if mini is not None:
                    add Transform(mini, zoom=0.068) xpos (px - 5 + index * 31) ypos (py + 33)
                else:
                    add DG_MAP_BADGE_NPC xpos (px + index * 24) ypos (py + 33)
    frame:
        background Solid("#102632ec")
        xpos 0 ypos 0 xsize 1920 ysize 94
        padding (68, 21)
        hbox:
            spacing 38
            text u"DON-GEN  /  КАРТА ЛАГЕРЯ" style "dg_meta" size 26 color "#f5edda"
            text (u"День %d/%d · %s · %s" % (dg_rpg_state["day"], dg_rpg_state["duration"],
                   dg_rpg.SLOTS[dg_rpg_state["slot"]], dg_world.weather(dg_rpg_state)[1])) style "dg_text" size 24
    textbutton u"ЗАКРЫТЬ" style "dg_map_pin" xpos 1690 ypos 19 action Return(("close", None))
    frame:
        background Solid("#102632ed")
        xpos 32 ypos 940 xsize 890 ysize 117
        padding (25, 12)
        vbox:
            spacing 8
            if dg_map_hover in dg_rpg.PLACE_NAMES:
                text dg_rpg.PLACE_NAMES[dg_map_hover] style "dg_text" size 32 color "#ffe2aa"
                $ hover_people = dg_rpg.at_place(dg_rpg_state, dg_map_hover)
                text (u"Здесь: " + u", ".join(name for code, name in hover_people) if hover_people else u"Никого из знакомых поблизости") style "dg_text" size 23
            else:
                text u"НАВЕДИ НА МАРКЕР · нажми для перехода" style "dg_meta" size 26 color "#ffe2aa"
                text u"Карта доступна свободно: путешествие не тратит время." style "dg_text" size 23
    frame:
        background Solid("#102632ed")
        xpos 1020 ypos 950 xsize 850 ysize 102
        padding (24, 10)
        hbox:
            spacing 14
            add DG_MAP_BADGE_STORY
            text u"История" style "dg_text" size 20
            add DG_MAP_BADGE_QUEST
            text u"Поручение" style "dg_text" size 20
            add DG_MAP_BADGE_MEET
            text u"Встреча" style "dg_text" size 20

screen dg_rpg_cabins(region):
    modal True
    add dg_rpg_bg()
    add Solid("#0b1b24ed")
    frame:
        background Solid("#14313df4")
        align (0.5, 0.5) xsize 1670 ysize 860 padding (38, 33)
        vbox:
            spacing 18
            text u"ЖИЛАЯ ЗОНА · ДОМИКИ" style "dg_title" size 53 color "#ffdcab"
            text u"Здесь можно посетить общий двор или любой из 31 домика. Все точки доступны независимо от сюжетного расписания." style "dg_text" size 26 xmaximum 1510
            hbox:
                spacing 35
                textbutton u"ОБЩИЙ ДВОР" style "dg_primary" action Return(("go", region))
                textbutton u"НАЗАД НА КАРТУ" style "dg_act" action Return(("close", None))
            viewport:
                mousewheel True
                scrollbars "vertical"
                ysize 615
                grid 8 4:
                    spacing 9
                    for cabin_number in range(1, 32):
                        textbutton (u"Домик %02d" % cabin_number) style "dg_map_pin" text_size 23 action Return(("go", "cabin_%02d" % cabin_number))
                    null

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
    viewport:
        xpos 96 ypos 132 xsize 960 ysize 815
        mousewheel True
        scrollbars "vertical"
        vbox:
            spacing 12
            xsize 895
            text dg_rpg.camp_time(dg_rpg_state) style "dg_title" size 59
            text dg_literal(u"%s, %d лет · %s" % (dg_rpg_state["hero"]["name"], dg_rpg_state["hero"]["age"], dg_rpg_state["hero"]["background"])) style "dg_sub" size 28
            text (u"Энергия: %d/100   ·   Любознательность: %d   ·   Доброта: %d   ·   Навык: %d" %
                  (dg_rpg_state["energy"], dg_rpg_state["stats"]["curiosity"], dg_rpg_state["stats"]["kindness"], dg_rpg_state["stats"]["skill"])) style "dg_small"
            text (u"Погода: " + dg_world.weather(dg_rpg_state)[1] + u" · Встречи и прогулки зависят от погоды") style "dg_small" size 23 color "#ffe3ae"
            $ day_event = dg_world.current(dg_rpg_state)
            if day_event:
                frame:
                    background Solid("#1e3240ef")
                    padding (22, 14)
                    xsize 855
                    vbox:
                        spacing 8
                        text (u"СЕГОДНЯ: " + day_event["title"]) style "dg_text" size 29 color "#ffe5a0"
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
            $ active_incident = dg_social.incident_at(dg_rpg_state, dg_rpg_state["place"])
            if active_incident:
                frame:
                    background Solid("#39412be8")
                    padding (18, 13)
                    xsize 855
                    vbox:
                        spacing 7
                        text (u"ВСТРЕЧА МЕЖДУ NPC: " + active_incident["title"]) style "dg_text" size 28 color "#ffe5a0"
                        textbutton u"ВМЕШАТЬСЯ В СОБЫТИЕ" style "dg_navlink" action Return(("incident", None)) sensitive dg_rpg_state["energy"] >= 9
            if not dg_rpg_state["finished"]:
                text u"ПОВСЕДНЕВНЫЕ ЗАНЯТИЯ" style "dg_meta"
                hbox:
                    spacing 23
                    textbutton u"Осмотреться" style "dg_act" action Return(("activity", "explore"))
                    textbutton u"Помочь" style "dg_act" action Return(("activity", "help"))
                    textbutton u"Заняться делом" style "dg_act" action Return(("activity", "practice"))
                textbutton u"Отдохнуть / пропустить время" style "dg_act" action Return(("activity", "rest"))
            if not dg_rpg_state["finished"]:
                textbutton u"СВОБОДНОЕ ДЕЙСТВИЕ · написать свой поступок" style "dg_primary" action Return(("free", None))
                textbutton u"ГИБРИДНАЯ СЦЕНА · действие + реакция AI" style "dg_act" action Return(("hybrid", None))
                textbutton u"ПОРУЧЕНИЯ · длинные задания" style "dg_act" action Return(("contracts", None))
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
                                textbutton u"Своя реплика + AI" style "dg_navlink" text_size 23 action Return(("hybrid_npc", who)) sensitive not dg_rpg_state["finished"]
                                textbutton u"Спрайт" style "dg_navlink" action Return(("sprite", who)) sensitive not dg_rpg_state["finished"]
                            if dg_social.personal_scene(dg_rpg_state, who) and not dg_rpg_state["finished"]:
                                textbutton u"ЛИЧНАЯ ИСТОРИЯ" style "dg_navlink" text_size 24 text_color "#f8d995" action Return(("personal", who)) sensitive dg_rpg_state["energy"] >= 12
                            if dg_rpg.available_route_events(dg_rpg_state, who) and not dg_rpg_state["finished"]:
                                textbutton u"Сюжетный этап рута" style "dg_navlink" action Return(("route", who))
            text u"Разговоры и активности меняют время и отношения локально. AI-сцены вызываются только вручную." style "dg_small" size 23


# Player-defined actions are resolved by a transparent local interpreter.
screen dg_rpg_hybrid_input(mode, who=None):
    modal True
    default action_text = u""
    add dg_rpg_bg()
    add Solid("#041622ee")
    frame:
        background Solid("#142f3df8")
        align (0.5, 0.5) xsize 1490 ysize 940
        padding (50, 32)
        vbox:
            spacing 16
            text (u"СВОЯ РЕПЛИКА" if mode == "npc" else u"СВОЙ ПОСТУПОК В СЮЖЕТЕ" if mode == "world" else u"СВОБОДНОЕ ДЕЙСТВИЕ + AI") style "dg_title" size 53 color "#ffe0a2"
            text (u"Напиши, что говоришь собеседнику. Модель создаст реакцию без вымышленных наград." if mode == "npc"
                  else u"Свой вариант решения события. Движок определит допустимый исход до AI." if mode == "world"
                  else u"Опиши своё действие. Последствия рассчитываются до генерации сцены.") style "dg_text" size 27 xmaximum 1345
            frame:
                background Solid("#081b27")
                padding (24, 22)
                xsize 1370 ysize 145
                input:
                    value ScreenVariableInputValue("action_text")
                    style "dg_rpg_edit_input"
                    length 4000
                    xmaximum 1290
                    default_focus True
            text (u"ПРЕДПРОСМОТР ТВОЕГО ТЕКСТА · %d / 4000" % len(action_text)) style "dg_meta" size 22
            frame:
                background Solid("#071e29")
                padding (21, 18)
                xsize 1370 ysize (min(310, max(140, 140 + len(action_text) // 80 * 24)))
                viewport:
                    mousewheel True scrollbars "vertical"
                    ysize (min(270, max(100, 100 + len(action_text) // 80 * 24)))
                    text dg_literal(action_text if action_text else u"Текст здесь будет переноситься автоматически, чтобы даже длинная реплика оставалась читаемой.") style "dg_text" size 27 xmaximum 1280
            text u"Любые игровые награды и изменения рассчитывает локальный движок. Модель отвечает только за повествование." style "dg_text" size 24 xmaximum 1310
            hbox:
                spacing 38
                textbutton u"ПРОВЕРИТЬ ПОСЛЕДСТВИЯ" style "dg_primary" sensitive bool(action_text.strip()) action Return(action_text.strip())
                textbutton u"ОТМЕНА" style "dg_act" action Return(None)
    key "K_ESCAPE" action Return(None)

screen dg_rpg_hybrid_review(plan):
    modal True
    add dg_rpg_bg()
    add Solid("#071a25ef")
    frame:
        background Solid("#13313df9")
        align (0.5, 0.5) xsize 1420 ysize 865
        padding (50, 39)
        vbox:
            spacing 19
            text u"ПОСЛЕДСТВИЯ ПРОВЕРЕНЫ ДВИЖКОМ" style "dg_title" size 43 color "#ffe0a2"
            if plan["status"] != "ready":
                text dg_literal(plan["message"]) style "dg_text" size 30 xmaximum 1270
                text u"Никаких изменений сохранения не сделано." style "dg_text" size 24
                textbutton u"ИЗМЕНИТЬ ТЕКСТ" style "dg_primary" action Return("retry")
                textbutton u"ОТМЕНИТЬ" style "dg_act" action Return("cancel")
            else:
                text dg_literal(u"Твоё действие: " + plan["action"]) style "dg_text" size 29 xmaximum 1265
                frame:
                    background Solid("#071d27")
                    padding (21, 14)
                    xsize 1300 ysize 305
                    viewport:
                        mousewheel True scrollbars "vertical" ysize 265
                        text dg_literal(plan["result"]["text"]) style "dg_text" size 29 xmaximum 1215
                text u"РЕАЛЬНЫЕ ИЗМЕНЕНИЯ ПОСЛЕ ПОДТВЕРЖДЕНИЯ" style "dg_meta" size 23
                frame:
                    background Solid("#172a29")
                    padding (18, 15)
                    xsize 1300 ysize 125
                    viewport:
                        mousewheel True scrollbars "vertical" ysize 90
                        vbox:
                            spacing 5
                            if plan["effects"]:
                                for item in plan["effects"]:
                                    text dg_literal(item) style "dg_text" size 25
                            else:
                                text u"Изменения мира не предусмотрены." style "dg_text" size 25
                text u"Ни один эффект пока не применён. Можно сыграть локально или заказать только художественный текст." style "dg_text" size 23 xmaximum 1260
                hbox:
                    spacing 25
                    textbutton u"AI · СЦЕНА + ЭФФЕКТЫ" style "dg_primary" action Return("ai")
                    textbutton u"ЛОКАЛЬНО · БЕЗ AI" style "dg_act" action Return("local")
                hbox:
                    spacing 38
                    textbutton u"ИЗМЕНИТЬ" style "dg_navlink" action Return("retry")
                    textbutton u"ОТМЕНА" style "dg_navlink" action Return("cancel")

screen dg_rpg_hybrid_read(entry):
    modal True
    add dg_rpg_bg()
    add Solid("#071621ec")
    frame:
        background Solid("#14313beb")
        align (0.5, 0.5) xsize 1530 ysize 900
        padding (53, 38)
        vbox:
            spacing 19
            text (u"AI-СЦЕНА" if entry["narrated_by_ai"] else u"СЦЕНА БЕЗ AI") style "dg_title" size 45 color "#ffe2a3"
            frame:
                background Solid("#071b28")
                padding (23, 19)
                xsize 1410 ysize 545
                viewport:
                    mousewheel True scrollbars "vertical" ysize 490
                    text dg_literal(entry["scene"] if entry["scene"] else entry["result"]) style "dg_text" size 29 xmaximum 1330
            text u"ИГРОВЫЕ ПОСЛЕДСТВИЯ · зафиксированы движком, а не моделью" style "dg_meta" size 22
            text dg_literal(u" · ".join(entry["effects"]) if entry["effects"] else u"Показатели не менялись.") style "dg_text" size 24 xmaximum 1390
            textbutton u"ПРОДОЛЖИТЬ" style "dg_primary" action Return(None)

screen dg_rpg_free_input:
    modal True
    default action_text = u""
    add dg_rpg_bg()
    add Solid("#041725ee")
    frame:
        background Solid("#143240fa")
        align (0.5, 0.5) xsize 1480 ysize 900
        padding (54, 36)
        vbox:
            spacing 21
            text u"СВОБОДНОЕ ДЕЙСТВИЕ" style "dg_title" size 56 color "#ffe5a0"
            text u"Опиши, что делает герой. Правила проверят присутствие персонажей, локацию, энергию и смысл действия." style "dg_text" size 27 xmaximum 1340
            frame:
                background Solid("#071b25")
                padding (24, 20)
                xsize 1350 ysize 146
                input:
                    value ScreenVariableInputValue("action_text")
                    style "dg_rpg_edit_input"
                    length 4000
                    xmaximum 1290
                    default_focus True
            text (u"ПРЕДПРОСМОТР · %d / 4000" % len(action_text)) style "dg_meta" size 23
            frame:
                background Solid("#09242e")
                padding (20, 15) xsize 1350
                ysize (min(300, max(140, 140 + len(action_text) // 80 * 24)))
                viewport:
                    mousewheel True scrollbars "vertical"
                    ysize (min(260, max(100, 100 + len(action_text) // 80 * 24)))
                    text dg_literal(action_text if action_text else u"Здесь будет показана длинная реплика с переносом строк.") style "dg_text" size 28 xmaximum 1260
            text u"Например: «Помочь Мику с репетицией». Неизвестное действие не расходует ход. Можно выбрать гибридную AI-сцену отдельно." style "dg_text" size 23 color "#b9d4d6" xmaximum 1290
            hbox:
                spacing 45
                textbutton u"СОВЕРШИТЬ ПОСТУПОК" style "dg_primary" sensitive bool(action_text.strip()) action Return(action_text.strip())
                textbutton u"ОТМЕНА" style "dg_act" action Return(None)
    key "K_ESCAPE" action Return(None)

screen dg_rpg_action_result(result):
    modal True
    add dg_rpg_bg()
    add Solid("#081c27f0")
    frame:
        background Solid("#13323a")
        align (0.5, 0.5)
        xsize 1380 ysize 810
        padding (48, 39)
        vbox:
            spacing 22
            text dg_literal(result.get("title", u"ТВОЙ ПОСТУПОК")) style "dg_title" size 49 color "#ffe5a0"
            frame:
                background Solid("#071a25")
                padding (22, 18)
                xsize 1265 ysize 535
                viewport:
                    mousewheel True scrollbars "vertical" ysize 490
                    text dg_literal(result["text"]) style "dg_text" size 30 xmaximum 1195
            textbutton u"Вернуться в лагерь" style "dg_primary" action Return(None)

screen dg_rpg_npc_incident:
    modal True
    add dg_rpg_bg()
    add Solid("#061924e8")
    $ event = dg_social.incident_at(dg_rpg_state, dg_rpg_state["place"])
    if event:
        frame:
            background Solid("#12333bf6")
            align (0.5, 0.5)
            xsize 1380 ysize 810
            padding (49, 40)
            vbox:
                spacing 23
                text u"СОБЫТИЕ МЕЖДУ ПЕРСОНАЖАМИ" style "dg_meta" size 25 color "#ffe5a0"
                text dg_literal(event["title"]) style "dg_title" size 51
                frame:
                    background Solid("#071a24")
                    padding (25, 20)
                    xsize 1260 ysize 270
                    viewport:
                        mousewheel True scrollbars "vertical" ysize 225
                        text dg_literal(event["text"]) style "dg_text" size 31 xmaximum 1185
                text (u"Их отношение сейчас: " + str(dg_social.bond(dg_rpg_state, event["pair"][0], event["pair"][1]))) style "dg_text" size 26 color "#ffe5a0"
                for code, title in dg_social.INCIDENT_CHOICES:
                    textbutton title style "dg_navlink" text_size 28 sensitive dg_rpg_state["energy"] >= 9 action Return(code)
                textbutton u"Не вмешиваться сейчас" style "dg_navlink" text_size 26 action Return(None)
    else:
        text u"Участники уже разошлись. Сегодня эта встреча закончилась." style "dg_text" xpos 360 ypos 500
        textbutton u"Закрыть" style "dg_primary" xpos 850 ypos 800 action Return(None)

screen dg_rpg_personal(who):
    modal True
    add dg_rpg_bg()
    add Solid("#081923dd")
    $ scene = dg_social.personal_scene(dg_rpg_state, who)
    $ portrait = dg_rpg_sprite(who)
    if portrait is not None:
        add portrait at dg_rpg_portrait_transform xpos 75 ypos 155
    frame:
        background Solid("#122f39f0")
        xpos 510 ypos 112 xsize 1330 ysize 840
        padding (48, 37)
        vbox:
            spacing 24
            text (u"ЛИЧНАЯ ИСТОРИЯ · " + dg_social.NAMES[who]) style "dg_meta" size 25 color "#ffe5a0"
            text dg_literal(scene["title"]) style "dg_title" size 50
            frame:
                background Solid("#081c26d9")
                padding (25, 20)
                xsize 1220 ysize 318
                viewport:
                    mousewheel True scrollbars "vertical" ysize 270
                    text dg_literal(scene["text"]) style "dg_text" size 32 xmaximum 1140
            text u"ОТ ТЕБЯ ЗАВИСИТ, КАК ПРОДОЛЖИТСЯ ВАША ИСТОРИЯ" style "dg_meta" size 23
            for code, caption in scene["choices"]:
                textbutton caption style "dg_navlink" text_size 27 action Return(code)
            textbutton u"Вернуться к разговору позже" style "dg_navlink" text_size 24 action Return(None)

screen dg_rpg_contracts:
    modal True
    add Solid("#102a35")
    use dg_chrome(u"ДОЛГОСРОЧНЫЕ ПОРУЧЕНИЯ", Return(None))
    text u"Дела, за которые отвечаешь" style "dg_title" size 62 xpos 110 ypos 115
    text u"Принятые задания выполняются через свободные действия в нужном месте. Сроки идут, даже пока ты занят другими историями." style "dg_sub" size 25 xpos 115 ypos 210 xmaximum 1610
    frame:
        background Solid("#0b202b")
        xpos 105 ypos 287 xsize 1710 ysize 680
        padding (35, 27)
        viewport:
            mousewheel True scrollbars "vertical" ysize 610
            vbox:
                spacing 24
                for entry in dg_social.quest_list(dg_rpg_state):
                    frame:
                        background Solid("#18353ce7")
                        padding (22, 19)
                        xsize 1580
                        vbox:
                            spacing 11
                            text dg_literal(entry["title"]) style "dg_title" size 34 color "#ffdfa0"
                            if entry["status"] == "available":
                                text (u"Этапы: %d. Срок: %d дней с момента принятия." % (entry["total"], entry["limit"])) style "dg_text" size 24
                                textbutton u"ПРИНЯТЬ ПОРУЧЕНИЕ" style "dg_navlink" action Return(("accept", entry["id"]))
                            elif entry["status"] == "active":
                                text (u"В работе: %d/%d · срок до дня %d" % (entry["step"], entry["total"], entry["deadline"])) style "dg_text" size 25
                                text dg_literal(entry["task"]) style "dg_text" size 26 xmaximum 1445
                                textbutton u"ПЕРЕЙТИ К МЕСТУ ЗАДАНИЯ" style "dg_navlink" action Return(("travel", dg_social.QUESTS[entry["id"]][4][entry["step"]][0]))
                            elif entry["status"] == "completed":
                                text u"ВЫПОЛНЕНО · награда получена · результаты влияют на другие истории" style "dg_text" size 25 color "#aadbb3"
                            else:
                                text u"СРОК ИСТЁК · другие пионеры продолжили дело без тебя" style "dg_text" size 25 color "#f4b0a9"

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
                textbutton u"НАПИСАТЬ СВОЮ РЕПЛИКУ · AI-РЕАКЦИЯ" style "dg_navlink" text_size 25 action Return("custom")
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
            textbutton u"Вернуться в лагерь" style "dg_ink_act" action Return(None)

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
            xpos 505 ypos 95 xsize 1340 ysize 930
            padding (39, 25)
            vbox:
                spacing 8
                text (u"ЖИВОЙ СЮЖЕТ · ДЕНЬ %d" % dg_rpg_state["day"]) style "dg_meta" size 24 color "#ffdd98"
                text dg_literal(active["title"]) style "dg_title" size 48
                text (dg_rpg.PLACE_NAMES[active["place"]] + u" · " +
                      (dg_world.PLOTS[active["arc"]]["name"] if active["arc"] != "daily" else u"Повседневная история")) style "dg_sub" size 27
                frame:
                    background Solid("#061b26e5")
                    padding (22, 15)
                    xsize 1230 ysize 270
                    viewport:
                        ysize 232
                        mousewheel True
                        scrollbars "vertical"
                        text dg_literal(active["story"]) style "dg_text" size 29 xmaximum 1168
                text u"КАК ТЫ ПОСТУПИШЬ? РЕШЕНИЕ ИЗМЕНИТ СЛЕДУЮЩИЕ ДНИ" style "dg_meta" size 22 color "#ffda91"
                if dg_rpg_state["energy"] >= 8:
                    viewport:
                        ysize 184
                        mousewheel True
                        scrollbars "vertical"
                        vbox:
                            spacing 9
                            for choice in active["choices"]:
                                textbutton dg_literal(choice["text"]) style "dg_navlink" text_size 26 xmaximum 1165 action Return(choice["key"])
                else:
                    text u"Для сюжетного выбора нужно 8 энергии. Сначала отдохни." style "dg_text" size 27 color "#ffe19b"
                textbutton u"НАПИСАТЬ СВОЁ ДЕЙСТВИЕ · гибридная сцена" style "dg_navlink" text_size 24 sensitive (dg_rpg_state["energy"] >= 8) action Return("custom")
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
        textbutton u"Люди и слухи" style "dg_navlink" selected view == "social" action SetScreenVariable("view", "social")
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
                    elif view == "social":
                        text u"ЖИЗНЬ ЛАГЕРЯ БЕЗ ТЕБЯ" style "dg_meta" size 25 color "#ffe5a0"
                        if not dg_rpg_state["social"]["rumours"]:
                            text u"Пока ничего необычного. Новые слухи появляются со временем." style "dg_text" size 25
                        for item in dg_rpg_state["social"]["rumours"][::-1]:
                            text (u"День %d" % item["day"]) style "dg_meta" size 22
                            text dg_literal(item["text"]) style "dg_text" size 26 xmaximum 850
                        text u"ЛИЧНЫЕ ИСТОРИИ" style "dg_meta" size 25 color "#ffe5a0"
                        for who, name in dg_social.NAMES.items():
                            if who != "uv" or dg_rpg_state.get("mystery", {}).get("yulia_discovered", False):
                                text (name + u": " + str(dg_rpg_state["social"]["personal"].get(who, 0)) + u"/3 этапов") style "dg_text" size 24
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
                    if view == "social":
                        text u"ОТНОШЕНИЯ МЕЖДУ NPC" style "dg_meta" size 25 color "#ffdf98"
                        for a, b, initial, caption, description in dg_social.PAIR_DEFS:
                            if dg_rpg_state.get("mystery", {}).get("yulia_discovered", False) or "uv" not in (a, b):
                                text (caption + u": " + str(dg_social.bond(dg_rpg_state, a, b))) style "dg_text" size 25
                        null height 14
                        text u"ДОЛГОСРОЧНЫЕ ПОРУЧЕНИЯ" style "dg_meta" size 25
                        for item in dg_social.quest_list(dg_rpg_state):
                            text (item["title"] + u": " +
                                  (u"Не принято" if item["status"] == "available"
                                   else u"В процессе" if item["status"] == "active"
                                   else u"Готово" if item["status"] == "completed" else u"Просрочено")) style "dg_text" size 23
                        null height 15
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
                        if who != "uv" or dg_rpg_state.get("mystery", {}).get("yulia_discovered", False):
                            text (u"%s: %d/100 · %s" % (name, dg_rpg_state["affinity"][who], dg_rpg.route_label(dg_rpg_state["affinity"][who]))) style "dg_text" size 25
                    null height 18
                    text u"ЗАДАНИЯ" style "dg_meta"
                    for key, title, progress, goal in dg_rpg.quest_progress(dg_rpg_state):
                        text (u"%s: %d/%d%s" % (title, (progress if progress <= goal else goal), goal, u" (готово)" if key in dg_rpg_state["quests_done"] else u"")) style "dg_text" size 24

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
        $ dg_map_result = _return
        if isinstance(dg_map_result, tuple) and len(dg_map_result) == 2 and dg_map_result[0] == "cabins":
            call screen dg_rpg_cabins(dg_map_result[1])
            $ dg_map_result = _return
        # A Ren'Py context/splashscreen sentinel is NOT a valid location ID.
        if isinstance(dg_map_result, tuple) and len(dg_map_result) == 2 and dg_map_result[0] == "go" and dg_map_result[1] in dg_rpg.PLACE_NAMES:
            $ dg_rpg_apply("move", dg_map_result[1])
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
    if dg_rpg_cmd == "hybrid":
        $ dg_rpg_hybrid_mode = "free"
        $ dg_rpg_hybrid_who = None
        $ dg_rpg_hybrid_topic = None
        jump dg_rpg_hybrid_entry
    if dg_rpg_cmd == "hybrid_npc":
        $ dg_rpg_hybrid_mode = "npc"
        $ dg_rpg_hybrid_who = dg_rpg_value
        $ dg_rpg_hybrid_topic = None
        jump dg_rpg_hybrid_entry
    if dg_rpg_cmd == "free":
        call screen dg_rpg_free_input
        if _return:
            $ dg_rpg_apply("free", _return)
            call screen dg_rpg_action_result(dg_rpg_last_action)
        jump dg_rpg_loop
    if dg_rpg_cmd == "contracts":
        call screen dg_rpg_contracts
        if _return:
            $ dg_contract_cmd, dg_contract_id = _return
            if dg_contract_cmd == "accept":
                $ dg_rpg_apply("contract", dg_contract_id)
                $ dg_rpg_contract_result = {"title": u"ПОРУЧЕНИЕ ПРИНЯТО", "text": dg_rpg_last_contract}
                call screen dg_rpg_action_result(dg_rpg_contract_result)
            elif dg_contract_cmd == "travel":
                $ dg_rpg_apply("move", dg_contract_id)
        jump dg_rpg_loop
    if dg_rpg_cmd == "incident":
        if dg_social.incident_at(dg_rpg_state, dg_rpg_state["place"]):
            call screen dg_rpg_npc_incident
            if _return:
                $ dg_rpg_incident_choice = _return
                $ dg_rpg_apply("incident", dg_rpg_incident_choice)
                $ dg_rpg_incident_result = {"title":dg_rpg_last_incident["title"],"text":dg_rpg_last_incident["text"]}
                call screen dg_rpg_action_result(dg_rpg_incident_result)
        jump dg_rpg_loop
    if dg_rpg_cmd == "personal":
        $ dg_rpg_focus = dg_rpg_value
        if dg_social.personal_scene(dg_rpg_state, dg_rpg_focus):
            call screen dg_rpg_personal(dg_rpg_focus)
            if _return:
                $ dg_rpg_personal_stance = _return
                $ dg_rpg_apply("personal", (dg_rpg_focus, dg_rpg_personal_stance))
                $ dg_rpg_personal_result = {"title": dg_rpg_last_personal["title"], "text": dg_rpg_last_personal["text"]}
                call screen dg_rpg_action_result(dg_rpg_personal_result)
        jump dg_rpg_loop
    if dg_rpg_cmd == "talk":
        $ dg_rpg_focus = dg_rpg_value
        if dg_rpg_state["energy"] < 8:
            jump dg_rpg_loop
        call screen dg_rpg_dialogue(dg_rpg_focus, "topics")
        if _return == "custom":
            $ dg_rpg_hybrid_mode = "npc"
            $ dg_rpg_hybrid_who = dg_rpg_focus
            $ dg_rpg_hybrid_topic = None
            jump dg_rpg_hybrid_entry
        if _return is None:
            jump dg_rpg_loop
        $ dg_rpg_talk_topic = int(_return)
        call screen dg_rpg_dialogue(dg_rpg_focus, "choice", dg_rpg_talk_topic)
        if _return == "custom":
            $ dg_rpg_hybrid_mode = "npc"
            $ dg_rpg_hybrid_who = dg_rpg_focus
            $ dg_rpg_hybrid_topic = dg_rpg_talk_topic
            jump dg_rpg_hybrid_entry
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
    if _return == "custom":
        $ dg_rpg_hybrid_mode = "world"
        $ dg_rpg_hybrid_who = None
        $ dg_rpg_hybrid_topic = None
        jump dg_rpg_hybrid_entry
    if _return:
        $ dg_rpg_world_stance = _return
        $ dg_rpg_apply("world", dg_rpg_world_stance)
        call screen dg_rpg_world_result(dg_rpg_last_world)
    jump dg_rpg_loop


# Hybrid turn lifecycle: PREVIEW (offline, pure) -> explicit AI/local choice
# -> generation (text only, worker thread) -> verified COMMIT (main thread).
label dg_rpg_hybrid_entry:
    call screen dg_rpg_hybrid_input(dg_rpg_hybrid_mode, dg_rpg_hybrid_who)
    if not _return:
        jump dg_rpg_loop
    $ dg_rpg_hybrid_action_text = _return
    $ dg_rpg_hybrid_preview(dg_rpg_hybrid_mode, dg_rpg_hybrid_action_text, dg_rpg_hybrid_who, dg_rpg_hybrid_topic)
    jump dg_rpg_hybrid_review_label

label dg_rpg_hybrid_review_label:
    call screen dg_rpg_hybrid_review(dg_rpg_hybrid_plan)
    if _return == "retry":
        jump dg_rpg_hybrid_entry
    if _return == "cancel" or not _return:
        jump dg_rpg_loop
    if _return == "local":
        $ dg_rpg_apply("hybrid", (dg_rpg_hybrid_plan, None))
        call screen dg_rpg_hybrid_read(dg_rpg_hybrid_entry)
        jump dg_rpg_loop
    if _return == "ai":
        if not dg_runtime.app.client.authenticated():
            call dg_connect
            if not dg_runtime.app.client.authenticated():
                jump dg_rpg_hybrid_review_label
        $ dg_run("chapter", dg_rpg_hybrid_generate, dg_rpg_hybrid_plan)
        if dg_runtime.app.error:
            call screen dg_error
            jump dg_rpg_hybrid_review_label
        $ dg_rpg_hybrid_scene = dg_runtime.app.result
        $ dg_rpg_apply("hybrid", (dg_rpg_hybrid_plan, dg_rpg_hybrid_scene))
        call screen dg_rpg_hybrid_read(dg_rpg_hybrid_entry)
        jump dg_rpg_loop
    jump dg_rpg_loop
