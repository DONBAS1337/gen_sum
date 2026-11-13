# -*- coding: utf-8 -*-

init 1000 python:
    import os
    import re
    import sys
    import time
    dg_module_dir = os.path.dirname(renpy.loader.transfn("mods/don_gen/dg_runtime.py"))
    if dg_module_dir not in sys.path:
        sys.path.insert(0, dg_module_dir)
    import dg_runtime
    import dg_resources

    # A private archive namespace prevents other mods from replacing even vanilla filenames.
    dg_archive_path = os.path.join(config.gamedir, "archive.rpa")
    dg_archive_name, dg_archive_index = next((path, index) for path, index in renpy.loader.archives
        if os.path.realpath(renpy.loader.transfn(path)) == os.path.realpath(dg_archive_path))
    renpy.loader.archives.append((dg_archive_name, {"dg_original/" + path: entries
        for path, entries in dg_archive_index.items()}))
    dg_runtime.original_images = {}
    dg_runtime.source_images = {}
    dg_runtime.original_sprite_layers = {}

    def dg_original_catalog(names):
        import ast
        import re
        catalog = {"backgrounds": [], "sprites": [], "characters": names,
                   "music": {}, "ambience": {}, "sounds": {}, "transitions": ["dissolve", "fade"]}
        # Build a physical vanilla sprite-layer index from the private archive.
        # This is separate from named Ren'Py images and keeps close/normal/far
        # independent, just like 7DL does.
        layer_re = re.compile(r"^images/sprites/(normal|far|close)/([^/]+)/([^/]+)$")
        file_re = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)_([0-9]+)_(.+)\.(?:png|jpg|jpeg|webp)$", re.IGNORECASE)
        for archive_path in dg_archive_index:
            normalized = archive_path.replace("\\", "/")
            layer_match = layer_re.match(normalized)
            if not layer_match:
                continue
            distance, who, filename = layer_match.groups()
            file_match = file_re.match(filename)
            if not file_match or file_match.group(1) != who:
                continue
            pose, token = file_match.group(2), file_match.group(3)
            dg_runtime.original_sprite_layers.setdefault(distance, {}).setdefault(who, {}).setdefault(pose, {})[token] = "dg_original/" + normalized

        # The game's compiled scripts retain their original image expressions and audio literals.
        # Do not discover resources through list_images(), music_list or the global store of mods.
        for node in renpy.game.script.namemap.values():
            if os.path.splitext(node.filename.replace("\\", "/"))[0] not in ("game/resources", "game/sprites"):
                continue
            if isinstance(node, renpy.ast.Image) and (node.imgname[0] == "bg" or node.imgname[0] in names):
                name = " ".join(node.imgname)
                source = re.sub(r'''(["'])images/''', r'\1dg_original/images/', node.code.source)
                dg_runtime.original_images[name] = renpy.easy.displayable(renpy.python.py_eval(source))
                catalog["backgrounds" if node.imgname[0] == "bg" else "sprites"].append(name)
            elif isinstance(node, renpy.ast.Python):
                for statement in ast.parse(node.code.source).body:
                    if not isinstance(statement, ast.Assign) or not isinstance(statement.value, ast.Str):
                        continue
                    path = statement.value.s
                    if path not in dg_archive_index:
                        continue
                    for target in statement.targets:
                        if isinstance(target, ast.Name) and target.id.startswith(("ambience_", "sfx_")):
                            group = "ambience" if target.id.startswith("ambience_") else "sounds"
                            catalog[group][target.id] = "dg_original/" + path
                        elif isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == "music_list":
                            catalog["music"][ast.literal_eval(target.slice.value)] = "dg_original/" + path
        dg_runtime.original_images["bg black"] = Solid("#000")
        catalog["backgrounds"].append("bg black")
        for group in ("backgrounds", "sprites"):
            catalog[group] = sorted(set(catalog[group]))
        return catalog

    # Available at init, including restoration of an ordinary Ren'Py save.
    dg_background_root = os.path.join(config.savedir, "don_gen")
    if dg_background_root not in config.searchpath:
        config.searchpath.append(dg_background_root)

    mods["don_gen"] = u"DON-GEN · свободный Совёнок"
    renpy.music.register_channel("dg_theme", mixer="music", loop=True)
    renpy.music.register_channel("dg_nature", mixer="sfx", loop=True)

    # Every screen of the mod is a place in the camp: background, ambience, the game's time-of-day skin.
    DG_PLACES = {
        "gate": ("bg ext_camp_entrance_day", "ambience_camp_entrance_day", "day"),
        "library": ("bg ext_library_day", "ambience_camp_center_day", "day"),
        "hall": ("bg int_library_day", "ambience_library_day", "day"),
        "glade": ("bg ext_polyana_sunset", "ambience_forest_evening", "sunset"),
        "road": ("images/misc/splashscreen_sunset.png", "ambience_ext_road_evening", "sunset"),
    }
    DG_THEME = "silhouette_in_sunset"
    DG_MONTHS = [u"января", u"февраля", u"марта", u"апреля", u"мая", u"июня",
                 u"июля", u"августа", u"сентября", u"октября", u"ноября", u"декабря"]
    # The paper of the game's own in-game menu, without its twig frame.
    DG_PAPER = Fixed(Solid("#f3e6cf"), Frame(im.Crop("images/gui/ingame_menu/day/ingame_menu.png", (140, 120, 380, 210)), 24, 24))

    def dg_menu_audio(place=None):
        # One theme for the whole menu, the ambience of the place; None leaves the mod's menus.
        if place is not None and dg_audio_pauses is None:
            store.dg_audio_pauses = [(ch, renpy.music.get_pause(channel=ch)) for ch in ("music", "ambience")]
            for ch, paused in dg_audio_pauses:
                renpy.music.set_pause(True, channel=ch)
        nature = getattr(store, DG_PLACES[place][1], None) if place else None
        for channel, path, volume in (("dg_theme", music_list.get(DG_THEME), 0.3), ("dg_nature", nature, 0.45)):
            if place and persistent.dg_atmosphere_sound and path and renpy.loadable(path):
                renpy.music.play(path, channel=channel, fadein=2.5, fadeout=1.5, if_changed=True, relative_volume=volume)
            else:
                renpy.music.stop(channel=channel, fadeout=1.2)
        if place is None and dg_audio_pauses is not None:
            for ch, paused in dg_audio_pauses:
                renpy.music.set_pause(paused, channel=ch)
            store.dg_audio_pauses = None

    def dg_place(place):
        # A scene change, as in the novel itself.
        if dg_current == place:
            return
        store.dg_current = place
        renpy.show_screen("dg_scene", place)
        renpy.with_statement(Dissolve(0.9))

    def dg_camera(place):
        if place == "road":
            return dg_tilt if persistent.dg_motion else dg_tilt_still
        return dg_pan if persistent.dg_motion else dg_still

    def dg_enter(step=0):
        return dg_rise(step * 0.14) if persistent.dg_motion else dg_still

    def dg_hover():
        return dg_nudge if persistent.dg_motion else dg_still

    def dg_skin():
        return DG_PLACES.get(dg_current, (None, None, "day"))[2]

    def dg_literal(value):
        return value.replace("{", "{{").replace("[", "[[")

    def dg_plural(number, one, few, many):
        number = abs(number) % 100
        if 10 < number < 20:
            return many
        number %= 10
        if number == 1:
            return one
        if 2 <= number <= 4:
            return few
        return many

    def dg_date(story):
        moment = time.localtime(story.get("created_at") or 0)
        return u"%d %s" % (moment.tm_mday, DG_MONTHS[moment.tm_mon - 1])

    def dg_wait_title():
        status = dg_runtime.app.status or u""
        if status.startswith(u"Рисуем фон"):
            return u"Рисуем фон для истории"
        return u"Исправляем детали главы" if status.startswith(u"Исправляем") else u"Пишем следующую главу"

    def dg_elapsed():
        seconds = int(time.time() - (dg_wait_started or time.time()))
        return u"ПРОШЛО  %d:%02d" % divmod(seconds, 60)

    def dg_detect_7dl_root():
        return dg_resources.detect_root(config.gamedir,
            os.path.join(dg_module_dir, "resource_sources.json"))

    def dg_sprite_layer_map(source, distance, who):
        return (((source or {}).get(distance) or {}).get(who) or {})

    def dg_7dl_sprite_layer(distance, who, pose, token):
        # 7DL overrides only the exact physical layer it supplies. Missing
        # layers fall back to the vanilla archive at the SAME distance/pose.
        source_assets = ((dg_runtime.app.catalog.get("source_assets") or {}).get("7dl") or {})
        source_map = source_assets.get("sprite_layers") or {}
        source_pose = dg_sprite_layer_map(source_map, distance, who).get(pose) or {}
        if token in source_pose:
            return source_pose[token]
        # 7DL Shurik uses a complete base + same-pose uniform, not body/pioneer.
        if who=='sh' and source_pose.get('uniform'):
            if token=='body':return source_pose.get('nude')
            if token=='pioneer':return source_pose['uniform']

        vanilla_pose = dg_sprite_layer_map(dg_runtime.original_sprite_layers, distance, who).get(pose) or {}
        return vanilla_pose.get(token)

    def dg_7dl_sprite_poses(distance, who):
        poses = set()
        source_assets = ((dg_runtime.app.catalog.get("source_assets") or {}).get("7dl") or {})
        source_map = source_assets.get("sprite_layers") or {}
        poses.update(dg_sprite_layer_map(source_map, distance, who).keys())
        poses.update(dg_sprite_layer_map(dg_runtime.original_sprite_layers, distance, who).keys())
        return sorted(poses, key=lambda value: int(value) if value.isdigit() else 999)

    def dg_7dl_sprite_displayable(name, pose_hint=None):
        cache_key = name + ("|pose:" + str(pose_hint) if pose_hint else "")
        cached = dg_runtime.source_images.get(cache_key, "__missing__")
        if cached != "__missing__":
            return cached or None

        parts = name.split()
        if len(parts) < 3:
            dg_runtime.source_images[cache_key] = False
            return None

        distance = "normal"
        if parts[-1] in ("far", "close"):
            distance = parts.pop()
        if len(parts) < 3 or len(parts) > 4:
            dg_runtime.source_images[cache_key] = False
            return None

        tag, emotion, clothes = parts[0], parts[1], parts[2]
        accessory = parts[3] if len(parts) == 4 else None
        if parts[0]=="sh" and clothes=="body":return None
        match = re.match(r"^([A-Za-z_]+?)([0-9]?)$", tag)
        if not match:
            dg_runtime.source_images[cache_key] = False
            return None
        who = match.group(1)
        variant = match.group(2)
        body_token = "body" + variant if variant else "body"
        canvas = {"close": (1050, 1080), "normal": (900, 1080), "far": (630, 1080)}[distance]

        # Do not probe arbitrary filenames or scale a normal sprite. Candidate
        # poses come from the exact union of physical 7DL + vanilla layer maps.
        poses = dg_7dl_sprite_poses(distance, who)
        if pose_hint is not None:
            poses = [pose for pose in poses if str(pose) == str(pose_hint)]
        for pose in poses:
            body = dg_7dl_sprite_layer(distance, who, pose, body_token)
            cloth = None if clothes == "body" else dg_7dl_sprite_layer(distance, who, pose, clothes)
            emotion_path = dg_7dl_sprite_layer(distance, who, pose, emotion)
            accessory_path = dg_7dl_sprite_layer(distance, who, pose, accessory) if accessory else None

            if not body or (not emotion_path and not (who=='sh' and emotion=='normal' and clothes=='pioneer' and cloth)):
                continue
            if clothes != "body" and not cloth:
                continue
            if accessory and not accessory_path:
                continue

            layers = [body]
            if cloth:
                layers.append(cloth)
            if emotion_path:layers.append(emotion_path)
            if accessory_path:
                layers.append(accessory_path)

            args = []
            for layer in layers:
                args.extend(((0, 0), layer))
            sprite = im.Composite(canvas, *args)
            dg_runtime.source_images[cache_key] = sprite
            return sprite

        dg_runtime.source_images[cache_key] = False
        return None

    def dg_setup():
        if dg_runtime.app is not None:
            return
        names = {"me": u"Семён", "th": u"Мысли Семёна", "sl": u"Славя", "dv": u"Алиса",
                 "un": u"Лена", "us": u"Ульяна", "mi": u"Мику", "mt": u"Ольга Дмитриевна",
                 "cs": u"Виола", "mz": u"Женя", "el": u"Электроник", "sh": u"Шурик",
                 "uv": u"Юля", "pi": u"Пионер"}
        names = {key: value for key, value in names.items() if hasattr(renpy.store, key)}
        catalog = dg_original_catalog(names)
        catalog["source_roots"] = {}
        catalog["source_assets"] = {}
        dg_7dl_root = dg_detect_7dl_root()
        if dg_7dl_root:
            catalog["source_roots"]["7dl"] = dg_7dl_root
            import dg_source_7dl
            catalog["source_assets"]["7dl"] = dg_resources.absolute_assets(
                dg_7dl_root, dg_source_7dl.asset_manifest(dg_7dl_root))
        import base64
        catalog["background_references"] = []
        for path in ("dg_original/images/bg/ext_square_day.jpg", "dg_original/images/bg/int_library_day.jpg"):
            if renpy.loadable(path):
                with renpy.file(path) as reference:
                    catalog["background_references"].append("data:image/jpeg;base64," + base64.b64encode(reference.read()).decode("ascii"))
        dg_runtime.app = dg_runtime.Runtime(os.path.join(config.savedir, "don_gen"), catalog)

    # dg_runtime.app lives in the imported Python module and is deliberately not
    # part of Ren'Py's save state. Recreate it when a save is loaded directly in
    # the middle of a DON-GEN screen/label.
    if dg_setup not in config.after_load_callbacks:
        config.after_load_callbacks.append(dg_setup)

    def dg_effect(command):
        op = command["op"]
        if op == "scene":
            renpy.scene()
            if command["image"].startswith("bg dg_generated_"):
                path = dg_runtime.app.library.background_path(dg_story_id, command["image"])
                renpy.show(command["image"], what=Image(path))
            else:
                source_assets = dg_runtime.app.catalog.get("source_assets", {})
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
                    renpy.show(command["image"], what=dg_runtime.original_images.get(command["image"], dg_runtime.original_images["bg black"]))
        elif op == "show":
            position = command.get("position") or "center"
            displayable = dg_runtime.original_images.get(command["image"])
            if displayable is None:
                displayable = dg_7dl_sprite_displayable(command["image"])
            if displayable is not None:
                renpy.show(command["image"], what=displayable, at_list=[getattr(renpy.store, position)])
        elif op == "hide":
            renpy.hide(command["tag"])
        elif op == "play":
            group = {"music": "music", "ambience": "ambience", "sound": "sounds"}[command["channel"]]
            path = dg_runtime.app.catalog[group].get(command["key"])
            if not path:
                for assets in dg_runtime.app.catalog.get("source_assets", {}).values():
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

    def dg_say():
        # One static dispatcher needs a separate read marker for each story line.
        key = (dg_story_id, dg_node["id"], dg_index)
        current = renpy.game.context().current
        if persistent.dg_seen.get(key):
            persistent._seen_ever[current] = True
        else:
            persistent._seen_ever.pop(current, None)
        text = dg_literal(dg_command["text"])
        if config.old_substitutions:
            text = text.replace("%", "%%")
        renpy.say(getattr(renpy.store, dg_command["who"]) if dg_command["who"] else None, text)
        persistent.dg_seen[key] = True

    def dg_wait_screen(mode="quick"):
        # Waiting is not a story checkpoint; rollback crosses it to the choice.
        renpy.suspend_rollback(True)
        try:
            store.dg_wait_started = time.time()
            return renpy.call_screen("dg_wait", mode=mode)
        finally:
            renpy.suspend_rollback(False)

    def dg_run(mode, task, *args):
        # Do not consume a result belonging to another request.
        if dg_runtime.app.busy:
            dg_wait_screen(mode)
        if dg_runtime.app.start(task, *args) is None:
            raise RuntimeError("The requested background task did not start")
        dg_wait_screen(mode)

    def dg_valid_chapter(node):
        import dg_core
        return dg_core.valid_runtime_chapter(node)

    def dg_poll(mode):
        if not dg_runtime.app.busy:
            renpy.end_interaction(True)
            return
        screen = renpy.get_screen("dg_wait")
        state = (dg_runtime.app.status, dg_runtime.app.client.login_url,
                 dg_elapsed() if mode == "chapter" else None)
        if screen is not None and screen.scope.get("wait_state") != state:
            screen.scope["wait_state"] = state
            renpy.restart_interaction()

    def dg_save_model(value):
        persistent.dg_model = value
        renpy.save_persistent()

default persistent.dg_model = None
default persistent.dg_fast_mode = True
default persistent.dg_seen = {}
default persistent.dg_atmosphere_sound = True
default persistent.dg_motion = True
default dg_audio_pauses = None
default dg_current = None
default dg_wait_started = None
default dg_story_id = None
default dg_node = None
default dg_index = 0
default dg_parent_id = None
default dg_choice_index = None
default dg_custom_choice = None

transform dg_still:
    alpha 1.0

transform dg_pan:
    subpixel True
    zoom 1.06
    yalign 0.5
    xalign 0.0
    ease 60.0 xalign 1.0
    ease 60.0 xalign 0.0
    repeat

transform dg_tilt:
    subpixel True
    xalign 0.5
    yalign 0.0
    ease 110.0 yalign 1.0
    ease 110.0 yalign 0.0
    repeat

transform dg_tilt_still:
    xalign 0.5
    yalign 0.85

transform dg_rise(delay=0.0):
    alpha 0.0
    yoffset 16
    pause delay
    parallel:
        ease 0.8 alpha 1.0
    parallel:
        ease 1.0 yoffset 0

transform dg_dot(delay):
    alpha 0.25
    pause delay
    block:
        ease 0.5 alpha 1.0
        ease 0.8 alpha 0.25
        pause 0.5
        repeat

transform dg_nudge:
    on hover:
        ease 0.15 xoffset 10
    on idle:
        ease 0.3 xoffset 0

# Type: the game's own fonts. Corbel for titles and choices, Calibri for reading, Gothic caps for labels.
style dg_text:
    font "fonts/calibri.ttf"
    size 28
    color "#fbf6ea"
    line_spacing 4
    outlines [(7, "#00000014", 2, 4), (6, "#00000016", 2, 3), (5, "#0000001a", 2, 3), (4, "#00000020", 1, 3), (3, "#00000028", 1, 2), (2, "#00000038", 1, 2), (1, "#00000060", 0, 1)]
style dg_title is dg_text:
    font "fonts/corbel.ttf"
    size 78
    color "#fffaf0"
    line_spacing 0
    outlines [(14, "#00000012", 4, 6), (11, "#00000016", 3, 5), (8, "#0000001c", 3, 5), (6, "#00000022", 2, 4), (4, "#0000002c", 2, 3), (3, "#00000034", 1, 2), (2, "#00000044", 1, 2), (1, "#00000060", 0, 1)]
style dg_title_plain is dg_title:
    outlines []
    drop_shadow (2, 3)
    drop_shadow_color "#000000a0"
style dg_sub is dg_text:
    font "fonts/corbeli.ttf"
    size 34
    color "#fff0c8"
style dg_small is dg_text:
    size 23
    color "#e6e6df"
style dg_label is dg_text:
    font "fonts/gothic.TTF"
    size 19
    kerning 4
    color "#e9ebe6"
    outlines [(5, "#00000016", 1, 3), (4, "#0000001c", 1, 2), (3, "#00000024", 1, 2), (2, "#00000034", 1, 1), (1, "#00000060", 0, 1)]
style dg_label_plain is dg_label:
    outlines []
    drop_shadow (1, 2)
    drop_shadow_color "#00000099"
style dg_meta is dg_label:
    size 17
    kerning 3
    color "#cfc8b6"
    outlines []
    hover_color "#ffdd7d"
    selected_color "#ffdd7d"
style dg_say is dg_text:
    outlines []
    slow_abortable False

style dg_act:
    background None
    padding (4, 6)
style dg_act_text is dg_text:
    font "fonts/corbel.ttf"
    size 34
    color "#f2ecdc"
    outlines [(10, "#00000012", 3, 5), (8, "#00000018", 2, 4), (6, "#0000001c", 2, 4), (4, "#00000024", 2, 3), (3, "#00000030", 1, 2), (2, "#00000040", 1, 2), (1, "#00000060", 0, 1)]
    hover_color "#ffdd7d"
    selected_color "#ffdd7d"
    insensitive_color "#a9aba4"
style dg_primary is dg_act
style dg_primary_text is dg_act_text:
    size 44
    color "#ffffff"
style dg_navlink is dg_act
style dg_navlink_text is dg_label:
    color "#c7cdcf"
    hover_color "#ffffff"
style dg_row:
    background None
    xfill True
    padding (4, 4)
style dg_row_text is dg_text:
    font "fonts/corbel.ttf"
    size 34
    color "#f2ead8"
    hover_color "#ffdd7d"
    selected_color "#ffdd7d"
    outlines []
style dg_box is default:
    background Frame("images/gui/choice/day/choice_box.png", 70, 70)
    padding (74, 66, 74, 66)
style dg_vscrollbar:
    xsize 17
    base_bar Frame("images/gui/settings/vbar_null.png", 0, 10)
    thumb "images/gui/settings/vthumb.png"
    unscrollable "hide"
style dg_paper_vscrollbar is dg_vscrollbar

# Ink on paper: the brown of the game's own settings pages.
style dg_ink is dg_text:
    color "#4d2e19"
    outlines []
style dg_ink_title is dg_ink:
    font "fonts/corbel.ttf"
    size 44
style dg_ink_small is dg_ink:
    size 24
    color "#6b4a30"
style dg_ink_label is dg_ink:
    font "fonts/gothic.TTF"
    size 18
    kerning 4
    color "#8a5a34"
style dg_ink_hint is dg_ink:
    font "fonts/corbeli.ttf"
    size 31
    color "#b39d83"
style dg_ink_input is dg_ink:
    size 31
    color "#3b2313"
style dg_ink_act is dg_act
style dg_ink_act_text is dg_ink:
    font "fonts/corbel.ttf"
    size 32
    hover_color "#a27146"
    selected_color "#a27146"

screen dg_scene(place):
    zorder -10
    on "show" action Function(dg_menu_audio, place)
    on "replace" action Function(dg_menu_audio, place)
    on "hide" action Function(dg_menu_audio, None)
    $ dg_image = DG_PLACES[place][0]
    add Solid("#0e0b0a")
    if renpy.has_image(dg_image) or renpy.loadable(dg_image):
        add dg_image at dg_camera(place)

screen dg_chrome(place_name, back=None):
    hbox:
        xpos 120
        ypos 64
        spacing 16
        text u"DON-GEN" style "dg_label"
        text u"·" style "dg_label"
        text place_name style "dg_label" color "#ffdd7d"
    if back is not None:
        textbutton u"НАЗАД" style "dg_navlink" xpos 1800 xanchor 1.0 ypos 56 action back

screen dg_narrator(message, slow=True):
    # The interface speaks in the novel's own dialogue box.
    add ("images/gui/dialogue_box/%s/dialogue_box.png" % dg_skin()) xpos 174 ypos 916
    if slow:
        text message style "dg_say" xpos 204 ypos 998 yanchor 0.5 xmaximum 1500 slow_cps True
    else:
        text message style "dg_say" xpos 204 ypos 998 yanchor 0.5 xmaximum 1500

screen dg_login():
    modal True
    use dg_chrome(u"ВХОД", Return("back"))
    vbox:
        at dg_enter(0)
        xalign 0.5
        ypos 420
        spacing 0
        text u"DON-GEN" style "dg_title" size 96 xalign 0.5
        text u"Своя история в «Совёнке»" style "dg_sub" size 38 xalign 0.5
    vbox:
        at dg_enter(1)
        xalign 0.5
        ypos 588
        spacing 14
        xsize 900
        text u"Опишите завязку — и получите главу с героями, местами и музыкой «Бесконечного лета». Каждая глава заканчивается выбором, а продолжение пишется по выбранной ветке." style "dg_text" text_align 0.5 xalign 0.5
    vbox:
        at dg_enter(2)
        xalign 0.5
        ypos 716
        spacing 8
        textbutton u"Войти через ChatGPT" style "dg_primary" xalign 0.5 action Return("login")
        if dg_runtime.app.stories:
            textbutton u"Читать сохранённые истории" style "dg_act" xalign 0.5 action Return("offline")
        textbutton u"Открыть RPG без входа" style "dg_act" xalign 0.5 action Return("offline")
        null height 6
        text u"Вход откроется в браузере. Завязка и текст истории отправляются в ChatGPT и расходуют лимиты вашего аккаунта." style "dg_small" xmaximum 860 text_align 0.5 xalign 0.5
    use dg_narrator(u"Чтобы начать, подключите аккаунт ChatGPT. Отдельный ключ API и другие программы не нужны.")

screen dg_home():
    modal True
    $ stories = dg_runtime.app.stories
    if renpy.loadable("mods/don_gen/images/don_gen_atlas.png"):
        add im.Scale("mods/don_gen/images/don_gen_atlas.png", 1920, 1080)
    else:
        add Solid("#142e35")
    add Solid("#081b28d8")
    use dg_chrome(u"ГЛАВНОЕ МЕНЮ")
    frame:
        background Solid("#102c39e9")
        xpos 95 ypos 132 xsize 1740 ysize 825
        padding (52, 38)
        hbox:
            spacing 57
            vbox:
                xsize 890 spacing 19
                text u"DON-GEN" style "dg_title" size 108 color "#ffe0a0"
                text u"ТВОЙ ЛАГЕРЬ. ТВОИ РЕШЕНИЯ." style "dg_meta" size 26 color "#f0cf97"
                text u"Живой Совёнок: путешествия, персонажи со своими планами, нелинейные истории и свободные действия. AI описывает события, а мир помнит последствия." style "dg_text" size 29 xmaximum 840
                null height 16
                frame:
                    background Solid("#21434cf2")
                    padding (29, 25) xsize 855
                    vbox:
                        spacing 14
                        text u"ОТКРЫТЫЙ МИР" style "dg_meta" size 26 color "#ffe1aa"
                        textbutton u"Открытый мир · RPG" style "dg_primary" action Return(("rpg", None))
                        text u"Свой герой · интерактивная карта · выборы и собственные поступки" style "dg_text" size 23 xmaximum 765
                frame:
                    background Solid("#18323bd9")
                    padding (25, 20) xsize 855
                    vbox:
                        spacing 10
                        text u"КЛАССИЧЕСКАЯ AI-ИСТОРИЯ" style "dg_meta" size 24
                        textbutton u"Начать новую историю" style "dg_act" action Return(("new", None))
                        text u"Режим глав с генерацией продолжения по выбранным ответам." style "dg_text" size 22
            vbox:
                xsize 635 spacing 18
                text u"ТВОЯ БИБЛИОТЕКА" style "dg_title" size 43
                frame:
                    background Solid("#081f2bdc")
                    padding (20, 16) xsize 630 ysize 404
                    viewport:
                        mousewheel True scrollbars "vertical" ysize 362
                        vbox:
                            spacing 11
                            if not stories:
                                text u"Здесь появятся главы классических AI-историй. Сохранённые RPG-смены находятся внутри «Открытого мира»." style "dg_text" size 25 xmaximum 550
                            for number, story in enumerate(stories):
                                textbutton dg_literal(u"%02d. %s" % (number + 1, story["title"][:70])) style "dg_row" action Return(("story", story["id"]))
                textbutton u"НАСТРОЙКИ" style "dg_act" action Return(("settings", None))
                textbutton u"ДИАГНОСТИКА" style "dg_act" action Return(("diagnostics", None))
                textbutton u"СОХРАНЕНИЯ ИГРЫ" style "dg_act" action ShowMenu("load")
                textbutton u"ВЫЙТИ" style "dg_act" action Return(("exit", None))
    if dg_runtime.app.library.list_warnings:
        use dg_narrator(u"Часть сохранённых историй не удалось открыть. Проверьте диагностику DON-GEN.")

screen dg_new():
    modal True
    key "rollback" action NullAction()
    key "rollforward" action NullAction()
    default premise = ""
    use dg_chrome(u"НОВАЯ ИСТОРИЯ", Return(""))
    vbox:
        at dg_enter(0)
        xpos 120
        ypos 150
        text u"Какое лето вы хотите прожить?" style "dg_title" size 64
    fixed:
        at dg_enter(1)
        xpos 420
        ypos 280
        xsize 1080
        ysize 480
        add Solid("#00000040") xoffset 10 yoffset 12
        add DG_PAPER
        vbox:
            xpos 56
            ypos 42
            xsize 968
            spacing 14
            text u"ЗАВЯЗКА" style "dg_ink_label"
            fixed:
                xsize 968
                ysize 350
                if not premise:
                    text u"Кого вы встретите? Что случится в первый день? Какое у этой истории настроение?" style "dg_ink_hint" xmaximum 920
                viewport:
                    mousewheel True
                    scrollbars "vertical"
                    style_prefix "dg_paper"
                    input:
                        copypaste True
                        value ScreenVariableInputValue("premise")
                        style "dg_ink_input"
                        length 4000
                        xmaximum 920
    hbox:
        at dg_enter(2)
        xpos 420
        ypos 800
        spacing 36
        textbutton u"Начать историю" style "dg_primary" sensitive bool(premise.strip()) action Return(premise.strip())
        textbutton u"Отмена" style "dg_act" yalign 0.5 action Return("")
    use dg_narrator(u"Например: «Мы с Леной нашли в библиотеке письмо из будущего. Хочу неспешную загадочную историю с тёплым юмором».")

screen dg_source_select():
    modal True
    use dg_chrome(u"ИСТОЧНИК ИСТОРИИ", Return(""))
    vbox:
        at dg_enter(0)
        xpos 120
        ypos 150
        text u"На какой версии мира опираться?" style "dg_title" size 64
        text u"Это влияет на характеры, отношения и детали мира. Сама история всё равно генерируется заново." style "dg_sub" size 30 xmaximum 1500

    frame:
        at dg_enter(1)
        style "dg_box"
        xpos 300
        ypos 330
        xsize 1320
        ysize 500
        vbox:
            xalign 0.5
            yalign 0.5
            spacing 24
            textbutton u"Оригинальное «Бесконечное лето»" style "dg_primary" xalign 0.5 action Return("vanilla")
            if dg_detect_7dl_root():
                text u"7 дней лета · Complete Edition · Мику" style "dg_meta" xalign 0.5
                hbox:
                    xalign 0.5
                    spacing 24
                    textbutton u"7ДЛ" style "dg_act" action Return("7dl:mi_7dl")
                    textbutton u"DJ" style "dg_act" action Return("7dl:mi_dj")
                    textbutton u"Классика" style "dg_act" action Return("7dl:mi_cl")
            else:
                text u"7 дней лета: Complete Edition не найден в этой Steam-библиотеке. Оригинальный режим доступен без него." style "dg_text" text_align 0.5 xmaximum 1000 xalign 0.5
            null height 6
            textbutton u"Назад" style "dg_act" xalign 0.5 action Return("")

    use dg_narrator(u"7ДЛ читается только как источник текста: чужой Ren'Py-код не запускается. На первом запуске профиль 7ДЛ построит локальный индекс сценария.")


screen dg_choice_input():
    modal True
    key "rollback" action NullAction()
    key "rollforward" action NullAction()
    key "game_menu" action Return("")
    key ["K_RETURN", "K_KP_ENTER"] action If(bool(dg_custom_choice.strip()), Return(dg_custom_choice.strip()), NullAction())
    add Solid("#00000080")
    frame:
        background DG_PAPER
        padding (56, 42)
        align (0.5, 0.5)
        xsize 1080
        vbox:
            spacing 20
            text u"Свой вариант" style "dg_ink_title"
            text u"Что вы сделаете или скажете? История продолжится с этого решения." style "dg_ink_small"
            viewport:
                mousewheel True
                scrollbars "vertical"
                style_prefix "dg_paper"
                ysize 240
                input:
                    value VariableInputValue("dg_custom_choice")
                    style "dg_ink_input"
                    length dg_runtime.dg_core.CUSTOM_CHOICE_LIMIT
                    copypaste True
                    xmaximum 920
            text (u"%d / %d" % (len(dg_custom_choice), dg_runtime.dg_core.CUSTOM_CHOICE_LIMIT)) style "dg_ink_small"
            hbox:
                spacing 36
                textbutton u"Продолжить" style "dg_ink_act" sensitive bool(dg_custom_choice.strip()) action Return(dg_custom_choice.strip())
                textbutton u"Отмена" style "dg_ink_act" action Return("")

screen dg_wait(mode="quick"):
    modal True
    default shown = False
    default wait_state = None
    key "game_menu" action NullAction()
    key "rollback" action NullAction()
    if mode == "chapter":
        use dg_chrome(u"НОВАЯ ГЛАВА")
        vbox:
            at dg_enter(0)
            xalign 0.5
            ypos 400
            spacing 22
            xsize 1400
            hbox:
                xalign 0.5
                text dg_wait_title() style "dg_title_plain" size 86
                if persistent.dg_motion:
                    for i in range(3):
                        text u"." style "dg_title_plain" size 86 at dg_dot(i * 0.3)
                else:
                    text u"…" style "dg_title_plain" size 86
            text dg_elapsed() style "dg_label_plain" xalign 0.5
            text dg_literal(dg_runtime.app.status) style "dg_small" outlines [] xalign 0.5 text_align 0.5
        use dg_narrator(u"Глава пишется несколько минут. Когда она будет готова, история продолжится сама.")
    elif mode == "login":
        use dg_chrome(u"ВХОД")
        vbox:
            at dg_enter(0)
            xalign 0.5
            ypos 450
            spacing 22
            xsize 1100
            text u"Завершите вход в браузере" style "dg_title" size 76 xalign 0.5
            text u"Открылась страница входа ChatGPT. Когда вход завершится, игра продолжится сама." style "dg_text" xalign 0.5 text_align 0.5
            hbox:
                xalign 0.5
                spacing 40
                if dg_runtime.app.client.login_url:
                    textbutton u"Открыть браузер снова" style "dg_act" action OpenURL(dg_runtime.app.client.login_url)
                textbutton u"Отменить вход" style "dg_act" action Function(dg_runtime.app.cancel.set)
        use dg_narrator(u"Откроется страница ChatGPT. После входа вернитесь в игру — дальше всё продолжится само.")
    else:
        timer 0.8 action SetScreenVariable("shown", True)
        if shown:
            use dg_narrator(dg_literal(dg_runtime.app.status or u"Подождите…"), slow=False)
    timer 0.2 repeat True action Function(dg_poll, mode, _update_screens=False)

screen dg_error():
    modal True
    use dg_chrome(u"ЧТО-ТО ПОШЛО НЕ ТАК")
    fixed:
        at dg_enter(0)
        xpos 420
        ypos 200
        xsize 1080
        ysize 570
        add Solid("#00000040") xoffset 10 yoffset 12
        add DG_PAPER
        vbox:
            xpos 56
            ypos 44
            xsize 968
            spacing 14
            text u"Не получилось продолжить" style "dg_ink_title"
            text u"Уже написанные главы сохранены. Вот что сообщил сервис:" style "dg_ink"
            viewport:
                mousewheel True
                draggable False
                scrollbars "vertical"
                style_prefix "dg_paper"
                ysize 330
                text dg_literal(dg_runtime.app.error or u"Неизвестная ошибка") style "dg_ink_small" xmaximum 920
    textbutton u"Понятно" style "dg_primary" xpos 420 ypos 800 action Return() at dg_enter(1)
    use dg_narrator(u"Ничего не потеряно: истории и главы лежат на диске. Можно повторить попытку позже.")

screen dg_settings():
    modal True
    use dg_chrome(u"НАСТРОЙКИ", Return("back"))
    vbox:
        at dg_enter(0)
        xpos 120
        ypos 150
        spacing 2
        text u"Настройки" style "dg_title"
        text u"Рассказчик, аккаунт и оформление" style "dg_sub"
    frame:
        at dg_enter(1)
        style "dg_box"
        xpos 60
        ypos 300
        xsize 860
        ysize 596
        vbox:
            spacing 18
            text u"РАССКАЗЧИК" style "dg_meta"
            viewport:
                mousewheel True
                draggable False
                scrollbars "vertical"
                style_prefix "gs"
                ysize 230
                vbox:
                    spacing 12
                    button:
                        style "dg_row"
                        selected (persistent.dg_model is None)
                        action Function(dg_save_model, None)
                        at dg_hover()
                        hbox:
                            spacing 16
                            if persistent.dg_model is None:
                                add "images/gui/settings/leaf.png" yalign 0.5
                            else:
                                null width 22
                            text u"Автовыбор · GPT-6 Astra, облегчённый режим" style "dg_row_text" xmaximum 640
                    for model in dg_runtime.app.models:
                        button:
                            style "dg_row"
                            selected (persistent.dg_model == model["slug"])
                            action Function(dg_save_model, model["slug"])
                            at dg_hover()
                            hbox:
                                spacing 16
                                if persistent.dg_model == model["slug"]:
                                    add "images/gui/settings/leaf.png" yalign 0.5
                                else:
                                    null width 22
                                text dg_literal(model.get("display_name") or model["slug"]) style "dg_row_text" xmaximum 640
            if not dg_runtime.app.models:
                text (u"Список моделей появится после входа в аккаунт." if not dg_runtime.app.client.authenticated() else u"Список моделей пока пуст. Попробуйте обновить его.") style "dg_small"
            button:
                style "dg_row"
                selected persistent.dg_fast_mode
                action [ToggleField(persistent, "dg_fast_mode"), Function(renpy.save_persistent)]
                hbox:
                    spacing 16
                    frame:
                        background Solid("#e6e6df")
                        padding (2, 2)
                        xysize (28, 28)
                        yalign 0.5
                        fixed:
                            add Solid("#272c24")
                            if persistent.dg_fast_mode:
                                add Solid("#ffdd7d") xysize (3, 10) rotate -45 xpos 3 ypos 9
                                add Solid("#ffdd7d") xysize (3, 17) rotate 45 xpos 9 ypos 3
                    text u"Fast mode" style "dg_row_text"
            text u"Истории генерируются быстрее, но лимиты аккаунта расходуются быстрее. Работает на моделях с поддержкой Fast mode." style "dg_small" outlines []
    fixed:
        at dg_enter(2)
        xpos 1060
        ypos 300
        xsize 740
        ysize 500
        add Solid("#00000040") xoffset 10 yoffset 12
        add DG_PAPER
        vbox:
            xpos 52
            ypos 40
            xsize 636
            spacing 10
            text u"АККАУНТ" style "dg_ink_label"
            if dg_runtime.app.client.authenticated():
                text u"ChatGPT подключён. Новые главы пишутся за счёт лимитов этого аккаунта." style "dg_ink_small"
                textbutton u"Отключить аккаунт" style "dg_ink_act" action Return("logout")
            else:
                text u"Аккаунт не подключён. Уже написанные главы можно читать и так." style "dg_ink_small"
                textbutton u"Войти через ChatGPT" style "dg_ink_act" action Return("login")
            textbutton u"Обновить список моделей" style "dg_ink_act" action Return("refresh")
            null height 22
            text u"ОФОРМЛЕНИЕ" style "dg_ink_label"
            textbutton (u"Музыка и звуки меню · вкл" if persistent.dg_atmosphere_sound else u"Музыка и звуки меню · выкл") style "dg_ink_act" action [ToggleField(persistent, "dg_atmosphere_sound"), Function(dg_menu_audio, dg_current)]
            textbutton (u"Движение · вкл" if persistent.dg_motion else u"Движение · выкл") style "dg_ink_act" action ToggleField(persistent, "dg_motion")
    textbutton u"Готово" style "dg_primary" xpos 1060 ypos 830 action Return("back") at dg_enter(3)
    use dg_narrator(u"Новая модель начнёт работать со следующей главы. Уже написанные главы останутся прежними.")

label don_gen:
    $ dg_setup()
    $ persistent.sprite_time = "day"
    $ day_time()
    $ set_mode_adv()
    window hide
    $ dg_place("gate")
    $ dg_run("quick", dg_runtime.app.refresh_stories)
    if dg_runtime.app.error:
        call screen dg_error
    if not dg_runtime.app.client.authenticated():
        call screen dg_login
        if _return == "back":
            hide screen dg_scene
            $ dg_current = None
            return
        if _return == "login":
            call dg_connect
    jump dg_menu

label dg_connect:
    $ dg_run("login", dg_runtime.app.login)
    if dg_runtime.app.error:
        call screen dg_error
    return

label dg_menu:
    window hide
    $ dg_place("library")
    $ dg_run("quick", dg_runtime.app.refresh_stories)
    if dg_runtime.app.error:
        call screen dg_error
    call screen dg_home
    $ dg_action, dg_value = _return
    if dg_action == "exit":
        hide screen dg_scene
        $ dg_current = None
        return
    if dg_action == "rpg":
        jump dg_rpg_main
    if dg_action == "diagnostics":
        call screen dg_diagnostics
        jump dg_menu
    if dg_action == "settings":
        jump dg_settings_label
    if dg_action == "new":
        if not dg_runtime.app.client.authenticated():
            call dg_connect
            if not dg_runtime.app.client.authenticated():
                jump dg_menu
        $ dg_place("glade")
        call screen dg_new
        if not _return:
            jump dg_menu
        $ dg_premise = _return
        call screen dg_source_select
        if not _return:
            jump dg_menu
        $ dg_run("quick", dg_runtime.app.create, dg_premise, _return)
        if dg_runtime.app.error:
            call screen dg_error
            jump dg_menu
        $ dg_story_id = dg_runtime.app.result["id"]
    else:
        $ dg_story_id = dg_value
    $ dg_parent_id = None
    $ dg_choice_index = None
    $ dg_custom_choice = None
    scene black
    stop music
    stop ambience
    jump dg_fetch

label dg_settings_label:
    $ dg_place("hall")
    if dg_runtime.app.client.authenticated() and not dg_runtime.app.models:
        $ dg_run("quick", dg_runtime.app.refresh_models)
        if dg_runtime.app.error:
            call screen dg_error
    call screen dg_settings
    if _return == "login":
        call dg_connect
        jump dg_settings_label
    if _return == "logout":
        $ dg_run("quick", dg_runtime.app.client.logout)
        $ dg_runtime.app.models = []
        if dg_runtime.app.error:
            call screen dg_error
        jump dg_settings_label
    if _return == "refresh":
        $ dg_run("quick", dg_runtime.app.refresh_models)
        if dg_runtime.app.error:
            call screen dg_error
        jump dg_settings_label
    jump dg_menu

label dg_fetch:
    # Immutable disk nodes make replay after rollback idempotent.
    $ dg_setup()
    $ dg_place("road")
    $ dg_run("chapter", dg_runtime.app.generate, dg_story_id, dg_parent_id, dg_choice_index, persistent.dg_model, dg_custom_choice, persistent.dg_fast_mode)
    if not dg_runtime.app.error and not dg_valid_chapter(dg_runtime.app.result):
        $ dg_runtime.app.error = u"Генерация не вернула корректную главу. Можно повторить попытку."
    if dg_runtime.app.error:
        call screen dg_error
        menu:
            "Попробовать снова":
                jump dg_fetch
            "Подключить ChatGPT":
                call dg_connect
                jump dg_fetch
            "К историям":
                jump dg_menu
    $ dg_node = dg_runtime.app.result
    $ dg_index = 0
    scene black
    hide screen dg_scene
    with Dissolve(1.0)
    $ dg_current = None
    jump dg_play

label dg_play:
    # Each native say/menu interaction has its own static Ren'Py statement.
    $ dg_setup()
    if not dg_valid_chapter(dg_node):
        $ dg_runtime.app.error = u"Глава отсутствует или повреждена. Вернись к списку историй и открой её снова."
        call screen dg_error
        jump dg_menu
    if dg_index < len(dg_node["commands"]):
        $ dg_command = dg_node["commands"][dg_index]
        if dg_command["op"] == "say":
            $ dg_say()
        else:
            $ dg_effect(dg_command)
        $ dg_index += 1
        jump dg_play
label dg_choose:
    if not dg_valid_chapter(dg_node):
        jump dg_menu
    if not dg_node["choices"]:
        menu:
            "История завершена."
            "К историям":
                jump dg_menu
    # This extra item belongs only to generated chapters; the global choice screen stays untouched.
    $ dg_custom_choice = None
    $ dg_choice_index = renpy.display_menu([(dg_literal(text), index) for index, text in enumerate(dg_node["choices"])] + [(u"Свой вариант…", "custom")])
    if dg_choice_index == "custom":
        $ dg_custom_choice = ""
        $ renpy.retain_after_load()
        call screen dg_choice_input
        if not _return:
            jump dg_choose
        $ dg_custom_choice = _return
        $ dg_choice_index = None
    $ dg_parent_id = dg_node["id"]
    jump dg_fetch

init 1002 python:
    def dg_trace_enabled():
        return os.path.isfile(os.path.join(config.savedir, "don_gen", "trace.enabled"))

    def dg_toggle_trace():
        path = os.path.join(config.savedir, "don_gen", "trace.enabled")
        if os.path.isfile(path):
            os.remove(path)
            dg_runtime.app.log.info("Detailed generation trace disabled")
        else:
            with open(path, "wb") as output:
                output.write(b"enabled")
            dg_runtime.app.log.warning("Detailed generation trace enabled; inspect for sensitive story text before sharing")
        renpy.restart_interaction()

    def dg_diagnostics_paths():
        root = os.path.join(config.savedir, "don_gen")
        game = os.path.abspath(os.path.join(config.gamedir, ".."))
        return [
            (u"Логи и сохранения DON-GEN", root),
            (u"Журнал запуска / действий", os.path.join(root, "don_gen.log")),
            (u"Журнал генератора", os.path.join(root, "don_gen_worker.log")),
            (u"RPG-сохранения", os.path.join(root, "_rpg")),
            (u"Расширенные трассы глав (при включении)", os.path.join(root, "traces")),
            (u"Ren'Py traceback.txt (возможный путь)", os.path.join(game, "traceback.txt")),
            (u"Ren'Py log.txt (возможный путь)", os.path.join(game, "log.txt")),
        ]

screen dg_diagnostics:
    modal True
    add Solid("#0c1c28")
    use dg_chrome(u"ДИАГНОСТИКА", Return())
    text u"DON-GEN · диагностика" style "dg_title" xpos 120 ypos 135 size 68
    text u"Автоматические логи действий и ошибок; расширенные трейсы — по желанию." style "dg_sub" xpos 120 ypos 237 size 26
    textbutton (u"Подробный трейс генерации: ВКЛ" if dg_trace_enabled() else u"Подробный трейс генерации: ВЫКЛ") style "dg_act" xpos 930 ypos 225 action Function(dg_toggle_trace)
    frame:
        background DG_PAPER
        padding (40, 30)
        xpos 110 ypos 305 xsize 1700 ysize 575
        viewport:
            mousewheel True
            scrollbars "vertical"
            ysize 495
            vbox:
                spacing 11
                for label, path in dg_diagnostics_paths():
                    text label style "dg_ink_label"
                    text dg_literal(path) style "dg_ink_small" size 24 xmaximum 1540
                null height 10
                text (u"Последняя ошибка: " + dg_literal(dg_runtime.app.error or u"нет")) style "dg_ink_small" size 24
    text u"При краше: traceback.txt + don_gen.log. При ошибках генерации: don_gen_worker.log." style "dg_small" xpos 140 ypos 915

