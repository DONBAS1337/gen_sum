# -*- coding: utf-8 -*-

init 1000 python:
    import os
    import re
    import sys
    import time
    gs_module_dir = os.path.dirname(renpy.loader.transfn("mods/generative_summer/gs_runtime.py"))
    if gs_module_dir not in sys.path:
        sys.path.insert(0, gs_module_dir)
    import gs_runtime

    # A private archive namespace prevents other mods from replacing even vanilla filenames.
    gs_archive_path = os.path.join(config.gamedir, "archive.rpa")
    gs_archive_name, gs_archive_index = next((path, index) for path, index in renpy.loader.archives
        if os.path.realpath(renpy.loader.transfn(path)) == os.path.realpath(gs_archive_path))
    renpy.loader.archives.append((gs_archive_name, {"gs_original/" + path: entries
        for path, entries in gs_archive_index.items()}))
    gs_runtime.original_images = {}
    gs_runtime.source_images = {}
    gs_runtime.original_sprite_layers = {}

    def gs_original_catalog(names):
        import ast
        import re
        catalog = {"backgrounds": [], "sprites": [], "characters": names,
                   "music": {}, "ambience": {}, "sounds": {}, "transitions": ["dissolve", "fade"]}
        # Build a physical vanilla sprite-layer index from the private archive.
        # This is separate from named Ren'Py images and keeps close/normal/far
        # independent, just like 7DL does.
        layer_re = re.compile(r"^images/sprites/(normal|far|close)/([^/]+)/([^/]+)$")
        file_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)_([0-9]+)_(.+)\.(?:png|jpg|jpeg|webp)$", re.IGNORECASE)
        for archive_path in gs_archive_index:
            normalized = archive_path.replace("\\", "/")
            layer_match = layer_re.match(normalized)
            if not layer_match:
                continue
            distance, who, filename = layer_match.groups()
            file_match = file_re.match(filename)
            if not file_match or file_match.group(1) != who:
                continue
            pose, token = file_match.group(2), file_match.group(3)
            gs_runtime.original_sprite_layers.setdefault(distance, {}).setdefault(who, {}).setdefault(pose, {})[token] = "gs_original/" + normalized

        # The game's compiled scripts retain their original image expressions and audio literals.
        # Do not discover resources through list_images(), music_list or the global store of mods.
        for node in renpy.game.script.namemap.values():
            if os.path.splitext(node.filename.replace("\\", "/"))[0] not in ("game/resources", "game/sprites"):
                continue
            if isinstance(node, renpy.ast.Image) and (node.imgname[0] == "bg" or node.imgname[0] in names):
                name = " ".join(node.imgname)
                source = re.sub(r'''(["'])images/''', r'\1gs_original/images/', node.code.source)
                gs_runtime.original_images[name] = renpy.easy.displayable(renpy.python.py_eval(source))
                catalog["backgrounds" if node.imgname[0] == "bg" else "sprites"].append(name)
            elif isinstance(node, renpy.ast.Python):
                for statement in ast.parse(node.code.source).body:
                    if not isinstance(statement, ast.Assign) or not isinstance(statement.value, ast.Str):
                        continue
                    path = statement.value.s
                    if path not in gs_archive_index:
                        continue
                    for target in statement.targets:
                        if isinstance(target, ast.Name) and target.id.startswith(("ambience_", "sfx_")):
                            group = "ambience" if target.id.startswith("ambience_") else "sounds"
                            catalog[group][target.id] = "gs_original/" + path
                        elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "music_list":
                            catalog["music"][ast.literal_eval(target.slice.value)] = "gs_original/" + path
        gs_runtime.original_images["bg black"] = Solid("#000")
        catalog["backgrounds"].append("bg black")
        for group in ("backgrounds", "sprites"):
            catalog[group] = sorted(set(catalog[group]))
        return catalog

    # Available at init, including restoration of an ordinary Ren'Py save.
    gs_background_root = os.path.join(config.savedir, "generative_summer")
    if gs_background_root not in config.searchpath:
        config.searchpath.append(gs_background_root)

    mods["generative_summer"] = u"Генеративное лето"
    renpy.music.register_channel("gs_theme", mixer="music", loop=True)
    renpy.music.register_channel("gs_nature", mixer="sfx", loop=True)

    # Every screen of the mod is a place in the camp: background, ambience, the game's time-of-day skin.
    GS_PLACES = {
        "gate": ("bg ext_camp_entrance_day", "ambience_camp_entrance_day", "day"),
        "library": ("bg ext_library_day", "ambience_camp_center_day", "day"),
        "hall": ("bg int_library_day", "ambience_library_day", "day"),
        "glade": ("bg ext_polyana_sunset", "ambience_forest_evening", "sunset"),
        "road": ("images/misc/splashscreen_sunset.png", "ambience_ext_road_evening", "sunset"),
    }
    GS_THEME = "silhouette_in_sunset"
    GS_MONTHS = [u"января", u"февраля", u"марта", u"апреля", u"мая", u"июня",
                 u"июля", u"августа", u"сентября", u"октября", u"ноября", u"декабря"]
    # The paper of the game's own in-game menu, without its twig frame.
    GS_PAPER = Fixed(Solid("#f3e6cf"), Frame(im.Crop("images/gui/ingame_menu/day/ingame_menu.png", (140, 120, 380, 210)), 24, 24))

    def gs_audio(place=None):
        # One theme for the whole menu, the ambience of the place; None leaves the mod's menus.
        if place is not None and gs_audio_pauses is None:
            store.gs_audio_pauses = [(ch, renpy.music.get_pause(channel=ch)) for ch in ("music", "ambience")]
            for ch, paused in gs_audio_pauses:
                renpy.music.set_pause(True, channel=ch)
        nature = getattr(store, GS_PLACES[place][1], None) if place else None
        for channel, path, volume in (("gs_theme", music_list.get(GS_THEME), 0.3), ("gs_nature", nature, 0.45)):
            if place and persistent.gs_atmosphere_sound and path and renpy.loadable(path):
                renpy.music.play(path, channel=channel, fadein=2.5, fadeout=1.5, if_changed=True, relative_volume=volume)
            else:
                renpy.music.stop(channel=channel, fadeout=1.2)
        if place is None and gs_audio_pauses is not None:
            for ch, paused in gs_audio_pauses:
                renpy.music.set_pause(paused, channel=ch)
            store.gs_audio_pauses = None

    def gs_place(place):
        # A scene change, as in the novel itself.
        if gs_current == place:
            return
        store.gs_current = place
        renpy.show_screen("gs_scene", place)
        renpy.with_statement(Dissolve(0.9))

    def gs_camera(place):
        if place == "road":
            return gs_tilt if persistent.gs_motion else gs_tilt_still
        return gs_pan if persistent.gs_motion else gs_still

    def gs_enter(step=0):
        return gs_rise(step * 0.14) if persistent.gs_motion else gs_still

    def gs_hover():
        return gs_nudge if persistent.gs_motion else gs_still

    def gs_skin():
        return GS_PLACES.get(gs_current, (None, None, "day"))[2]

    def gs_literal(value):
        return value.replace("{", "{{").replace("[", "[[")

    def gs_plural(number, one, few, many):
        number = abs(number) % 100
        if 10 < number < 20:
            return many
        number %= 10
        if number == 1:
            return one
        if 2 <= number <= 4:
            return few
        return many

    def gs_date(story):
        moment = time.localtime(story.get("created_at") or 0)
        return u"%d %s" % (moment.tm_mday, GS_MONTHS[moment.tm_mon - 1])

    def gs_wait_title():
        status = gs_runtime.app.status or u""
        if status.startswith(u"Рисуем фон"):
            return u"Рисуем фон для истории"
        return u"Исправляем детали главы" if status.startswith(u"Исправляем") else u"Пишем следующую главу"

    def gs_elapsed():
        seconds = int(time.time() - (gs_wait_started or time.time()))
        return u"ПРОШЛО  %d:%02d" % divmod(seconds, 60)

    def gs_detect_7dl_root():
        # From .../331470/3800447567/mods/generative_summer go back to .../331470.
        workshop_game = os.path.abspath(os.path.join(gs_module_dir, "..", "..", ".."))
        candidate = os.path.join(workshop_game, "3266357374")
        if os.path.isdir(os.path.join(candidate, "scenario_alt")):
            return candidate
        return None

    def gs_sprite_layer_map(source, distance, who):
        return (((source or {}).get(distance) or {}).get(who) or {})

    def gs_7dl_sprite_layer(distance, who, pose, token):
        # 7DL overrides only the exact physical layer it supplies. Missing
        # layers fall back to the vanilla archive at the SAME distance/pose.
        source_assets = ((gs_runtime.app.catalog.get("source_assets") or {}).get("7dl") or {})
        source_map = source_assets.get("sprite_layers") or {}
        source_pose = gs_sprite_layer_map(source_map, distance, who).get(pose) or {}
        if token in source_pose:
            return source_pose[token]

        vanilla_pose = gs_sprite_layer_map(gs_runtime.original_sprite_layers, distance, who).get(pose) or {}
        return vanilla_pose.get(token)

    def gs_7dl_sprite_poses(distance, who):
        poses = set()
        source_assets = ((gs_runtime.app.catalog.get("source_assets") or {}).get("7dl") or {})
        source_map = source_assets.get("sprite_layers") or {}
        poses.update(gs_sprite_layer_map(source_map, distance, who).keys())
        poses.update(gs_sprite_layer_map(gs_runtime.original_sprite_layers, distance, who).keys())
        return sorted(poses, key=lambda value: int(value) if value.isdigit() else 999)

    def gs_7dl_sprite_displayable(name):
        cached = gs_runtime.source_images.get(name, "__missing__")
        if cached != "__missing__":
            return cached or None

        parts = name.split()
        if len(parts) < 3:
            gs_runtime.source_images[name] = False
            return None

        distance = "normal"
        if parts[-1] in ("far", "close"):
            distance = parts.pop()
        if len(parts) < 3 or len(parts) > 4:
            gs_runtime.source_images[name] = False
            return None

        tag, emotion, clothes = parts[0], parts[1], parts[2]
        accessory = parts[3] if len(parts) == 4 else None
        match = re.match(r"^([A-Za-z_]+?)([0-9]?)$", tag)
        if not match:
            gs_runtime.source_images[name] = False
            return None
        who = match.group(1)
        variant = match.group(2)
        body_token = "body" + variant if variant else "body"
        canvas = {"close": (1050, 1080), "normal": (900, 1080), "far": (630, 1080)}[distance]

        # Do not probe arbitrary filenames or scale a normal sprite. Candidate
        # poses come from the exact union of physical 7DL + vanilla layer maps.
        for pose in gs_7dl_sprite_poses(distance, who):
            body = gs_7dl_sprite_layer(distance, who, pose, body_token)
            cloth = None if clothes == "body" else gs_7dl_sprite_layer(distance, who, pose, clothes)
            emotion_path = gs_7dl_sprite_layer(distance, who, pose, emotion)
            accessory_path = gs_7dl_sprite_layer(distance, who, pose, accessory) if accessory else None

            if not body or not emotion_path:
                continue
            if clothes != "body" and not cloth:
                continue
            if accessory and not accessory_path:
                continue

            layers = [body]
            if cloth:
                layers.append(cloth)
            layers.append(emotion_path)
            if accessory_path:
                layers.append(accessory_path)

            args = []
            for layer in layers:
                args.extend(((0, 0), layer))
            sprite = im.Composite(canvas, *args)
            gs_runtime.source_images[name] = sprite
            return sprite

        gs_runtime.source_images[name] = False
        return None

    def gs_setup():
        if gs_runtime.app is not None:
            return
        names = {"me": u"Семён", "th": u"Мысли Семёна", "sl": u"Славя", "dv": u"Алиса",
                 "un": u"Лена", "us": u"Ульяна", "mi": u"Мику", "mt": u"Ольга Дмитриевна",
                 "cs": u"Виола", "mz": u"Женя", "el": u"Электроник", "sh": u"Шурик",
                 "uv": u"Юля", "pi": u"Пионер"}
        names = {key: value for key, value in names.items() if hasattr(renpy.store, key)}
        catalog = gs_original_catalog(names)
        catalog["source_roots"] = {}
        catalog["source_assets"] = {}
        gs_7dl_root = gs_detect_7dl_root()
        if gs_7dl_root:
            catalog["source_roots"]["7dl"] = gs_7dl_root
            # Make scenario_alt/... paths loadable without importing/executing 7DL.
            if gs_7dl_root not in config.searchpath:
                config.searchpath.append(gs_7dl_root)
            import gs_source_7dl
            catalog["source_assets"]["7dl"] = gs_source_7dl.asset_manifest(gs_7dl_root)
        import base64
        catalog["background_references"] = []
        for path in ("gs_original/images/bg/ext_square_day.jpg", "gs_original/images/bg/int_library_day.jpg"):
            if renpy.loadable(path):
                with renpy.file(path) as reference:
                    catalog["background_references"].append("data:image/jpeg;base64," + base64.b64encode(reference.read()).decode("ascii"))
        gs_runtime.app = gs_runtime.Runtime(os.path.join(config.savedir, "generative_summer"), catalog)

    # gs_runtime.app lives in the imported Python module and is deliberately not
    # part of Ren'Py's save state. Recreate it when a save is loaded directly in
    # the middle of a Generative Summer screen/label.
    if gs_setup not in config.after_load_callbacks:
        config.after_load_callbacks.append(gs_setup)

    def gs_effect(command):
        op = command["op"]
        if op == "scene":
            renpy.scene()
            if command["image"].startswith("bg gs_generated_"):
                path = gs_runtime.app.library.background_path(gs_story_id, command["image"])
                renpy.show(command["image"], what=Image(path))
            else:
                source_assets = gs_runtime.app.catalog.get("source_assets", {})
                external = None
                for assets in source_assets.values():
                    external = (assets.get("backgrounds") or {}).get(command["image"])
                    if not external:
                        external = (assets.get("cgs") or {}).get(command["image"])
                    if external:
                        break
                if external:
                    renpy.show(command["image"], what=Image(external))
                else:
                    # Ordinary Ren'Py saves may still contain commands from the old mixed catalog.
                    renpy.show(command["image"], what=gs_runtime.original_images.get(command["image"], gs_runtime.original_images["bg black"]))
        elif op == "show":
            position = command.get("position") or "center"
            displayable = gs_runtime.original_images.get(command["image"])
            if displayable is None:
                displayable = gs_7dl_sprite_displayable(command["image"])
            if displayable is not None:
                renpy.show(command["image"], what=displayable, at_list=[getattr(renpy.store, position)])
        elif op == "hide":
            renpy.hide(command["tag"])
        elif op == "play":
            group = {"music": "music", "ambience": "ambience", "sound": "sounds"}[command["channel"]]
            path = gs_runtime.app.catalog[group].get(command["key"])
            if not path:
                for assets in gs_runtime.app.catalog.get("source_assets", {}).values():
                    path = (assets.get(group) or {}).get(command["key"])
                    if path:
                        break
            if path:
                renpy.music.play(path, channel=command["channel"])
            else:
                renpy.music.stop(channel=command["channel"])
        elif op == "stop":
            renpy.music.stop(channel=command["channel"])
        if command.get("transition"):
            renpy.with_statement(getattr(renpy.store, command["transition"]))

    def gs_say():
        # One static dispatcher needs a separate read marker for each story line.
        key = (gs_story_id, gs_node["id"], gs_index)
        current = renpy.game.context().current
        if persistent.gs_seen.get(key):
            persistent._seen_ever[current] = True
        else:
            persistent._seen_ever.pop(current, None)
        text = gs_literal(gs_command["text"])
        if config.old_substitutions:
            text = text.replace("%", "%%")
        renpy.say(getattr(renpy.store, gs_command["who"]) if gs_command["who"] else None, text)
        persistent.gs_seen[key] = True

    def gs_wait_screen(mode="quick"):
        # Waiting is not a story checkpoint; rollback crosses it to the choice.
        renpy.suspend_rollback(True)
        try:
            store.gs_wait_started = time.time()
            return renpy.call_screen("gs_wait", mode=mode)
        finally:
            renpy.suspend_rollback(False)

    def gs_run(mode, task, *args):
        gs_runtime.app.start(task, *args)
        gs_wait_screen(mode)

    def gs_poll(mode):
        if not gs_runtime.app.busy:
            renpy.end_interaction(True)
            return
        screen = renpy.get_screen("gs_wait")
        state = (gs_runtime.app.status, gs_runtime.app.client.login_url,
                 gs_elapsed() if mode == "chapter" else None)
        if screen is not None and screen.scope.get("wait_state") != state:
            screen.scope["wait_state"] = state
            renpy.restart_interaction()

    def gs_save_model(value):
        persistent.gs_model = value
        renpy.save_persistent()

default persistent.gs_model = None
default persistent.gs_fast_mode = True
default persistent.gs_seen = {}
default persistent.gs_atmosphere_sound = True
default persistent.gs_motion = True
default gs_audio_pauses = None
default gs_current = None
default gs_wait_started = None
default gs_story_id = None
default gs_node = None
default gs_index = 0
default gs_parent_id = None
default gs_choice_index = None
default gs_custom_choice = None

transform gs_still:
    alpha 1.0

transform gs_pan:
    subpixel True
    zoom 1.06
    yalign 0.5
    xalign 0.0
    ease 60.0 xalign 1.0
    ease 60.0 xalign 0.0
    repeat

transform gs_tilt:
    subpixel True
    xalign 0.5
    yalign 0.0
    ease 110.0 yalign 1.0
    ease 110.0 yalign 0.0
    repeat

transform gs_tilt_still:
    xalign 0.5
    yalign 0.85

transform gs_rise(delay=0.0):
    alpha 0.0
    yoffset 16
    pause delay
    parallel:
        ease 0.8 alpha 1.0
    parallel:
        ease 1.0 yoffset 0

transform gs_dot(delay):
    alpha 0.25
    pause delay
    block:
        ease 0.5 alpha 1.0
        ease 0.8 alpha 0.25
        pause 0.5
        repeat

transform gs_nudge:
    on hover:
        ease 0.15 xoffset 10
    on idle:
        ease 0.3 xoffset 0

# Type: the game's own fonts. Corbel for titles and choices, Calibri for reading, Gothic caps for labels.
style gs_text:
    font "fonts/calibri.ttf"
    size 28
    color "#fbf6ea"
    line_spacing 4
    outlines [(7, "#00000014", 2, 4), (6, "#00000016", 2, 3), (5, "#0000001a", 2, 3), (4, "#00000020", 1, 3), (3, "#00000028", 1, 2), (2, "#00000038", 1, 2), (1, "#00000060", 0, 1)]
style gs_title is gs_text:
    font "fonts/corbel.ttf"
    size 78
    color "#fffaf0"
    line_spacing 0
    outlines [(14, "#00000012", 4, 6), (11, "#00000016", 3, 5), (8, "#0000001c", 3, 5), (6, "#00000022", 2, 4), (4, "#0000002c", 2, 3), (3, "#00000034", 1, 2), (2, "#00000044", 1, 2), (1, "#00000060", 0, 1)]
style gs_title_plain is gs_title:
    outlines []
    drop_shadow (2, 3)
    drop_shadow_color "#000000a0"
style gs_sub is gs_text:
    font "fonts/corbeli.ttf"
    size 34
    color "#fff0c8"
style gs_small is gs_text:
    size 23
    color "#e6e6df"
style gs_label is gs_text:
    font "fonts/gothic.TTF"
    size 19
    kerning 4
    color "#e9ebe6"
    outlines [(5, "#00000016", 1, 3), (4, "#0000001c", 1, 2), (3, "#00000024", 1, 2), (2, "#00000034", 1, 1), (1, "#00000060", 0, 1)]
style gs_label_plain is gs_label:
    outlines []
    drop_shadow (1, 2)
    drop_shadow_color "#00000099"
style gs_meta is gs_label:
    size 17
    kerning 3
    color "#cfc8b6"
    outlines []
    hover_color "#ffdd7d"
    selected_color "#ffdd7d"
style gs_say is gs_text:
    outlines []
    slow_abortable False

style gs_act:
    background None
    padding (4, 6)
style gs_act_text is gs_text:
    font "fonts/corbel.ttf"
    size 34
    color "#f2ecdc"
    outlines [(10, "#00000012", 3, 5), (8, "#00000018", 2, 4), (6, "#0000001c", 2, 4), (4, "#00000024", 2, 3), (3, "#00000030", 1, 2), (2, "#00000040", 1, 2), (1, "#00000060", 0, 1)]
    hover_color "#ffdd7d"
    selected_color "#ffdd7d"
    insensitive_color "#a9aba4"
style gs_primary is gs_act
style gs_primary_text is gs_act_text:
    size 44
    color "#ffffff"
style gs_navlink is gs_act
style gs_navlink_text is gs_label:
    color "#c7cdcf"
    hover_color "#ffffff"
style gs_row:
    background None
    xfill True
    padding (4, 4)
style gs_row_text is gs_text:
    font "fonts/corbel.ttf"
    size 34
    color "#f2ead8"
    hover_color "#ffdd7d"
    selected_color "#ffdd7d"
    outlines []
style gs_box is default:
    background Frame("images/gui/choice/day/choice_box.png", 70, 70)
    padding (74, 66, 74, 66)
style gs_vscrollbar:
    xsize 17
    base_bar Frame("images/gui/settings/vbar_null.png", 0, 10)
    thumb "images/gui/settings/vthumb.png"
    unscrollable "hide"
style gs_paper_vscrollbar is gs_vscrollbar

# Ink on paper: the brown of the game's own settings pages.
style gs_ink is gs_text:
    color "#4d2e19"
    outlines []
style gs_ink_title is gs_ink:
    font "fonts/corbel.ttf"
    size 44
style gs_ink_small is gs_ink:
    size 24
    color "#6b4a30"
style gs_ink_label is gs_ink:
    font "fonts/gothic.TTF"
    size 18
    kerning 4
    color "#8a5a34"
style gs_ink_hint is gs_ink:
    font "fonts/corbeli.ttf"
    size 31
    color "#b39d83"
style gs_ink_input is gs_ink:
    size 31
    color "#3b2313"
style gs_ink_act is gs_act
style gs_ink_act_text is gs_ink:
    font "fonts/corbel.ttf"
    size 32
    hover_color "#a27146"
    selected_color "#a27146"

screen gs_scene(place):
    zorder -10
    on "show" action Function(gs_audio, place)
    on "replace" action Function(gs_audio, place)
    on "hide" action Function(gs_audio, None)
    $ gs_image = GS_PLACES[place][0]
    add Solid("#0e0b0a")
    if renpy.has_image(gs_image) or renpy.loadable(gs_image):
        add gs_image at gs_camera(place)

screen gs_chrome(place_name, back=None):
    hbox:
        xpos 120
        ypos 64
        spacing 16
        text u"ГЕНЕРАТИВНОЕ ЛЕТО" style "gs_label"
        text u"·" style "gs_label"
        text place_name style "gs_label" color "#ffdd7d"
    if back is not None:
        textbutton u"НАЗАД" style "gs_navlink" xpos 1800 xanchor 1.0 ypos 56 action back

screen gs_narrator(message, slow=True):
    # The interface speaks in the novel's own dialogue box.
    add ("images/gui/dialogue_box/%s/dialogue_box.png" % gs_skin()) xpos 174 ypos 916
    if slow:
        text message style "gs_say" xpos 204 ypos 998 yanchor 0.5 xmaximum 1500 slow_cps True
    else:
        text message style "gs_say" xpos 204 ypos 998 yanchor 0.5 xmaximum 1500

screen gs_login():
    modal True
    use gs_chrome(u"ВХОД", Return("back"))
    vbox:
        at gs_enter(0)
        xalign 0.5
        ypos 420
        spacing 0
        text u"Генеративное лето" style "gs_title" size 96 xalign 0.5
        text u"Своя история в «Совёнке»" style "gs_sub" size 38 xalign 0.5
    vbox:
        at gs_enter(1)
        xalign 0.5
        ypos 588
        spacing 14
        xsize 900
        text u"Опишите завязку — и получите главу с героями, местами и музыкой «Бесконечного лета». Каждая глава заканчивается выбором, а продолжение пишется по выбранной ветке." style "gs_text" text_align 0.5 xalign 0.5
    vbox:
        at gs_enter(2)
        xalign 0.5
        ypos 716
        spacing 8
        textbutton u"Войти через ChatGPT" style "gs_primary" xalign 0.5 action Return("login")
        if gs_runtime.app.stories:
            textbutton u"Читать сохранённые истории" style "gs_act" xalign 0.5 action Return("offline")
        null height 6
        text u"Вход откроется в браузере. Завязка и текст истории отправляются в ChatGPT и расходуют лимиты вашего аккаунта." style "gs_small" xmaximum 860 text_align 0.5 xalign 0.5
    use gs_narrator(u"Чтобы начать, подключите аккаунт ChatGPT. Отдельный ключ API и другие программы не нужны.")

screen gs_home():
    modal True
    $ stories = gs_runtime.app.stories
    vbox:
        at gs_enter(0)
        xpos 120
        ypos 150
        text u"Генеративное лето" style "gs_title"
    frame:
        at gs_enter(1)
        style "gs_box"
        xpos 60
        ypos 300
        xsize 1800
        ysize 596
        hbox:
            spacing 60
            vbox:
                xsize 1040
                spacing 14
                if stories:
                    text u"ВАШИ ИСТОРИИ" style "gs_meta"
                    viewport:
                        mousewheel True
                        draggable False
                        scrollbars "vertical"
                        style_prefix "gs"
                        ysize 420
                        vbox:
                            spacing 18
                            for number, story in enumerate(stories):
                                button:
                                    style "gs_row"
                                    action Return(("story", story["id"]))
                                    at gs_hover()
                                    vbox:
                                        spacing 2
                                        text (u"%02d   ·   %s" % (number + 1, gs_date(story))) style "gs_meta"
                                        text gs_literal(story["title"]) style "gs_row_text" xmaximum 900
                else:
                    text u"Пока здесь пусто." style "gs_sub" outlines []
                    text u"Первая история появится, как только вы опишете её начало. Одной-двух фраз достаточно: рассказчик подхватит." style "gs_text" outlines [] xmaximum 900
            vbox:
                at gs_enter(2)
                xsize 552
                spacing 18
                textbutton u"Начать новую историю" style "gs_primary" action Return(("new", None))
                null height 14
                textbutton u"Настройки" style "gs_act" action Return(("settings", None))
                textbutton u"Сохранения игры" style "gs_act" action ShowMenu("load")
                textbutton u"Выйти" style "gs_act" action Return(("exit", None))
    if gs_runtime.app.library.list_warnings:
        use gs_narrator(u"Часть историй не удалось открыть, их файлы сохранены. Остальные — здесь.")
    elif stories:
        use gs_narrator(u"История открывается с первой главы. Место, где вы остановились, хранится в обычных сохранениях игры.")
    else:
        use gs_narrator(u"Здесь будут храниться ваши истории. Начните первую.")

screen gs_new():
    modal True
    default premise = ""
    use gs_chrome(u"НОВАЯ ИСТОРИЯ", Return(""))
    vbox:
        at gs_enter(0)
        xpos 120
        ypos 150
        text u"Какое лето вы хотите прожить?" style "gs_title" size 64
    fixed:
        at gs_enter(1)
        xpos 420
        ypos 280
        xsize 1080
        ysize 480
        add Solid("#00000040") xoffset 10 yoffset 12
        add GS_PAPER
        vbox:
            xpos 56
            ypos 42
            xsize 968
            spacing 14
            text u"ЗАВЯЗКА" style "gs_ink_label"
            fixed:
                xsize 968
                ysize 350
                if not premise:
                    text u"Кого вы встретите? Что случится в первый день? Какое у этой истории настроение?" style "gs_ink_hint" xmaximum 920
                viewport:
                    mousewheel True
                    scrollbars "vertical"
                    style_prefix "gs_paper"
                    input:
                        value ScreenVariableInputValue("premise")
                        style "gs_ink_input"
                        length 4000
                        xmaximum 920
    hbox:
        at gs_enter(2)
        xpos 420
        ypos 800
        spacing 36
        textbutton u"Начать историю" style "gs_primary" sensitive bool(premise.strip()) action Return(premise.strip())
        textbutton u"Отмена" style "gs_act" yalign 0.5 action Return("")
    use gs_narrator(u"Например: «Мы с Леной нашли в библиотеке письмо из будущего. Хочу неспешную загадочную историю с тёплым юмором».")

screen gs_source_select():
    modal True
    use gs_chrome(u"ИСТОЧНИК ИСТОРИИ", Return(""))
    vbox:
        at gs_enter(0)
        xpos 120
        ypos 150
        text u"На какой версии мира опираться?" style "gs_title" size 64
        text u"Это влияет на характеры, отношения и детали мира. Сама история всё равно генерируется заново." style "gs_sub" size 30 xmaximum 1500

    frame:
        at gs_enter(1)
        style "gs_box"
        xpos 300
        ypos 330
        xsize 1320
        ysize 500
        vbox:
            xalign 0.5
            yalign 0.5
            spacing 24
            textbutton u"Оригинальное «Бесконечное лето»" style "gs_primary" xalign 0.5 action Return("vanilla")
            if gs_detect_7dl_root():
                text u"7 дней лета · Complete Edition · Мику" style "gs_meta" xalign 0.5
                hbox:
                    xalign 0.5
                    spacing 24
                    textbutton u"7ДЛ" style "gs_act" action Return("7dl:mi_7dl")
                    textbutton u"DJ" style "gs_act" action Return("7dl:mi_dj")
                    textbutton u"Классика" style "gs_act" action Return("7dl:mi_cl")
            else:
                text u"7 дней лета: Complete Edition не найден в этой Steam-библиотеке. Оригинальный режим доступен без него." style "gs_text" text_align 0.5 xmaximum 1000 xalign 0.5
            null height 6
            textbutton u"Назад" style "gs_act" xalign 0.5 action Return("")

    use gs_narrator(u"7ДЛ читается только как источник текста: чужой Ren'Py-код не запускается. На первом запуске профиль 7ДЛ построит локальный индекс сценария.")


screen gs_choice_input():
    modal True
    key "game_menu" action Return("")
    key ["K_RETURN", "K_KP_ENTER"] action If(bool(gs_custom_choice.strip()), Return(gs_custom_choice.strip()), NullAction())
    add Solid("#00000080")
    frame:
        background GS_PAPER
        padding (56, 42)
        align (0.5, 0.5)
        xsize 1080
        vbox:
            spacing 20
            text u"Свой вариант" style "gs_ink_title"
            text u"Что вы сделаете или скажете? История продолжится с этого решения." style "gs_ink_small"
            viewport:
                mousewheel True
                scrollbars "vertical"
                style_prefix "gs_paper"
                ysize 240
                input:
                    value VariableInputValue("gs_custom_choice")
                    style "gs_ink_input"
                    length gs_runtime.gs_core.CUSTOM_CHOICE_LIMIT
                    copypaste True
                    xmaximum 920
            text (u"%d / %d" % (len(gs_custom_choice), gs_runtime.gs_core.CUSTOM_CHOICE_LIMIT)) style "gs_ink_small"
            hbox:
                spacing 36
                textbutton u"Продолжить" style "gs_ink_act" sensitive bool(gs_custom_choice.strip()) action Return(gs_custom_choice.strip())
                textbutton u"Отмена" style "gs_ink_act" action Return("")

screen gs_wait(mode="quick"):
    modal True
    default shown = False
    default wait_state = None
    key "game_menu" action NullAction()
    key "rollback" action NullAction()
    if mode == "chapter":
        use gs_chrome(u"НОВАЯ ГЛАВА")
        vbox:
            at gs_enter(0)
            xalign 0.5
            ypos 400
            spacing 22
            xsize 1400
            hbox:
                xalign 0.5
                text gs_wait_title() style "gs_title_plain" size 86
                if persistent.gs_motion:
                    for i in range(3):
                        text u"." style "gs_title_plain" size 86 at gs_dot(i * 0.3)
                else:
                    text u"…" style "gs_title_plain" size 86
            text gs_elapsed() style "gs_label_plain" xalign 0.5
            text gs_literal(gs_runtime.app.status) style "gs_small" outlines [] xalign 0.5 text_align 0.5
        use gs_narrator(u"Глава пишется несколько минут. Когда она будет готова, история продолжится сама.")
    elif mode == "login":
        use gs_chrome(u"ВХОД")
        vbox:
            at gs_enter(0)
            xalign 0.5
            ypos 450
            spacing 22
            xsize 1100
            text u"Завершите вход в браузере" style "gs_title" size 76 xalign 0.5
            text u"Открылась страница входа ChatGPT. Когда вход завершится, игра продолжится сама." style "gs_text" xalign 0.5 text_align 0.5
            hbox:
                xalign 0.5
                spacing 40
                if gs_runtime.app.client.login_url:
                    textbutton u"Открыть браузер снова" style "gs_act" action OpenURL(gs_runtime.app.client.login_url)
                textbutton u"Отменить вход" style "gs_act" action Function(gs_runtime.app.cancel.set)
        use gs_narrator(u"Откроется страница ChatGPT. После входа вернитесь в игру — дальше всё продолжится само.")
    else:
        timer 0.8 action SetScreenVariable("shown", True)
        if shown:
            use gs_narrator(gs_literal(gs_runtime.app.status or u"Подождите…"), slow=False)
    timer 0.2 repeat True action Function(gs_poll, mode, _update_screens=False)

screen gs_error():
    modal True
    use gs_chrome(u"ЧТО-ТО ПОШЛО НЕ ТАК")
    fixed:
        at gs_enter(0)
        xpos 420
        ypos 200
        xsize 1080
        ysize 570
        add Solid("#00000040") xoffset 10 yoffset 12
        add GS_PAPER
        vbox:
            xpos 56
            ypos 44
            xsize 968
            spacing 14
            text u"Не получилось продолжить" style "gs_ink_title"
            text u"Уже написанные главы сохранены. Вот что сообщил сервис:" style "gs_ink"
            viewport:
                mousewheel True
                draggable False
                scrollbars "vertical"
                style_prefix "gs_paper"
                ysize 330
                text gs_literal(gs_runtime.app.error or u"Неизвестная ошибка") style "gs_ink_small" xmaximum 920
    textbutton u"Понятно" style "gs_primary" xpos 420 ypos 800 action Return() at gs_enter(1)
    use gs_narrator(u"Ничего не потеряно: истории и главы лежат на диске. Можно повторить попытку позже.")

screen gs_settings():
    modal True
    use gs_chrome(u"НАСТРОЙКИ", Return("back"))
    vbox:
        at gs_enter(0)
        xpos 120
        ypos 150
        spacing 2
        text u"Настройки" style "gs_title"
        text u"Рассказчик, аккаунт и оформление" style "gs_sub"
    frame:
        at gs_enter(1)
        style "gs_box"
        xpos 60
        ypos 300
        xsize 860
        ysize 596
        vbox:
            spacing 18
            text u"РАССКАЗЧИК" style "gs_meta"
            viewport:
                mousewheel True
                draggable False
                scrollbars "vertical"
                style_prefix "gs"
                ysize 230
                vbox:
                    spacing 12
                    button:
                        style "gs_row"
                        selected (persistent.gs_model is None)
                        action Function(gs_save_model, None)
                        at gs_hover()
                        hbox:
                            spacing 16
                            if persistent.gs_model is None:
                                add "images/gui/settings/leaf.png" yalign 0.5
                            else:
                                null width 22
                            text u"Автовыбор · GPT-6 Astra, облегчённый режим" style "gs_row_text" xmaximum 640
                    for model in gs_runtime.app.models:
                        button:
                            style "gs_row"
                            selected (persistent.gs_model == model["slug"])
                            action Function(gs_save_model, model["slug"])
                            at gs_hover()
                            hbox:
                                spacing 16
                                if persistent.gs_model == model["slug"]:
                                    add "images/gui/settings/leaf.png" yalign 0.5
                                else:
                                    null width 22
                                text gs_literal(model.get("display_name") or model["slug"]) style "gs_row_text" xmaximum 640
            if not gs_runtime.app.models:
                text (u"Список моделей появится после входа в аккаунт." if not gs_runtime.app.client.authenticated() else u"Список моделей пока пуст. Попробуйте обновить его.") style "gs_small"
            button:
                style "gs_row"
                selected persistent.gs_fast_mode
                action [ToggleField(persistent, "gs_fast_mode"), Function(renpy.save_persistent)]
                hbox:
                    spacing 16
                    frame:
                        background Solid("#e6e6df")
                        padding (2, 2)
                        xysize (28, 28)
                        yalign 0.5
                        fixed:
                            add Solid("#272c24")
                            if persistent.gs_fast_mode:
                                add Solid("#ffdd7d") xysize (3, 10) rotate -45 xpos 3 ypos 9
                                add Solid("#ffdd7d") xysize (3, 17) rotate 45 xpos 9 ypos 3
                    text u"Fast mode" style "gs_row_text"
            text u"Истории генерируются быстрее, но лимиты аккаунта расходуются быстрее. Работает на моделях с поддержкой Fast mode." style "gs_small" outlines []
    fixed:
        at gs_enter(2)
        xpos 1060
        ypos 300
        xsize 740
        ysize 500
        add Solid("#00000040") xoffset 10 yoffset 12
        add GS_PAPER
        vbox:
            xpos 52
            ypos 40
            xsize 636
            spacing 10
            text u"АККАУНТ" style "gs_ink_label"
            if gs_runtime.app.client.authenticated():
                text u"ChatGPT подключён. Новые главы пишутся за счёт лимитов этого аккаунта." style "gs_ink_small"
                textbutton u"Отключить аккаунт" style "gs_ink_act" action Return("logout")
            else:
                text u"Аккаунт не подключён. Уже написанные главы можно читать и так." style "gs_ink_small"
                textbutton u"Войти через ChatGPT" style "gs_ink_act" action Return("login")
            textbutton u"Обновить список моделей" style "gs_ink_act" action Return("refresh")
            null height 22
            text u"ОФОРМЛЕНИЕ" style "gs_ink_label"
            textbutton (u"Музыка и звуки меню · вкл" if persistent.gs_atmosphere_sound else u"Музыка и звуки меню · выкл") style "gs_ink_act" action [ToggleField(persistent, "gs_atmosphere_sound"), Function(gs_audio, gs_current)]
            textbutton (u"Движение · вкл" if persistent.gs_motion else u"Движение · выкл") style "gs_ink_act" action ToggleField(persistent, "gs_motion")
    textbutton u"Готово" style "gs_primary" xpos 1060 ypos 830 action Return("back") at gs_enter(3)
    use gs_narrator(u"Новая модель начнёт работать со следующей главы. Уже написанные главы останутся прежними.")

label generative_summer:
    $ gs_setup()
    $ persistent.sprite_time = "day"
    $ day_time()
    $ set_mode_adv()
    window hide
    $ gs_place("gate")
    $ gs_run("quick", gs_runtime.app.refresh_stories)
    if gs_runtime.app.error:
        call screen gs_error
    if not gs_runtime.app.client.authenticated():
        call screen gs_login
        if _return == "back":
            hide screen gs_scene
            $ gs_current = None
            return
        if _return == "login":
            call gs_connect
    jump gs_menu

label gs_connect:
    $ gs_run("login", gs_runtime.app.login)
    if gs_runtime.app.error:
        call screen gs_error
    return

label gs_menu:
    window hide
    $ gs_place("library")
    $ gs_run("quick", gs_runtime.app.refresh_stories)
    if gs_runtime.app.error:
        call screen gs_error
    call screen gs_home
    $ gs_action, gs_value = _return
    if gs_action == "exit":
        hide screen gs_scene
        $ gs_current = None
        return
    if gs_action == "settings":
        jump gs_settings_label
    if gs_action == "new":
        if not gs_runtime.app.client.authenticated():
            call gs_connect
            if not gs_runtime.app.client.authenticated():
                jump gs_menu
        $ gs_place("glade")
        call screen gs_new
        if not _return:
            jump gs_menu
        $ gs_premise = _return
        call screen gs_source_select
        if not _return:
            jump gs_menu
        $ gs_run("quick", gs_runtime.app.create, gs_premise, _return)
        if gs_runtime.app.error:
            call screen gs_error
            jump gs_menu
        $ gs_story_id = gs_runtime.app.result["id"]
    else:
        $ gs_story_id = gs_value
    $ gs_parent_id = None
    $ gs_choice_index = None
    $ gs_custom_choice = None
    scene black
    stop music
    stop ambience
    jump gs_fetch

label gs_settings_label:
    $ gs_place("hall")
    if gs_runtime.app.client.authenticated() and not gs_runtime.app.models:
        $ gs_run("quick", gs_runtime.app.refresh_models)
        if gs_runtime.app.error:
            call screen gs_error
    call screen gs_settings
    if _return == "login":
        call gs_connect
        jump gs_settings_label
    if _return == "logout":
        $ gs_run("quick", gs_runtime.app.client.logout)
        $ gs_runtime.app.models = []
        if gs_runtime.app.error:
            call screen gs_error
        jump gs_settings_label
    if _return == "refresh":
        $ gs_run("quick", gs_runtime.app.refresh_models)
        if gs_runtime.app.error:
            call screen gs_error
        jump gs_settings_label
    jump gs_menu

label gs_fetch:
    # Immutable disk nodes make replay after rollback idempotent.
    $ gs_setup()
    $ gs_place("road")
    $ gs_run("chapter", gs_runtime.app.generate, gs_story_id, gs_parent_id, gs_choice_index, persistent.gs_model, gs_custom_choice, persistent.gs_fast_mode)
    if gs_runtime.app.error:
        call screen gs_error
        menu:
            "Попробовать снова":
                jump gs_fetch
            "Подключить ChatGPT":
                call gs_connect
                jump gs_fetch
            "К историям":
                jump gs_menu
    $ gs_node = gs_runtime.app.result
    $ gs_index = 0
    scene black
    hide screen gs_scene
    with Dissolve(1.0)
    $ gs_current = None
    jump gs_play

label gs_play:
    # Each native say/menu interaction has its own static Ren'Py statement.
    $ gs_setup()
    if gs_index < len(gs_node["commands"]):
        $ gs_command = gs_node["commands"][gs_index]
        if gs_command["op"] == "say":
            $ gs_say()
        else:
            $ gs_effect(gs_command)
        $ gs_index += 1
        jump gs_play
label gs_choose:
    if not gs_node["choices"]:
        menu:
            "История завершена."
            "К историям":
                jump gs_menu
    # This extra item belongs only to generated chapters; the global choice screen stays untouched.
    $ gs_custom_choice = None
    $ gs_choice_index = renpy.display_menu([(gs_literal(text), index) for index, text in enumerate(gs_node["choices"])] + [(u"Свой вариант…", "custom")])
    if gs_choice_index == "custom":
        $ gs_custom_choice = ""
        $ renpy.retain_after_load()
        call screen gs_choice_input
        if not _return:
            jump gs_choose
        $ gs_custom_choice = _return
        $ gs_choice_index = None
    $ gs_parent_id = gs_node["id"]
    jump gs_fetch