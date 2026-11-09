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
    import dg_comfy
    import dg_adult
    import dg_art
    import dg_narrative
    import dg_visual
    import dg_stage
    import dg_map
    import dg_resources
    import dg_turn
    import dg_bkrr

    def dg_rpg_notice_board():
        root = dg_bkrr.find_root(config.gamedir, dg_rpg_workshop_root())
        return dg_bkrr.board(root)

    class DgCampButton(renpy.Displayable):
        def __init__(self, fill, edge, **kwargs):
            super(DgCampButton, self).__init__(**kwargs)
            self.fill, self.edge = fill, edge

        def render(self, width, height, st, at):
            width, height = int(width), int(height)
            result = renpy.Render(width, height)
            canvas = result.canvas()
            def rounded(color, x, y, w, h, radius):
                canvas.rect(color, (x + radius, y, w - radius * 2, h))
                canvas.rect(color, (x, y + radius, w, h - radius * 2))
                for cx, cy in ((x + radius, y + radius), (x + w - radius - 1, y + radius),
                               (x + radius, y + h - radius - 1), (x + w - radius - 1, y + h - radius - 1)):
                    canvas.circle(color, (cx, cy), radius)
            radius = 7 if width >= 18 and height >= 18 else 1
            rounded(self.edge, 0, 0, width, height, radius)
            rounded(self.fill, 1, 1, width - 2, height - 2, radius - 1)
            return result

    def dg_camp_button_surface(fill, edge):
        return DgCampButton(fill, edge)

    def dg_rpg_vn_pages(text):
        # Narrative is shown in the game's regular Ren'Py say window.
        # Keep pages short enough for the classic bottom textbox.
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        if text is None:
            return []
        import re
        result = []
        for paragraph in re.split(u"\\n\\s*\\n", text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            sentences = re.split(u"(?<=[.!?…])\\s+", paragraph)
            page = u""
            for sentence in sentences:
                if not sentence:
                    continue
                if page and len(page) + len(sentence) + 1 > 240:
                    result.append(page)
                    page = u""
                if len(sentence) > 260:
                    tokens = sentence.split(u" ")
                    for token in tokens:
                        if page and len(page) + len(token) + 1 > 240:
                            result.append(page)
                            page = u""
                        page = page + (u" " if page else u"") + token
                else:
                    page = page + (u" " if page else u"") + sentence
            if page:
                result.append(page)
        return result

    def dg_rpg_preview_height(value, low, high, base, chars_per_row, row_height):
        # In Everlasting Summer's Ren'Py 7 store, 'min'/'max' may be unicode
        # globals rather than Python built-ins. Avoid either in screen code.
        height = base + len(value) // chars_per_row * row_height
        if height < low:
            return low
        if height > high:
            return high
        return height

    def dg_rpg_root():
        return dg_runtime.app.library.root

    def dg_rpg_start(name, age, days, history, source, pronouns, adult=False):
        state = dg_rpg.new_game(name, age, days, history, source, pronouns)
        if adult:
            dg_adult.set_enabled(state, True, confirmed=True)
        dg_rpg.save(dg_rpg_root(), state)
        store.dg_rpg_state = state
        store.dg_rpg_action_draft = u""
        logging.getLogger("don_gen").info("RPG created id=%s days=%s", state["id"], state["duration"])
        renpy.block_rollback()

    def dg_rpg_open(game_id):
        store.dg_rpg_action_draft = u""
        store.dg_rpg_state = dg_rpg.load(dg_rpg_root(), game_id)
        logging.getLogger("don_gen").info("RPG opened id=%s", game_id)
        renpy.block_rollback()

    def dg_rpg_apply(action, arg=None):
        state = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        transactional = action in ("conversation", "world", "personal", "incident", "route")
        pending = dg_turn.begin(state) if transactional else None
        if pending is not None:
            state = pending["state"]
        if action in ("talk", "route", "conversation", "world", "free", "personal", "incident", "hybrid", "spontaneous"):
            store.dg_rpg_scene_context = dg_stage.freeze(state)
        if action == "move":
            dg_rpg.move(state, arg)
        elif action == "talk":
            dg_rpg.activity(state, "talk", arg)
        elif action == "route":
            route_level = dg_rpg.available_route_events(state, arg[0])[0][0]
            dg_rpg.route_event(state, arg[0], arg[1])
            pending.update(who=arg[0], intention=u"Важный разговор: " + arg[1],
                           result=dg_dialogue.route_conclusion(arg[0], route_level, arg[1]))
        elif action == "conversation":
            store.dg_rpg_last_scene = dg_rpg.conversation(state, arg[0], arg[1], arg[2])
            if store.dg_rpg_last_scene:
                pending.update(who=arg[0], intention=store.dg_rpg_last_scene['topic'] + u" — " + arg[2],
                               result=store.dg_rpg_last_scene['text'])
        elif action == "world":
            store.dg_rpg_last_world = dg_rpg.story_choice(state, arg)
            pending.update(who=store.dg_rpg_last_world['npc'],
                           intention=store.dg_rpg_last_world['title'] + u" — " + arg,
                           result=store.dg_rpg_last_world['text'])
        elif action == "free":
            store.dg_rpg_last_action = dg_rpg.free_action(state, arg)
        elif action == "personal":
            store.dg_rpg_last_personal = dg_rpg.personal_choice(state, arg[0], arg[1])
            pending.update(who=arg[0], intention=store.dg_rpg_last_personal['title'] + u" — " + arg[1],
                           result=store.dg_rpg_last_personal['text'])
        elif action == "incident":
            store.dg_rpg_last_incident = dg_rpg.social_encounter(state, arg)
            pending.update(who=None, intention=store.dg_rpg_last_incident['title'] + u" — " + arg,
                           result=store.dg_rpg_last_incident['text'])
        elif action == "hybrid":
            store.dg_rpg_hybrid_entry = dg_hybrid.commit(state, arg[0], arg[1])
        elif action == "adult_mode":
            dg_adult.set_enabled(state, arg, confirmed=bool(arg))
        elif action == "profile":
            dg_rpg.set_source(state, arg)
        elif action == "remember_narrative":
            if store.dg_rpg_pending_turn is not None:
                state = dg_turn.finish(dg_rpg_root(), store.dg_rpg_pending_turn, arg[0], arg[1])
                store.dg_rpg_pending_turn = None
                store.dg_rpg_state = state
                renpy.block_rollback()
                return
            dg_narrative.remember_scene(state, arg[0], arg[1])
        elif action == "spontaneous":
            who=arg
            if state["finished"] or (who is not None and dg_rpg.where_is(state,who)!=state["place"]):
                raise ValueError("Encounter unavailable")
            if state["energy"]<4:
                raise ValueError("Not enough energy")
            key="%d:%d:%s:%s" % (state["day"],state["slot"],state["place"],who or "-")
            state.setdefault("surprise_counts",{})
            state["surprise_counts"][key]=state["surprise_counts"].get(key,0)+1
            state["energy"]-=4
            dg_rpg._journal(state,u"Неожиданная встреча: %s." %
                            (dg_rpg.NPC_NAMES[who] if who else dg_rpg.PLACE_NAMES[state["place"]]))
            dg_rpg._tick(state)
        elif action == "cg_record":
            if dg_art.marker(state,arg) is None:
                raise ValueError("CG access denied")
            status=dg_art.resolve(dg_rpg_root(),state["id"],arg["kind"],
                                  arg["key"],dg_rpg_cg_builtin(arg))
            if status["status"] == "missing":
                raise ValueError("CG not available")
            state.setdefault("cg_history",[])
            if not any(x["key"] == arg["key"] and x["kind"] == arg["kind"]
                       for x in state["cg_history"]):
                state["cg_history"].append(dict(arg))
                state["cg_history"] = state["cg_history"][-60:]
        elif action == "contract":
            store.dg_rpg_last_contract = dg_rpg.accept_contract(state, arg)
        else:
            dg_rpg.activity(state, action)
        if pending is None:
            dg_rpg.save(dg_rpg_root(), state)
        store.dg_rpg_pending_turn = pending
        store.dg_rpg_state = state
        if action == "move":
            store.dg_rpg_scene_context = dg_stage.freeze(state)
        logging.getLogger("don_gen").info("RPG action=%s day=%d slot=%d place=%s", action, state["day"], state["slot"], state["place"])
        renpy.block_rollback()

    def dg_rpg_hybrid_preview(mode, action, who=None, topic=None):
        current = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        try:
            plan = dg_hybrid.preview(current, action, mode, who, topic)
        except (ValueError, TypeError, UnicodeError) as exc:
            try:
                readable_error = unicode(exc)
            except UnicodeError:
                readable_error = u"Невозможно обработать ввод. Попробуй другую формулировку."
            plan = {"status":"unknown","mode":mode,"message":readable_error,
                    "action":u"","who":who,"topic":topic}
        # Always publish a preview, including rejections. Follow-up screens
        # must never access an undefined store variable after invalid input.
        store.dg_rpg_hybrid_plan = plan
        logging.getLogger("don_gen").info(
            "Hybrid preview mode=%s day=%d valid=%s", mode, current["day"],
            plan["status"] == "ready")

    def dg_rpg_hybrid_generate(plan):
        # The background worker ONLY generates a text string. No save writes.
        current = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        instructions, prompt = dg_hybrid.build_request(current, plan)
        context = json.loads(prompt)
        context['visual_scene_facts'] = dg_rpg_visual_brief(current)
        prompt = json.dumps(context, ensure_ascii=False, sort_keys=True)
        app = dg_runtime.app
        # The 7DL source is read-only reference context, never executed.
        if current["source"].startswith("7dl:") and plan.get("who") == "mi":
            root=(app.catalog.get("source_roots") or {}).get("7dl")
            if root and os.path.isdir(root):
                try:
                    import dg_source_7dl
                    raw=dg_source_7dl.source_context(
                        root,os.path.join(dg_rpg_root(),"_source_cache"),
                        current["source"].split(":",1)[1],
                        u"Мику "+plan["action"][:190],mode="divergent",
                        day=(current["day"] if current["day"]<=7 else 7),
                        limit=3,max_chars=5200)
                    context=json.loads(prompt)
                    context["reference_7dl_source"]=raw
                    prompt=json.dumps(context,ensure_ascii=False,sort_keys=True)
                except (IOError,OSError,ValueError,TypeError):
                    logging.getLogger("don_gen").warning("7DL hybrid context unavailable",exc_info=True)
        if not app.models:
            app.refresh_models()
        model = dg_backend.default_model(app.models, persistent.dg_model)
        app.set_status(u"Пишем сцену с зафиксированным игровым исходом…")
        story = app.client.generate(instructions, prompt, model=model,
                                    effort=dg_backend.DEFAULT_EFFORT,
                                    fast_mode=persistent.dg_fast_mode)
        if not isinstance(story, basestring) or len(dg_stage.readable(story).strip()) < 45 or len(story) > dg_hybrid.MAX_SCENE:
            raise ValueError("AI returned invalid scene length")
        dg_stage.validate_speakers(story, dg_stage.freeze(current, plan.get("who"))["present"])
        return story.strip()

    def dg_rpg_auto_generate(kind, who, identity, story, choices=None):
        # The worker only WRITES PROSE; world mechanics remain locked.
        import copy
        pending = store.dg_rpg_pending_turn
        state = (copy.deepcopy(pending["state"]) if pending is not None else
                 dg_rpg.load(dg_rpg_root(),dg_rpg_state["id"]))
        app=dg_runtime.app
        if (kind == "result" or kind == "npc_result") and dg_rpg_scene_context is not None:
            import copy
            state = copy.deepcopy(state)
            for key in ("day", "slot", "place"):
                state[key] = dg_rpg_scene_context[key]
        ref=u""
        # Use the actual installed 7DL route text when available. If no 7DL
        # resources exist, the route-specific persona profile still applies.
        if who=="mi" and state["source"].startswith("7dl:"):
            root=(app.catalog.get("source_roots") or {}).get("7dl")
            if root and os.path.isdir(root):
                try:
                    import dg_source_7dl
                    ref=dg_source_7dl.source_context(
                        root,os.path.join(dg_rpg_root(),"_source_cache"),
                        state["source"].split(":",1)[1],
                        dg_rpg.NPC_NAMES[who]+u" "+story[:160],
                        mode="divergent",day=(state["day"] if state["day"]<=7 else 7),
                        limit=3,max_chars=5200)
                except (IOError,OSError,ValueError,TypeError):
                    logging.getLogger("don_gen").warning(
                        "7DL context unavailable for auto scene",exc_info=True)
        instructions,prompt=dg_narrative.request(
            state,kind,who,identity,story,choices=choices,source_reference=ref)
        context = json.loads(prompt)
        context['visual_scene_facts'] = dg_rpg_visual_brief(state)
        prompt = json.dumps(context, ensure_ascii=False, sort_keys=True)
        instructions+=u" "+dg_adult.scene_policy(state,who)+u" "+dg_stage.FORMATTING
        if not app.models:
            app.refresh_models()
        model=dg_backend.default_model(app.models,persistent.dg_model)
        app.set_status(u"Рассказываем уникальный эпизод лагеря…")
        result=app.client.generate(instructions,prompt,model=model,
                                   effort=dg_backend.DEFAULT_EFFORT,
                                   fast_mode=persistent.dg_fast_mode)
        if isinstance(result,bytes):
            result=result.decode("utf-8")
        if not isinstance(result,unicode) or len(dg_stage.readable(result).strip())<100 or len(result)>12000:
            raise ValueError("Narrator returned invalid scene text")
        dg_stage.validate_speakers(result, dg_stage.freeze(state, who)["present"])
        return result.strip()

    # Classic resources stay in the private gen_assets pack, imported by install.ps1.
    DG_MAP_ROOT = "mods/don_gen/images/gen_assets/"
    DG_MAP_USER = DG_MAP_ROOT + "map_bg.jpg"
    DG_MAP_HOVER = DG_MAP_ROOT + "map_avaliable.jpg"
    DG_MAP_SELECTED = DG_MAP_ROOT + "map_selected.jpg"
    DG_MAP_ICON_BY_NPC = {
        "dv":"dv", "el":"el", "mi":"mi", "mz":"zh", "mt":"od",
        "sl":"sl", "sh":"sh", "cs":"vi", "us":"ul", "un":"un", "uv":"yu"
    }

    def dg_rpg_workshop_root():
        roots = dg_runtime.app.catalog.get("source_roots", {})
        return roots.get("7dl") or dg_detect_7dl_root()

    def dg_rpg_map_asset(filename):
        external = dg_resources.map_asset(dg_rpg_workshop_root(), filename)
        return external or DG_MAP_ROOT + filename

    def dg_map_npc_icon(who):
        external = dg_resources.map_icon(dg_rpg_workshop_root(), who)
        if external:
            return im.Scale(external, 42, 42)
        code = "me" if who == "hero" else DG_MAP_ICON_BY_NPC.get(who)
        if code is None:
            return None
        path = DG_MAP_ROOT + "map_icon_%s.png" % code
        return im.Scale(path, 42, 42) if renpy.loadable(path) else None

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

    DG_RPG_EXACT_BG = ("square","gate","cabins","canteen","library","clubs",
                       "stage","beach","lake","forest","infirmary","sports")

    def dg_rpg_visual_state():
        if dg_rpg_stage_active and dg_rpg_scene_context is not None:
            return dg_rpg_scene_context
        return dg_rpg_state

    def dg_rpg_bg_native(place, visual=None):
        # Prefer the actual location AND matching time of day when available.
        # Only exact 12 canonical locations block manual BG generation.
        visual = visual or dg_rpg_visual_state()
        if dg_rpg_state.get("source") == dg_bkrr.SOURCE:
            root = dg_bkrr.find_root(config.gamedir, dg_rpg_workshop_root())
            backdrop = dg_bkrr.background(root, place, visual["slot"])
            if backdrop:
                return backdrop
        external = dg_resources.background(
            dg_runtime.app.catalog.get("source_assets", {}).get("7dl", {}),
            place, visual["slot"])
        if place not in DG_RPG_EXACT_BG:
            return external
        base = DG_RPG_BG.get(place)
        if base is None and place.startswith("cabin_"):
            base = "bg ext_houses_day"
        for name in dg_visual.background_names(base, visual["slot"]):
            if name in dg_runtime.original_images:
                return name
        return external

    def dg_rpg_visual_brief(state):
        backdrop = dg_rpg_bg_native(state['place'], visual=state) or ''
        filename = os.path.basename(backdrop).lower().replace('bg ', '')
        setting = 'exterior' if filename.startswith('ext_') else 'interior' if filename.startswith('int_') else None
        return {'setting':setting, 'rule':u'Сцена должна соответствовать показанному фону: exterior — снаружи, interior — внутри. Не меняй место без действия игрока.'}

    def dg_rpg_bg_status():
        place = dg_rpg_visual_state()["place"]
        native = dg_rpg_bg_native(place)
        return dg_art.resolve(dg_rpg_root(), dg_rpg_state["id"],
                              "background", place, native,
                              getattr(persistent,"dg_prefer_generated",True))

    def dg_rpg_bg():
        place = dg_rpg_visual_state()["place"]
        available = dg_rpg_bg_status()
        if available["status"] == "generated" and renpy.loadable(available["path"]):
            return Image(available["path"])
        if available["status"] == "builtin":
            native = dg_runtime.original_images.get(available["path"])
            return native if native is not None else Image(available["path"])
        # Fallback scenery is shown while specific visual art is absent.
        base = DG_RPG_BG.get(place)
        if base is None and place.startswith("cabin_"):
            base = "bg ext_houses_day"
        for name in dg_visual.background_names(base, dg_rpg_visual_state()["slot"]):
            if name in dg_runtime.original_images:
                return dg_runtime.original_images[name]
        return Solid("#173039")

    def dg_rpg_sprite(who, emotion="normal", distance="normal", pose=None):
        # Original game registered sprites first; physical 7DL/vanilla layer
        # composition when the exact named pose is missing. No image generation.
        if who not in dg_rpg.NPC_NAMES:
            return None
        if pose is not None:
            for name in dg_visual.sprite_queries(who, emotion, distance):
                sprite = dg_7dl_sprite_displayable(name, pose_hint=pose)
                if sprite is not None:
                    return sprite
        known = dg_visual.sprite_names(who,emotion,distance,
                                        dg_runtime.original_images.keys())
        exact=[name for name in known if
               (name.endswith(" "+distance) if distance!="normal"
                else not name.endswith((" far"," close")))]
        # For the specific 7DL route, layer-aware image composition may supply
        # a more expressive pose that doesn't have a registered vanilla name.
        use_7dl=dg_rpg_state["source"].startswith("7dl:")
        if use_7dl:
            for name in dg_visual.sprite_queries(who,emotion,distance):
                sprite=dg_7dl_sprite_displayable(name)
                if sprite is not None:
                    return sprite
        if exact:
            return dg_runtime.original_images[exact[0]]
        # Only after trying genuine close/far poses do we accept an existing
        # normal-distance sprite. Never scale a normal pose as if it were close.
        if known:
            return dg_runtime.original_images[known[0]]
        for name in dg_visual.sprite_queries(who,emotion,distance):
            sprite=dg_7dl_sprite_displayable(name)
            if sprite is not None:
                return sprite
        # Old generated portraits are a last fallback; they must not replace
        # expressive canonical sprites when those are available.
        custom = dg_rpg.asset_path(dg_rpg_root(),dg_rpg_state["id"],"sprite",who)
        if renpy.loadable(custom):
            return Image(custom)
        logging.getLogger("don_gen").warning("No original sprite found for npc=%s emotion=%s distance=%s",
                                             who,emotion,distance)
        return None

    def dg_rpg_say_character(who):
        native = getattr(store, who or "narrator", None) if who != "hero" else None
        name = None if who is None else ((dg_rpg_scene_context or {}).get("hero_name", dg_rpg_state["hero"]["name"]) if who == "hero" else dg_stage.NAMES[who])
        # Keep the host's say screen, but give this mod explicit typography.
        # Never modify the global characters or other installed mods' styles.
        kind = native if isinstance(native, renpy.character.ADVCharacter) else None
        return Character(dg_literal(name) if name is not None else None, kind=kind,
                         who_font="fonts/calibri.ttf", who_size=28, who_bold=True,
                         who_color=dg_stage.COLORS.get(who, "#ffaa00"), who_outlines=[],
                         what_font="fonts/calibri.ttf", what_size=28, what_bold=False,
                         what_color="#f3d887", what_outlines=[])

    def dg_rpg_stage_actors(turns, cast_ids, turn):
        # Update one actor's expression; narration does not make everybody cry/smile.
        if turn["who"] in dg_stage.NAMES:
            if turn['who'] not in turn.get('stage', {}):
                inferred = dg_visual.mood(turn["text"])
                if inferred != 'normal':
                    store.dg_rpg_actor_moods[turn["who"]] = inferred
        visible = dg_stage.positions(cast_ids, turn["who"])
        visible_ids = [who for who, x in visible]
        for who in dg_stage.NAMES:
            if who not in visible_ids:
                renpy.hide("dg_actor_" + who)
        signature = []
        for who, x in visible:
            direction = turn.get('stage', {}).get(who, {})
            emotion = direction.get('emotion', dg_rpg_actor_moods.get(who, "normal"))
            store.dg_rpg_actor_moods[who] = emotion
            signature.append((who, emotion, direction.get('distance', 'normal'), direction.get('pose'), x))
            sprite = dg_rpg_sprite(who, emotion, direction.get('distance', 'normal'), direction.get('pose'))
            if sprite is not None:
                renpy.show("dg_actor_" + who, what=Transform(sprite, xpos=x, xanchor=.5, ypos=1.0, yanchor=1.0),
                           zorder=15 if who == turn["who"] else 10)

        if store.dg_rpg_visual_cast != signature:
            store.dg_rpg_visual_cast = signature
            renpy.with_statement(Dissolve(.16))

    def dg_rpg_cg_builtin(plan):
        index_path = os.path.join(renpy.config.gamedir, "mods", "don_gen", "images", "gen_assets", "cg_index.json")
        if os.path.isfile(index_path):
            try:
                with open(index_path, "rb") as handle:
                    dictionary = json.loads(handle.read().decode("utf-8"))
                target = dg_art.approve_cg_lookup(dg_rpg_root(), dictionary, plan["key"])
                if target and renpy.loadable(target):
                    return target
            except (IOError, OSError, ValueError, TypeError):
                pass
        import dg_gallery
        candidate = dg_gallery.match(dg_gallery.catalog(dg_gallery.roots(dg_rpg_workshop_root())), plan)
        return candidate['path'] if candidate and renpy.loadable(candidate['path']) else None

    def dg_rpg_cg_for(source, title, description, who=None, action=u""):
        state=dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        explicit_adult=bool(dg_adult.classify_sensitive(action))
        # A mature AU CG is never inferred merely from the 18+ toggle.
        plan = dg_art.scene_plan(state, source, title, description, who,
                                 adult_requested=explicit_adult)
        if plan:
            context = dg_rpg_scene_context or dg_stage.freeze(state, who)
            present = context.get('present', [])
            cast_ids = dg_stage.cast(dg_stage.parse(description, present, who), present, who)
            plan.update(scene_place=context['place'], scene_slot=context['slot'],
                        cast=cast_ids, profile=state['source'], hero_pronouns=state['hero']['pronouns'],
                        setting=dg_rpg_visual_brief(dict(state, place=context['place'], slot=context['slot']))['setting'])
            if plan['kind'] == 'cg' and plan.get('who') is None and cast_ids:
                plan['who'] = cast_ids[0]
        return plan

    def dg_rpg_cg_status(plan):
        if plan is None:
            return {"status":"missing","path":None,"generate":False}
        state=dg_rpg.load(dg_rpg_root(),dg_rpg_state["id"])
        if dg_art.marker(state,plan) is None:
            return {"status":"missing","path":None,"generate":False}
        return dg_art.resolve(dg_rpg_root(),state["id"],plan["kind"],
                              plan["key"],dg_rpg_cg_builtin(plan),
                              getattr(persistent,"dg_prefer_generated",True))

    def dg_rpg_fit_cg(path):
        width, height = renpy.image_size(path)
        horizontal, vertical = 1920.0 / width, 1080.0 / height
        scale = horizontal if horizontal < vertical else vertical
        return im.Scale(path, int(width * scale), int(height * scale))

    def dg_rpg_scene_generate(who, intent):
        # Called via dg_runtime.app.start(), never on the screen rendering thread.
        state = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        context = dg_rpg.summary_for_ai(state, who, intent)
        context["narrative_direction"] = dg_narrative.context(state, "special", who, intent)
        context['visual_scene_facts'] = dg_rpg_visual_brief(state)
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
        instructions += u" " + dg_adult.scene_policy(state, who) + u" " + dg_stage.FORMATTING
        violation = dg_adult.validate_action(state, intent, who)
        if violation:
            raise ValueError(violation)
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
        # All image generation is explicit, no invisible image requests.
        state=dg_rpg.load(dg_rpg_root(),dg_rpg_state["id"])
        if kind == "background":
            if key not in dg_rpg.PLACE_NAMES:
                raise ValueError("Unknown location")
            if key != state["place"]:
                raise ValueError("Player moved before background request")
            prompt=dg_art.background_prompt(state,key)
            asset_key=key
        elif kind in ("cg","cg18"):
            # The screen sends immutable UTF-8 JSON rather than a Ren'Py store
            # dictionary that might change during the background thread.
            plan=dg_art.validate_scene_request(state,kind,key)
            prompt=dg_art.cg_prompt(state,plan)
            asset_key=plan["key"]
        else:
            raise ValueError("Sprite generation disabled: use stock assets")
        if getattr(persistent,"dg_rpg_art_provider","cloud") == "comfy":
            workflow_dir=os.path.join(renpy.config.gamedir,"mods","don_gen")
            dedicated=os.path.join(workflow_dir,"comfy_workflow_%s_api.json" % kind)
            fallback=os.path.join(workflow_dir,"comfy_workflow_background_api.json")
            generic=os.path.join(workflow_dir,"comfy_workflow_api.json")
            # A dedicated 18+ workflow is optional. The approved Anima BG
            # workflow can render a wide CG with different scene prompting.
            workflow=(dedicated if os.path.isfile(dedicated) else
                      fallback if os.path.isfile(fallback) else generic)
            dg_runtime.app.set_status(u"ComfyUI: создаём иллюстрацию…")
            data=dg_comfy.generate(workflow,prompt,kind,
                                   negative_prompt=dg_art.NEGATIVE)
        else:
            if kind=="cg18":
                raise ValueError("Adult CG is available only with explicit local ComfyUI workflow")
            app=dg_runtime.app
            app.set_status(u"Рисуем фон…" if kind=="background" else u"Рисуем CG…")
            data=app.client.generate_background(prompt,transparent=False)
        # Existing files are overwritten only after a validated PNG is ready.
        relative=dg_rpg.save_asset(dg_rpg_root(),state["id"],kind,asset_key,data)
        logging.getLogger("don_gen").info("Art saved type=%s key=%s path=%s",kind,asset_key,relative)
        return relative


default dg_rpg_hybrid_plan = None
default dg_rpg_state = None
default dg_rpg_pending_turn = None
default dg_rpg_focus = None
default dg_rpg_scene_context = None
default dg_rpg_stage_active = False
default dg_rpg_actor_moods = {}
default dg_rpg_visual_cast = None

screen dg_rpg_picker:
    modal True
    add Solid("#0b2029")
    text u"Твоя история в Совёнке" style "dg_note_heading" xpos 64 ypos 52
    text u"Свои решения, живые сцены и персонажи. Для новых сцен нужны ИИ и интернет." style "dg_note_hint" xpos 64 ypos 116 xmaximum 1680
    frame:
        background Solid("#102b33e8") xpos 64 ypos 192 xsize 728 ysize 716 padding (32, 28)
        vbox:
            xsize 664 spacing 24
            text u"Новая смена" style "dg_note_heading"
            text u"Создай героя, выбери предысторию и начни знакомство с лагерем." style "dg_note_body"
            textbutton u"Создать персонажа" style "dg_note_main" action Return(("new", None))
            text u"Игра сохраняет поступки автоматически. Смены хранятся отдельно от обычных сохранений «Бесконечного лета»." style "dg_note_hint"
    frame:
        background Solid("#102b33e8") xpos 816 ypos 192 xsize 1040 ysize 716 padding (32, 28)
        vbox:
            spacing 24
            text u"Продолжить историю" style "dg_note_heading"
            viewport:
                viewport_xfill True
                vscrollbar_xsize 16
                vscrollbar_base_bar Solid("#0b2029")
                vscrollbar_thumb Solid("#6d918e")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                xsize 976 ysize 580 mousewheel True draggable True scrollbars "vertical"
                vbox:
                    xsize 936 spacing 16
                    $ saved = dg_rpg.list_games(dg_rpg_root())
                    if not saved:
                        text u"Сохранённых смен пока нет." style "dg_note_body"
                    for game in saved:
                        frame:
                            background Solid("#17352edb") xsize 936 padding (24, 20)
                            vbox:
                                xsize 888 spacing 12
                                text dg_literal(game["name"]) style "dg_note_heading" size 34 xmaximum 880
                                text (u"День %d / %d · %s" % (game["day"], game["duration"], u"Завершена" if game["finished"] else u"В лагере")) style "dg_note_hint"
                                textbutton u"Открыть смену" style "dg_note_button" action Return(("load", game["id"]))
    textbutton u"Назад в меню" style "dg_note_tab" xpos 64 ypos 944 action Return(("back", None))
    key "K_ESCAPE" action Return(("back", None))

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
        padding (42, 24)
        align (0.5, 0.5)
        xsize 1440
        ysize (945 if field == "history" else 680)
        vbox:
            spacing 13
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
                    xsize 1310 ysize (dg_rpg_preview_height(editor_text, 175, 300, 150, 55, 24))
                    viewport:
                        viewport_xfill True
                        vscrollbar_xsize 16
                        vscrollbar_base_bar Solid("#0b2029")
                        vscrollbar_thumb Solid("#6d918e")
                        vscrollbar_unscrollable "hide"
                        side_spacing 12
                        mousewheel True
                        scrollbars "vertical"
                        ysize (dg_rpg_preview_height(editor_text, 135, 260, 110, 55, 24))
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
    $ dg_valid = bool(dg_create_name.strip() and dg_create_history.strip() and dg_create_age.isdigit() and dg_create_days.isdigit() and 1 <= int(dg_create_age) <= 999999999 and 1 <= int(dg_create_days) <= 120 and (not dg_create_adult or int(dg_create_age) >= 18))
    add Solid("#152c34")
    use dg_chrome(u"СОЗДАНИЕ ПЕРСОНАЖА", Return(("cancel",)))
    text u"Ваша история начинается здесь" style "dg_title" xpos 120 ypos 120 size 67
    frame:
        background DG_PAPER
        padding (32, 28)
        xpos 180 ypos 208 xsize 1560 ysize 826
        fixed:
            xsize 1496 ysize 770
            viewport:
                viewport_xfill True
                vscrollbar_xsize 16
                vscrollbar_base_bar Solid("#0b2029")
                vscrollbar_thumb Solid("#6d918e")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                xsize 1496 ysize 644 mousewheel True scrollbars "vertical"
                vbox:
                    xsize 1420 spacing 16
                    hbox:
                        spacing 65
                        vbox:
                            xsize 590
                            spacing 9
                            text u"ИМЯ" style "dg_ink_label"
                            textbutton (dg_literal(dg_create_name[:65]) + (u"…" if len(dg_create_name) > 65 else u"") + u"  · ИЗМЕНИТЬ") style "dg_ink_act" text_size 29 action Return(("edit", "name"))
                            null height 11
                            text u"ВОЗРАСТ ГЕРОЯ" style "dg_ink_label"
                            textbutton (dg_create_age + u"  · ИЗМЕНИТЬ") style "dg_ink_act" text_size 29 action Return(("edit", "age"))
                            null height 11
                            text u"ДНЕЙ В СМЕНЕ (1–120)" style "dg_ink_label"
                            textbutton (dg_create_days + u"  · ИЗМЕНИТЬ") style "dg_ink_act" text_size 29 action Return(("edit", "days"))
                            null height 5
                            text u"Нажмите «изменить», чтобы ввести значение." style "dg_ink_small" size 21
                        vbox:
                            xsize 700
                            spacing 10
                            text u"ПРЕДЫСТОРИЯ" style "dg_ink_label"
                            textbutton (dg_literal(dg_create_history[:105]) + (u"…" if len(dg_create_history) > 105 else u"") + u"  · ИЗМЕНИТЬ") style "dg_ink_act" text_size 29 action Return(("edit", "history")) xmaximum 565
                            null height 9
                            text u"МИР И ХАРАКТЕРЫ" style "dg_ink_label"
                            textbutton u"Мику · Булки, кефир и рок-н-ролл" style "dg_ink_act" text_size 27 action SetVariable("dg_create_source", "bkrr:mi") selected dg_create_source == "bkrr:mi"
                            textbutton u"Оригинальный Совёнок" style "dg_ink_act" text_size 29 action SetVariable("dg_create_source", "vanilla") selected dg_create_source == "vanilla"
                            if dg_detect_7dl_root():
                                textbutton u"7ДЛ · Мику" style "dg_ink_act" text_size 29 action SetVariable("dg_create_source", "7dl:mi_7dl") selected dg_create_source == "7dl:mi_7dl"
                                textbutton u"7ДЛ · DJ" style "dg_ink_act" text_size 29 action SetVariable("dg_create_source", "7dl:mi_dj") selected dg_create_source == "7dl:mi_dj"
                                textbutton u"7ДЛ · Классика" style "dg_ink_act" text_size 29 action SetVariable("dg_create_source", "7dl:mi_cl") selected dg_create_source == "7dl:mi_cl"
                    text u"РЕЖИМ ИСТОРИИ" style "dg_ink_label"
                    textbutton (u"18+ · ВЗРОСЛАЯ AU: ВКЛЮЧЕНА" if dg_create_adult else u"18+ · ВЗРОСЛАЯ AU: ВЫКЛЮЧЕНА") style "dg_ink_act" text_size 24 selected dg_create_adult sensitive (dg_create_age.isdigit() and int(dg_create_age) >= 18) action SetVariable("dg_create_adult", not dg_create_adult)
                    text u"Только для совершеннолетнего героя. В альтернативной версии допустимы зрелые романтические сцены между взрослыми. Ульяна и Юля исключены." style "dg_ink_small" size 21
                    text u"ОБРАЩЕНИЕ" style "dg_ink_label"
                    hbox:
                        spacing 36
                        for choice in (u"он/его", u"она/её", u"они/их"):
                            textbutton choice style "dg_ink_act" text_size 29 selected dg_create_pronouns == choice action SetVariable("dg_create_pronouns", choice)
                    null height 8
                    text u"Имя, возраст и длительность можно изменить до начала смены. Для живых сцен нужны ИИ и интернет." style "dg_ink_small" size 22
            hbox:
                ypos 684 spacing 24
                textbutton u"Начать смену" style "dg_rpg_main_button" xsize 430 sensitive dg_valid action Return(("start",))
                textbutton u"Отмена" style "dg_rpg_button" xsize 260 action Return(("cancel",))
    key "K_ESCAPE" action Return(("cancel",))

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

screen dg_rpg_artist_settings:
    modal True
    add dg_rpg_bg()
    add Solid("#071a28f0")
    frame:
        background Solid("#163844f9")
        align (0.5, 0.5) xsize 1460 ysize 775 padding (46, 37)
        vbox:
            spacing 23
            text u"ГЕНЕРАЦИЯ ФОНОВ И CG" style "dg_title" size 49 color "#ffe1aa"
            text u"Выбери, кто создаёт изображения. На обычные разговоры и механику RPG эта настройка не влияет." style "dg_text" size 29 xmaximum 1330
            textbutton u"ОБЛАЧНЫЙ ГЕНЕРАТОР" style "dg_primary" selected getattr(persistent, "dg_rpg_art_provider", "cloud") != "comfy" action SetField(persistent, "dg_rpg_art_provider", "cloud")
            textbutton u"COMFYUI · 127.0.0.1:8188" style "dg_primary" selected getattr(persistent, "dg_rpg_art_provider", "cloud") == "comfy" action SetField(persistent, "dg_rpg_art_provider", "comfy")
            text u"ComfyUI 8188: comfy_workflow_background_api.json для фонов, comfy_workflow_cg_api.json для CG, comfy_workflow_cg18_api.json для взрослых CG." style "dg_text" size 25 xmaximum 1320
            text u"Подстановки __DG_PROMPT__ и __DG_NEGATIVE__. Seed у Anima берётся как число прямо из KSampler и обновляется автоматически. Спрайты не генерируются." style "dg_text" size 24 xmaximum 1300
            text u"Генерация только вручную, если фона или CG нет; ранее созданные изображения читаются из кэша. Сервис 8189 не используется." style "dg_text" size 23 color "#c0dbd7" xmaximum 1300
            textbutton (u"Приоритет: сгенерированные" if getattr(persistent, "dg_prefer_generated", True) else u"Приоритет: оригинальные") style "dg_act" action SetField(persistent, "dg_prefer_generated", not getattr(persistent, "dg_prefer_generated", True))
            textbutton u"ЗАКРЫТЬ" style "dg_act" action Return(None)

screen dg_rpg_adult_settings:
    modal True
    add dg_rpg_bg()
    add Solid("#071a28f2")
    frame:
        background Solid("#173541f9")
        align (0.5, 0.5) xsize 1490 ysize 790 padding (50, 41)
        vbox:
            spacing 20
            text u"ДОПОЛНИТЕЛЬНЫЙ РЕЖИМ 18+" style "dg_title" size 52 color "#ffe1aa"
            text u"По умолчанию взрослые темы выключены. Этот режим — отдельная альтернативная вселенная с совершеннолетними версиями допущенных персонажей, не изменение их канонического возраста." style "dg_text" size 29 xmaximum 1350
            text u"Не распространяется на Ульяну и Юлю. Взаимное согласие обязательно. Любое изменение сохраняется только в текущей смене." style "dg_text" size 26 xmaximum 1310
            text (u"Сейчас: ВКЛЮЧЁН" if dg_adult.enabled(dg_rpg_state) else u"Сейчас: ВЫКЛЮЧЕН") style "dg_meta" size 26 color "#ffdfaa"
            if dg_adult.enabled(dg_rpg_state):
                textbutton u"ВЫКЛЮЧИТЬ РЕЖИМ 18+" style "dg_primary" action Return("disable")
            elif dg_rpg_state["hero"]["age"] >= 18:
                textbutton u"ПОДТВЕРЖДАЮ 18+ · ВКЛЮЧИТЬ ВЗРОСЛУЮ AU" style "dg_primary" action Return("enable")
            else:
                text u"Герой несовершеннолетний. Включение недоступно." style "dg_text" size 26 color "#ffe5b4"
            textbutton u"ОТМЕНА" style "dg_act" action Return(None)

screen dg_rpg_map:
    modal True
    default dg_map_hover = None
    $ dg_map_background = dg_rpg_map_asset("map_bg.jpg")
    $ dg_map_available = dg_rpg_map_asset("map_avaliable.jpg")
    $ dg_map_selection = dg_rpg_map_asset("map_selected.jpg")
    if renpy.loadable(dg_map_background):
        imagemap:
            ground dg_map_background
            idle dg_map_background
            hover (dg_map_available if renpy.loadable(dg_map_available) else dg_map_background)
            selected_idle (dg_map_selection if renpy.loadable(dg_map_selection) else dg_map_background)
            selected_hover (dg_map_selection if renpy.loadable(dg_map_selection) else dg_map_background)
            alpha False
            cache False
            for slug, rect in dg_map.regions():
                hotspot rect:
                    selected dg_rpg_state["place"] == slug
                    sensitive not dg_rpg_state["finished"]
                    hovered SetScreenVariable("dg_map_hover", slug)
                    unhovered SetScreenVariable("dg_map_hover", None)
                    action Return(("go", slug))
        for slug, rect in dg_map.regions():
            $ map_x, map_y = dg_map.center(rect)
            $ map_people = dg_rpg.at_place(dg_rpg_state, slug)
            for index, pair in enumerate(map_people[:4]):
                $ map_icon = dg_map_npc_icon(pair[0])
                if map_icon is not None:
                    add map_icon xpos (map_x - 21 + index * 30) ypos (rect[1] - 40)
            if dg_rpg_state["place"] == slug:
                $ map_hero = dg_map_npc_icon("hero")
                if map_hero is not None:
                    add map_hero xpos (map_x - 21) ypos (rect[1] + rect[3] - 4)
    else:
        add Solid("#142d31")
        frame:
            background Solid("#1d3c41") padding (40, 32)
            align (.5, .5) xsize 1250
            vbox:
                spacing 20
                text u"Нужна классическая карта лагеря" style "dg_rpg_heading"
                text u"Укажи установленную 7ДЛ: CE через install.ps1 -WorkshopDir или подключи набор gen_assets через -AssetsDir. Все места доступны через поиск." style "dg_rpg_body"
                textbutton u"Открыть список мест" style "dg_rpg_main_button" action Return(("places", None))
    # Compact controls leave the original map at its native 1920x1080 size.
    frame:
        background Solid("#12272bc9") padding (18, 12)
        xpos 24 ypos 22
        text dg_rpg.camp_time(dg_rpg_state) style "dg_rpg_body" size 25
    hbox:
        xpos 1410 ypos 22 spacing 12
        textbutton u"Найти место" style "dg_rpg_tab" xsize 238 action Return(("places", None))
        textbutton u"Закрыть" style "dg_rpg_tab" xsize 220 action Return(("close", None))
    if dg_map_hover in dg_rpg.PLACE_NAMES:
        frame:
            background Solid("#12272be8") padding (20, 14)
            xpos 980 ypos 938 xsize 880 ysize 118
            vbox:
                spacing 8
                text dg_rpg.PLACE_NAMES[dg_map_hover] style "dg_rpg_body" color "#ffe0a2"
                $ hover_people = dg_rpg.at_place(dg_rpg_state, dg_map_hover)
                text (u"Здесь: " + u", ".join(name for who, name in hover_people) if hover_people else u"Никого из знакомых поблизости") style "dg_rpg_hint" xmaximum 820
                if dg_world.event_at(dg_rpg_state, dg_map_hover) or dg_social.incident_at(dg_rpg_state, dg_map_hover):
                    text u"Здесь происходит событие" style "dg_rpg_hint" color "#ffe0a2"
    key "K_ESCAPE" action Return(("close", None))

screen dg_rpg_places:
    modal True
    default place_query = u""
    add Solid("#0b2029")
    text u"Куда пойдём?" style "dg_rpg_heading" xpos 80 ypos 54
    text u"Найди место по названию. Переход не расходует время." style "dg_rpg_hint" xpos 80 ypos 116
    frame:
        background Solid("#193840") xpos 80 ypos 174 xsize 1760 ysize 84 padding (20, 16)
        input:
            value ScreenVariableInputValue("place_query") style "dg_rpg_edit_input"
            length 80 xmaximum 1680 default_focus True
    viewport:
        viewport_xfill True
        vscrollbar_xsize 16
        vscrollbar_base_bar Solid("#0b2029")
        vscrollbar_thumb Solid("#6d918e")
        vscrollbar_unscrollable "hide"
        side_spacing 12
        xpos 80 ypos 286 xsize 1760 ysize 620 mousewheel True draggable True scrollbars "vertical"
        vbox:
            xsize 1710 spacing 12
            $ matching_places = [(slug, title) for slug, title, x, y in dg_rpg.PLACES if place_query.strip().lower() in title.lower()]
            if not matching_places:
                text u"Место не найдено. Попробуй другое название." style "dg_rpg_body"
            for place, name in matching_places:
                textbutton (dg_literal(name) + (u" · ты здесь" if place == dg_rpg_state["place"] else u"")) style "dg_rpg_button" action Return(("go", place))
    textbutton u"Назад на карту" style "dg_rpg_tab" xpos 80 ypos 944 action Return(("map", None))
    key "K_ESCAPE" action Return(("map", None))

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
                textbutton u"НАЗАД НА КАРТУ" style "dg_act" action Return(("map", None))
            viewport:
                viewport_xfill True
                vscrollbar_xsize 16
                vscrollbar_base_bar Solid("#0b2029")
                vscrollbar_thumb Solid("#6d918e")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                mousewheel True
                scrollbars "vertical"
                ysize 615
                grid 4 8:
                    spacing 9
                    for cabin_number in range(1, 32):
                        textbutton (u"Домик %02d" % cabin_number) style "dg_rpg_button" xsize 360 text_size 27 action Return(("go", "cabin_%02d" % cabin_number))
                    null

    key "K_ESCAPE" action Return(("map", None))

# RPG controls use bounded buttons and independent scroll areas.
style dg_rpg_body is dg_text:
    size 28
    outlines []
    color "#edf2ef"
style dg_rpg_hint is dg_rpg_body:
    size 23
    color "#b5c9c6"
style dg_rpg_heading is dg_rpg_body:
    font "fonts/corbel.ttf"
    size 42
    color "#ffe0a2"
style dg_rpg_button is dg_act:
    background Solid("#24434a")
    hover_background Solid("#355a60")
    selected_background Solid("#526244")
    insensitive_background Solid("#1c3037")
    padding (20, 14)
    xfill True
style dg_rpg_button_text is dg_rpg_body:
    size 28
    hover_color "#ffffff"
    insensitive_color "#80938f"
style dg_rpg_main_button is dg_rpg_button:
    background Solid("#d8b678")
    hover_background Solid("#f0d49c")
    insensitive_background Solid("#243a3e")
style dg_rpg_main_button_text is dg_rpg_button_text:
    color "#172a30"
    hover_color "#172a30"
    insensitive_color "#85958e"
style dg_rpg_tab is dg_rpg_button:
    xfill False
    xsize 252
style dg_rpg_tab_text is dg_rpg_button_text:
    size 26

default dg_rpg_action_draft = u""
default dg_rpg_action_context = None

# Camp navigation stays outside the dialogue area.
init 1002:
    style dg_camp_nav is button:
        background dg_camp_button_surface("#071c17c9", "#a7996470")
        hover_background dg_camp_button_surface("#bfa769e8", "#efdc9ecc")
        insensitive_background Solid("#071c1770")
        padding (22, 14)
        xminimum 142
        ysize 58
    style dg_camp_nav_text is dg_rpg_button_text:
        font "fonts/calibri.ttf"
        size 26
        color "#e7d9ac"
        hover_color "#172b22"
        insensitive_color "#869087"
        outlines []
    style dg_camp_action is dg_camp_nav:
        background dg_camp_button_surface("#a18d4ccc", "#e2cd8da0")
        hover_background dg_camp_button_surface("#dbc080f0", "#fff1bd")
        xminimum 238
    style dg_camp_action_text is dg_camp_nav_text:
        color "#fff0bc"
        hover_color "#172b22"
    style dg_camp_arrow is dg_camp_nav:
        xminimum 44
        xsize 44
        ysize 44
        padding (10, 2)
        background None
        hover_background Solid("#bfa76970")
    style dg_camp_arrow_text is dg_camp_nav_text:
        size 32

    style dg_note_body is dg_rpg_body:
        color "#e7d9ac"
        outlines []
    style dg_note_hint is dg_note_body:
        color "#b5c9c6"
        size 23
    style dg_note_heading is dg_rpg_heading:
        color "#ffe0a2"
        outlines []
    style dg_note_button is dg_rpg_button:
        background dg_camp_button_surface("#17352edb", "#8c865a80")
        hover_background dg_camp_button_surface("#3b5846ee", "#b6ac77")
        selected_background dg_camp_button_surface("#506344ee", "#d8c786")
        insensitive_background Solid("#1c3037")
    style dg_note_button_text is dg_note_body:
        size 27
        hover_color "#172b22"
        insensitive_color "#869087"
    style dg_note_main is dg_note_button:
        background dg_camp_button_surface("#a18d4ccc", "#e2cd8da0")
        hover_background dg_camp_button_surface("#dbc080f0", "#fff1bd")
    style dg_note_main_text is dg_note_button_text:
        color "#fff0bc"
        hover_color "#172b22"
    style dg_note_tab is dg_note_button:
        xfill False
        xsize 252
    style dg_note_tab_text is dg_note_button_text:
        size 26
    style dg_note_input is dg_rpg_edit_input:
        size 30
        color "#e7d9ac"
        outlines []

    style dg_camp_name is dg_rpg_body:
        font "fonts/calibri.ttf"
        size 28
        bold True
        outlines []
    style dg_camp_narration is dg_rpg_body:
        font "fonts/calibri.ttf"
        size 28
        color "#f3d887"
        outlines []

screen dg_rpg_hub:
    modal True
    default selected_person = 0
    default show_interface = True
    $ inhabitants = dg_rpg.at_place(dg_rpg_state)
    if dg_rpg_state.get("source") == "bkrr:mi":
        $ inhabitants = sorted(inhabitants, key=lambda item: item[0] != "mi")
    $ shift_open = not dg_rpg_state["finished"]
    $ selected_who = inhabitants[selected_person % len(inhabitants)][0] if inhabitants else None
    $ visible_cast = dg_stage.cast([], [item[0] for item in inhabitants], selected_who)
    add dg_rpg_bg()
    for actor, actor_x in dg_stage.positions(visible_cast, selected_who):
        $ actor_image = dg_rpg_sprite(actor, "normal", "normal")
        if actor_image is not None:
            add actor_image xpos actor_x xanchor .5 ypos 1.0 yanchor 1.0
    if show_interface:
        frame:
            background Solid("#071914b0")
            xpos 52 ypos 36 xsize 650 padding (20, 12)
            vbox:
                spacing 3
                text dg_rpg.PLACE_NAMES[dg_rpg_state["place"]] style "dg_rpg_heading" size 30 color "#e7d9ac"
                text (dg_rpg.camp_time(dg_rpg_state) + u"   ·   Силы: %d" % dg_rpg_state["energy"]) style "dg_note_hint" size 23
        hbox:
            xpos 1052 ypos 36 spacing 8
            textbutton u"Карта" style "dg_camp_nav" action Return(("map", None))
            textbutton u"Дневник" style "dg_camp_nav" action Return(("journal", None))
            textbutton u"События" style "dg_camp_nav" action Return(("controls", None))
            textbutton u"Меню" style "dg_camp_nav" action Return(("exit", None))
        if renpy.loadable("images/gui/dialogue_box/day/dialogue_box.png"):
            add "images/gui/dialogue_box/day/dialogue_box.png" xpos 174 ypos 916
        else:
            add Solid("#061a19d9") xpos 174 ypos 916 xsize 1572 ysize 164
        if inhabitants:
            text dg_rpg.NPC_NAMES[selected_who] style "dg_camp_name" color dg_stage.COLORS[selected_who] xpos 204 ypos 924
            if len(inhabitants) > 1:
                hbox:
                    xpos 174 ypos 824 spacing 8
                    textbutton u"‹" style "dg_camp_arrow" action SetScreenVariable("selected_person", selected_person - 1)
                    textbutton u"›" style "dg_camp_arrow" action SetScreenVariable("selected_person", selected_person + 1)
                    text (u"Собеседник %d / %d" % (selected_person % len(inhabitants) + 1, len(inhabitants))) style "dg_rpg_hint" yalign .5
            text u"Что ты хочешь сказать?" style "dg_camp_narration" xpos 204 ypos 962 xmaximum 1490
        else:
            text u"Рядом никого" style "dg_camp_name" xpos 204 ypos 924 color "#ffaa00"
            text u"Можно осмотреться или открыть карту." style "dg_camp_narration" xpos 204 ypos 962 xmaximum 1490
        hbox:
            xpos 950 ypos 824 spacing 12
            textbutton u"Своё действие" style "dg_camp_action" xminimum 200 action Return(("hybrid", None)) sensitive (shift_open and dg_rpg_state["energy"] >= 4)
            if inhabitants:
                textbutton u"Своя реплика" style "dg_camp_nav" action Return(("hybrid_npc", selected_who)) sensitive (shift_open and dg_rpg_state["energy"] >= 6)
                textbutton u"Темы разговора" style "dg_camp_nav" action Return(("talk", selected_who)) sensitive (shift_open and dg_rpg_state["energy"] >= 8)
        text u"M — карта   ·   J — дневник   ·   H — скрыть интерфейс" style "dg_rpg_hint" size 18 xpos 1052 ypos 108 color "#f1e7c5"
    else:
        textbutton u"Показать интерфейс · H" style "dg_camp_nav" xpos 52 ypos 990 action SetScreenVariable("show_interface", True)
    key "h" action ToggleScreenVariable("show_interface")
    key "m" action Return(("map", None))
    key "j" action Return(("journal", None))
    key "K_ESCAPE" action Return(("controls", None))

screen dg_rpg_controls:
    modal True
    default dg_hub_tab = "story"
    default dg_expanded_npc = None
    add dg_rpg_bg()
    add Solid("#071914b0")
    $ inhabitants = dg_rpg.at_place(dg_rpg_state)
    $ shift_open = not dg_rpg_state["finished"]
    $ day_event = dg_world.current(dg_rpg_state)
    frame:
        background Solid("#102b33e8")
        xpos 48 ypos 32 xsize 1824 ysize 126 padding (28, 18)
        vbox:
            spacing 6
            text dg_rpg.PLACE_NAMES[dg_rpg_state["place"]] style "dg_note_heading" xmaximum 1320
            text (dg_rpg.camp_time(dg_rpg_state) + u"  ·  " + dg_world.weather(dg_rpg_state)[1] + u"  ·  Энергия %d/100" % dg_rpg_state["energy"]) style "dg_note_hint" xmaximum 1320
    textbutton u"Вернуться в лагерь" style "dg_note_tab" xpos 1578 ypos 65 action Return(("camp", None))
    hbox:
        xpos 48 ypos 178 spacing 12
        textbutton u"События" style "dg_note_tab" selected dg_hub_tab == "story" action SetScreenVariable("dg_hub_tab","story")
        textbutton u"Занятия" style "dg_note_tab" selected dg_hub_tab == "actions" action SetScreenVariable("dg_hub_tab","actions")
        textbutton u"Настройки" style "dg_note_tab" selected dg_hub_tab == "settings" action SetScreenVariable("dg_hub_tab","settings")
    frame:
        background Solid("#102b33ed")
        xpos 48 ypos 258 xsize 1100 ysize 656 padding (28, 24)
        viewport:
            viewport_xfill True
            vscrollbar_xsize 16
            vscrollbar_base_bar Solid("#0b2029")
            vscrollbar_thumb Solid("#6d918e")
            vscrollbar_unscrollable "hide"
            side_spacing 12
            xsize 1044 ysize 608
            mousewheel True draggable True scrollbars "vertical"
            vbox:
                xsize 1008 spacing 18
                if dg_hub_tab == "story":
                    if not shift_open:
                        text u"Смена завершена" style "dg_note_heading"
                        text u"Перечитай дневник или узнай, к чему привели твои решения." style "dg_note_body"
                        textbutton u"Итоги смены" style "dg_note_main" action Return(("finale", None))
                    else:
                        text u"Что ты сделаешь?" style "dg_note_heading"
                        text u"Опиши поступок своими словами или обратись к тому, кто рядом." style "dg_note_body"
                        textbutton u"Написать своё действие" style "dg_note_main" action Return(("hybrid", None)) sensitive dg_rpg_state["energy"] >= 4
                        if dg_rpg_state["energy"] < 4:
                            text u"Ты устал. Отдых доступен во вкладке «Действия»." style "dg_note_hint"
                        if day_event:
                            text u"Событие дня" style "dg_note_hint"
                            text dg_literal(day_event["title"]) style "dg_note_heading" size 34
                            text (u"Где: " + dg_rpg.PLACE_NAMES[day_event["place"]]) style "dg_note_body"
                            textbutton (u"Участвовать · 8 энергии" if dg_rpg_state["place"] == day_event["place"] else u"Перейти к событию") style "dg_note_button" sensitive (dg_rpg_state["place"] != day_event["place"] or dg_rpg_state["energy"] >= 8) action Return(("world", None) if dg_rpg_state["place"] == day_event["place"] else ("world_travel", day_event["place"]))
                        else:
                            text u"Событие дня завершено. Можно продолжать свою историю." style "dg_note_hint"
                        $ active_incident = dg_social.incident_at(dg_rpg_state, dg_rpg_state["place"])
                        if active_incident:
                            text dg_literal(u"Рядом: " + active_incident["title"]) style "dg_note_body"
                            textbutton u"Присоединиться · 9 энергии" style "dg_note_button" action Return(("incident", None)) sensitive dg_rpg_state["energy"] >= 9
                    text u"Последняя запись" style "dg_note_hint"
                    text dg_literal(dg_rpg_state["event"]) style "dg_note_body"
                elif dg_hub_tab == "actions":
                    text u"Твой ход" style "dg_note_heading"
                    if shift_open:
                        textbutton u"Написать своё действие" style "dg_note_main" action Return(("hybrid", None)) sensitive dg_rpg_state["energy"] >= 4
                        textbutton u"Поручения и исследования" style "dg_note_button" action Return(("contracts", None))
                        textbutton u"Неожиданная встреча · 4 энергии" style "dg_note_button" action Return(("surprise", None)) sensitive dg_rpg_state["energy"] >= 4
                        text u"Занятия · каждое переводит время на следующий период" style "dg_note_hint"
                        textbutton u"Осмотреться · 12 энергии" style "dg_note_button" action Return(("activity", "explore")) sensitive dg_rpg_state["energy"] >= 12
                        textbutton u"Помочь лагерю · 17 энергии" style "dg_note_button" action Return(("activity", "help")) sensitive dg_rpg_state["energy"] >= 17
                        textbutton u"Заняться делом · 20 энергии" style "dg_note_button" action Return(("activity", "practice")) sensitive dg_rpg_state["energy"] >= 20
                        textbutton u"Отдохнуть · +35 энергии" style "dg_note_button" action Return(("activity", "rest"))
                    else:
                        text u"Смена окончена. История сохранена в дневнике." style "dg_note_body"
                else:
                    text u"Настройки истории" style "dg_note_heading"
                    if dg_rpg_state.get("source") == "bkrr:mi":
                        text u"Ориентир: БКРР · Мику, музыка и лагерное лето" style "dg_note_body"
                    else:
                        textbutton u"Выбрать настроение БКРР · Мику" style "dg_note_button" action Return(("profile", "bkrr:mi"))
                    text (u"ИИ подключён" if dg_runtime.app.client.authenticated() else u"Для новых сцен подключи ИИ") style "dg_note_body"
                    textbutton u"Подключение ИИ" style "dg_note_button" action Return(("connect", None))
                    textbutton (u"Взрослая AU: включена" if dg_adult.enabled(dg_rpg_state) else u"Взрослая AU: выключена") style "dg_note_button" action Return(("adult", None))
                    textbutton u"Настройки изображений" style "dg_note_button" action Return(("artist", None))
                    $ bg_state = dg_rpg_bg_status()
                    if shift_open and bg_state["status"] == "missing":
                        textbutton u"Создать фон этого места" style "dg_note_button" action Return(("background", dg_rpg_state["place"]))
                    textbutton u"Галерея CG" style "dg_note_button" action Return(("cg_gallery", None))
                    textbutton u"Диагностика" style "dg_note_button" action Return(("diag", None))
                    text (u"Навык %d · Доброта %d · Любознательность %d" % (dg_rpg_state["stats"]["skill"], dg_rpg_state["stats"]["kindness"], dg_rpg_state["stats"]["curiosity"])) style "dg_note_hint"
    frame:
        background Solid("#102b33ed")
        xpos 1172 ypos 178 xsize 700 ysize 736 padding (28, 24)
        vbox:
            spacing 18
            text u"Кто рядом" style "dg_note_heading"
            viewport:
                viewport_xfill True
                vscrollbar_xsize 16
                vscrollbar_base_bar Solid("#0b2029")
                vscrollbar_thumb Solid("#6d918e")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                xsize 644 ysize 606 mousewheel True draggable True scrollbars "vertical"
                vbox:
                    xsize 608 spacing 22
                    if not inhabitants:
                        text u"Здесь пока никого." style "dg_note_body"
                        text u"Посмотри карту: персонажи перемещаются в течение дня." style "dg_note_hint"
                    for who, person in inhabitants:
                        frame:
                            background Solid("#17352edb")
                            xsize 608 padding (18, 16)
                            vbox:
                                spacing 12 xsize 572
                                text person style "dg_note_heading" size 34
                                text (u"%s · %d/100" % (dg_rpg.route_label(dg_rpg_state["affinity"][who]), dg_rpg_state["affinity"][who])) style "dg_note_hint"
                                textbutton u"Сказать своими словами" style "dg_note_main" action Return(("hybrid_npc", who)) sensitive (shift_open and dg_rpg_state["energy"] >= 6)
                                textbutton u"Выбрать тему разговора" style "dg_note_button" action Return(("talk", who)) sensitive (shift_open and dg_rpg_state["energy"] >= 8)
                                textbutton u"Другие встречи" style "dg_note_button" selected dg_expanded_npc == who action SetScreenVariable("dg_expanded_npc", None if dg_expanded_npc == who else who)
                                if dg_expanded_npc == who:
                                    textbutton u"Особая AI-сцена" style "dg_note_button" action Return(("ai", who)) sensitive shift_open
                                    textbutton u"Неожиданная встреча · 4 энергии" style "dg_note_button" action Return(("surprise", who)) sensitive (shift_open and dg_rpg_state["energy"] >= 4)
                                if dg_social.personal_scene(dg_rpg_state, who) and shift_open:
                                    textbutton u"Личная история · 12 энергии" style "dg_note_button" action Return(("personal", who)) sensitive dg_rpg_state["energy"] >= 12
                                if dg_rpg.available_route_events(dg_rpg_state, who) and shift_open:
                                    textbutton u"Важный разговор · 12 энергии" style "dg_note_button" action Return(("route", who)) sensitive dg_rpg_state["energy"] >= 12
    hbox:
        xpos 48 ypos 942 spacing 18
        textbutton u"Карта лагеря" style "dg_note_tab" action Return(("map", None))
        textbutton u"Дневник и связи" style "dg_note_tab" action Return(("journal", None))
        textbutton u"Своё действие" style "dg_note_tab" action Return(("hybrid", None)) sensitive (shift_open and dg_rpg_state["energy"] >= 4)
    text u"Переходы бесплатны. Поступки и разговоры двигают время." style "dg_note_hint" color "#d3d3b5" xpos 882 ypos 960 xmaximum 970
    key "K_ESCAPE" action Return(("camp", None))

screen dg_rpg_hybrid_input(mode, who=None):
    modal True
    default action_text = dg_rpg_action_draft
    add dg_rpg_bg()
    add Solid("#07191490")
    frame:
        background Solid("#102b33e8")
        align (0.5, 0.5) xsize 1480 ysize 900 padding (40, 32)
        fixed:
            xsize 1400 ysize 836
            vbox:
                spacing 18 xsize 1380
                text (u"Что ты скажешь?" if mode == "npc" else u"Как ты поступишь?") style "dg_note_heading"
                if who is not None:
                    text (u"Собеседник: " + dg_rpg.NPC_NAMES[who]) style "dg_note_body"
                text u"Опиши один поступок или реплику. Затем можно проверить ход и продолжить сцену с ИИ." style "dg_note_body"
                frame:
                    background Solid("#071c17d9") padding (24, 20) xsize 1380 ysize 430
                    viewport:
                        viewport_xfill True
                        vscrollbar_xsize 16
                        vscrollbar_base_bar Solid("#0b2029")
                        vscrollbar_thumb Solid("#6d918e")
                        vscrollbar_unscrollable "hide"
                        side_spacing 12
                        xsize 1332 ysize 390 mousewheel True scrollbars "vertical"
                        input:
                            value ScreenVariableInputValue("action_text")
                            style "dg_note_input"
                            length 4000
                            xmaximum 1280
                            default_focus True
                text (u"%d / 4000 символов" % len(action_text)) style "dg_note_hint"
                text u"Один поступок или одна реплика. Текст сохранится, если вернуться назад." style "dg_note_hint"
            hbox:
                ypos 756 spacing 18
                textbutton u"Продолжить" style "dg_note_main" xsize 430 sensitive bool(action_text.strip()) action [SetVariable("dg_rpg_action_draft", action_text), Return(("submit", action_text.strip()))]
                textbutton u"Назад" style "dg_note_button" xsize 260 action [SetVariable("dg_rpg_action_draft", action_text), Return(None)]
    key "K_ESCAPE" action [SetVariable("dg_rpg_action_draft", action_text), Return(None)]

screen dg_rpg_hybrid_review(plan):
    modal True
    add dg_rpg_bg()
    add Solid("#07191490")
    frame:
        background Solid("#102b33e8")
        align (0.5, 0.5) xsize 1480 ysize 900 padding (40, 32)
        fixed:
            xsize 1400 ysize 836
            viewport:
                viewport_xfill True
                vscrollbar_xsize 16
                vscrollbar_base_bar Solid("#0b2029")
                vscrollbar_thumb Solid("#6d918e")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                xsize 1400 ysize 718 mousewheel True draggable True scrollbars "vertical"
                vbox:
                    xsize 1340 spacing 20
                    text (u"Твой следующий ход" if plan["status"] == "ready" else u"Уточни действие") style "dg_note_heading"
                    text dg_literal(plan.get("action", u"")[:700] + (u"…" if len(plan.get("action", u"")) > 700 else u"")) style "dg_note_body"
                    if len(plan.get("action", u"")) > 700:
                        text u"Полный текст сохранён. Его можно открыть кнопкой «Изменить текст»." style "dg_note_hint"
                    if plan["status"] != "ready":
                        text dg_literal(plan["message"]) style "dg_note_body"
                    else:
                        text dg_literal(plan["result"]["text"] if len(plan["result"]["text"]) <= 1000 else plan["result"]["text"][:450] + u"…" + plan["result"]["text"][-450:]) style "dg_note_body"
                        text u"Что изменится" style "dg_note_heading" size 32
                        for item in plan["effects"]:
                            text dg_literal(item) style "dg_note_body"
                    text u"Ход ещё не сделан. После продолжения ИИ напишет сцену." style "dg_note_hint"
            hbox:
                ypos 756 spacing 18
                if plan["status"] == "ready":
                    textbutton u"Продолжить с ИИ" style "dg_note_main" xsize 430 action Return("ai")
                textbutton u"Изменить текст" style "dg_note_button" xsize 310 action Return("retry")
                textbutton u"Отмена" style "dg_note_button" xsize 240 action Return("cancel")
    key "K_ESCAPE" action Return("cancel")

screen dg_rpg_art_error(message):
    modal True
    add dg_rpg_bg()
    add Solid("#061923de")
    frame:
        background Solid("#142f3df6")
        align (0.5,0.5) xsize 1410 ysize 500 padding (48,34)
        vbox:
            spacing 24
            text u"CG · НЕ УДАЛОСЬ СОЗДАТЬ ИЛЛЮСТРАЦИЮ" style "dg_title" size 43 color "#ffe2a6"
            viewport:
                viewport_xfill True
                vscrollbar_xsize 16
                vscrollbar_base_bar Solid("#0b2029")
                vscrollbar_thumb Solid("#6d918e")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                mousewheel True scrollbars "vertical" ysize 245
                text dg_literal(message) style "dg_text" size 27 xmaximum 1300
            textbutton u"ВЕРНУТЬСЯ К СЦЕНЕ" style "dg_primary" action Return(None)

screen dg_rpg_cg_gallery:
    modal True
    add dg_rpg_bg()
    add Solid("#071924f0")
    frame:
        background Solid("#102c37fa")
        align (0.5,0.5) xsize 1590 ysize 915 padding (43,31)
        vbox:
            spacing 20
            text u"ГАЛЕРЕЯ CG · ТЕКУЩАЯ СМЕНА" style "dg_title" size 49 color "#ffe1a4"
            text u"Иллюстрации сохранены на диске. Открытие галереи не запускает генерацию." style "dg_text" size 26
            viewport:
                viewport_xfill True
                vscrollbar_xsize 16
                vscrollbar_base_bar Solid("#0b2029")
                vscrollbar_thumb Solid("#6d918e")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                mousewheel True scrollbars "vertical" ysize 665
                vbox:
                    spacing 15
                    $ gallery_items = dg_rpg_state.get("cg_history", [])
                    if not gallery_items:
                        text u"Пока CG нет. Их можно создавать после крупных сюжетных сцен." style "dg_text" size 29
                    for cg_item in gallery_items[::-1]:
                        if cg_item["kind"] != "cg18" or dg_adult.enabled(dg_rpg_state):
                            frame:
                                background Solid("#21414be9")
                                padding (22,15)
                                xsize 1420
                                hbox:
                                    spacing 22
                                    text (u"18+" if cg_item["kind"] == "cg18" else u"CG") style "dg_meta" size 26 color "#ffe0ad"
                                    textbutton dg_literal(cg_item["title"]) style "dg_navlink" text_size 27 action Return(("view",cg_item))
            textbutton u"ВЕРНУТЬСЯ В ЛАГЕРЬ" style "dg_primary" action Return(None)

screen dg_rpg_cg_art(plan):
    modal True
    $ resource = dg_rpg_cg_status(plan)
    if resource["status"] in ("generated","builtin") and resource["path"]:
        add Solid("#000000")
        add dg_rpg_fit_cg(resource["path"]) align (.5,.5)
    else:
        add dg_rpg_bg()
        add Solid("#071725a0")
        if plan.get("who") is not None:
            $ dg_cg_preview_sprite = dg_rpg_sprite(plan["who"], "normal", "normal")
            if dg_cg_preview_sprite is not None:
                add dg_cg_preview_sprite at dg_rpg_portrait_transform xpos 1130 ypos 100
        frame:
            background Solid("#0d2734e8")
            xpos 115 ypos 470 xsize 1640 ysize 490 padding (43,30)
            vbox:
                spacing 22
                text u"ИЛЛЮСТРАЦИЯ · CG" style "dg_title" size 43 color "#ffe4a6"
                text dg_literal(plan["title"]) style "dg_text" size 34 xmaximum 1520
                text u"Готовой картинки для этого эпизода пока нет. Сцену можно оставить текстовой или сгенерировать изображение отдельно." style "dg_text" size 27 xmaximum 1480
                text (u"Взрослый CG · локальный ComfyUI" if plan["kind"]=="cg18" else u"Обычный CG · широкий кадр 16:9") style "dg_small" size 24 color "#e3c691"
                textbutton u"СОЗДАТЬ CG" style "dg_primary" action Return("generate")
                text (u"ID эпизода: " + plan["key"]) style "dg_small" size 19 color "#afc6cc"
    frame:
        background Solid("#082432db")
        xpos 45 ypos 24 xsize 1390 ysize 92 padding (24,14)
        hbox:
            spacing 19
            text u"DON-GEN · CG" style "dg_meta" size 28 color "#ffe7aa"
            text dg_literal(plan["title"]) style "dg_text" size 24 xmaximum 1000
    if resource["status"] in ("generated","builtin"):
        textbutton u"ПЕРЕРИСОВАТЬ" style "dg_map_pin" xpos 1375 ypos 30 action Return("generate")
    textbutton u"НАЗАД К ИСТОРИИ" style "dg_map_pin" xpos 1500 ypos 990 action Return(None)

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
                    viewport_xfill True
                    vscrollbar_xsize 16
                    vscrollbar_base_bar Solid("#0b2029")
                    vscrollbar_thumb Solid("#6d918e")
                    vscrollbar_unscrollable "hide"
                    side_spacing 12
                    mousewheel True scrollbars "vertical" ysize 490
                    text dg_literal(entry["scene"] if entry["scene"] else entry["result"]) style "dg_text" size 29 xmaximum 1330
            text u"ИГРОВЫЕ ПОСЛЕДСТВИЯ · зафиксированы движком, а не моделью" style "dg_meta" size 22
            text dg_literal(u" · ".join(entry["effects"]) if entry["effects"] else u"Показатели не менялись.") style "dg_text" size 24 xmaximum 1390
            textbutton u"Иллюстрация сцены · CG (необязательно)" style "dg_act" action Return("cg")
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
                ysize (dg_rpg_preview_height(action_text, 140, 300, 140, 80, 24))
                viewport:
                    viewport_xfill True
                    vscrollbar_xsize 16
                    vscrollbar_base_bar Solid("#0b2029")
                    vscrollbar_thumb Solid("#6d918e")
                    vscrollbar_unscrollable "hide"
                    side_spacing 12
                    mousewheel True scrollbars "vertical"
                    ysize (dg_rpg_preview_height(action_text, 100, 260, 100, 80, 24))
                    text dg_literal(action_text if action_text else u"Здесь будет показана длинная реплика с переносом строк.") style "dg_text" size 28 xmaximum 1260
            text u"Например: «Помочь Мику с репетицией». Неизвестное действие не расходует ход. Можно выбрать гибридную AI-сцену отдельно." style "dg_text" size 23 color "#b9d4d6" xmaximum 1290
            hbox:
                spacing 45
                textbutton u"СОВЕРШИТЬ ПОСТУПОК" style "dg_primary" sensitive bool(action_text.strip()) action Return(action_text.strip())
                textbutton u"ОТМЕНА" style "dg_act" action Return(None)
    key "K_ESCAPE" action Return(None)

screen dg_rpg_action_result(result, cg_worthy=False):
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
                    viewport_xfill True
                    vscrollbar_xsize 16
                    vscrollbar_base_bar Solid("#0b2029")
                    vscrollbar_thumb Solid("#6d918e")
                    vscrollbar_unscrollable "hide"
                    side_spacing 12
                    mousewheel True scrollbars "vertical" ysize 490
                    text dg_literal(result["text"]) style "dg_text" size 30 xmaximum 1195
            if cg_worthy:
                textbutton u"Иллюстрировать событие (CG)" style "dg_act" action Return("cg")
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
                        viewport_xfill True
                        vscrollbar_xsize 16
                        vscrollbar_base_bar Solid("#0b2029")
                        vscrollbar_thumb Solid("#6d918e")
                        vscrollbar_unscrollable "hide"
                        side_spacing 12
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
                    viewport_xfill True
                    vscrollbar_xsize 16
                    vscrollbar_base_bar Solid("#0b2029")
                    vscrollbar_thumb Solid("#6d918e")
                    vscrollbar_unscrollable "hide"
                    side_spacing 12
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
            viewport_xfill True
            vscrollbar_xsize 16
            vscrollbar_base_bar Solid("#0b2029")
            vscrollbar_thumb Solid("#6d918e")
            vscrollbar_unscrollable "hide"
            side_spacing 12
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

    key "K_ESCAPE" action Return(None)

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
                    viewport_xfill True
                    vscrollbar_xsize 16
                    vscrollbar_base_bar Solid("#0b2029")
                    vscrollbar_thumb Solid("#6d918e")
                    vscrollbar_unscrollable "hide"
                    side_spacing 12
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
                viewport_xfill True
                vscrollbar_xsize 16
                vscrollbar_base_bar Solid("#0b2029")
                vscrollbar_thumb Solid("#6d918e")
                vscrollbar_unscrollable "hide"
                side_spacing 12
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
                        viewport_xfill True
                        vscrollbar_xsize 16
                        vscrollbar_base_bar Solid("#0b2029")
                        vscrollbar_thumb Solid("#6d918e")
                        vscrollbar_unscrollable "hide"
                        side_spacing 12
                        ysize 232
                        mousewheel True
                        scrollbars "vertical"
                        text dg_literal(active["story"]) style "dg_text" size 29 xmaximum 1168
                text u"КАК ТЫ ПОСТУПИШЬ? РЕШЕНИЕ ИЗМЕНИТ СЛЕДУЮЩИЕ ДНИ" style "dg_meta" size 22 color "#ffda91"
                if dg_rpg_state["energy"] >= 8:
                    viewport:
                        viewport_xfill True
                        vscrollbar_xsize 16
                        vscrollbar_base_bar Solid("#0b2029")
                        vscrollbar_thumb Solid("#6d918e")
                        vscrollbar_unscrollable "hide"
                        side_spacing 12
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
                    viewport_xfill True
                    vscrollbar_xsize 16
                    vscrollbar_base_bar Solid("#0b2029")
                    vscrollbar_thumb Solid("#6d918e")
                    vscrollbar_unscrollable "hide"
                    side_spacing 12
                    ysize 390
                    mousewheel True scrollbars "vertical"
                    text dg_literal(result["text"]) style "dg_text" size 31 xmaximum 1290
            text (u"Лагерь: сплочённость %d · знания %d · свобода %d · ресурсы %d" %
                  (dg_rpg_state["world"]["morale"], dg_rpg_state["world"]["knowledge"],
                   dg_rpg_state["world"]["freedom"], dg_rpg_state["world"]["resources"])) style "dg_text" size 26 color "#ffe19b"
            textbutton u"Создать / посмотреть CG сцены" style "dg_act" action Return("cg")
            textbutton u"Продолжить историю" style "dg_primary" action Return(None)

screen dg_rpg_journal:
    modal True
    default view = "timeline"
    add Solid("#142832")
    textbutton u"Вернуться в лагерь" style "dg_note_tab" xpos 1580 ypos 105 action Return(None)
    text u"Дневник смены" style "dg_note_heading" xpos 100 ypos 115 size 52
    hbox:
        xpos 100 ypos 215 spacing 16
        textbutton u"События" style "dg_note_tab" selected view == "timeline" action SetScreenVariable("view", "timeline")
        textbutton u"Разговоры" style "dg_note_tab" selected view == "talks" action SetScreenVariable("view", "talks")
        textbutton u"AI-сцены" style "dg_note_tab" selected view == "ai" action SetScreenVariable("view", "ai")
        textbutton u"Хроника мира" style "dg_note_tab" selected view == "world" action SetScreenVariable("view", "world")
        textbutton u"Люди и слухи" style "dg_note_tab" selected view == "social" action SetScreenVariable("view", "social")
        textbutton u"Незавершённое" style "dg_note_tab" selected view == "threads" action SetScreenVariable("view", "threads")
    hbox:
        xpos 95 ypos 295 spacing 45
        frame:
            background Solid("#102b33e8")
            padding (23, 21)
            xsize 970 ysize 660
            viewport:
                viewport_xfill True
                vscrollbar_xsize 16
                vscrollbar_base_bar Solid("#0b2029")
                vscrollbar_thumb Solid("#6d918e")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                mousewheel True
                scrollbars "vertical"
                ysize 610
                vbox:
                    spacing 16
                    if view == "threads":
                        text u"Дела, которые могут получить продолжение" style "dg_note_heading" size 30
                        for thread in dg_rpg_state.get("story_memory", {}).get("threads", [])[::-1]:
                            text (thread["title"] + u" · " + {"open":u"открыто", "resolved":u"завершено", "abandoned":u"упущено"}[thread["status"]]) style "dg_note_body"
                            text dg_literal(thread["intention"]) style "dg_note_hint" xmaximum 855
                        text u"Память прежних встреч" style "dg_note_heading" size 30
                        for episode in dg_rpg_state.get("story_memory", {}).get("episodes", [])[-8:][::-1]:
                            text (u"День %d · %s" % (episode["day"], dg_rpg.PLACE_NAMES[episode["place"]])) style "dg_note_hint"
                            text dg_literal(episode["confirmed_result"]) style "dg_note_body" xmaximum 855
                    elif view == "timeline":
                        for row in dg_rpg_state["journal"][::-1]:
                            text (u"День %d · %s" % (row["day"], dg_rpg.SLOTS[row["slot"]])) style "dg_note_hint" size 20
                            text dg_literal(row["text"]) style "dg_note_body" size 26 xmaximum 855
                    elif view == "talks":
                        if not dg_rpg_state.get("dialogue_history"):
                            text u"Вы ещё не вели подробных разговоров. Встретьте персонажа и выберите тему беседы." style "dg_note_body" size 28 xmaximum 850
                        for item in dg_rpg_state.get("dialogue_history", [])[::-1]:
                            text (u"День %d · %s · %s" % (item["day"], dg_rpg.NPC_NAMES[item["who"]], item["topic"])) style "dg_note_hint" size 23
                            text dg_literal(dg_stage.readable(item["text"])) style "dg_note_body" size 26 xmaximum 855
                            text (u"Отношения +%d" % item["affinity_gain"]) style "dg_note_body" size 22 color "#e0ce93"
                            null height 12
                    elif view == "world":
                        if not dg_rpg_state["world"]["chronicle"]:
                            text u"Лагерные истории только начинаются. Посетите место события дня и примите решение." style "dg_note_body" size 28 xmaximum 850
                        for item in dg_rpg_state["world"]["chronicle"][::-1]:
                            text (u"День %d · %s · %s" % (item["day"], item["title"],
                                  u"Пропущено" if item["status"] == "missed" else u"Событие сыграно")) style "dg_note_hint" size 23
                            text dg_literal(dg_stage.readable(item["text"])) style "dg_note_body" size 26 xmaximum 855
                            null height 12
                    elif view == "social":
                        text u"ЖИЗНЬ ЛАГЕРЯ БЕЗ ТЕБЯ" style "dg_note_hint" size 25 color "#e0ce93"
                        if not dg_rpg_state["social"]["rumours"]:
                            text u"Пока ничего необычного. Новые слухи появляются со временем." style "dg_note_body" size 25
                        for item in dg_rpg_state["social"]["rumours"][::-1]:
                            text (u"День %d" % item["day"]) style "dg_note_hint" size 22
                            text dg_literal(dg_stage.readable(item["text"])) style "dg_note_body" size 26 xmaximum 850
                        text u"ЛИЧНЫЕ ИСТОРИИ" style "dg_note_hint" size 25 color "#e0ce93"
                        for who, name in dg_social.NAMES.items():
                            if who != "uv" or dg_rpg_state.get("mystery", {}).get("yulia_discovered", False):
                                text (name + u": " + str(dg_rpg_state["social"]["personal"].get(who, 0)) + u"/3 этапов") style "dg_note_body" size 24
                    else:
                        for item in dg_rpg_state.get("hybrid_history", [])[::-1]:
                            text (u"День %d · Твой поступок" % item["day"]) style "dg_note_hint"
                            text dg_literal(item["action"]) style "dg_note_body" xmaximum 855
                            text dg_literal(dg_stage.readable(item["scene"] or item["result"])) style "dg_note_body" xmaximum 855
                            null height 16
                        if not dg_rpg_state["ai_scenes"] and not dg_rpg_state.get("hybrid_history"):
                            text u"Пока нет AI-сцен. Продолжи историю своим действием или репликой." style "dg_note_body" size 28
                        for item in dg_rpg_state["ai_scenes"][::-1]:
                            text (u"День %d · %s" % (item["day"], dg_rpg.NPC_NAMES[item["who"]])) style "dg_note_hint" size 23
                            text dg_literal(dg_stage.readable(item["text"])) style "dg_note_body" size 26 xmaximum 855
                            null height 13
        frame:
            background Solid("#102b33e8")
            padding (24, 19)
            xsize 750 ysize 660
            viewport:
                viewport_xfill True
                vscrollbar_xsize 16
                vscrollbar_base_bar Solid("#0b2029")
                vscrollbar_thumb Solid("#6d918e")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                mousewheel True scrollbars "vertical" ysize 610
                vbox:
                    spacing 13
                    if view == "social":
                        text u"ОТНОШЕНИЯ МЕЖДУ NPC" style "dg_note_hint" size 25 color "#e0ce93"
                        for a, b, initial, caption, description in dg_social.PAIR_DEFS:
                            if dg_rpg_state.get("mystery", {}).get("yulia_discovered", False) or "uv" not in (a, b):
                                text (caption + u": " + str(dg_social.bond(dg_rpg_state, a, b))) style "dg_note_body" size 25
                        null height 14
                        text u"ДОЛГОСРОЧНЫЕ ПОРУЧЕНИЯ" style "dg_note_hint" size 25
                        for item in dg_social.quest_list(dg_rpg_state):
                            text (item["title"] + u": " +
                                  (u"Не принято" if item["status"] == "available"
                                   else u"В процессе" if item["status"] == "active"
                                   else u"Готово" if item["status"] == "completed" else u"Просрочено")) style "dg_note_body" size 23
                        null height 15
                    text u"ХАРАКТЕРИСТИКИ" style "dg_note_hint" size 25
                    text (u"Энергия: %d/100" % dg_rpg_state["energy"]) style "dg_note_body" size 26
                    text (u"Любознательность: %d · Доброта: %d · Навык: %d" %
                          (dg_rpg_state["stats"]["curiosity"], dg_rpg_state["stats"]["kindness"],
                           dg_rpg_state["stats"]["skill"])) style "dg_note_body" size 23 xmaximum 680
                    null height 12
                    text u"СОСТОЯНИЕ ЛАГЕРЯ" style "dg_note_hint" size 25 color "#e0ce93"
                    text (u"Сплочённость: %d/100 · Знания: %d/100" %
                          (dg_rpg_state["world"]["morale"], dg_rpg_state["world"]["knowledge"])) style "dg_note_body" size 23
                    text (u"Свобода: %d/100 · Ресурсы: %d/100" %
                          (dg_rpg_state["world"]["freedom"], dg_rpg_state["world"]["resources"])) style "dg_note_body" size 23
                    null height 12
                    text u"СЮЖЕТНЫЕ ЛИНИИ" style "dg_note_hint" size 25
                    for plot in dg_world.PLOT_ORDER:
                        text (dg_world.PLOTS[plot]["name"] + u" · " +
                              str(dg_rpg_state["world"]["tracks"][plot]["stage"]) + u"/5") style "dg_note_body" size 25 color "#e0ce93"
                        text dg_world.story_status(dg_rpg_state, plot) style "dg_note_body" size 21 xmaximum 680
                    null height 15
                    text u"ОТНОШЕНИЯ" style "dg_note_hint"
                    for who, name, morning, daytime, evening, night in dg_rpg.NPCS:
                        if who != "uv" or dg_rpg_state.get("mystery", {}).get("yulia_discovered", False):
                            text (u"%s: %d/100 · %s" % (name, dg_rpg_state["affinity"][who], dg_rpg.route_label(dg_rpg_state["affinity"][who]))) style "dg_note_body" size 25
                    null height 18
                    text u"ЗАДАНИЯ" style "dg_note_hint"
                    for key, title, progress, goal in dg_rpg.quest_progress(dg_rpg_state):
                        text (u"%s: %d/%d%s" % (title, (progress if progress <= goal else goal), goal, u" (готово)" if key in dg_rpg_state["quests_done"] else u"")) style "dg_note_body" size 24

    key "K_ESCAPE" action Return(None)

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
                    viewport_xfill True
                    vscrollbar_xsize 16
                    vscrollbar_base_bar Solid("#0b2029")
                    vscrollbar_thumb Solid("#6d918e")
                    vscrollbar_unscrollable "hide"
                    side_spacing 12
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
            viewport_xfill True
            vscrollbar_xsize 16
            vscrollbar_base_bar Solid("#0b2029")
            vscrollbar_thumb Solid("#6d918e")
            vscrollbar_unscrollable "hide"
            side_spacing 12
            ysize 640
            mousewheel True scrollbars "vertical"
            text dg_literal(scene_text) style "dg_ink_small" size 30 xmaximum 1240
    textbutton u"Иллюстрировать сцену (CG)" style "dg_primary" xpos 1120 ypos 955 action Return("cg")

# Native named dialogue over a frozen, full-screen stage. No hub overlay.
label dg_rpg_vn_text(scene_text, who=None):
    $ renpy.hide_screen("dg_scene")
    if dg_rpg_scene_context is None:
        $ dg_rpg_scene_context = dg_stage.freeze(dg_rpg_state, who)
    $ dg_rpg_stage_active = True
    scene expression dg_rpg_bg()
    $ dg_rpg_actor_moods = {}
    $ dg_rpg_visual_cast = None
    $ dg_stage_present = list(dg_rpg_scene_context["present"])
    if who in dg_stage.NAMES and who not in dg_stage_present:
        $ dg_stage_present.append(who)
    $ dg_rpg_vn_turns = dg_stage.parse(scene_text, dg_stage_present, who)
    $ dg_rpg_vn_cast = dg_stage.cast(dg_rpg_vn_turns, dg_stage_present, who)
    $ dg_rpg_vn_line_index = 0
    while dg_rpg_vn_line_index < len(dg_rpg_vn_turns):
        $ dg_rpg_vn_turn = dg_rpg_vn_turns[dg_rpg_vn_line_index]
        $ dg_rpg_stage_actors(dg_rpg_vn_turns, dg_rpg_vn_cast, dg_rpg_vn_turn)
        $ dg_rpg_vn_line = dg_literal(dg_rpg_vn_turn["text"])
        $ renpy.say(dg_rpg_say_character(dg_rpg_vn_turn["who"]), dg_rpg_vn_line)
        $ dg_rpg_vn_line_index += 1
    $ dg_rpg_stage_active = False
    return

label dg_rpg_vn_scene(scene_text, cg_possible=True, who=None, scene_identity=None):
    if scene_identity is not None:
        call dg_rpg_narrate("result",who,scene_identity,scene_text)
        $ scene_text = _return
        if scene_text is None:
            return None
    # The optional CG must depict the actual visible narrative, not the
    # shorter scripted fallback that was replaced by the narrator.
    $ store.dg_rpg_last_narrated_text = scene_text
    call dg_rpg_vn_text(scene_text, who)
    if cg_possible:
        menu:
            "Продолжить историю":
                return None
            "Посмотреть или создать CG":
                return "cg"
    else:
        return None

# New narrative requires the online narrator. Cached scenes remain readable.
label dg_rpg_narrate(kind, who, identity, source_text, choices=None):
    $ dg_narrative_key = dg_narrative.context(dg_rpg_state,kind,who,identity)["scene_id"]
    $ dg_narrative_saved = dg_narrative.read_scene(dg_rpg_state,dg_narrative_key)
    if dg_narrative_saved is not None:
        if dg_rpg_pending_turn is not None:
            $ dg_rpg_apply("remember_narrative",(dg_narrative_key,dg_narrative_saved["text"]))
        return dg_narrative_saved["text"]
    while True:
        if not dg_runtime.app.client.authenticated():
            call dg_connect
            if not dg_runtime.app.client.authenticated():
                return None
        $ dg_run("chapter",dg_rpg_auto_generate,kind,who,identity,source_text,choices)
        if not dg_runtime.app.error:
            $ dg_rpg_apply("remember_narrative",(dg_narrative_key,dg_runtime.app.result))
            return dg_runtime.app.result
        call screen dg_error
        menu:
            "Повторить генерацию сцены":
                pass
            "Вернуться в лагерь":
                return None

label dg_rpg_vn_choice(story_text, choice_pairs, who=None, scene_identity=None):
    if scene_identity is not None:
        call dg_rpg_narrate("world" if who is not None else "encounter", who, scene_identity, story_text, choice_pairs)
        $ story_text = _return
        if story_text is None:
            return None
    call dg_rpg_vn_text(story_text, who)
    $ dg_rpg_vn_selected = renpy.display_menu([(dg_literal(caption), key) for key, caption in choice_pairs])
    if dg_rpg_vn_selected == "__cancel__":
        return None
    return dg_rpg_vn_selected

label dg_rpg_vn_dialogue(who, phase, topic_index=0, stance="support"):
    if phase == "topics":
        $ dg_rpg_vn_dlg = dg_dialogue.opening(dg_rpg_state, who)
    elif phase == "choice":
        $ dg_rpg_vn_dlg = dg_dialogue.topic(dg_rpg_state, who, topic_index)
    else:
        $ dg_rpg_vn_dlg = dg_dialogue.outcome(dg_rpg_state, who, topic_index, stance)
    $ dg_rpg_vn_dlg = dg_narrative.decorate_dialogue(dg_rpg_state,who,phase,dg_rpg_vn_dlg,topic_index,stance)
    $ dg_npc_situation_id = "%s:%d:%s:%d" % (who,topic_index,phase,dg_rpg_state["dialogue_counts"].get("%d:%s" % (dg_rpg_state["day"],who),0))
    call dg_rpg_narrate("npc_"+phase,who,dg_npc_situation_id,dg_rpg_vn_dlg["text"],dg_rpg_vn_dlg.get("options"))
    $ dg_rpg_vn_narrated = _return
    if dg_rpg_vn_narrated is None:
        return None
    call dg_rpg_vn_text(dg_rpg_vn_narrated, who)
    if phase == "result":
        return
    $ dg_rpg_vn_options = [(dg_literal(caption), key) for key, caption in dg_rpg_vn_dlg["options"]]
    $ dg_rpg_vn_options.append((u"Написать свою реплику · AI", "custom"))
    $ dg_rpg_vn_options.append((u"Завершить разговор", "__cancel__"))
    $ dg_rpg_vn_selected = renpy.display_menu(dg_rpg_vn_options)
    if dg_rpg_vn_selected == "__cancel__":
        return None
    return dg_rpg_vn_selected

label dg_rpg_main:
    $ dg_setup()
    # The old DG place screen paints a gate image on the screens layer,
    # covering Ren'Py master-layer backgrounds and actor sprites.
    $ renpy.hide_screen("dg_scene")
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
        $ dg_create_source = "bkrr:mi"
        $ dg_create_pronouns = u"он/его"
        $ dg_create_adult = False
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
        $ dg_rpg_start(dg_create_name.strip(), dg_create_age, dg_create_days, dg_create_history.strip(), dg_create_source, dg_create_pronouns, dg_create_adult)
        jump dg_rpg_loop
    jump dg_rpg_create_loop

label dg_rpg_loop:
    # Abandoned/failed narration leaves the durable save untouched.
    if dg_rpg_pending_turn is not None:
        $ dg_rpg_pending_turn = None
        $ dg_rpg_open(dg_rpg_state["id"])
    $ dg_rpg_stage_active = False
    $ dg_rpg_scene_context = dg_stage.freeze(dg_rpg_state)
    call screen dg_rpg_hub
    $ dg_rpg_cmd, dg_rpg_value = _return
    if dg_rpg_cmd == "controls":
        call screen dg_rpg_controls
        $ dg_rpg_cmd, dg_rpg_value = _return
    if dg_rpg_cmd == "exit":
        jump dg_rpg_picker_label
    if dg_rpg_cmd == "profile":
        $ dg_rpg_apply("profile", dg_rpg_value)
        jump dg_rpg_loop
    if dg_rpg_cmd == "journal":
        call screen dg_rpg_journal
        jump dg_rpg_loop
    if dg_rpg_cmd == "cg_gallery":
        call screen dg_rpg_cg_gallery
        if isinstance(_return, tuple) and len(_return)==2 and _return[0]=="view":
            $ dg_cg_plan = _return[1]
            jump dg_rpg_cg_label
        jump dg_rpg_loop
    if dg_rpg_cmd == "finale":
        call screen dg_rpg_finale
        jump dg_rpg_loop
    if dg_rpg_cmd == "connect":
        call dg_connect
        jump dg_rpg_loop
    if dg_rpg_cmd == "diag":
        call screen dg_diagnostics
        jump dg_rpg_loop
    if dg_rpg_cmd == "narrator":
        $ persistent.dg_auto_narrate = not getattr(persistent,"dg_auto_narrate",True)
        jump dg_rpg_loop
    if dg_rpg_cmd == "artist":
        call screen dg_rpg_artist_settings
        jump dg_rpg_loop
    if dg_rpg_cmd == "adult":
        call screen dg_rpg_adult_settings
        if _return == "enable":
            $ dg_rpg_apply("adult_mode", True)
        elif _return == "disable":
            $ dg_rpg_apply("adult_mode", False)
        jump dg_rpg_loop
    if dg_rpg_cmd == "map":
        $ dg_map_result = ("map", None)
        while dg_map_result and dg_map_result[0] in ("map", "places", "cabins"):
            if dg_map_result[0] == "places":
                call screen dg_rpg_places
            elif dg_map_result[0] == "cabins":
                call screen dg_rpg_cabins(dg_map_result[1])
            else:
                call screen dg_rpg_map
            $ dg_map_result = _return
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
    if dg_rpg_cmd == "surprise":
        $ dg_rpg_focus = dg_rpg_value
        $ dg_rpg_spontaneous = dg_narrative.spontaneous(dg_rpg_state,dg_rpg_focus)
        call dg_rpg_vn_scene(dg_rpg_spontaneous["text"],False,dg_rpg_focus,dg_rpg_spontaneous["id"])
        menu:
            "Ответить своим действием / репликой":
                $ dg_rpg_hybrid_mode = "npc" if dg_rpg_focus is not None else "free"
                $ dg_rpg_hybrid_who = dg_rpg_focus
                $ dg_rpg_hybrid_topic = None
                jump dg_rpg_hybrid_entry
            "Послушать и продолжить день":
                $ dg_rpg_apply("spontaneous",dg_rpg_focus)
                jump dg_rpg_loop
            "Уйти, не вмешиваясь":
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
        if dg_social.incident_at(dg_rpg_state, dg_rpg_state["place"]) and dg_rpg_state["energy"] >= 9:
            $ dg_incident_current = dg_social.incident_at(dg_rpg_state, dg_rpg_state["place"])
            $ dg_rpg_incident_choices = list(dg_social.INCIDENT_CHOICES) + [("__cancel__", u"Не вмешиваться сейчас")]
            call dg_rpg_vn_choice(dg_incident_current["text"], dg_rpg_incident_choices, None, "incident:%d" % dg_rpg_state["day"])
            if _return:
                $ dg_rpg_incident_choice = _return
                $ dg_rpg_apply("incident", dg_rpg_incident_choice)
                $ dg_rpg_incident_result = {"title":dg_rpg_last_incident["title"],"text":dg_rpg_last_incident["text"]}
                call dg_rpg_vn_scene(dg_rpg_incident_result["text"], True, None, "incident_outcome:%d:%s" % (dg_rpg_state["day"],dg_rpg_incident_choice))
                if _return == "cg":
                    $ dg_cg_plan = dg_rpg_cg_for("incident", dg_rpg_incident_result["title"], dg_rpg_last_narrated_text, None)
                    jump dg_rpg_cg_label
        jump dg_rpg_loop
    if dg_rpg_cmd == "personal":
        $ dg_rpg_focus = dg_rpg_value
        if dg_social.personal_scene(dg_rpg_state, dg_rpg_focus) and dg_rpg_state["energy"] >= 12:
            $ dg_personal_current = dg_social.personal_scene(dg_rpg_state,dg_rpg_focus)
            $ dg_personal_choices = list(dg_personal_current["choices"]) + [("__cancel__", u"Вернуться позже")]
            call dg_rpg_vn_choice(dg_personal_current["text"], dg_personal_choices, dg_rpg_focus, "personal:%s:%d" % (dg_rpg_focus,dg_personal_current["stage"]))
            if _return:
                $ dg_rpg_personal_stance = _return
                $ dg_rpg_apply("personal", (dg_rpg_focus, dg_rpg_personal_stance))
                $ dg_rpg_personal_result = {"title": dg_rpg_last_personal["title"], "text": dg_rpg_last_personal["text"]}
                call dg_rpg_vn_scene(dg_rpg_personal_result["text"], True, dg_rpg_focus, "personal_result:%s:%s:%d" % (dg_rpg_focus,dg_rpg_personal_stance,dg_rpg_state["day"]))
                if _return == "cg":
                    $ dg_cg_plan = dg_rpg_cg_for("personal", dg_rpg_personal_result["title"], dg_rpg_last_narrated_text, dg_rpg_focus)
                    jump dg_rpg_cg_label
        jump dg_rpg_loop
    if dg_rpg_cmd == "talk":
        $ dg_rpg_focus = dg_rpg_value
        if dg_rpg_state["energy"] < 8:
            jump dg_rpg_loop
        call dg_rpg_vn_dialogue(dg_rpg_focus, "topics")
        if _return == "custom":
            $ dg_rpg_hybrid_mode = "npc"
            $ dg_rpg_hybrid_who = dg_rpg_focus
            $ dg_rpg_hybrid_topic = None
            jump dg_rpg_hybrid_entry
        if _return is None:
            jump dg_rpg_loop
        $ dg_rpg_talk_topic = int(_return)
        call dg_rpg_vn_dialogue(dg_rpg_focus, "choice", dg_rpg_talk_topic)
        if _return == "custom":
            $ dg_rpg_hybrid_mode = "npc"
            $ dg_rpg_hybrid_who = dg_rpg_focus
            $ dg_rpg_hybrid_topic = dg_rpg_talk_topic
            jump dg_rpg_hybrid_entry
        if _return is None:
            jump dg_rpg_loop
        $ dg_rpg_talk_stance = _return
        $ dg_rpg_apply("conversation", (dg_rpg_focus, dg_rpg_talk_topic, dg_rpg_talk_stance))
        call dg_rpg_vn_dialogue(dg_rpg_focus, "result", dg_rpg_talk_topic, dg_rpg_talk_stance)
        jump dg_rpg_loop
    if dg_rpg_cmd == "route":
        if dg_rpg_state["energy"] < 12:
            jump dg_rpg_loop
        $ dg_rpg_focus = dg_rpg_value
        $ dg_rpg_route_level = dg_rpg.available_route_events(dg_rpg_state, dg_rpg_focus)[0][0]
        $ dg_route_intro = dg_dialogue.route_intro(dg_rpg_state, dg_rpg_focus, dg_rpg_route_level)
        $ dg_route_choices = list(dg_route_intro["options"]) + [("__cancel__", u"Вернуться позже")]
        call dg_rpg_vn_choice(dg_route_intro["text"], dg_route_choices, dg_rpg_focus, "route:%s:%d" % (dg_rpg_focus,dg_rpg_route_level))
        if _return:
            $ dg_rpg_route_stance = _return
            $ dg_rpg_apply("route", (dg_rpg_focus, dg_rpg_route_stance))
            call dg_rpg_vn_scene(dg_dialogue.route_conclusion(dg_rpg_focus, dg_rpg_route_level, dg_rpg_route_stance), False, dg_rpg_focus, "route_result:%s:%d:%s" % (dg_rpg_focus,dg_rpg_route_level,dg_rpg_route_stance))
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
            call dg_rpg_vn_scene(dg_runtime.app.result, True, dg_rpg_focus)
            if _return == "cg":
                $ dg_cg_plan = dg_rpg_cg_for("ai", u"Особая сцена", dg_runtime.app.result, dg_rpg_focus, dg_rpg_intent)
                jump dg_rpg_cg_label
        jump dg_rpg_loop
    if dg_rpg_cmd == "background":
        # Never generate a background that already has an exact canonical asset
        # or was synthesized in this shift. No implicit API calls.
        if dg_rpg_bg_status()["status"] != "missing":
            jump dg_rpg_loop
        if getattr(persistent, "dg_rpg_art_provider", "cloud") != "comfy":
            if not dg_runtime.app.client.authenticated():
                call dg_connect
                if not dg_runtime.app.client.authenticated():
                    jump dg_rpg_loop
        $ dg_run("chapter", dg_rpg_art_generate, "background", dg_rpg_value)
        if dg_runtime.app.error:
            call screen dg_error
        jump dg_rpg_loop
    jump dg_rpg_loop

label dg_rpg_world_label:
    if dg_rpg_state["finished"]:
        jump dg_rpg_loop
    if dg_rpg_state["energy"] < 8:
        call dg_rpg_vn_text(u"Сейчас не хватает сил вмешаться в это событие. Отдохни, а потом возвращайся.")
        jump dg_rpg_loop
    if not dg_world.event_at(dg_rpg_state, dg_rpg_state["place"]):
        jump dg_rpg_loop
    $ dg_world_active = dg_world.event_at(dg_rpg_state, dg_rpg_state["place"])
    $ dg_world_choices = [(choice["key"], choice["text"]) for choice in dg_world_active["choices"]]
    $ dg_world_choices.append(("custom", u"Написать своё действие · AI"))
    $ dg_world_choices.append(("__cancel__", u"Вернуться в лагерь"))
    call dg_rpg_vn_choice(dg_world_active["story"], dg_world_choices, dg_world_active["npc"], dg_world_active["id"])
    if _return == "custom":
        $ dg_rpg_hybrid_mode = "world"
        $ dg_rpg_hybrid_who = None
        $ dg_rpg_hybrid_topic = None
        jump dg_rpg_hybrid_entry
    if _return:
        $ dg_rpg_world_stance = _return
        $ dg_rpg_apply("world", dg_rpg_world_stance)
        call dg_rpg_vn_scene(dg_rpg_last_world["text"], True, dg_world_active["npc"], "outcome:"+dg_world_active["id"]+":"+dg_rpg_world_stance)
        if _return == "cg":
            $ dg_cg_plan = dg_rpg_cg_for("world", dg_rpg_last_world["title"], dg_rpg_last_narrated_text, dg_rpg_last_world.get("npc"))
            jump dg_rpg_cg_label
    jump dg_rpg_loop


# Hybrid turn lifecycle: PREVIEW (offline, pure) -> explicit AI/local choice
# -> generation (text only, worker thread) -> verified COMMIT (main thread).
label dg_rpg_hybrid_entry:
    if dg_rpg_action_context != (dg_rpg_hybrid_mode, dg_rpg_hybrid_who, dg_rpg_hybrid_topic):
        $ dg_rpg_action_draft = u""
        $ dg_rpg_action_context = (dg_rpg_hybrid_mode, dg_rpg_hybrid_who, dg_rpg_hybrid_topic)
    call screen dg_rpg_hybrid_input(dg_rpg_hybrid_mode, dg_rpg_hybrid_who)
    $ dg_rpg_hybrid_submission = _return
    if not isinstance(dg_rpg_hybrid_submission, tuple) or len(dg_rpg_hybrid_submission) != 2 or dg_rpg_hybrid_submission[0] != "submit":
        jump dg_rpg_loop
    $ dg_rpg_hybrid_action_text = dg_rpg_hybrid_submission[1]
    $ logging.getLogger("don_gen").info("Hybrid input submitted mode=%s chars=%d",dg_rpg_hybrid_mode,len(dg_rpg_hybrid_action_text))
    $ dg_rpg_hybrid_preview(dg_rpg_hybrid_mode, dg_rpg_hybrid_action_text, dg_rpg_hybrid_who, dg_rpg_hybrid_topic)
    jump dg_rpg_hybrid_review_label

label dg_rpg_hybrid_review_label:
    if not isinstance(dg_rpg_hybrid_plan, dict):
        jump dg_rpg_hybrid_entry
    call screen dg_rpg_hybrid_review(dg_rpg_hybrid_plan)
    if _return == "retry":
        $ dg_rpg_action_draft = dg_rpg_hybrid_plan.get("action", dg_rpg_action_draft)
        jump dg_rpg_hybrid_entry
    if _return == "cancel" or not _return:
        jump dg_rpg_loop
    if _return == "local":
        $ dg_rpg_apply("hybrid", (dg_rpg_hybrid_plan, None))
        call dg_rpg_vn_scene(dg_rpg_hybrid_entry["scene"] or dg_rpg_hybrid_entry["result"])
        if _return == "cg":
            $ dg_cg_who = dg_rpg_hybrid_plan.get("who") or dg_rpg_hybrid_plan["result"].get("npc") or dg_rpg_hybrid_plan["result"].get("target")
            $ dg_cg_plan = dg_rpg_cg_for("hybrid", u"Мой поступок", dg_rpg_hybrid_entry["scene"] or dg_rpg_hybrid_entry["result"], dg_cg_who, dg_rpg_hybrid_entry["action"])
            jump dg_rpg_cg_label
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
        $ dg_rpg_action_draft = u""
        call dg_rpg_vn_scene(dg_rpg_hybrid_entry["scene"] or dg_rpg_hybrid_entry["result"])
        if _return == "cg":
            $ dg_cg_who = dg_rpg_hybrid_plan.get("who") or dg_rpg_hybrid_plan["result"].get("npc")
            $ dg_cg_plan = dg_rpg_cg_for("hybrid", u"Мой поступок", dg_rpg_hybrid_entry["scene"] or dg_rpg_hybrid_entry["result"], dg_cg_who, dg_rpg_hybrid_entry["action"])
            jump dg_rpg_cg_label
        jump dg_rpg_loop
    jump dg_rpg_loop


# All CG displays use this explicit, user-clicked path.
# No image request is made when a story screen is merely opened.
label dg_rpg_cg_label:
    if dg_cg_plan is None:
        jump dg_rpg_loop
    if dg_rpg_cg_status(dg_cg_plan)["status"] in ("generated","builtin"):
        $ dg_rpg_apply("cg_record",dg_cg_plan)
    call screen dg_rpg_cg_art(dg_cg_plan)
    if _return == "generate":
        if not dg_art.marker(dg_rpg_state,dg_cg_plan):
            jump dg_rpg_loop
        if dg_cg_plan["kind"] == "cg18" and getattr(persistent,"dg_rpg_art_provider","cloud") != "comfy":
            call screen dg_rpg_artist_settings
            jump dg_rpg_cg_label
        if getattr(persistent,"dg_rpg_art_provider","cloud") != "comfy":
            if not dg_runtime.app.client.authenticated():
                call dg_connect
                if not dg_runtime.app.client.authenticated():
                    jump dg_rpg_cg_label
        $ dg_cg_payload = dg_art.freeze_scene_request(dg_cg_plan)
        $ dg_run("chapter", dg_rpg_art_generate, dg_cg_plan["kind"], dg_cg_payload)
        if dg_runtime.app.error:
            $ dg_cg_failed_text = dg_runtime.app.error
            $ logging.getLogger("don_gen").error("CG generation failure: %s",dg_cg_failed_text)
            call screen dg_rpg_art_error(dg_cg_failed_text)
        else:
            $ dg_rpg_apply("cg_record",dg_cg_plan)
        jump dg_rpg_cg_label
    jump dg_rpg_loop

