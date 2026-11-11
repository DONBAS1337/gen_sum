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
    import dg_agents
    import dg_housing
    import dg_visits
    import dg_projects
    import dg_inventory
    import dg_relationships
    import dg_presentation
    import dg_consistency
    import dg_conversation
    import dg_audio
    import dg_intent
    import dg_cgvision
    import dg_bkrr
    import dg_camp
    import dg_clock
    import dg_affection
    if getattr(persistent,"dg_stock_policy_version",None)!=1:
        persistent.dg_prefer_generated=False
        persistent.dg_stock_policy_version=1

    def dg_rpg_audio_sync(who=None):
        if store.dg_rpg_audio_pauses is None:
            store.dg_rpg_audio_pauses=[(ch,renpy.music.get_pause(channel=ch)) for ch in ("music","ambience")]
            for ch,paused in store.dg_rpg_audio_pauses:
                renpy.music.set_pause(True,channel=ch)
        context = dg_rpg_scene_context if dg_rpg_stage_active else None
        audio_state = dict(dg_rpg_state)
        if context:
            for field in ("place","slot","day"):
                audio_state[field] = context[field]
            if dg_camp.enabled(audio_state) and context.get('minute') is not None:
                audio_state['camp_life']=dict(audio_state['camp_life'])
                audio_state['camp_life']['minute']=context['minute']
        visual = dg_rpg_visual_brief(audio_state)
        direction = dg_audio.plan(audio_state,who,visual.get("setting"))
        # Separate DG channels obey the host music/SFX mixers and do not restart.
        for channel, group, volume, enabled in (("dg_theme","music",.35,persistent.dg_rpg_music),("dg_nature","ambience",.5,persistent.dg_rpg_ambience)):
            choices = dict(dg_runtime.app.catalog.get(group,{}) or {})
            for key in direction[group]:
                folder="music" if group=="music" else "ambiences"
                basename=key if group=="music" else key[len("ambience_"):]
                path="sound/"+folder+"/"+basename+".ogg"
                if renpy.loadable(path): choices[key]=path
            path = dg_audio.resolve(choices,direction[group],renpy.loadable) if enabled else None
            signature=(audio_state["place"],audio_state["slot"],visual.get("setting"),path)
            if store.dg_rpg_audio_last.get(channel)!=signature:
                logging.getLogger("don_gen").info("RPG audio channel=%s place=%s slot=%s setting=%s path=%s",channel,audio_state["place"],audio_state["slot"],visual.get("setting"),path)
                store.dg_rpg_audio_last[channel]=signature
            if path:
                renpy.music.play(path,channel=channel,loop=True,fadein=1.5,fadeout=1.2,if_changed=True,relative_volume=volume)
            else:
                renpy.music.stop(channel=channel,fadeout=1.2)

    def dg_rpg_audio_stop():
        if store.dg_rpg_audio_pauses is not None:
            for ch,paused in store.dg_rpg_audio_pauses:
                renpy.music.set_pause(paused,channel=ch)
            store.dg_rpg_audio_pauses=None
        for channel in ("dg_theme","dg_nature"):
            renpy.music.stop(channel=channel,fadeout=1.0)

    def dg_rpg_move_sound(before,after):
        if not persistent.dg_rpg_effects: return
        before_state=dict(dg_rpg_state);before_state['place']=before
        after_state=dict(dg_rpg_state);after_state['place']=after
        keys = dg_audio.movement(before,after,dg_rpg_visual_brief(before_state).get('setting'),dg_rpg_visual_brief(after_state).get('setting'))
        choices = dict(dg_runtime.app.catalog.get("sounds",{}) or {})
        for key in keys:
            if key not in choices:
                path="sound/sfx/"+key[len("sfx_"):]+".ogg"
                if renpy.loadable(path): choices[key]=path
        path=dg_audio.resolve(choices,keys,renpy.loadable)
        if path: renpy.music.play(path,channel="sound")

    def dg_rpg_after_load():
        state=getattr(store,'dg_rpg_state',None)
        if not isinstance(state,dg_rpg.DICT_TYPE) or not state.get('id'): return
        try:
            node=renpy.game.script.lookup(renpy.game.context().current)
            own_script=node.filename.replace('\\','/').endswith('/dg_rpg.rpy')
        except (KeyError,AttributeError,TypeError):
            own_script=False
        if not (getattr(store,'dg_rpg_active',False) or own_script): return
        if __import__('dg_sessions').removed(dg_rpg_root(),state['id']):
            store.dg_rpg_state=None
            store.dg_rpg_pending_turn=None
            renpy.notify(u'Эта смена удалена. Открыт список смен.')
            renpy.jump('dg_rpg_picker_label')
            return
        if state.get('native_resume')==2 or (state.get('version')==1 and getattr(store,'dg_rpg_pending_turn',None) is None):
            try:
                import dg_checkpoints
                if hasattr(dg_runtime.app,'invalidate'):dg_runtime.app.invalidate()
                pending=getattr(store,'dg_rpg_pending_turn',None)
                store.dg_rpg_state=dg_checkpoints.restore(dg_rpg_root(),state,pending)
                store.dg_rpg_interrupt=False
                if pending is not None or state.get('native_resume')!=2:
                    store.dg_rpg_pending_turn=None
                    store.dg_rpg_stage_active=False
                    store.dg_rpg_scene_context=dg_stage.freeze(store.dg_rpg_state)
                    renpy.jump('dg_rpg_resume_loaded')
                return
            except (IOError,OSError,ValueError,KeyError,TypeError):
                logging.getLogger('don_gen').warning('Native snapshot could not be restored; falling back to committed JSON')
        # JSON is the committed session. A native save can retain obsolete
        # Character objects and return addresses from other loaded scripts.
        try:
            dg_rpg_open(state['id'])
        except (IOError,OSError,ValueError):
            logging.getLogger('don_gen').warning('Native save has no recoverable DON-GEN session')
            renpy.jump('dg_rpg_picker_label')
            return
        store.dg_rpg_pending_turn=None
        store.dg_rpg_interrupt=False
        store.dg_rpg_stage_active=False
        store.dg_rpg_scene_context=dg_stage.freeze(store.dg_rpg_state)
        renpy.jump('dg_rpg_resume_loaded')

    if dg_rpg_after_load not in config.after_load_callbacks:
        config.after_load_callbacks.append(dg_rpg_after_load)

    def dg_rpg_choice_height(items):
        height=0
        for item in items:
            lines=(len(item.caption)+72)//73
            row=lines*30+20
            if row<50: row=50
            height+=row+12
        if height<130: return 130
        return 470 if height>470 else height

    def dg_rpg_poll(mode):
        if not dg_runtime.app.busy:
            renpy.end_interaction(True)
            return
        screen = renpy.get_screen("dg_rpg_wait")
        state=(dg_runtime.app.status,dg_elapsed())
        if screen is not None and screen.scope.get("wait_state")!=state:
            screen.scope["wait_state"]=state
            renpy.restart_interaction()

    def dg_rpg_run(mode,task,*args):
        import time
        dg_runtime.app.start(task,*args)
        renpy.suspend_rollback(True)
        try:
            store.dg_wait_started=time.time()
            return renpy.call_screen("dg_rpg_wait",mode=mode)
        finally:
            renpy.suspend_rollback(False)

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
            if width < 1 or height < 1:
                return result
            canvas = result.canvas()
            def rounded(color,x,y,w,h,radius):
                import math
                points=[]
                for cx,cy,start in ((x+w-radius-1,y+radius,-90),(x+w-radius-1,y+h-radius-1,0),(x+radius,y+h-radius-1,90),(x+radius,y+radius,180)):
                    for i in range(7):
                        angle=math.radians(start+i*15)
                        points.append((int(cx+radius*math.cos(angle)),int(cy+radius*math.sin(angle))))
                canvas.polygon(color,points)
            radius = 10 if width >= 18 and height >= 18 else 1
            rounded(self.edge, 0, 0, width, height, radius)
            rounded(self.fill, 1, 1, width - 2, height - 2, radius - 1)
            return result

    def dg_camp_button_surface(fill, edge):
        return DgCampButton(fill, edge)

    class DgNavIcon(renpy.Displayable):
        def __init__(self,kind,**kwargs):
            super(DgNavIcon,self).__init__(**kwargs)
            self.kind=kind
        def render(self,width,height,st,at):
            r=renpy.Render(24,24);c=r.canvas();color="#F2E4BB"
            if self.kind=="map":
                for points in ([(2,5),(8,3),(16,6),(22,4),(22,19),(16,21),(8,18),(2,20),(2,5)],[(8,3),(8,18)],[(16,6),(16,21)]):c.lines(color,False,points,2)
            elif self.kind=="book":
                c.lines(color,False,[(12,6),(4,3),(2,4),(2,19),(12,22),(22,19),(22,4),(20,3),(12,6),(12,22)],2)
            elif self.kind=="events":
                c.rect(color,(3,5,18,17),2);c.line(color,(3,10),(21,10),2)
                for x in (7,16):c.line(color,(x,2),(x,7),2)
                for x in (7,12,17):c.circle(color,(x,15),1)
            else:
                c.circle(color,(12,12),8,2);c.circle(color,(12,12),3,2)
                for x,y in ((12,1),(12,23),(1,12),(23,12)):c.line(color,(12+(x-12)*.65,12+(y-12)*.65),(x,y),2)
            return r

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

    def dg_rpg_manage_shift(action,value):
        import dg_sessions
        if dg_runtime.app.busy:
            renpy.notify(u'Дождись завершения текущей операции.')
            return False
        renpy.block_rollback()
        try:
            if hasattr(dg_runtime.app,'invalidate'):dg_runtime.app.invalidate()
            if action=='trash':dg_sessions.trash(dg_rpg_root(),value)
            elif action=='restore':dg_sessions.restore(dg_rpg_root(),value)
            elif action=='purge':dg_sessions.purge(dg_rpg_root(),value)
            else:return False
            if action=='trash' and getattr(store,'dg_rpg_state',None) and store.dg_rpg_state.get('id')==value:
                store.dg_rpg_state=None;store.dg_rpg_pending_turn=None;store.dg_rpg_stage_active=False
            renpy.notify({'trash':u'Смена перемещена в корзину.','restore':u'Смена восстановлена.','purge':u'Смена удалена окончательно.'}[action])
            return True
        except (IOError,OSError,ValueError,KeyError,TypeError) as exc:
            logging.getLogger('don_gen').exception('Shift management failed action=%s id=%s',action,value)
            renpy.notify(u'Операция не завершилась. Проверь доступ к папке сохранений и повтори её.')
            return False

    def dg_random_housing():
        store.dg_create_cabin = renpy.random.choice(dg_housing.AVAILABLE_CABINS)
        store.dg_create_roommate = renpy.random.choice((None,) + dg_housing.ROOMMATES)

    def dg_rpg_start(name, age, days, history, source, pronouns, adult=False, cabin="cabin_01", roommate="mt"):
        state = dg_rpg.new_game(name, age, days, history, source, pronouns, cabin, roommate, camp_life=True)
        if adult:
            dg_adult.set_enabled(state, True, confirmed=True)
        dg_rpg.save(dg_rpg_root(), state)
        store.dg_rpg_state = state
        store.dg_rpg_action_draft = u""
        store.dg_rpg_intro_attempted=[]
        logging.getLogger("don_gen").info("RPG created id=%s days=%s", state["id"], state["duration"])
        renpy.block_rollback()

    def dg_rpg_open(game_id):
        store.dg_rpg_action_draft = u""
        store.dg_rpg_state = dg_rpg.load(dg_rpg_root(), game_id)
        store.dg_rpg_state["native_resume"]=2
        dg_rpg.save(dg_rpg_root(),store.dg_rpg_state)
        logging.getLogger("don_gen").info("RPG opened id=%s", game_id)
        renpy.block_rollback()

    def dg_rpg_apply(action, arg=None):
        if action == "music_door":
            state=dg_rpg.load(dg_rpg_root(),dg_rpg_state['id'])
            dg_visual.music_door(state,arg)
            dg_rpg.save(dg_rpg_root(),state)
            store.dg_rpg_state=state
            store.dg_rpg_scene_context=dg_stage.freeze(state)
            return True
        if action == "inventory":
            arg = dg_inventory.command(arg)
            if arg is None:
                return False
        state = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        transactional = action in ("conversation", "world", "personal", "incident", "route", "visit", "project", "relation", "inventory", "camp", "affection")
        pending = dg_turn.begin(state) if transactional else None
        if pending is not None:
            state = pending["state"]
        if action in ("talk", "route", "conversation", "world", "free", "personal", "incident", "hybrid", "spontaneous", "visit", "project", "relation", "inventory", "camp", "affection"):
            store.dg_rpg_scene_context = dg_stage.freeze(state)
        if action == "camp_enable":
            dg_camp.enable(state,arrival=False)
        elif action == "camp":
            store.dg_rpg_last_camp=dg_camp.act(state,arg)
            if state['place']!=store.dg_rpg_scene_context['place']:
                store.dg_rpg_scene_context=dg_stage.freeze(state,store.dg_rpg_last_camp['who'])
            if store.dg_rpg_last_camp.get('private'):
                store.dg_rpg_scene_context['present']=[store.dg_rpg_last_camp['who']]
            pending['private']=store.dg_rpg_last_camp.get('private')
            pending.update(who=store.dg_rpg_last_camp['who'],intention=store.dg_rpg_last_camp['title'],result=store.dg_rpg_last_camp['text'])
        elif action == "affection":
            store.dg_rpg_last_affection=dg_affection.act(state,arg[0],arg[1])
            pending.update(who=arg[0],intention=store.dg_rpg_last_affection['title'],result=store.dg_rpg_last_affection['text'])
        elif action == "end_conversation":
            dg_conversation.end(state)
        elif action == "move":
            before_place=state["place"]
            dg_rpg.move(state, arg)
            dg_rpg_move_sound(before_place,state["place"])
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
        elif action == "events_seen":
            dg_presentation.seen(state)
        elif action == "project_register":
            store.dg_rpg_new_project=dg_projects.register(state,arg)
        elif action == "project_cancel":
            dg_rpg._journal(state,dg_projects.cancel(state,arg))
        elif action == "inventory":
            store.dg_rpg_last_inventory=dg_inventory.act(state,arg[0],arg[1],arg[2])
            pending.update(who=store.dg_rpg_last_inventory['who'],intention=store.dg_rpg_last_inventory['title'],result=store.dg_rpg_last_inventory['text'])
        elif action == "project":
            store.dg_rpg_last_project=dg_projects.act(state,arg)
            pending.update(who=store.dg_rpg_last_project['who'],intention=store.dg_rpg_last_project['title'],result=store.dg_rpg_last_project['text'])
        elif action == "relation":
            store.dg_rpg_last_relation=dg_relationships.act(state,arg[0],arg[1],arg[2])
            pending.update(who=arg[0],intention=u'Личный разговор: '+arg[1],result=store.dg_rpg_last_relation)
        elif action == "visit_seen":
            if dg_visits.current(state):
                state['npc_visits']['active']['seen']=True
        elif action == "visit":
            store.dg_rpg_last_visit = dg_visits.respond(state,arg)
            pending.update(who=store.dg_rpg_last_visit['who'], intention=u'Ответ на инициативу NPC: '+arg,
                           result=store.dg_rpg_last_visit['text'])
        elif action == "visit_reply":
            dg_visits.respond(state,arg)
        elif action == "personal":
            store.dg_rpg_last_personal = dg_rpg.personal_choice(state, arg[0], arg[1])
            pending.update(who=arg[0], intention=store.dg_rpg_last_personal['title'] + u" — " + arg[1],
                           result=store.dg_rpg_last_personal['text'])
        elif action == "incident":
            store.dg_rpg_last_incident = dg_rpg.social_encounter(state, arg)
            pending.update(who=None, intention=store.dg_rpg_last_incident['title'] + u" — " + arg,
                           result=store.dg_rpg_last_incident['text'])
        elif action == "hybrid":
            hybrid_context=dg_hybrid.scene_context(state,arg[0])
            store.dg_rpg_hybrid_entry = dg_hybrid.commit(state, arg[0], arg[1])
            if arg[0]["result"].get("kind")=="risk" or arg[0]["result"].get("private"):store.dg_rpg_scene_context=hybrid_context
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

    def dg_rpg_propose_project(text):
        import copy,re
        state=dg_rpg.load(dg_rpg_root(),dg_rpg_state['id'])
        system=state.get('projects',{})
        if len(system.get('blueprints',{}))>=12 or len([row for key,row in system.get('records',{}).items() if key.startswith('custom_') and row['stage']<4 and not row.get('cancelled')])>=4:raise ValueError(u'Сначала заверши или отмени активные общие дела.')
        choices=[]
        for item,spec in sorted(dg_inventory.CATALOG.items()):
            if spec['source']:
                waiting=sum(1 for key,row in system.get('records',{}).items() if row['stage']==0 and not row.get('cancelled') and dg_projects.definitions(state)[key]['steps'][0][2]==item)
                free=__import__('dg_inventory').nonnegative(dg_inventory.stock_at(state,spec['source']).get(item,0)-waiting)+sum(dg_inventory.free_count(state,who,item) for who in ['hero']+list(system.get('npc_inventory',{})))
                if free:choices.append({'item':item,'title':spec['title'],'source':spec['source'],'available':free})
        if not choices:raise ValueError(u'Для нового дела нет свободных материалов. Сначала заверши текущие дела или освободи материалы отменой.')
        rules=(u'Предложи одно реалистичное безопасное лагерное дело по запросу игрока. Верни только JSON: '
               u'{"title":"5–80 символов","item":"код материала","recipient":"код NPC","work_place":"код места","final_place":"код места","theme":"festival|radio|lake|council","activity":"music|repair|read|explore|organize|help","participants":["2–4 кода NPC"]}. '
               u'Выбирай только известные материалы и места. Дело состоит из получения материала, доставки получателю, совместной подготовки и завершения. '
               u'Не обещай создания предметов вне известных рецептов, мгновенных навыков, фантастических технологий или заранее взаимной любви. '
               u'theme — направление истории, activity — реальный вид работы. Стенгазета и оформление — organize, чтение — read; для music нужен mi/dv/us, для repair el/sh. Не превращай любое дело в музыку только из-за профиля БКРР и не подменяй указанных игроком участников. '
               u'Материал должен существовать; роль героев учитывает характер и профиль мира. Игрок может предложить тему, но не изменить формат и правила.')
        context={'player_idea':text[:1000],'materials':choices,'places':dg_projects.PUBLIC_PLACES,'people':dg_narrative.PERSONA,'profile':dg_narrative.context(state,'project',None,text[:100]),'inventory':dg_inventory.report(state)}
        app=dg_runtime.app
        if not app.models:app.refresh_models()
        repair=u''
        for attempt in range(2):
            raw=app.client.generate(rules+repair,json.dumps(context,ensure_ascii=False),model=dg_backend.default_model(app.models,persistent.dg_model),effort=dg_backend.DEFAULT_EFFORT,fast_mode=persistent.dg_fast_mode)
            try:
                raw=re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip())
                if len(raw)>12000:raise ValueError(u'Слишком большой ответ планировщика.')
                value=dg_projects.check_blueprint(json.loads(raw))
                dg_projects.register(copy.deepcopy(state),value)
                return {'blueprint':value,'before':dg_hybrid.fingerprint(state)}
            except ValueError as exc:
                repair=u' Предыдущий вариант не прошёл проверку: '+type(u'')(exc)[:600]+u'. Исправь только причину отказа; не меняй задачу игрока ради обхода правил.'
        raise ValueError(u'Не удалось составить выполнимый план. Уточни материал, место или участников.')

    def dg_rpg_interpret_action(action, mode, who):
        current = dg_rpg.load(dg_rpg_root(), dg_rpg_state['id'])
        instructions, prompt = dg_intent.request(current, action, mode, who)
        app = dg_runtime.app
        if not app.models:
            app.refresh_models()
        model = dg_backend.default_model(app.models, persistent.dg_model)
        app.set_status(u'Разбираем намерение и условия…')
        text = app.client.generate(instructions, prompt, model=model,
                                  effort=dg_backend.DEFAULT_EFFORT, fast_mode=persistent.dg_fast_mode)
        proposal = dg_intent.validate(current, dg_intent.decode(text))
        proposal['_state'] = dg_hybrid.fingerprint(current)
        return proposal

    def dg_rpg_hybrid_preview(mode, action, who=None, topic=None, interpretation=None):
        current = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        try:
            plan = dg_hybrid.preview(current, action, mode, who, topic, interpretation)
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

    def dg_rpg_voice_reference(state,who,query):
        if state['source']!=dg_bkrr.SOURCE:return None
        try:
            import dg_source_bkrr
            root=dg_bkrr.find_root(config.gamedir,dg_rpg_workshop_root())
            people=([who] if who in dg_rpg.NPC_NAMES else [code for code,name in dg_rpg.at_place(state)])
            result=dg_source_bkrr.context(root,people,query,state['day']+3 if dg_camp.enabled(state) else state['day'])
            result['available']=bool(root)
            return result
        except (IOError,OSError,ValueError,UnicodeError):
            logging.getLogger('don_gen').warning('BKRR voice references unavailable')
            return {'source':'БКРР','available':False,'examples':[]}

    def dg_rpg_hybrid_generate(plan):
        # The background worker ONLY generates a text string. No save writes.
        current = dg_rpg.load(dg_rpg_root(), dg_rpg_state["id"])
        instructions, prompt = dg_hybrid.build_request(current, plan)
        hybrid_context=dg_hybrid.scene_context(current,plan)
        current=dg_hybrid.scene_state(current,plan)
        context = json.loads(prompt)
        context['visual_scene_facts'] = dg_rpg_visual_brief(current)
        context['voice_reference']=dg_rpg_voice_reference(current,plan.get('who'),plan['action'])
        prompt = json.dumps(context, ensure_ascii=False, sort_keys=True)
        app = dg_runtime.app
        # The 7DL source is read-only reference context, never executed.
        if current["source"].startswith("7dl:"):
            root=(app.catalog.get("source_roots") or {}).get("7dl")
            if root and os.path.isdir(root):
                try:
                    import dg_source_7dl
                    raw=dg_source_7dl.source_context(
                        root,os.path.join(dg_rpg_root(),"_source_cache"),
                        current["source"].split(":",1)[1],
                        dg_rpg.NPC_NAMES.get(plan.get("who"),u"Лагерь")+u" "+plan["action"][:190],mode="divergent",
                        day=(current["day"] if current["day"]<=7 else 7),
                        limit=3,max_chars=5200,voices_only=True,characters=([plan["who"]] if plan.get("who") else dg_stage.freeze(current)["present"]))
                    context=json.loads(prompt)
                    context["reference_7dl_source"]=raw
                    prompt=json.dumps(context,ensure_ascii=False,sort_keys=True)
                except (IOError,OSError,ValueError,TypeError):
                    logging.getLogger("don_gen").warning("7DL hybrid context unavailable",exc_info=True)
        if not app.models:
            app.refresh_models()
        model = dg_backend.default_model(app.models, persistent.dg_model)
        app.set_status(u"Пишем сцену с зафиксированным игровым исходом…")
        story = dg_consistency.generate(app.client,instructions, prompt,hybrid_context["present"], model=model,
                                    effort=dg_backend.DEFAULT_EFFORT,
                                    fast_mode=persistent.dg_fast_mode)
        if not isinstance(story, basestring) or len(dg_stage.readable(story).strip()) < 45 or len(story) > dg_hybrid.MAX_SCENE:
            raise ValueError("AI returned invalid scene length")
        dg_stage.validate_speakers(story, hybrid_context["present"])
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
            if dg_camp.enabled(state) and dg_rpg_scene_context.get('minute') is not None:
                state['camp_life']['minute']=dg_rpg_scene_context['minute']
        ref=u""
        # Use the actual installed 7DL route text when available. If no 7DL
        # resources exist, the route-specific persona profile still applies.
        if state["source"].startswith("7dl:"):
            root=(app.catalog.get("source_roots") or {}).get("7dl")
            if root and os.path.isdir(root):
                try:
                    import dg_source_7dl
                    ref=dg_source_7dl.source_context(
                        root,os.path.join(dg_rpg_root(),"_source_cache"),
                        state["source"].split(":",1)[1],
                        dg_rpg.NPC_NAMES.get(who,u"Лагерь")+u" "+story[:160],
                        mode="divergent",day=(state["day"] if state["day"]<=7 else 7),
                        limit=3,max_chars=5200,voices_only=True,characters=([who] if who else dg_stage.freeze(state)["present"]))
                except (IOError,OSError,ValueError,TypeError):
                    logging.getLogger("don_gen").warning(
                        "7DL context unavailable for auto scene",exc_info=True)
        instructions,prompt=dg_narrative.request(
            state,kind,who,identity,story,choices=choices,source_reference=ref)
        context = json.loads(prompt)
        context['visual_scene_facts'] = dg_rpg_visual_brief(state)
        context['voice_reference']=dg_rpg_voice_reference(state,who,story)
        present=dg_stage.freeze(state,who)['present']
        if kind in ('result','npc_result') and dg_rpg_scene_context is not None:
            present=list(dg_rpg_scene_context['present'])
            context['scene_identity']['present_people']=[(code,dg_rpg.NPC_NAMES[code]) for code in present]
        prompt = json.dumps(context, ensure_ascii=False, sort_keys=True)
        instructions+=u" "+dg_adult.scene_policy(state,who)+u" "+dg_stage.FORMATTING
        if not app.models:
            app.refresh_models()
        model=dg_backend.default_model(app.models,persistent.dg_model)
        app.set_status(u"Рассказываем уникальный эпизод лагеря…")
        result=dg_consistency.generate(app.client,instructions,prompt,present,model=model,
                                   effort=dg_backend.DEFAULT_EFFORT,
                                   fast_mode=persistent.dg_fast_mode)
        if isinstance(result,bytes):
            result=result.decode("utf-8")
        if not isinstance(result,unicode) or len(dg_stage.readable(result).strip())<100 or len(result)>12000:
            raise ValueError("Narrator returned invalid scene text")
        dg_stage.validate_speakers(result,present)
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

    def dg_rpg_local_map_root():
        return dg_resources.local_map_root(os.path.join(config.gamedir,"mods","don_gen","resource_sources.json"))

    def dg_rpg_map_asset(filename):
        local = dg_resources.local_map_asset(dg_rpg_local_map_root(),filename)
        if local:
            return local
        external = dg_resources.map_asset(dg_rpg_workshop_root(), filename)
        return external or DG_MAP_ROOT + filename

    def dg_map_npc_icon(who):
        code = "me" if who == "hero" else DG_MAP_ICON_BY_NPC.get(who)
        local = dg_resources.local_map_asset(dg_rpg_local_map_root(),"map_icon_%s.png" % code)
        if local:
            return im.Scale(local,42,42)
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
        lighting_slot=dg_visual.light_slot(dg_rpg_state,visual)
        if place in dg_housing.CABINS:
            bases = ["bg ext_houses_day"]
            if place == "cabin_13":
                bases.insert(0, "bg ext_house_of_un_day")
            for base in bases:
                for name in dg_visual.background_names(base, lighting_slot):
                    if name in dg_runtime.original_images:
                        return name
            return None
        if place=='music' and visual.get('music_inside',False):
            for room_name in dg_visual.background_names('bg int_musclub_day',lighting_slot):
                if room_name in dg_runtime.original_images:return room_name
        if dg_rpg_state.get("source") == dg_bkrr.SOURCE:
            root = dg_bkrr.find_root(config.gamedir, dg_rpg_workshop_root())
            backdrop = dg_bkrr.background(root, place, lighting_slot)
            if visual.get("weather",dg_world.weather(dg_rpg_state)[0])=="rain":
                backdrop=dg_bkrr.rain_background(root,place,lighting_slot) or backdrop
            if backdrop:
                return backdrop
        external = dg_resources.background(
            dg_runtime.app.catalog.get("source_assets", {}).get("7dl", {}),
            place, lighting_slot)
        if place not in DG_RPG_EXACT_BG:
            return external
        base = DG_RPG_BG.get(place)
        if base is None and place.startswith("cabin_"):
            base = "bg ext_houses_day"
        for name in dg_visual.background_names(base, lighting_slot):
            if name in dg_runtime.original_images:
                return name
        return external

    def dg_rpg_visual_brief(state):
        backdrop = dg_rpg_bg_native(state['place'], visual=state) or ''
        filename = os.path.basename(backdrop).lower().replace('bg ', '')
        setting = 'exterior' if filename.startswith('ext_') else 'interior' if filename.startswith('int_') else None
        return {'wardrobe':dict((who,dg_visual.clothing(state,who)) for who,name in dg_rpg.at_place(state)),'setting':setting, 'rule':u'wardrobe задаёт одежду: dress — праздничная, pioneer — форма. Сцена должна соответствовать показанному фону: exterior — снаружи, interior — внутри. Не меняй место без действия игрока.'}

    def dg_rpg_bg_status():
        place = dg_rpg_visual_state()["place"]
        native = dg_rpg_bg_native(place)
        return dg_art.resolve(dg_rpg_root(), dg_rpg_state["id"],
                              "background", dg_visual.background_key(place,dg_rpg_visual_state()["slot"]), native,
                              place not in dg_housing.CABINS and getattr(persistent,"dg_prefer_generated",True))

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
        clothes=dg_visual.clothing(dg_rpg_state,who,dg_rpg_visual_state())
        if pose is not None:
            for name in dg_visual.sprite_queries(who, emotion, distance,clothes):
                sprite = dg_7dl_sprite_displayable(name, pose_hint=pose)
                if sprite is not None:
                    return sprite
        known = dg_visual.sprite_names(who,emotion,distance,
                                        dg_runtime.original_images.keys(),clothes=clothes)
        exact=[name for name in known if
               (name.endswith(" "+distance) if distance!="normal"
                else not name.endswith((" far"," close")))]
        # For the specific 7DL route, layer-aware image composition may supply
        # a more expressive pose that doesn't have a registered vanilla name.
        use_7dl=dg_rpg_state["source"].startswith("7dl:") or clothes!="pioneer"
        if use_7dl:
            for name in dg_visual.sprite_queries(who,emotion,distance,clothes):
                sprite=dg_7dl_sprite_displayable(name)
                if sprite is not None:
                    return sprite
        if exact:
            return dg_runtime.original_images[exact[0]]
        # Only after trying genuine close/far poses do we accept an existing
        # normal-distance sprite. Never scale a normal pose as if it were close.
        if known:
            return dg_runtime.original_images[known[0]]
        for name in dg_visual.sprite_queries(who,emotion,distance,clothes):
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
        name = None if who is None else ((dg_rpg_scene_context or {}).get("hero_name", dg_rpg_state["hero"]["name"]) if who == "hero" else dg_stage.NAMES[who])
        # Host characters can be DynamicCharacter instances and use foreign
        # screens/callbacks. A literal Cyrillic name must never be evaluated.
        return Character(dg_literal(name) if name is not None else None,
                         dynamic=False, screen="dg_rpg_say", mode="say",
                         window_style="dg_rpg_say_window", who_style="dg_rpg_say_name", what_style="dg_rpg_say_text",
                         show_function=renpy.character.show_display_say,
                         predict_function=renpy.character.predict_show_display_say,
                         callback=None, condition=None, image=None, show_image=False,
                         show_side_image=None, show_two_window=False,
                         who_prefix=u"", who_suffix=u"", what_prefix=u"", what_suffix=u"",
                         who_font="fonts/calibri.ttf", who_size=24, who_bold=True,
                         who_color=dg_stage.COLORS.get(who, "#ffaa00"), who_outlines=[],
                         what_font="fonts/calibri.ttf", what_size=24, what_bold=False,
                         what_color="#F2E4BB", what_outlines=[])

    def dg_rpg_stage_actors(turns, cast_ids, turn):
        # Named reactions in narration affect only the explicitly named actor.
        if turn["who"] is None:
            for actor, emotion in dg_visual.narrated_moods(turn["text"],cast_ids).items():
                if actor not in turn.get('stage',{}):
                    store.dg_rpg_actor_moods[actor]=emotion
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
        for candidate in dg_rpg_cg_candidates(plan):
            try:
                verdict = dg_cgvision.cached(dg_rpg_root(), candidate['path'], plan)
                if verdict and verdict['accepted'] and renpy.loadable(candidate['path']):
                    return candidate['path']
            except (IOError, OSError, ValueError):
                continue
        return None

    def dg_rpg_cg_candidates(plan):
        import dg_gallery
        return dg_gallery.candidates(dg_gallery.catalog(dg_gallery.roots(dg_rpg_workshop_root())), plan,allow_uncertain=True)

    def dg_rpg_verify_cg(payload):
        current = dg_rpg.load(dg_rpg_root(), dg_rpg_state['id'])
        plan = dg_art.validate_scene_request(current, 'cg', payload)
        app = dg_runtime.app
        if not app.models:
            app.refresh_models()
        model = dg_backend.default_model(app.models, persistent.dg_model)
        reasons = []
        for candidate in dg_rpg_cg_candidates(plan):
            app.set_status(u'Сверяем иллюстрацию с содержанием сцены…')
            verdict = dg_cgvision.verify(app.client, candidate['path'], plan, dg_rpg_root(), model)
            if verdict['accepted']:
                return candidate['path']
            reasons.extend(verdict['reasons'])
        return u'Подходящей иллюстрации не найдено. ' + u' '.join(reasons[:3])

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
            plan.update(scene_place=context['place'], scene_slot=dg_visual.light_slot(state,context),
                        cast=cast_ids, profile=state['source'],hero_description=state['hero']['background'][:2000], hero_pronouns=state['hero']['pronouns'],
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
        context["voice_reference"]=dg_rpg_voice_reference(state,who,intent)
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
                        limit=3, max_chars=7000,voices_only=True,characters=[who])
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
        story_text = dg_consistency.generate(app.client,instructions,json.dumps(context,ensure_ascii=False),dg_stage.freeze(state,who)["present"],
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
            asset_key=dg_visual.background_key(key,state["slot"])
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
default dg_project_draft = u"Хочу организовать небольшое лагерное дело вместе с Мику"
default dg_create_cabin = "cabin_01"
default dg_create_roommate = "mt"
default dg_cg_vision_attempted = None
default dg_cg_vision_note = u""
default dg_rpg_pending_turn = None
default dg_rpg_focus = None
default dg_rpg_scene_context = None
default dg_rpg_stage_active = False
default dg_rpg_actor_moods = {}
default dg_rpg_audio_last = {}
default dg_rpg_audio_pauses = None
default persistent.dg_rpg_music = True
default persistent.dg_rpg_ambience = True
default persistent.dg_rpg_effects = True
default dg_rpg_intro_attempted = []
default dg_rpg_interrupt = False
default dg_rpg_active = False
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
            textbutton u"Корзина смен" style "dg_note_button" action Return(("trash",None))
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
                                textbutton u"Удалить смену…" style "dg_note_button" action Return(("delete_shift",game["id"]))
    textbutton u"Назад в меню" style "dg_note_tab" xpos 64 ypos 944 action Return(("back", None))
    key "K_ESCAPE" action Return(("back", None))

screen dg_rpg_shift_confirm(name,permanent=False):
    modal True
    add Solid("#0b2029f5")
    frame:
        background dg_camp_button_surface("#101923f5","#65D8D080")
        align (.5,.5) xsize 1160 padding (34,30)
        vbox:
            spacing 22 xsize 1090
            text (u"Удалить смену навсегда?" if permanent else u"Переместить смену в корзину?") style "dg_note_heading" size 36
            text dg_literal(name) style "dg_note_body" size 30 xmaximum 1060
            text (u"Будут окончательно удалены данные этой смены, её изображения и архивные ветки. Отменить это действие нельзя." if permanent else u"Смена исчезнет из списка продолжения. Её данные, изображения и архивные ветки сохранятся в корзине; их можно восстановить.") style "dg_note_body" size 26 xmaximum 1060
            text (u"Обычные слоты Ren’Py и другие смены не удаляются. Старый слот не возобновит окончательно удалённую смену." if permanent else u"Обычные слоты Ren’Py и другие смены не удаляются. Старый слот не возобновит удалённую смену, пока она не восстановлена из корзины.") style "dg_note_hint" xmaximum 1060
            hbox:
                spacing 20
                textbutton u"Отмена" style "dg_note_button" xfill False xsize 280 action Return(False)
                textbutton (u"Удалить навсегда" if permanent else u"В корзину") style "dg_note_button" xfill False xsize 340 action Return(True)
    key "K_ESCAPE" action Return(False)

screen dg_rpg_shift_trash:
    modal True
    add Solid("#0b2029")
    frame:
        background Solid("#102b33e8")
        align (.5,.5) xsize 1560 ysize 920 padding (30,26)
        vbox:
            spacing 18
            text u"Корзина смен" style "dg_note_heading" size 36
            text u"Восстанови удалённую смену или удали её данные окончательно. Другие истории и обычные слоты остаются на месте." style "dg_note_hint" xmaximum 1470
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_base_bar Solid("#243441")
                vscrollbar_thumb Solid("#65D8D0a0")
                vscrollbar_unscrollable "hide"
                xsize 1490 ysize 650 mousewheel True scrollbars "vertical"
                vbox:
                    xsize 1440 spacing 16
                    $ trash_games=__import__('dg_sessions').deleted(dg_rpg_root())
                    if not trash_games:
                        text u"Корзина пуста." style "dg_note_body"
                    for game in trash_games:
                        frame:
                            background Solid("#17352edb") padding (22,18) xsize 1430
                            vbox:
                                spacing 14
                                text dg_literal(game['name']) style "dg_note_heading" size 32 xmaximum 1380
                                text (u"День %d / %d · %s"%(game['day'],game['duration'],u'Завершена' if game['finished'] else u'В лагере')) style "dg_note_hint"
                                hbox:
                                    spacing 20
                                    textbutton u"Восстановить" style "dg_note_button" xfill False xsize 280 action Return(('restore',game['key']))
                                    textbutton u"Удалить навсегда…" style "dg_note_button" xfill False xsize 340 action Return(('purge',game['key']))
            textbutton u"Назад" style "dg_note_button" xfill False xsize 240 action Return(False)
    key "K_ESCAPE" action Return(False)

# Contrast-focused modal editor; avoids the tiny global Ren'Py input overlay.
style dg_rpg_edit_input is dg_ink_input:
    size 46
    color "#fff5d8"
    outlines []
    kerning 1

screen dg_rpg_edit_field(field, current):
    modal True
    key "rollback" action NullAction()
    key "rollforward" action NullAction()
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
                        copypaste True
                        value ScreenVariableInputValue("editor_text")
                        allow "0123456789"
                        length 9
                        xmaximum 1220
                        style "dg_rpg_edit_input"
                        default_focus True
                elif field == "days":
                    input:
                        copypaste True
                        value ScreenVariableInputValue("editor_text")
                        allow "0123456789"
                        length 3
                        xmaximum 1220
                        style "dg_rpg_edit_input"
                        default_focus True
                elif field == "name":
                    input:
                        copypaste True
                        value ScreenVariableInputValue("editor_text")
                        length 100
                        xmaximum 1220
                        style "dg_rpg_edit_input"
                        default_focus True
                else:
                    input:
                        copypaste True
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
                    text u"Предыстория влияет на реплики, навыки и варианты занятий. Например: «играю на гитаре», «умею паять», «занимаюсь спортом», «боюсь высоты». Личные знакомства и вещи она не выдаёт." style "dg_ink" size 23 xmaximum 1380
                    text (u"Распознано: "+(u", ".join(__import__('dg_hero').profile({'hero':{'background':dg_create_history}})['labels']) or u"общие интересы — уточни в описании")) style "dg_ink" size 23 xmaximum 1380
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
                    text u"ЗАСЕЛЕНИЕ" style "dg_ink_label"
                    hbox:
                        spacing 24
                        textbutton (u"Домик №%d · выбрать" % int(dg_create_cabin.split("_")[1])) style "dg_ink_act" text_size 27 action Return(("housing",))
                        textbutton (u"Сосед: " + dg_rpg.NPC_NAMES.get(dg_create_roommate,u"Жить одному")) style "dg_ink_act" text_size 27 action Return(("housing",))
                    text u"Обычное заселение: не задаёт отношения и не предрешает сюжет." style "dg_ink_small" size 21
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
            textbutton u"ЗАКРЫТЬ" style "dg_act" action Return(False)

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
            textbutton u"ОТМЕНА" style "dg_act" action Return(False)

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
        vbox:
            spacing 8
            text dg_rpg.camp_time(dg_rpg_state) style "dg_rpg_body" size 25
            if dg_rpg_state.get("housing"):
                textbutton (u"Мой домик №%d" % int(dg_rpg_state["housing"]["cabin"].split("_")[1])) style "dg_camp_nav" action Return(("go",dg_rpg_state["housing"]["cabin"]))
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
    key "rollback" action NullAction()
    key "rollforward" action NullAction()
    default place_query = u""
    add Solid("#0b2029")
    text u"Куда пойдём?" style "dg_rpg_heading" xpos 80 ypos 54
    text u"Найди место по названию. Переход не расходует время." style "dg_rpg_hint" xpos 80 ypos 116
    frame:
        background Solid("#193840") xpos 80 ypos 174 xsize 1760 ysize 84 padding (20, 16)
        input:
            copypaste True
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
    background Solid("#1d3848")
    hover_background Solid("#365363")
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
        background dg_camp_button_surface("#152b3af5", "#88b9cacc")
        hover_background dg_camp_button_surface("#365363", "#9cf8ef")
        selected_background dg_camp_button_surface("#396474", "#9cf8ef")
        selected_hover_background dg_camp_button_surface("#477b88", "#c0fff8")
        insensitive_background Solid("#071c1770")
        padding (18, 10)
        xminimum 122
        ysize 50
    style dg_camp_nav_text is dg_rpg_button_text:
        font "fonts/calibri.ttf"
        size 24
        color "#F2E4BB"
        hover_color "#65D8D0"
        insensitive_color "#869087"
        outlines []
    style dg_camp_action is dg_camp_nav:
        background dg_camp_button_surface("#285e70", "#8af2e7")
        hover_background dg_camp_button_surface("#397d8d", "#c0fff8")
        xminimum 238
    style dg_camp_action_text is dg_camp_nav_text:
        color "#fff0bc"
        hover_color "#ffffff"
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
        background dg_camp_button_surface("#203c4c", "#88b9cacc")
        hover_background dg_camp_button_surface("#365363", "#9cf8ef")
        selected_background dg_camp_button_surface("#396474", "#9cf8ef")
        insensitive_background Solid("#1c3037")
    style dg_note_button_text is dg_note_body:
        size 27
        hover_color "#ffffff"
        insensitive_color "#869087"
    style dg_note_main is dg_note_button:
        background dg_camp_button_surface("#285e70", "#8af2e7")
        hover_background dg_camp_button_surface("#397d8d", "#c0fff8")
    style dg_note_main_text is dg_note_button_text:
        color "#fff0bc"
        hover_color "#ffffff"
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
        size 24
        color "#F2E4BB"
        outlines []

transform dg_panel_appear:
    alpha 0.0
    linear .16 alpha 1.0

style dg_rpg_say_window is default:
    xanchor 0.0
    yanchor 0.0

style dg_rpg_say_name is default:
    font "fonts/calibri.ttf"
    size 24
    bold True
    color "#ffaa00"
    outlines []

style dg_rpg_say_text is default:
    font "fonts/calibri.ttf"
    size 24
    color "#F2E4BB"
    outlines []

screen dg_rpg_say(who, what):
    window:
        id "window"
        style "dg_rpg_say_window"
        xanchor 0.0 yanchor 0.0
        background dg_camp_button_surface("#101923ed","#65D8D080")
        xpos 90 ypos 905 xsize 1740 ysize 140 padding (24,18)
        fixed:
            if who:
                text who id "who" style "dg_rpg_say_name" font "fonts/calibri.ttf" size 24 bold True xpos 0 ypos 0 outlines []
            text what id "what" style "dg_rpg_say_text" font "fonts/calibri.ttf" size 24 color "#F2E4BB" outlines [] xpos 0 ypos (38 if who else 8) xmaximum 1440
            textbutton u"Закончить" style "dg_camp_nav" xminimum 172 xsize 172 xpos 1450 ypos 53 action [SetVariable("dg_rpg_interrupt",True),Function(renpy.end_interaction,True)]
            textbutton u"История" style "dg_camp_nav" xminimum 112 xsize 112 xpos 1450 ypos -8 action Show("dg_rpg_dialogue_history",overlay=True)
            textbutton u"−" style "dg_camp_nav" xminimum 48 xsize 48 xpos 1574 ypos -8 action HideInterface()

screen dg_rpg_choice(items):
    modal True
    add Solid("#10192365")
    frame:
        background dg_camp_button_surface("#101923ed","#65D8D080")
        xalign .5 ypos (865-dg_rpg_choice_height(items)-48) xsize 1120 padding (24,24)
        viewport:
            viewport_xfill True
            vscrollbar_xsize 14
            vscrollbar_unscrollable "hide"
            vscrollbar_base_bar Solid("#243441")
            vscrollbar_thumb Solid("#65D8D0a0")
            xsize 1070 ysize (dg_rpg_choice_height(items)) mousewheel True scrollbars "vertical"
            vbox:
                spacing 12 xsize 1036
                for item in items:
                    if item.action:
                        textbutton item.caption style "dg_camp_nav" xsize 1036 xminimum 0 xfill True ysize None yminimum 50 text_size 24 text_xmaximum 978 text_layout "subtitle" action item.action
                    else:
                        text item.caption size 24 color "#F2E4BB" xmaximum 1000
    key "rollback" action NullAction()

screen dg_rpg_wait(mode="chapter"):
    modal True
    default wait_state = None
    add dg_rpg_bg()
    add Solid("#101923b8")
    frame:
        background dg_camp_button_surface("#101923f5","#65D8D080")
        align (.5,.5) xsize 1160 ysize 320 padding (36,32)
        vbox:
            spacing 22 xsize 1080
            text u"Готовим сцену…" size 38 bold True color "#F2E4BB" outlines []
            text dg_literal(dg_runtime.app.status or u"Пишем продолжение истории") size 26 color "#F2E4BB" xmaximum 1080 outlines []
            text dg_elapsed() size 22 color "#A9B9C6" outlines []
            text u"Когда сцена будет готова, история продолжится." size 22 color "#A9B9C6" xmaximum 1080
    timer .2 repeat True action Function(dg_rpg_poll,mode,_update_screens=False)
    key "game_menu" action NullAction()
    key "rollback" action NullAction()

screen dg_rpg_error:
    modal True
    add dg_rpg_bg()
    add Solid("#101923b8")
    frame:
        background dg_camp_button_surface("#101923f5","#65D8D080")
        align (.5,.5) xsize 1320 padding (36,30)
        vbox:
            spacing 24
            text u"Не удалось подготовить сцену" size 34 color "#65D8D0"
            text u"Подтверждённая история сохранена. Ниже — причина остановки запроса." size 24 color "#F2E4BB" xmaximum 1240
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_unscrollable "hide"
                vscrollbar_base_bar Solid("#243441")
                vscrollbar_thumb Solid("#65D8D0a0")
                xsize 1240 ysize 280 mousewheel True scrollbars "vertical"
                text dg_literal(dg_runtime.app.error or u"Неизвестная ошибка") size 23 color "#A9B9C6" xmaximum 1190
            textbutton u"Продолжить" style "dg_camp_action" action Return(False)
    key "K_ESCAPE" action Return(False)
    key "rollback" action NullAction()

screen dg_rpg_hub(initial_show=True):
    modal True
    default selected_person = 0
    default show_interface = initial_show
    default dialogue_open = True
    default hide_hint = False
    default nav_tip = u""
    $ inhabitants = dg_rpg.at_place(dg_rpg_state)
    if dg_rpg_state.get("source") == "bkrr:mi":
        $ inhabitants = sorted(inhabitants,key=lambda item:item[0]!="mi")
    $ shift_open = not dg_rpg_state["finished"]
    $ selected_who = inhabitants[selected_person % len(inhabitants)][0] if inhabitants else None
    $ intro_here = dg_camp.intro_here(dg_rpg_state,selected_who)
    $ visible_cast = dg_stage.cast([], [item[0] for item in inhabitants], selected_who)
    on "show" action Function(dg_rpg_audio_sync,selected_who)
    on "replace" action Function(dg_rpg_audio_sync,selected_who)
    add dg_rpg_bg()
    for actor, actor_x in dg_stage.positions(visible_cast,selected_who):
        $ actor_image = dg_rpg_sprite(actor,"normal","normal")
        if actor_image is not None:
            add actor_image xpos actor_x xanchor .5 ypos 1.0 yanchor 1.0
    if show_interface:
        frame:
            background dg_camp_button_surface("#101923cc","#31445190")
            xpos 60 ypos 30 xsize 430 padding (18,12)
            vbox:
                spacing 4
                text dg_rpg.PLACE_NAMES[dg_rpg_state["place"]] style "dg_camp_narration" size 24 bold True
                text (dg_rpg.camp_time(dg_rpg_state)+u" · силы %d" % dg_rpg_state["energy"]) style "dg_rpg_hint" size 20 color "#A9B9C6"
                if __import__("dg_risk").injured(dg_rpg_state):
                    text ((u"Перенапряжение" if dg_rpg_state.get("health",{}).get("kind")=="strain" else u"Ушиб")+u" · нагрузка ограничена") size 20 color "#ffd19c"
        hbox:
            xpos 1596 ypos 30 spacing 10
            for icon, caption, command in (("map",u"Карта · M","map"),("book",u"Дневник · J","journal"),("events",u"События","controls"),("settings",u"Настройки","settings")):
                button:
                    style "dg_camp_nav" xsize 52 xminimum 52 ysize 50 padding (14,13)
                    hovered SetScreenVariable("nav_tip",caption)
                    unhovered SetScreenVariable("nav_tip",u"")
                    action Return((command,None))
                    add DgNavIcon(icon)
        if dg_presentation.unread(dg_rpg_state):
            add Solid("#65D8D0") xpos 1762 ypos 31 xsize 7 ysize 7
        if nav_tip:
            text nav_tip xpos 1585 ypos 89 size 20 color "#A9B9C6"
        if inhabitants:
            hbox:
                xpos 90 ypos 738 spacing 10
                for index, pair in enumerate(inhabitants):
                    button:
                        style "dg_camp_nav" xsize 58 xminimum 58 ysize 62 padding (3,3)
                        selected selected_who==pair[0]
                        action [SetScreenVariable("selected_person",index),Function(dg_rpg_audio_sync,pair[0])]
                        $ portrait = dg_rpg_sprite(pair[0],"normal","normal")
                        if portrait is not None:
                            add portrait xysize (50,58) fit "cover" crop (250,120,400,450)
                        else:
                            text dg_rpg.NPC_NAMES[pair[0]][:1] size 24
            frame:
                background Solid("#101923d9") xpos 90 ypos 804 padding (8,4)
                text dg_presentation.status(dg_rpg_state,selected_who) size 20 color "#D2DFE7"
        hbox:
            xalign .5 ypos 838 spacing 14
            if dg_conversation.rounds(dg_rpg_state) and shift_open:
                textbutton (u"Завершить беседу" if dg_camp.enabled(dg_rpg_state) else u"Завершить беседу · %d/%d" % (dg_conversation.rounds(dg_rpg_state),dg_conversation.EXCHANGES)) style "dg_camp_nav" action Return(("end_conversation",None))
            if shift_open and dg_rpg_state['place']=='music':
                textbutton (u"Выйти на крыльцо" if dg_rpg_state.get('music_inside',False) else u"Войти в музклуб") style "dg_camp_nav" action Return(("music_door",not dg_rpg_state.get('music_inside',False)))
            if intro_here and shift_open:
                textbutton intro_here["title"] style "dg_camp_action" action Return(("camp_do","arrival"))
            elif inhabitants and shift_open:
                if dg_rpg_state["energy"]>=8:
                    textbutton u"Темы" style "dg_camp_nav" action Return(("talk",selected_who))
                if dg_rpg_state["energy"]>=6:
                    textbutton u"Своя реплика" style "dg_camp_nav" action Return(("hybrid_npc",selected_who))
            if shift_open:
                textbutton u"Своё действие" style "dg_camp_action" action Return(("hybrid",None))
            if shift_open and dg_rpg_state["energy"]>=4:
                textbutton u"Действия" style "dg_camp_nav" action Return(("context",selected_who))
            if shift_open and dg_camp.enabled(dg_rpg_state):
                textbutton u"Распорядок" style "dg_camp_nav" action Return(("camp",None))
            if shift_open and any(row["ready"] for row in dg_projects.available(dg_rpg_state)):
                textbutton u"Общие дела" style "dg_camp_nav" action Return(("projects",None))
            if selected_who in dg_relationships.LIKES and shift_open and selected_who in dg_rpg_state["met"]:
                textbutton u"Личное" style "dg_camp_nav" action Return(("relationship",selected_who))
        if dg_visits.current(dg_rpg_state):
            textbutton (dg_rpg.NPC_NAMES[dg_visits.current(dg_rpg_state)["who"]]+u" хочет поговорить") style "dg_camp_nav" xalign .5 ypos 768 action Return(("visit",None))
        if dialogue_open:
            frame:
                at dg_panel_appear
                background dg_camp_button_surface("#101923d0","#65D8D060")
                xpos 90 ypos 905 xsize 1740 ysize 140 padding (24,18)
                fixed:
                    text (dg_rpg.NPC_NAMES[selected_who] if selected_who else u"Совёнок") style "dg_camp_name" color "#65D8D0" xpos 0 ypos 0
                    text (u"Что ты хочешь сказать?" if inhabitants else dg_camp.hint(dg_rpg_state)) style "dg_camp_narration" xpos 0 ypos 45 xmaximum 1490
                    textbutton u"История" style "dg_camp_nav" xminimum 112 xsize 112 xpos 1450 ypos -8 action Return(("history",None))
                    textbutton u"−" style "dg_camp_nav" xminimum 48 xsize 48 xpos 1574 ypos -8 action SetScreenVariable("dialogue_open",False)
        else:
            textbutton u"Показать разговор" style "dg_camp_nav" xpos 1550 ypos 982 action SetScreenVariable("dialogue_open",True)
    elif hide_hint:
        text u"H — вернуть интерфейс" xpos 70 ypos 1000 size 20 color "#A9B9C6"
        timer 2.5 action SetScreenVariable("hide_hint",False)
    key "h" action [ToggleScreenVariable("show_interface"),SetScreenVariable("hide_hint",not getattr(persistent,"dg_hide_hint_seen",False)),SetField(persistent,"dg_hide_hint_seen",True)]
    key "m" action Return(("map",None))
    key "j" action Return(("journal",None))
    key "K_ESCAPE" action Return(("controls",None))

screen dg_rpg_controls(initial_tab="story"):
    modal True
    default dg_hub_tab = initial_tab
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
        textbutton u"События" style "dg_note_tab" xsize 196 xminimum 0 text_size 24 padding (16,10) selected dg_hub_tab == "story" action SetScreenVariable("dg_hub_tab","story")
        textbutton u"Занятия" style "dg_note_tab" xsize 196 xminimum 0 text_size 24 padding (16,10) selected dg_hub_tab == "actions" action SetScreenVariable("dg_hub_tab","actions")
        textbutton u"Настройки" style "dg_note_tab" xsize 196 xminimum 0 text_size 24 padding (16,10) selected dg_hub_tab == "settings" action SetScreenVariable("dg_hub_tab","settings")
        textbutton u"Общие дела" style "dg_note_tab" xsize 196 xminimum 0 text_size 24 padding (16,10) action Return(("projects",None))
        textbutton u"Предметы" style "dg_note_tab" xsize 196 xminimum 0 text_size 24 padding (16,10) action Return(("inventory",None))
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
                    textbutton (u"Музыка сцен: вкл" if persistent.dg_rpg_music else u"Музыка сцен: выкл") style "dg_note_button" action [ToggleField(persistent,"dg_rpg_music"),Function(dg_rpg_audio_sync)]
                    textbutton (u"Атмосфера: вкл" if persistent.dg_rpg_ambience else u"Атмосфера: выкл") style "dg_note_button" action [ToggleField(persistent,"dg_rpg_ambience"),Function(dg_rpg_audio_sync)]
                    textbutton (u"Звуки действий: вкл" if persistent.dg_rpg_effects else u"Звуки действий: выкл") style "dg_note_button" action ToggleField(persistent,"dg_rpg_effects")
                    text (u"Громкость музыки и звуков — в общих настройках игры. Реплика — %d мин; обычное дело — 30 мин. У старых смен прежний режим можно сменить кнопкой ниже."%__import__('dg_pacing').dialogue_minutes(dg_rpg_state)) style "dg_note_hint" xmaximum 1008
                    textbutton u"Состояния до загрузки старых слотов" style "dg_note_button" action Return(("branches",None))
                    if not dg_camp.enabled(dg_rpg_state) and shift_open:
                        textbutton u"Включить распорядок и время в минутах для этой смены" style "dg_note_button" action Return(("camp_enable",None))
                    textbutton u"Настройки изображений" style "dg_note_button" action Return(("artist", None))
                    text u"Длительность реплики" style "dg_note_hint"
                    hbox:
                        spacing 14
                        for minutes in (3,5,8):
                            textbutton (u"%d мин"%minutes) style "dg_note_button" xfill False xsize 190 selected __import__('dg_pacing').dialogue_minutes(dg_rpg_state)==minutes action Return(("pacing",('dialogue_minutes',minutes)))
                    text u"Инициативные визиты NPC" style "dg_note_hint"
                    hbox:
                        spacing 14
                        for value,title in [('rare',u'Реже'),('normal',u'Обычно'),('often',u'Чаще')]:
                            textbutton title style "dg_note_button" xfill False xsize 190 selected dg_rpg_state.get('pacing',{}).get('visits','normal')==value action Return(("pacing",('visits',value)))
                    $ bg_state = dg_rpg_bg_status()
                    if shift_open and bg_state["status"] == "missing":
                        textbutton u"Создать фон этого места" style "dg_note_button" action Return(("background", dg_rpg_state["place"]))
                    textbutton u"Галерея CG" style "dg_note_button" action Return(("cg_gallery", None))
                    textbutton u"Каталог ресурсов БКРР / 7ДЛ" style "dg_note_button" action Return(("stock_catalog",None))
                    textbutton u"Диагностика" style "dg_note_button" action Return(("diag", None))
                    textbutton u"К выбору смены" style "dg_note_button" action Return(("exit",None))
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
                                text (u"%s · %d/100" % (dg_rpg.relationship_label(dg_rpg_state,who), dg_rpg_state["affinity"][who])) style "dg_note_hint"
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
    text u"Новый распорядок: переход 5 минут; окончание беседы не добавляет времени." style "dg_note_hint" color "#d3d3b5" xpos 882 ypos 960 xmaximum 970
    key "K_ESCAPE" action Return(("camp", None))

screen dg_rpg_hybrid_input(mode, who=None):
    modal True
    key "rollback" action NullAction()
    key "rollforward" action NullAction()
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
                if mode == "free":
                    text u"Опиши, что ты делаешь сейчас. Можно описать несколько связанных шагов. Перед подтверждением игра покажет ближайший шаг и его последствия." style "dg_note_body"
                else:
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
                            copypaste True
                            value ScreenVariableInputValue("action_text")
                            style "dg_note_input"
                            length 4000
                            xmaximum 1280
                            default_focus True
                text (u"%d / 4000 символов" % len(action_text)) style "dg_note_hint"
                text u"Текст сохранится, если вернуться назад." style "dg_note_hint"
            hbox:
                ypos 756 spacing 18
                textbutton u"Продолжить" style "dg_note_main" xsize 430 sensitive bool(action_text.strip()) action [SetVariable("dg_rpg_action_draft", action_text), Return(("submit", action_text.strip()))]
                textbutton u"Назад" style "dg_note_button" xsize 260 action [SetVariable("dg_rpg_action_draft", action_text), Return(False)]
    key "K_ESCAPE" action [SetVariable("dg_rpg_action_draft", action_text), Return(False)]

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
                    if plan.get("interpretation") and plan["interpretation"].get("status") == "ready":
                        text (u"Сейчас: " + dg_literal(plan["interpretation"]["canonical"])) style "dg_note_body"
                        for later in plan["interpretation"].get("deferred", []):
                            text (u"Потом, ещё не выполнено: " + dg_literal(later)) style "dg_note_hint"
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
            textbutton u"ВЕРНУТЬСЯ К СЦЕНЕ" style "dg_primary" action Return(False)

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
            textbutton u"ВЕРНУТЬСЯ В ЛАГЕРЬ" style "dg_primary" action Return(False)

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
            xpos 115 ypos 370 xsize 1640 ysize 590 padding (43,30)
            vbox:
                spacing 22
                text u"ИЛЛЮСТРАЦИЯ · CG" style "dg_title" size 43 color "#ffe4a6"
                text dg_literal(plan["title"]) style "dg_text" size 34 xmaximum 1520
                text u"Готовой картинки для этого эпизода пока нет. Сцену можно оставить текстовой или сгенерировать изображение отдельно." style "dg_text" size 27 xmaximum 1480
                text (u"Взрослый CG · локальный ComfyUI" if plan["kind"]=="cg18" else u"Обычный CG · широкий кадр 16:9") style "dg_small" size 24 color "#e3c691"
                hbox:
                    spacing 24
                    textbutton u"Создать CG" style "dg_camp_action" action Return("generate")
                    if plan["kind"] == "cg" and dg_rpg_cg_candidates(plan):
                        textbutton u"Проверить готовые" style "dg_camp_nav" action Return("verify")
                if dg_cg_vision_note:
                    viewport:
                        ysize 85 mousewheel True scrollbars "vertical"
                        text dg_literal(dg_cg_vision_note) style "dg_small" size 22 xmaximum 1450
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
    textbutton u"НАЗАД К ИСТОРИИ" style "dg_map_pin" xpos 1500 ypos 990 action Return(False)

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
            textbutton u"ПРОДОЛЖИТЬ" style "dg_primary" action Return(False)

screen dg_rpg_free_input:
    modal True
    key "rollback" action NullAction()
    key "rollforward" action NullAction()
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
                    copypaste True
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
                textbutton u"ОТМЕНА" style "dg_act" action Return(False)
    key "K_ESCAPE" action Return(False)

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
            textbutton u"Вернуться в лагерь" style "dg_primary" action Return(False)

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
                textbutton u"Не вмешиваться сейчас" style "dg_navlink" text_size 26 action Return(False)
    else:
        text u"Участники уже разошлись. Сегодня эта встреча закончилась." style "dg_text" xpos 360 ypos 500
        textbutton u"Закрыть" style "dg_primary" xpos 850 ypos 800 action Return(False)

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
            textbutton u"Вернуться к разговору позже" style "dg_navlink" text_size 24 action Return(False)

screen dg_rpg_contracts:
    modal True
    add Solid("#102a35")
    use dg_chrome(u"ДОЛГОСРОЧНЫЕ ПОРУЧЕНИЯ", Return(False))
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

    key "K_ESCAPE" action Return(False)

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
                textbutton u"Завершить разговор без выбора" style "dg_navlink" text_size 24 action Return(False)
            else:
                textbutton u"Закончить встречу" style "dg_primary" text_size 33 action Return("done")

screen dg_rpg_finale:
    modal True
    add Solid("#0e252f")
    use dg_chrome(u"ИТОГИ СМЕНЫ", Return(False))
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
            textbutton u"Вернуться в лагерь" style "dg_ink_act" action Return(False)

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
                textbutton u"Вернуться в лагерь (решение можно принять позже)" style "dg_navlink" text_size 24 action Return(False)
    else:
        text u"На этом месте сегодня больше нет активных событий." style "dg_text" xpos 500 ypos 500
        textbutton u"Назад" style "dg_primary" xpos 1000 ypos 800 action Return(False)

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
            textbutton u"Продолжить историю" style "dg_primary" action Return(False)

screen dg_rpg_journal(initial_view="timeline"):
    modal True
    default view = initial_view
    add Solid("#142832")
    textbutton u"Вернуться в лагерь" style "dg_note_tab" xpos 1580 ypos 105 action Return(False)
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
                        for item in dg_agents.report(dg_rpg_state)["recent_actions"][::-1]:
                            text (u"День %d · %s · %s" % (item["day"],dg_rpg.SLOTS[item["slot"]],dg_rpg.NPC_NAMES[item["who"]])) style "dg_note_hint" size 22
                            text dg_literal(item["text"]) style "dg_note_body" size 25 xmaximum 850
                        if not dg_rpg_state["social"]["rumours"] and not dg_agents.report(dg_rpg_state)["recent_actions"]:
                            text u"Пока ничего необычного. Новые слухи появляются со временем." style "dg_note_body" size 25
                        for item in dg_rpg_state["social"]["rumours"][::-1]:
                            text (u"День %d" % item["day"]) style "dg_note_hint" size 22
                            text dg_literal(dg_stage.readable(item["text"])) style "dg_note_body" size 26 xmaximum 850
                        for item in dg_rpg_state.get("npc_visits",{}).get("history",[])[-12:][::-1]:
                            text (u"День %d · %s" % (item["day"],dg_rpg.NPC_NAMES[item["who"]])) style "dg_note_hint" size 22
                            text ({"arrived":u"Сам подошёл поговорить", "expired":u"Встреча не состоялась", "accepted":u"Вы приняли приглашение", "declined":u"Вы вежливо отказались"}[item["status"]] + (u" · просьба о помощи" if item["kind"]=="help" else u" · провести время")) style "dg_note_body" size 25 xmaximum 850
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
                        if dg_rpg_state.get("npc_visits",{}).get("romance"):
                            text u"РОМАНТИЧЕСКИЕ ОТНОШЕНИЯ" style "dg_note_hint" size 25
                            for npc in dg_rpg_state["npc_visits"]["romance"]:
                                text dg_rpg.NPC_NAMES[npc] style "dg_note_body" size 24
                        text u"СОБСТВЕННЫЕ ДЕЛА ПЕРСОНАЖЕЙ" style "dg_note_hint" size 25
                        for npc, person in sorted(dg_agents.report(dg_rpg_state)["people"].items()):
                            text (dg_rpg.NPC_NAMES[npc] + u": " + person["goal"]["title"]) style "dg_note_body" size 24 xmaximum 680
                            text (u"%d/%d · " % (person["goal"]["progress"],person["goal"]["required"]) + {"working":(u"занимается делом" if person["active"] else u"в планах"),"blocked":u"нужна помощь","completed":u"завершено","abandoned":u"план изменён"}[person["goal"]["status"]]) style "dg_note_hint" size 21
                            text (dg_rpg.PLACE_NAMES.get(dg_rpg.where_is(dg_rpg_state,npc),u"Вне лагеря") + u" · силы: %d" % person["energy"]) style "dg_note_hint" size 21
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
                            text (u"%s: %d/100 · %s" % (name, dg_rpg_state["affinity"][who], dg_rpg.relationship_label(dg_rpg_state,who))) style "dg_note_body" size 25
                    null height 18
                    text u"ЗАДАНИЯ" style "dg_note_hint"
                    for key, title, progress, goal in dg_rpg.quest_progress(dg_rpg_state):
                        text (u"%s: %d/%d%s" % (title, (progress if progress <= goal else goal), goal, u" (готово)" if key in dg_rpg_state["quests_done"] else u"")) style "dg_note_body" size 24

    key "K_ESCAPE" action Return(False)

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
            textbutton u"Вернуться позже" style "dg_navlink" text_size 25 action Return(False)

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
            textbutton u"Продолжить смену" style "dg_ink_act" action Return(False)

transform dg_rpg_portrait_transform:
    zoom 0.56
    alpha 0.7

screen dg_rpg_ai_input(who):
    modal True
    key "rollback" action NullAction()
    key "rollforward" action NullAction()
    default intent = u"Хочу побеседовать и узнать персонажа получше"
    add Solid("#0a1823d9")
    frame:
        background DG_PAPER padding (60, 50)
        align (0.5, 0.5) xsize 1100
        vbox:
            spacing 22
            text (u"Особая сцена: " + dg_rpg.NPC_NAMES[who]) style "dg_ink_title"
            text u"Опишите действие или тему разговора. Только этот запрос вызовет LLM." style "dg_ink_small"
            input value ScreenVariableInputValue("intent") style "dg_ink_input" length 500 xmaximum 940 copypaste True
            hbox:
                spacing 35
                textbutton u"Сгенерировать" style "dg_ink_act" sensitive bool(intent.strip()) action Return(intent.strip())
                textbutton u"Отмена" style "dg_ink_act" action Return("")

screen dg_rpg_read_scene(scene_text):
    modal True
    add Solid("#091827")
    use dg_chrome(u"ОСОБАЯ СЦЕНА", Return(False))
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
    $ dg_rpg_interrupt = False
    $ save_name = u"DON-GEN · "+dg_rpg.camp_time(dg_rpg_state)+u" · "+dg_rpg.PLACE_NAMES[dg_rpg_state["place"]]
    $ dg_rpg_stage_active = True
    $ dg_rpg_audio_sync(who)
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
        if dg_rpg_interrupt:
            $ dg_rpg_stage_active = False
            return "__interrupted__"
        $ dg_rpg_vn_line_index += 1
    $ dg_rpg_stage_active = False
    return

label dg_rpg_vn_scene(scene_text, cg_possible=True, who=None, scene_identity=None):
    if scene_identity is not None:
        call dg_rpg_narrate("result",who,scene_identity,scene_text) from dg_return_dg_rpg_narrate_1
        $ scene_text = _return
        if scene_text is None:
            return None
    # The optional CG must depict the actual visible narrative, not the
    # shorter scripted fallback that was replaced by the narrator.
    $ store.dg_rpg_last_narrated_text = scene_text
    call dg_rpg_vn_text(scene_text, who) from dg_return_dg_rpg_vn_text_1
    if _return == "__interrupted__":
        return None
    if cg_possible:
        $ dg_scene_next=renpy.display_menu([(u"Вернуться к сцене лагеря","back"),(u"Иллюстрация сцены","cg")],screen="dg_rpg_choice")
        return "cg" if dg_scene_next=="cg" else None
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
            call dg_connect from dg_return_dg_connect_1
            if not dg_runtime.app.client.authenticated():
                return None
        $ dg_rpg_run("chapter",dg_rpg_auto_generate,kind,who,identity,source_text,choices)
        if not dg_runtime.app.error:
            $ dg_rpg_apply("remember_narrative",(dg_narrative_key,dg_runtime.app.result))
            return dg_runtime.app.result
        call screen dg_rpg_error
        menu (screen="dg_rpg_choice"):
            "Повторить генерацию сцены":
                pass
            "Вернуться в лагерь":
                return None

label dg_rpg_vn_choice(story_text, choice_pairs, who=None, scene_identity=None):
    if scene_identity is not None:
        call dg_rpg_narrate("world" if who is not None else "encounter", who, scene_identity, story_text, choice_pairs) from dg_return_dg_rpg_narrate_2
        $ story_text = _return
        if story_text is None:
            return None
    call dg_rpg_vn_text(story_text, who) from dg_return_dg_rpg_vn_text_2
    if _return == "__interrupted__":
        return None
    $ dg_rpg_vn_selected = renpy.display_menu([(dg_literal(caption), key) for key, caption in choice_pairs],screen="dg_rpg_choice")
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
    call dg_rpg_narrate("npc_"+phase,who,dg_npc_situation_id,dg_rpg_vn_dlg["text"],dg_rpg_vn_dlg.get("options")) from dg_return_dg_rpg_narrate_3
    $ dg_rpg_vn_narrated = _return
    if dg_rpg_vn_narrated is None:
        return None
    call dg_rpg_vn_text(dg_rpg_vn_narrated, who) from dg_return_dg_rpg_vn_text_3
    if _return == "__interrupted__":
        return None
    if phase == "result":
        return
    $ dg_rpg_vn_options = [(dg_literal(caption), key) for key, caption in dg_rpg_vn_dlg["options"]]
    $ dg_rpg_vn_options.append((u"Написать свою реплику · AI", "custom"))
    $ dg_rpg_vn_options.append((u"Завершить разговор", "__cancel__"))
    $ dg_rpg_vn_selected = renpy.display_menu(dg_rpg_vn_options,screen="dg_rpg_choice")
    if dg_rpg_vn_selected == "__cancel__":
        return None
    return dg_rpg_vn_selected

label dg_rpg_resume_loaded:
    $ renpy.set_return_stack([])
    jump dg_rpg_loop

label dg_rpg_main:
    $ dg_setup()
    $ dg_rpg_active = True
    # The old DG place screen paints a gate image on the screens layer,
    # covering Ren'Py master-layer backgrounds and actor sprites.
    $ renpy.hide_screen("dg_scene")
label dg_rpg_picker_label:
    $ dg_rpg_audio_stop()
    $ renpy.block_rollback()
    call screen dg_rpg_picker
    $ renpy.block_rollback()
    $ dg_rpg_cmd, dg_rpg_value = dg_presentation.command(_return)
    if dg_rpg_cmd not in ("delete_shift","trash","back","new","load"):
        $ dg_rpg_active=False
        jump dg_menu
    if dg_rpg_cmd == "delete_shift":
        $ dg_shift_delete_info=next((r for r in dg_rpg.list_games(dg_rpg_root()) if r['id']==dg_rpg_value),None)
        if dg_shift_delete_info is None:
            $ renpy.notify(u'Смена больше не найдена. Список обновлён.')
            jump dg_rpg_picker_label
        call screen dg_rpg_shift_confirm(dg_shift_delete_info['name'],False)
        if _return:
            $ dg_rpg_manage_shift('trash',dg_rpg_value)
        jump dg_rpg_picker_label
    if dg_rpg_cmd == "trash":
        call screen dg_rpg_shift_trash
        if _return:
            $ dg_shift_trash_action,dg_shift_trash_key=dg_presentation.command(_return)
            if dg_shift_trash_action == "restore":
                $ dg_rpg_manage_shift('restore',dg_shift_trash_key)
            elif dg_shift_trash_action == "purge":
                $ dg_shift_purge_info=next((r for r in __import__('dg_sessions').deleted(dg_rpg_root()) if r['key']==dg_shift_trash_key),None)
                if dg_shift_purge_info is None:
                    jump dg_rpg_picker_label
                call screen dg_rpg_shift_confirm(dg_shift_purge_info['name'],True)
                if _return:
                    $ dg_rpg_manage_shift('purge',dg_shift_trash_key)
        jump dg_rpg_picker_label
    if dg_rpg_cmd == "back":
        $ dg_rpg_active = False
        jump dg_menu
    if dg_rpg_cmd == "new":
        $ dg_create_name = u"Семён"
        $ dg_create_age = u"18"
        $ dg_create_days = u"14"
        $ dg_create_history = u"Новичок в лагере"
        $ dg_create_source = "bkrr:mi"
        $ dg_create_pronouns = u"он/его"
        $ dg_create_adult = False
        $ dg_create_cabin = "cabin_01"
        $ dg_create_roommate = "mt"
        jump dg_rpg_create_loop
    $ dg_rpg_open(dg_rpg_value)
    jump dg_rpg_loop

label dg_rpg_create_loop:
    call screen dg_rpg_setup
    $ dg_create_cmd = dg_presentation.creation_command(_return)
    if not dg_create_cmd or dg_create_cmd[0] == "cancel":
        jump dg_rpg_picker_label
    if dg_create_cmd[0] == "housing":
        call screen dg_rpg_housing_picker
        jump dg_rpg_create_loop
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
        $ dg_edit_result = dg_presentation.command(_return,"cancel")
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
        $ dg_rpg_start(dg_create_name.strip(), dg_create_age, dg_create_days, dg_create_history.strip(), dg_create_source, dg_create_pronouns, dg_create_adult, dg_create_cabin, dg_create_roommate)
        jump dg_rpg_loop
    jump dg_rpg_create_loop

label dg_rpg_loop:
    $ dg_rpg_active = True
    $ save_name = u"DON-GEN · "+dg_rpg.camp_time(dg_rpg_state)+u" · "+dg_rpg.PLACE_NAMES[dg_rpg_state["place"]]
    if dg_rpg_interrupt:
        $ dg_rpg_interrupt = False
        $ dg_rpg_apply("end_conversation")
    # Abandoned/failed narration leaves the durable save untouched.
    if dg_rpg_pending_turn is not None:
        $ dg_rpg_pending_turn = None
        $ dg_rpg_open(dg_rpg_state["id"])
    $ dg_rpg_stage_active = False
    $ dg_rpg_scene_context = dg_stage.freeze(dg_rpg_state)
    if dg_camp.enabled(dg_rpg_state) and dg_rpg_state['camp_life']['arrival']==0 and dg_rpg_state['place']=='gate' and dg_rpg_state['id'] not in dg_rpg_intro_attempted:
        $ dg_rpg_intro_attempted.append(dg_rpg_state['id'])
        $ dg_rpg_intro_attempted = dg_rpg_intro_attempted[-40:]
        $ dg_rpg_apply("camp","arrival")
        call dg_rpg_vn_scene(dg_rpg_last_camp["text"],False,"sl","camp:"+dg_hybrid.fingerprint(dg_rpg_state)) from dg_return_auto_arrival
        jump dg_rpg_loop
    $ dg_active_visit = dg_visits.current(dg_rpg_state)
    if dg_active_visit and not dg_active_visit["seen"]:
        jump dg_rpg_visit_label
    call screen dg_rpg_hub
    $ dg_rpg_cmd, dg_rpg_value = dg_presentation.command(_return,"noop")
    if dg_rpg_cmd in ("controls","settings"):
        $ dg_initial_tab="settings" if dg_rpg_cmd=="settings" else "story"
        $ dg_rpg_apply("events_seen")
        call screen dg_rpg_controls(dg_initial_tab)
        $ dg_rpg_cmd, dg_rpg_value = dg_presentation.command(_return,"noop")
label dg_rpg_dispatch:
    if dg_rpg_cmd == "music_door":
        $ dg_rpg_apply("music_door",dg_rpg_value)
        jump dg_rpg_loop
    if dg_rpg_cmd == "pacing":
        $ dg_rpg_state.setdefault('pacing',{})[dg_rpg_value[0]]=dg_rpg_value[1]
        $ dg_rpg.save(dg_rpg_root(),dg_rpg_state)
        jump dg_rpg_loop
    if dg_rpg_cmd == "stock_catalog":
        call screen dg_rpg_stock_catalog
        jump dg_rpg_loop
    if dg_rpg_cmd == "deeds":
        call screen dg_rpg_deeds(dg_rpg_value)
        if not _return:
            jump dg_rpg_loop
        $ dg_rpg_cmd,dg_rpg_value=dg_presentation.command(_return,"noop")
        jump dg_rpg_dispatch
    if dg_rpg_cmd == "camp_enable":
        $ dg_rpg_apply("camp_enable")
        jump dg_rpg_loop
    if dg_rpg_cmd == "card_table":
        jump dg_rpg_card_table_label
    if dg_rpg_cmd == "branches":
        call screen dg_rpg_branches
        if _return:
            $ dg_rpg_state=__import__('dg_checkpoints').recover(dg_rpg_root(),dg_rpg_state['id'],_return)
            $ dg_rpg_pending_turn=None
        jump dg_rpg_loop
    if dg_rpg_cmd == "camp_do":
        $ dg_rpg_apply("camp",dg_rpg_value)
        call dg_rpg_vn_scene(dg_rpg_last_camp["text"],dg_rpg_value.startswith(("event:","clue:")),dg_rpg_last_camp["who"],"camp:"+dg_hybrid.fingerprint(dg_rpg_state)) from dg_return_arrival_action
        if _return=="cg":
            $ dg_cg_plan=dg_rpg_cg_for("personal",dg_rpg_last_camp['title'],dg_rpg_last_narrated_text,dg_rpg_last_camp['who'])
            jump dg_rpg_cg_label
        jump dg_rpg_loop
    if dg_rpg_cmd == "camp":
        jump dg_rpg_camp_label
    if dg_rpg_cmd == "context":
        $ dg_context_who = dg_rpg_value
        call screen dg_rpg_context(dg_context_who)
        if not _return:
            jump dg_rpg_loop
        $ dg_rpg_cmd,dg_rpg_value=dg_presentation.command(_return,"noop")
        jump dg_rpg_dispatch
    if dg_rpg_cmd == "affection":
        $ dg_rpg_apply("affection",dg_rpg_value)
        call dg_rpg_vn_scene(dg_rpg_last_affection["text"],dg_rpg_last_affection['consent'],dg_rpg_last_affection["who"],"affection:"+dg_hybrid.fingerprint(dg_rpg_state)) from dg_return_dg_rpg_vn_scene_1
        if _return=="cg":
            $ dg_cg_plan=dg_rpg_cg_for("personal",dg_rpg_last_affection['title'],dg_rpg_last_narrated_text,dg_rpg_last_affection['who'])
            jump dg_rpg_cg_label
        jump dg_rpg_loop
    if dg_rpg_cmd == "end_conversation":
        $ dg_rpg_apply("end_conversation")
        jump dg_rpg_loop
    if dg_rpg_cmd == "history":
        call screen dg_rpg_dialogue_history
        jump dg_rpg_loop
    if dg_rpg_cmd == "projects":
        jump dg_rpg_projects_label
    if dg_rpg_cmd == "inventory":
        call screen dg_rpg_inventory
        $ dg_item_action=dg_inventory.command(_return)
        if dg_item_action is not None:
            $ dg_rpg_apply("inventory",dg_item_action)
            call dg_rpg_vn_scene(dg_rpg_last_inventory["text"],True,dg_rpg_last_inventory["who"],"inventory:"+dg_hybrid.fingerprint(dg_rpg_state)) from dg_return_dg_rpg_vn_scene_2
        jump dg_rpg_loop
    if dg_rpg_cmd == "relationship":
        $ dg_relation_who=dg_rpg_value
        call screen dg_rpg_relationship(dg_relation_who)
        if _return:
            $ dg_relation_action,dg_relation_key=_return
            $ dg_rpg_apply("relation",(dg_relation_who,dg_relation_action,dg_relation_key))
            call dg_rpg_vn_scene(dg_rpg_last_relation,False,dg_relation_who,"relation:"+dg_hybrid.fingerprint(dg_rpg_state)) from dg_return_dg_rpg_vn_scene_3
        jump dg_rpg_loop
    if dg_rpg_cmd == "exit":
        jump dg_rpg_picker_label
    if dg_rpg_cmd == "visit":
        jump dg_rpg_visit_label
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
        call dg_connect from dg_return_dg_connect_2
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
        call dg_rpg_vn_scene(dg_rpg_spontaneous["text"],False,dg_rpg_focus,dg_rpg_spontaneous["id"]) from dg_return_dg_rpg_vn_scene_4
        menu (screen="dg_rpg_choice"):
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
            call dg_rpg_vn_choice(dg_incident_current["text"], dg_rpg_incident_choices, None, "incident:%d" % dg_rpg_state["day"]) from dg_return_dg_rpg_vn_choice_1
            if _return:
                $ dg_rpg_incident_choice = _return
                $ dg_rpg_apply("incident", dg_rpg_incident_choice)
                $ dg_rpg_incident_result = {"title":dg_rpg_last_incident["title"],"text":dg_rpg_last_incident["text"]}
                call dg_rpg_vn_scene(dg_rpg_incident_result["text"], True, None, "incident_outcome:%d:%s" % (dg_rpg_state["day"],dg_rpg_incident_choice)) from dg_return_dg_rpg_vn_scene_5
                if _return == "cg":
                    $ dg_cg_plan = dg_rpg_cg_for("incident", dg_rpg_incident_result["title"], dg_rpg_last_narrated_text, None)
                    jump dg_rpg_cg_label
        jump dg_rpg_loop
    if dg_rpg_cmd == "personal":
        $ dg_rpg_focus = dg_rpg_value
        if dg_social.personal_scene(dg_rpg_state, dg_rpg_focus) and dg_rpg_state["energy"] >= 12:
            $ dg_personal_current = dg_social.personal_scene(dg_rpg_state,dg_rpg_focus)
            $ dg_personal_choices = list(dg_personal_current["choices"]) + [("__cancel__", u"Вернуться позже")]
            call dg_rpg_vn_choice(dg_personal_current["text"], dg_personal_choices, dg_rpg_focus, "personal:%s:%d" % (dg_rpg_focus,dg_personal_current["stage"])) from dg_return_dg_rpg_vn_choice_2
            if _return:
                $ dg_rpg_personal_stance = _return
                $ dg_rpg_apply("personal", (dg_rpg_focus, dg_rpg_personal_stance))
                $ dg_rpg_personal_result = {"title": dg_rpg_last_personal["title"], "text": dg_rpg_last_personal["text"]}
                call dg_rpg_vn_scene(dg_rpg_personal_result["text"], True, dg_rpg_focus, "personal_result:%s:%s:%d" % (dg_rpg_focus,dg_rpg_personal_stance,dg_rpg_state["day"])) from dg_return_dg_rpg_vn_scene_6
                if _return == "cg":
                    $ dg_cg_plan = dg_rpg_cg_for("personal", dg_rpg_personal_result["title"], dg_rpg_last_narrated_text, dg_rpg_focus)
                    jump dg_rpg_cg_label
        jump dg_rpg_loop
    if dg_rpg_cmd == "talk":
        $ dg_rpg_focus = dg_rpg_value
        if dg_rpg_state["energy"] < 8:
            jump dg_rpg_loop
        call dg_rpg_vn_dialogue(dg_rpg_focus, "topics") from dg_return_dg_rpg_vn_dialogue_1
        if _return == "custom":
            $ dg_rpg_hybrid_mode = "npc"
            $ dg_rpg_hybrid_who = dg_rpg_focus
            $ dg_rpg_hybrid_topic = None
            jump dg_rpg_hybrid_entry
        if _return is None:
            jump dg_rpg_loop
        $ dg_rpg_talk_topic = int(_return)
        call dg_rpg_vn_dialogue(dg_rpg_focus, "choice", dg_rpg_talk_topic) from dg_return_dg_rpg_vn_dialogue_2
        if _return == "custom":
            $ dg_rpg_hybrid_mode = "npc"
            $ dg_rpg_hybrid_who = dg_rpg_focus
            $ dg_rpg_hybrid_topic = dg_rpg_talk_topic
            jump dg_rpg_hybrid_entry
        if _return is None:
            jump dg_rpg_loop
        $ dg_rpg_talk_stance = _return
        $ dg_rpg_apply("conversation", (dg_rpg_focus, dg_rpg_talk_topic, dg_rpg_talk_stance))
        call dg_rpg_vn_dialogue(dg_rpg_focus, "result", dg_rpg_talk_topic, dg_rpg_talk_stance) from dg_return_dg_rpg_vn_dialogue_3
        jump dg_rpg_loop
    if dg_rpg_cmd == "route":
        if dg_rpg_state["energy"] < 12:
            jump dg_rpg_loop
        $ dg_rpg_focus = dg_rpg_value
        $ dg_rpg_route_level = dg_rpg.available_route_events(dg_rpg_state, dg_rpg_focus)[0][0]
        $ dg_route_intro = dg_dialogue.route_intro(dg_rpg_state, dg_rpg_focus, dg_rpg_route_level)
        $ dg_route_choices = list(dg_route_intro["options"]) + [("__cancel__", u"Вернуться позже")]
        call dg_rpg_vn_choice(dg_route_intro["text"], dg_route_choices, dg_rpg_focus, "route:%s:%d" % (dg_rpg_focus,dg_rpg_route_level)) from dg_return_dg_rpg_vn_choice_3
        if _return:
            $ dg_rpg_route_stance = _return
            $ dg_rpg_apply("route", (dg_rpg_focus, dg_rpg_route_stance))
            call dg_rpg_vn_scene(dg_dialogue.route_conclusion(dg_rpg_focus, dg_rpg_route_level, dg_rpg_route_stance), False, dg_rpg_focus, "route_result:%s:%d:%s" % (dg_rpg_focus,dg_rpg_route_level,dg_rpg_route_stance)) from dg_return_dg_rpg_vn_scene_7
        jump dg_rpg_loop
    if dg_rpg_cmd == "ai":
        if not dg_runtime.app.client.authenticated():
            call dg_connect from dg_return_dg_connect_3
            if not dg_runtime.app.client.authenticated():
                jump dg_rpg_loop
        $ dg_rpg_focus = dg_rpg_value
        call screen dg_rpg_ai_input(dg_rpg_focus)
        if not _return:
            jump dg_rpg_loop
        $ dg_rpg_intent = _return
        $ dg_rpg_run("chapter", dg_rpg_scene_generate, dg_rpg_focus, dg_rpg_intent)
        if dg_runtime.app.error:
            call screen dg_rpg_error
        else:
            $ dg_rpg_open(dg_rpg_state["id"])
            call dg_rpg_vn_scene(dg_runtime.app.result, True, dg_rpg_focus) from dg_return_dg_rpg_vn_scene_8
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
                call dg_connect from dg_return_dg_connect_4
                if not dg_runtime.app.client.authenticated():
                    jump dg_rpg_loop
        $ dg_rpg_run("chapter", dg_rpg_art_generate, "background", dg_rpg_value)
        if dg_runtime.app.error:
            call screen dg_rpg_error
        jump dg_rpg_loop
    jump dg_rpg_loop

label dg_rpg_world_label:
    if dg_rpg_state["finished"]:
        jump dg_rpg_loop
    if dg_rpg_state["energy"] < 8:
        call dg_rpg_vn_text(u"Сейчас не хватает сил вмешаться в это событие. Отдохни, а потом возвращайся.") from dg_return_dg_rpg_vn_text_4
        jump dg_rpg_loop
    if not dg_world.event_at(dg_rpg_state, dg_rpg_state["place"]):
        jump dg_rpg_loop
    $ dg_world_active = dg_world.event_at(dg_rpg_state, dg_rpg_state["place"])
    $ dg_world_choices = [(choice["key"], choice["text"]) for choice in dg_world_active["choices"]]
    $ dg_world_choices.append(("custom", u"Написать своё действие · AI"))
    $ dg_world_choices.append(("__cancel__", u"Вернуться в лагерь"))
    call dg_rpg_vn_choice(dg_world_active["story"], dg_world_choices, dg_world_active["npc"], dg_world_active["id"]) from dg_return_dg_rpg_vn_choice_4
    if _return == "custom":
        $ dg_rpg_hybrid_mode = "world"
        $ dg_rpg_hybrid_who = None
        $ dg_rpg_hybrid_topic = None
        jump dg_rpg_hybrid_entry
    if _return:
        $ dg_rpg_world_stance = _return
        $ dg_rpg_apply("world", dg_rpg_world_stance)
        call dg_rpg_vn_scene(dg_rpg_last_world["text"], True, dg_world_active["npc"], "outcome:"+dg_world_active["id"]+":"+dg_rpg_world_stance) from dg_return_dg_rpg_vn_scene_9
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
    $ dg_rpg_interpretation = None
    if dg_intent.needs_ai(dg_rpg_hybrid_action_text, dg_rpg_hybrid_mode):
        if not dg_runtime.app.client.authenticated():
            call dg_connect from dg_return_dg_connect_5
            if not dg_runtime.app.client.authenticated():
                jump dg_rpg_hybrid_entry
        $ dg_rpg_run("chapter", dg_rpg_interpret_action, dg_rpg_hybrid_action_text, dg_rpg_hybrid_mode, dg_rpg_hybrid_who)
        if dg_runtime.app.error:
            call screen dg_rpg_error
            jump dg_rpg_hybrid_entry
        $ dg_rpg_interpretation = dg_runtime.app.result
    $ dg_rpg_hybrid_preview(dg_rpg_hybrid_mode, dg_rpg_hybrid_action_text, dg_rpg_hybrid_who, dg_rpg_hybrid_topic, dg_rpg_interpretation)
    jump dg_rpg_hybrid_review_label

label dg_rpg_hybrid_review_label:
    if not isinstance(dg_rpg_hybrid_plan, dg_rpg.DICT_TYPE):
        jump dg_rpg_hybrid_entry
    call screen dg_rpg_hybrid_review(dg_rpg_hybrid_plan)
    if _return == "retry":
        $ dg_rpg_action_draft = dg_rpg_hybrid_plan.get("action", dg_rpg_action_draft)
        jump dg_rpg_hybrid_entry
    if _return == "cancel" or not _return:
        jump dg_rpg_loop
    if _return == "local":
        $ dg_rpg_apply("hybrid", (dg_rpg_hybrid_plan, None))
        call dg_rpg_vn_scene(dg_rpg_hybrid_entry["scene"] or dg_rpg_hybrid_entry["result"]) from dg_return_dg_rpg_vn_scene_10
        if _return == "cg":
            $ dg_cg_who = dg_rpg_hybrid_plan.get("who") or dg_rpg_hybrid_plan["result"].get("npc") or dg_rpg_hybrid_plan["result"].get("target")
            $ dg_cg_plan = dg_rpg_cg_for("hybrid", u"Мой поступок", dg_rpg_hybrid_entry["scene"] or dg_rpg_hybrid_entry["result"], dg_cg_who, dg_rpg_hybrid_entry["action"])
            jump dg_rpg_cg_label
        jump dg_rpg_loop
    if _return == "ai":
        if not dg_runtime.app.client.authenticated():
            call dg_connect from dg_return_dg_connect_6
            if not dg_runtime.app.client.authenticated():
                jump dg_rpg_hybrid_review_label
        $ dg_rpg_run("chapter", dg_rpg_hybrid_generate, dg_rpg_hybrid_plan)
        if dg_runtime.app.error:
            call screen dg_rpg_error
            jump dg_rpg_hybrid_review_label
        $ dg_rpg_hybrid_scene = dg_runtime.app.result
        $ dg_rpg_apply("hybrid", (dg_rpg_hybrid_plan, dg_rpg_hybrid_scene))
        $ dg_rpg_action_draft = u""
        if dg_rpg_hybrid_plan.get("mode")=="npc":
            call dg_rpg_vn_text(dg_rpg_hybrid_entry["scene"] or dg_rpg_hybrid_entry["result"],dg_rpg_hybrid_plan.get("who")) from dg_return_hybrid_conversation_text
            if _return=="__interrupted__":
                jump dg_rpg_loop
            $ dg_continue_conversation=renpy.display_menu([(u"Продолжить беседу своей репликой","continue"),(u"Вернуться к сцене лагеря","back"),(u"Иллюстрация сцены","cg")],screen="dg_rpg_choice")
            if dg_continue_conversation=="continue":
                $ dg_rpg_action_draft=u""
                jump dg_rpg_hybrid_entry
            if dg_continue_conversation=="cg":
                $ dg_cg_plan=dg_rpg_cg_for("hybrid",u"Беседа",dg_rpg_hybrid_entry["scene"],dg_rpg_hybrid_plan.get("who"),dg_rpg_hybrid_entry["action"])
                jump dg_rpg_cg_label
            jump dg_rpg_loop
        else:
            call dg_rpg_vn_scene(dg_rpg_hybrid_entry["scene"] or dg_rpg_hybrid_entry["result"]) from dg_return_dg_rpg_vn_scene_11
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
    if dg_cg_vision_attempted != dg_cg_plan["key"]:
        $ dg_cg_vision_attempted = dg_cg_plan["key"]
        $ dg_cg_vision_note = u""
        if dg_cg_plan["kind"] == "cg" and dg_rpg_cg_status(dg_cg_plan)["status"] == "missing" and dg_rpg_cg_candidates(dg_cg_plan) and dg_runtime.app.client.authenticated():
            $ dg_rpg_run("chapter", dg_rpg_verify_cg, dg_art.freeze_scene_request(dg_cg_plan))
            $ dg_cg_vision_note = (u"Не удалось проверить картинки: " + dg_runtime.app.error) if dg_runtime.app.error else (u"" if dg_rpg_cg_builtin(dg_cg_plan) else dg_runtime.app.result)
    if dg_rpg_cg_status(dg_cg_plan)["status"] in ("generated","builtin"):
        $ dg_rpg_apply("cg_record",dg_cg_plan)
    call screen dg_rpg_cg_art(dg_cg_plan)
    if _return == "verify":
        if not dg_runtime.app.client.authenticated():
            call dg_connect from dg_return_dg_connect_7
        if dg_runtime.app.client.authenticated():
            $ dg_rpg_run("chapter", dg_rpg_verify_cg, dg_art.freeze_scene_request(dg_cg_plan))
            $ dg_cg_vision_note = (u"Не удалось проверить картинки: " + dg_runtime.app.error) if dg_runtime.app.error else (u"" if dg_rpg_cg_builtin(dg_cg_plan) else dg_runtime.app.result)
        jump dg_rpg_cg_label
    if _return == "generate":
        if not dg_art.marker(dg_rpg_state,dg_cg_plan):
            jump dg_rpg_loop
        if dg_cg_plan["kind"] == "cg18" and getattr(persistent,"dg_rpg_art_provider","cloud") != "comfy":
            call screen dg_rpg_artist_settings
            jump dg_rpg_cg_label
        if getattr(persistent,"dg_rpg_art_provider","cloud") != "comfy":
            if not dg_runtime.app.client.authenticated():
                call dg_connect from dg_return_dg_connect_8
                if not dg_runtime.app.client.authenticated():
                    jump dg_rpg_cg_label
        $ dg_cg_payload = dg_art.freeze_scene_request(dg_cg_plan)
        $ dg_rpg_run("chapter", dg_rpg_art_generate, dg_cg_plan["kind"], dg_cg_payload)
        if dg_runtime.app.error:
            $ dg_cg_failed_text = dg_runtime.app.error
            $ logging.getLogger("don_gen").error("CG generation failure: %s",dg_cg_failed_text)
            call screen dg_rpg_art_error(dg_cg_failed_text)
        else:
            $ dg_rpg_apply("cg_record",dg_cg_plan)
        jump dg_rpg_cg_label
    jump dg_rpg_loop



screen dg_rpg_housing_picker:
    modal True
    add Solid("#102831f5")
    frame:
        background Solid("#17352ef2")
        xpos 160 ypos 85 xsize 1600 ysize 920 padding (40,30)
        vbox:
            spacing 20
            text u"Твой домик и сосед" style "dg_note_heading"
            text u"Домик №13 занят Леной и Мику. Если выберешь Мику соседкой, вы будете жить в другом домике." style "dg_note_body" size 26 xmaximum 1500
            text u"ДОМИК" style "dg_note_hint"
            grid 8 4:
                spacing 10
                for cabin in dg_housing.CABINS:
                    textbutton (u"№%d" % int(cabin.split("_")[1])) style "dg_camp_nav" xsize 160 ysize 48 selected dg_create_cabin==cabin sensitive cabin in dg_housing.AVAILABLE_CABINS action SetVariable("dg_create_cabin",cabin)
                null
            text u"СОСЕД" style "dg_note_hint"
            grid 3 4:
                spacing 10
                for roommate in (None,)+dg_housing.ROOMMATES:
                    textbutton dg_rpg.NPC_NAMES.get(roommate,u"Жить одному") style "dg_camp_nav" xsize 460 ysize 48 selected dg_create_roommate==roommate action SetVariable("dg_create_roommate",roommate)
                null
            hbox:
                spacing 20
                textbutton u"Случайное заселение" style "dg_camp_nav" action Function(dg_random_housing)
                textbutton u"Готово" style "dg_camp_action" action Return(False)
    key "K_ESCAPE" action Return(False)


label dg_rpg_visit_label:
    $ dg_active_visit = dg_visits.current(dg_rpg_state)
    if not dg_active_visit:
        jump dg_rpg_loop
    $ dg_rpg_apply("visit_seen")
    $ dg_visit_choices = dg_visits.choices(dg_rpg_state,dg_active_visit)
    if dg_rpg_state["energy"] < 8:
        $ dg_visit_choices = [row for row in dg_visit_choices if row[0] in ("later","decline")]
    call dg_rpg_vn_choice(dg_visits.opening(dg_rpg_state,dg_active_visit),dg_visit_choices,dg_active_visit["who"],"visit_offer:"+dg_active_visit["id"]) from dg_return_dg_rpg_vn_choice_5
    if not _return:
        jump dg_rpg_loop
    $ dg_visit_reply = _return
    if dg_visit_reply in ("later","decline"):
        $ dg_rpg_apply("visit_reply",dg_visit_reply)
        jump dg_rpg_loop
    $ dg_rpg_apply("visit",dg_visit_reply)
    call dg_rpg_vn_scene(dg_rpg_last_visit["text"],True,dg_active_visit["who"],"visit_result:"+dg_active_visit["id"]+":"+dg_visit_reply) from dg_return_dg_rpg_vn_scene_12
    if _return == "cg":
        $ dg_cg_plan = dg_rpg_cg_for("personal",dg_rpg_last_visit["title"],dg_rpg_last_narrated_text,dg_active_visit["who"])
        jump dg_rpg_cg_label
    jump dg_rpg_loop


screen dg_rpg_projects:
    modal True
    add Solid("#101923f5")
    frame:
        background dg_camp_button_surface("#101923ee","#65D8D060")
        xpos 90 ypos 55 xsize 1740 ysize 960 padding (30,24)
        fixed:
            text u"Общие дела" size 34 color "#65D8D0"
            hbox:
                xpos 850 ypos 0 spacing 16
                textbutton u"Предложить новое дело" style "dg_camp_action" action Return(("propose",None))
                textbutton u"Предметы" style "dg_camp_nav" action Return(("inventory",None))
                textbutton u"Назад" style "dg_camp_nav" action Return(False)
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_base_bar Solid("#243441")
                vscrollbar_thumb Solid("#65D8D0a0")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                xpos 0 ypos 82 xsize 1660 ysize 820 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 18
                    text u"Материал должен существовать. Каждый этап выполняется отдельно; NPC тоже вносят свой вклад." size 24 color "#A9B9C6" xmaximum 1600
                    for row in dg_projects.available(dg_rpg_state):
                        frame:
                            background Solid("#243441ee") xsize 1600 padding (22,18)
                            vbox:
                                spacing 12
                                text (dg_projects.definitions(dg_rpg_state)[row["project"]]["title"]+u" · этап %d/4" % (row["stage"]+1)) size 28 color "#F2E4BB"
                                text row["caption"] size 24 color "#F2E4BB" xmaximum 1520
                                text (dg_rpg.PLACE_NAMES[row["place"]]+u" · вкладов %d/%d" % (row["progress"],row["required"])) size 22 color "#A9B9C6"
                                hbox:
                                    spacing 18
                                    if row["ready"] and dg_rpg_state["energy"]>=8:
                                        textbutton (u"Выполнить · 8 сил, 30 минут" if dg_camp.enabled(dg_rpg_state) else u"Выполнить · 8 сил, один период") style "dg_camp_action" action Return(("act",row["project"]))
                                    elif dg_rpg_state["place"]!=row["place"]:
                                        textbutton u"К месту дела" style "dg_camp_nav" action Return(("travel",row["place"]))
                                    else:
                                        text u"Нужны материалы, участник, силы или чужой вклад." size 22 color "#A9B9C6" xmaximum 1040
                                    textbutton u"Отменить дело" style "dg_camp_nav" action Return(("cancel",row["project"]))
                    text u"Закрытые дела" size 24 color "#65D8D0"
                    for key, record in sorted(dg_rpg_state.get("projects",{}).get("records",{}).items()):
                        if record["stage"]==4 or record.get("cancelled"):
                            text (dg_projects.definitions(dg_rpg_state)[key]["title"]+(u" · отменено" if record.get("cancelled") else u" · завершено")) size 23 color "#A9B9C6"

screen dg_rpg_relationship(who):
    modal True
    add Solid("#101923f5")
    $ relation=dg_rpg_state.get("relationships",{}).get("people",{}).get(who,{})
    frame:
        background dg_camp_button_surface("#101923ee","#65D8D060")
        xpos 180 ypos 75 xsize 1560 ysize 930 padding (34,26)
        fixed:
            text (dg_rpg.NPC_NAMES[who]+u" · личное") size 34 color "#65D8D0"
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_base_bar Solid("#243441")
                vscrollbar_thumb Solid("#65D8D0a0")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                xpos 0 ypos 65 xsize 1492 ysize 715 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 17
                    text (u"Близкие занятия: "+u", ".join(dg_relationships.ACTIVITY_NAMES[kind] for kind in dg_relationships.PREFERENCES[who]["activities"])) size 24 color "#F2E4BB"
                    text (u"Доверие: %d · напряжение: %d" % (relation.get("trust",0),relation.get("tension",0))) size 22 color "#A9B9C6"
                    textbutton (u"Приглашения: "+(u"разрешены" if relation.get("invitations",True) else u"пауза")) style "dg_camp_nav" action Return(("invitations",None))
                    textbutton (u"Визиты в мой домик: "+(u"разрешены" if relation.get("home_visits",True) else u"только по отдельному приглашению")) style "dg_camp_nav" action Return(("home_visits",None))
                    for row in dg_rpg_state.get("relationships",{}).get("promises",[]):
                        if row["who"]==who:
                            text (dg_projects.definitions(dg_rpg_state)[row["project"]]["title"]+u" · до дня %d · "%row["deadline"]+{"open":u"обещано","fulfilled":u"выполнено","broken":u"срок нарушен","cancelled":u"отменено"}[row["status"]]) size 22 color "#A9B9C6" xmaximum 1430
                    for key in sorted(dg_projects.definitions(dg_rpg_state)):
                        if dg_projects.step(dg_rpg_state,key)[1] and not any(row["who"]==who and row["project"]==key and row["status"]=="open" for row in dg_rpg_state.get("relationships",{}).get("promises",[])):
                            textbutton (u"Обещать личный вклад: "+dg_projects.definitions(dg_rpg_state)[key]["title"]) style "dg_camp_nav" action Return(("promise",key))
                    if relation.get("tension",0)>0 and relation.get("last_apology")!=dg_rpg_state["day"] and dg_rpg_state["energy"]>=6:
                        textbutton (u"Извиниться и выслушать · 6 сил, 10 минут" if dg_camp.enabled(dg_rpg_state) else u"Извиниться и выслушать · 6 сил, один период") style "dg_camp_action" action Return(("apologize",None))
                    if who in dg_rpg_state.get("npc_visits",{}).get("romance",[]):
                        textbutton u"Завершить романтические отношения" style "dg_camp_nav" action Return(("end_romance",None))
            textbutton u"Назад" style "dg_camp_nav" xpos 0 ypos 812 action Return(False)
    key "K_ESCAPE" action Return(False)

screen dg_rpg_dialogue_history(overlay=False):
    modal True
    add Solid("#101923f5")
    frame:
        background dg_camp_button_surface("#101923ee","#65D8D060")
        xpos 90 ypos 55 xsize 1740 ysize 960 padding (30,24)
        vbox:
            spacing 20
            text u"История диалога" size 34 color "#65D8D0"
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_base_bar Solid("#243441")
                vscrollbar_thumb Solid("#65D8D0a0")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                xsize 1660 ysize 760 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 14
                    for row in dg_presentation.history_display(dg_rpg_state):
                        text (u"День %d · "%row["day"]+dg_rpg.SLOTS[row["slot"]]+u" · "+(dg_rpg.NPC_NAMES.get(row["who"],dg_rpg_state["hero"]["name"] if row["who"]=="hero" else u"Повествование"))) size 21 color "#65D8D0"
                        text dg_literal(row["text"]) size 24 color "#F2E4BB" xmaximum 1580
                    if not dg_presentation.history(dg_rpg_state):
                        text u"Здесь появятся прочитанные сцены и свободные разговоры." size 24 color "#A9B9C6"
            textbutton u"Назад" style "dg_camp_nav" action (Hide("dg_rpg_dialogue_history") if overlay else Return(False))
    key "K_ESCAPE" action (Hide("dg_rpg_dialogue_history") if overlay else Return(False))


screen dg_rpg_inventory:
    modal True
    add Solid("#101923f5")
    frame:
        background dg_camp_button_surface("#101923ee","#65D8D060")
        xpos 90 ypos 55 xsize 1740 ysize 960 padding (30,24)
        vbox:
            spacing 18
            text (u"Предметы · "+dg_rpg.PLACE_NAMES[dg_rpg_state["place"]]) size 34 color "#65D8D0"
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_base_bar Solid("#243441")
                vscrollbar_thumb Solid("#65D8D0a0")
                vscrollbar_unscrollable "hide"
                side_spacing 12
                xsize 1660 ysize 760 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 14
                    text u"При себе" size 26 color "#65D8D0"
                    $ player_bag=dg_rpg_state.get("projects",{}).get("inventory",{})
                    text (u", ".join(dg_inventory.CATALOG[item]["title"]+u" ×%d"%n for item,n in sorted(player_bag.items()) if n) or u"Пока пусто.") size 24 color "#F2E4BB" xmaximum 1600
                    text u"Запас в этом месте" size 26 color "#65D8D0"
                    text (u", ".join(dg_inventory.CATALOG[item]["title"]+u" ×%d"%n for item,n in sorted(dg_inventory.stock_at(dg_rpg_state,dg_rpg_state["place"]).items()) if n) or u"Нет доступного запаса.") size 24 color "#F2E4BB" xmaximum 1600
                    text u"Материалы для плаката: бумага и краски; нужен карандаш. Для заплаты: ткань и изолента; нужен набор инструментов. Работа — в клубах." size 22 color "#A9B9C6" xmaximum 1600
                    for loan in dg_rpg_state.get("inventory_world",{}).get("loans",[]):
                        if loan["status"]=="open":
                            text (dg_rpg.NPC_NAMES[loan["holder"]]+u" держит "+dg_inventory.CATALOG[loan["item"]]["title"]+u" · срок до дня %d"%loan["deadline"]) size 23 color "#A9B9C6"
                    text u"Доступные действия" size 26 color "#65D8D0"
                    for operation,item,who,caption in dg_inventory.actions(dg_rpg_state):
                        textbutton caption style "dg_camp_nav" action Return((operation,item,who))
            textbutton u"Назад" style "dg_camp_nav" action Return(False)
    key "K_ESCAPE" action Return(False)

screen dg_rpg_project_request:
    modal True
    key "rollback" action NullAction()
    key "rollforward" action NullAction()
    default idea=dg_project_draft
    add Solid("#101923f5")
    frame:
        background dg_camp_button_surface("#101923ee","#65D8D060")
        xpos 180 ypos 190 xsize 1560 ysize 690 padding (34,30)
        vbox:
            spacing 28
            text u"Какое дело ты хочешь организовать?" size 34 color "#65D8D0"
            text u"ИИ предложит тему и участников. Материалы, места и этапы проверит движок; проект появится только после твоего выбора." size 24 color "#A9B9C6" xmaximum 1460
            frame:
                background Solid("#243441") padding (20,18) xsize 1460 ysize 180
                input value ScreenVariableInputValue("idea") length 500 color "#F2E4BB" size 24 xmaximum 1390 copypaste True
            hbox:
                spacing 20
                textbutton u"Предложить вариант" style "dg_camp_action" sensitive bool(idea.strip()) action Return(idea.strip())
                textbutton u"Назад" style "dg_camp_nav" action [SetVariable("dg_project_draft",idea),Return(False)]
    key "K_ESCAPE" action [SetVariable("dg_project_draft",idea),Return(False)]

screen dg_rpg_project_review(proposal):
    modal True
    $ value=proposal["blueprint"]
    $ material=dg_inventory.CATALOG[value["item"]]
    add Solid("#101923f5")
    frame:
        background dg_camp_button_surface("#101923ee","#65D8D060")
        xpos 180 ypos 150 xsize 1560 ysize 780 padding (34,30)
        vbox:
            spacing 25
            text value["title"] size 34 color "#65D8D0" xmaximum 1460
            text (u"Материал: "+material["title"]+u" · источник: "+dg_rpg.PLACE_NAMES[material["source"]]) size 26 color "#F2E4BB"
            text (u"Участники: "+u", ".join(dg_rpg.NPC_NAMES[who] for who in value["participants"])) size 24 color "#F2E4BB" xmaximum 1460
            text (u"Получить материал → доставить "+dg_rpg.NPC_NAMES[value["recipient"]]+u" → общая подготовка → завершение") size 24 color "#A9B9C6" xmaximum 1460
            text (dg_rpg.PLACE_NAMES[value["work_place"]]+u" → "+dg_rpg.PLACE_NAMES[value["final_place"]]) size 24 color "#A9B9C6"
            text u"Это план, а не уже выполненные действия. Предметы и результаты не выдаются одним предложением." size 24 color "#A9B9C6" xmaximum 1460
            hbox:
                spacing 20
                textbutton u"Начать общее дело" style "dg_camp_action" action Return("start")
                textbutton u"Изменить идею" style "dg_camp_nav" action Return("retry")
                textbutton u"Отмена" style "dg_camp_nav" action Return(False)
    key "K_ESCAPE" action Return(False)

label dg_rpg_projects_label:
    call screen dg_rpg_projects
    if not _return:
        jump dg_rpg_loop
    $ dg_project_command,dg_project_key=_return
    if dg_project_command=="inventory":
        $ dg_rpg_cmd="inventory"
        call screen dg_rpg_inventory
        $ dg_item_action=dg_inventory.command(_return)
        if dg_item_action is not None:
            $ dg_rpg_apply("inventory",dg_item_action)
            call dg_rpg_vn_scene(dg_rpg_last_inventory["text"],True,dg_rpg_last_inventory["who"],"inventory:"+dg_hybrid.fingerprint(dg_rpg_state)) from dg_return_dg_rpg_vn_scene_13
        jump dg_rpg_loop
    if dg_project_command=="propose":
        jump dg_rpg_project_propose_label
    if dg_project_command=="travel":
        $ dg_rpg_apply("move",dg_project_key)
        jump dg_rpg_loop
    if dg_project_command=="cancel":
        menu (screen="dg_rpg_choice"):
            "Отменить это общее дело и связанные обещания?":
                $ dg_rpg_apply("project_cancel",dg_project_key)
            "Продолжить дело":
                pass
        jump dg_rpg_projects_label
    $ dg_rpg_apply("project",dg_project_key)
    call dg_rpg_vn_scene(dg_rpg_last_project["text"],True,dg_rpg_last_project["who"],"project:"+dg_project_key+":"+dg_hybrid.fingerprint(dg_rpg_state)) from dg_return_dg_rpg_vn_scene_14
    jump dg_rpg_loop

label dg_rpg_project_propose_label:
    call screen dg_rpg_project_request
    if not _return:
        jump dg_rpg_projects_label
    $ dg_project_draft=_return
    if not dg_runtime.app.client.authenticated():
        call dg_connect from dg_return_dg_connect_9
        if not dg_runtime.app.client.authenticated():
            jump dg_rpg_projects_label
    $ dg_rpg_run("chapter",dg_rpg_propose_project,dg_project_draft)
    if dg_runtime.app.error:
        call screen dg_rpg_error
        jump dg_rpg_project_propose_label
    $ dg_project_proposal=dg_runtime.app.result
    call screen dg_rpg_project_review(dg_project_proposal)
    if _return=="retry":
        jump dg_rpg_project_propose_label
    if _return=="start":
        if dg_hybrid.fingerprint(dg_rpg.load(dg_rpg_root(),dg_rpg_state["id"]))!=dg_project_proposal["before"]:
            jump dg_rpg_project_propose_label
        $ dg_rpg_apply("project_register",dg_project_proposal["blueprint"])
    jump dg_rpg_projects_label

screen dg_rpg_context(who=None):
    modal True
    add dg_rpg_bg()
    add Solid("#101923b8")
    frame:
        background dg_camp_button_surface("#101923f5","#65D8D080")
        align (.5,.5) xsize 1150 ysize 700 padding (30,26)
        vbox:
            spacing 18
            text (u"Действия · "+(dg_rpg.NPC_NAMES[who] if who else u"лагерь")) size 32 color "#65D8D0"
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_unscrollable "hide"
                vscrollbar_base_bar Solid("#243441")
                vscrollbar_thumb Solid("#65D8D0a0")
                xsize 1080 ysize 510 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 14 xsize 1040
                    if dg_rpg_state.get('card_table',{}).get('phase') in ('playing','round_done') and dg_rpg_state['card_table']['day']==dg_rpg_state['day']:
                        textbutton u"Вернуться к карточному столу" style "dg_camp_action" action Return(("card_table",None))
                    textbutton u"Своё действие" style "dg_camp_action" action Return(("hybrid",None))
                    if who:
                        if dg_rpg_state['place']=='music' and dg_rpg_state.get('camp_life',{}).get('club') is None:
                            text u"Вход в здание свободный. Запись в кружок — отдельное действие после обходного листа второго дня: пять отметок, затем «Выбрать: Музыкальный кружок» в распорядке." size 22 color "#A9B9C6" xmaximum 1000
                        for row in dg_camp.cards(dg_rpg_state):
                            if row['who']==who and row['ready'] and row['key'].startswith(('risk:','clue:','cards:')):
                                textbutton row['title'] style "dg_camp_nav" action Return(("camp_do",row['key']))
                        textbutton u"Своя реплика" style "dg_camp_nav" action Return(("hybrid_npc",who))
                        for kind,caption in dg_affection.options(dg_rpg_state,who):
                            textbutton caption style "dg_camp_nav" action Return(("affection",(who,kind)))
                        text u"Близкие жесты открываются по знакомству и доверию. Каждое предложение требует отдельного согласия; занятость и усталость могут привести к отказу." size 23 color "#A9B9C6" xmaximum 1000
                    if dg_camp.enabled(dg_rpg_state):
                        textbutton u"Дела на месте" style "dg_camp_nav" action Return(("deeds",("objects",None)))
                        textbutton u"Договорённости и встречи" style "dg_camp_nav" action Return(("deeds",("commitments",who)))
                        textbutton u"Совместные события с продолжением" style "dg_camp_nav" action Return(("deeds",("crew",None)))
                        textbutton u"Распорядок, обходной лист и поручения" style "dg_camp_nav" action Return(("camp",None))
                    textbutton u"Предметы" style "dg_camp_nav" action Return(("inventory",None))
                    if dg_projects.available(dg_rpg_state):
                        textbutton u"Общие дела" style "dg_camp_nav" action Return(("projects",None))
            textbutton u"Назад" style "dg_camp_nav" action Return(False)
    key "K_ESCAPE" action Return(False)

screen dg_rpg_camp:
    modal True
    add dg_rpg_bg()
    add Solid("#101923b8")
    frame:
        background dg_camp_button_surface("#101923f5","#65D8D080")
        xpos 90 ypos 55 xsize 1740 ysize 960 padding (30,26)
        vbox:
            spacing 18
            text (u"Лагерный день · "+dg_rpg.camp_time(dg_rpg_state)+u" · "+__import__("dg_schedule").WEEK[__import__("dg_schedule").weekday(dg_rpg_state)]) size 32 color "#65D8D0"
            text (dg_world.weather(dg_rpg_state)[1]+u" · "+(u"После травмы: отдых и спокойные занятия" if __import__("dg_risk").injured(dg_rpg_state) else u"Самочувствие: обычное")) size 22 color "#A9B9C6"
            if __import__('dg_cards').public(dg_rpg_state):
                textbutton u"Открыть карточный стол" style "dg_camp_action" action Return(("table",None))
                $ card_view=__import__('dg_cards').public(dg_rpg_state)
                text (u"Стол «21»: твои карты "+u", ".join(str(v) for v in card_view['hero'])+u" · соперник: "+u", ".join(str(v) for v in card_view['dealer'])) size 22 color "#65D8D0"
            text (u"Сегодня: "+(u" · ".join(row['title']+u" %02d:%02d"%(row['start']//60,row['start']%60) for row in __import__('dg_schedule').events(dg_rpg_state)) or u"свободный день по распорядку")) size 22 color "#F2E4BB" xmaximum 1630
            text ((u"Реплика — %d мин; переход — 5 минут; длительность дел указана ниже."%__import__('dg_pacing').dialogue_minutes(dg_rpg_state))+(u" Кружок выбираешь после обхода лагеря." if not dg_rpg_state["camp_life"]["club"] else u"")) size 24 color "#F2E4BB" xmaximum 1640
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_unscrollable "hide"
                vscrollbar_base_bar Solid("#243441")
                vscrollbar_thumb Solid("#65D8D0a0")
                xsize 1660 ysize 480 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 16 xsize 1620
                    for row in [r for r in dg_camp.cards(dg_rpg_state) if not r['key'].startswith(('object:','commit:','crew:'))]:
                        frame:
                            background Solid("#1c3040e8") padding (20,16) xsize 1610
                            vbox:
                                spacing 10
                                text (row["title"]+(u"" if dg_rpg.PLACE_NAMES[row["place"]] in row["title"] else u" · "+dg_rpg.PLACE_NAMES[row["place"]])+u" · %d мин"%row["minutes"]) size 25 color "#F2E4BB" xmaximum 1560
                                if row["ready"]:
                                    textbutton u"Выполнить" style "dg_camp_action" action Return(("do",row["key"]))
                                elif row["place"]!=dg_rpg_state["place"]:
                                    textbutton u"Отправиться к месту" style "dg_camp_nav" action Return(("go",row["place"]))
                                else:
                                    text u"Дождись ответственного или вернись в подходящее время." size 22 color "#A9B9C6"
            textbutton u"Назад" style "dg_camp_nav" action Return(False)
    key "K_ESCAPE" action Return(False)

label dg_rpg_camp_label:
    call screen dg_rpg_camp
    if not _return:
        jump dg_rpg_loop
    $ dg_camp_cmd,dg_camp_value=_return
    if dg_camp_cmd=="table":
        jump dg_rpg_card_table_label
    if dg_camp_cmd=="go":
        $ dg_rpg_apply("move",dg_camp_value)
        jump dg_rpg_camp_label
    if dg_camp_cmd=="do":
        $ dg_rpg_apply("camp",dg_camp_value)
        call dg_rpg_vn_scene(dg_rpg_last_camp["text"],dg_camp_value.startswith(("event:","clue:")),dg_rpg_last_camp["who"],"camp:"+dg_hybrid.fingerprint(dg_rpg_state)) from dg_return_camp_result
        if _return=="cg":
            $ dg_cg_plan=dg_rpg_cg_for("personal",dg_rpg_last_camp['title'],dg_rpg_last_narrated_text,dg_rpg_last_camp['who'])
            jump dg_rpg_cg_label
    jump dg_rpg_loop


screen dg_rpg_deeds(selection):
    modal True
    default deeds_tab = selection[0]
    $ deeds_who=selection[1]
    add dg_rpg_bg()
    add Solid("#101923c8")
    frame:
        background dg_camp_button_surface("#101923f5","#65D8D080")
        align (.5,.5) xsize 1600 ysize 920 padding (30,26)
        vbox:
            spacing 16
            text (u"Дела и договорённости · "+dg_rpg.PLACE_NAMES[dg_rpg_state['place']]) size 32 color "#65D8D0"
            hbox:
                spacing 18
                textbutton u"Дела на месте" style "dg_camp_nav" action SetScreenVariable("deeds_tab","objects")
                textbutton u"Договорённости" style "dg_camp_nav" action SetScreenVariable("deeds_tab","commitments")
                textbutton u"Общие события" style "dg_camp_nav" action SetScreenVariable("deeds_tab","crew")
            text (u"Нужны время, силы и реальные инструменты. Недоступные действия объясняют причину." if deeds_tab=="objects" else u"Участники готовятся вечером в 18:15–18:55; их обязательные дела сохраняют приоритет." if deeds_tab=="crew" else u"Слова не выполняют работу. Встреча требует реального прихода; об отмене можно предупредить заранее.") size 23 color "#A9B9C6" xmaximum 1500
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_base_bar Solid("#243441")
                vscrollbar_thumb Solid("#65D8D0a0")
                vscrollbar_unscrollable "hide"
                xsize 1530 ysize 630 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 14 xsize 1480
                    if deeds_tab=="objects":
                        $ deed_rows=__import__('dg_actions').available(dg_rpg_state,True)
                        if not deed_rows:
                            text u"Здесь пока нет размеченных объектов. Свой поступок можно описать с основного экрана." size 24 color "#F2E4BB" xmaximum 1420
                        for row in deed_rows:
                            frame:
                                background Solid("#1c3040e8") padding (18,14) xsize 1460
                                vbox:
                                    spacing 10
                                    text (row['title']+u" · %d мин · %d сил"%(row['minutes'],row['cost'])) size 25 color "#F2E4BB"
                                    if row['ready']:
                                        textbutton u"Выполнить" style "dg_camp_action" action Return(("camp_do","object:"+row['key']))
                                    else:
                                        text row['reason'] size 23 color "#A9B9C6" xmaximum 1400
                    elif deeds_tab=="crew":
                        for event in __import__('dg_ensemble').report(dg_rpg_state)['events'][::-1]:
                            text (__import__('dg_ensemble').SPECS[event['kind']]['title']+u" · день %d"%(event['due']//1440+1)) size 25 color "#65D8D0"
                            text ({'plan':u'Обсуждение плана','rehearsal':u'Репетиция','scout':u'Проверка маршрута','research':u'Подготовка материалов','technical':u'Проверка оборудования','ready':u'Подготовлено','feedback':u'Можно обсудить результат','closed':u'История завершена','missed':u'Подготовку не удалось закончить'}[event['phase']]) size 23 color "#A9B9C6"
                        $ crew_rows=__import__('dg_ensemble').cards(dg_rpg_state)
                        if not crew_rows:
                            text u"Познакомься с координатором и закончи обход лагеря. Новое дело можно начать при наличии времени до конца смены." size 24 color "#F2E4BB" xmaximum 1400
                        for row in crew_rows:
                            frame:
                                background Solid("#1c3040e8") padding (18,14) xsize 1460
                                vbox:
                                    spacing 10
                                    text (row['title']+u" · "+dg_rpg.PLACE_NAMES[row['place']]) size 25 color "#F2E4BB" xmaximum 1400
                                    if row['ready']:
                                        textbutton u"Участвовать" style "dg_camp_action" action Return(("camp_do",row['key']))
                                    else:
                                        text (row.get('reason') or u'Подойди к координатору или дождись сбора участников.') size 23 color "#A9B9C6" xmaximum 1400
                                        textbutton u"Открыть карту" style "dg_camp_nav" action Return(("map",None))
                    else:
                        for record in [r for r in __import__('dg_commitments').report(dg_rpg_state)['records'][::-1] if deeds_who is None or r['who']==deeds_who]:
                            frame:
                                background Solid("#1c3040e8") padding (18,14) xsize 1460
                                vbox:
                                    spacing 8
                                    text (record['title']+u" · "+dg_rpg.NPC_NAMES[record['who']]) size 25 color "#F2E4BB"
                                    text (u"День %d · %02d:%02d · "%(record['due']//1440+1,(record['due']%1440)//60,record['due']%60)+dg_rpg.PLACE_NAMES[record['place']]+u" · "+{'open':u'договорились','performed':u'дело сделано, нужен личный отчёт','fulfilled':u'подтверждено','cancelled':u'отменено заранее','missed':u'не выполнено','excused':u'собеседник не смог прийти'}[record['status']]) size 22 color "#A9B9C6" xmaximum 1400
                        $ commitment_rows=[r for r in __import__('dg_commitments').options(dg_rpg_state) if r['ready'] and (deeds_who is None or r['who']==deeds_who)]
                        if not commitment_rows:
                            text u"Подойди к знакомому персонажу, чтобы договориться о деле или встрече. Личные встречи открываются после развития дружбы." size 24 color "#F2E4BB" xmaximum 1420
                        for row in commitment_rows:
                            textbutton row['title'] style "dg_camp_nav" text_xmaximum 1380 action Return(("camp_do","commit:"+row['key']))
            textbutton u"Назад" style "dg_camp_nav" action Return(False)
    key "K_ESCAPE" action Return(False)

screen dg_rpg_stock_catalog:
    modal True
    default stock_kind = 'cg'
    default stock_source = None
    default stock_page = 0
    $ stock_data=__import__('dg_catalog').load()
    $ stock_stats=__import__('dg_catalog').summary(stock_data)
    $ stock_visual=__import__('dg_catalog').visual().get('images',{})
    $ stock_rows=[r for r in stock_data.get('assets',[]) if r['kind']==stock_kind and (stock_source is None or r['source']==stock_source)]
    add dg_rpg_bg()
    add Solid("#101923ed")
    frame:
        background Solid("#101923")
        align (.5,.5) xsize 1660 ysize 960 padding (30,26)
        vbox:
            spacing 14
            text u"Каталог ресурсов · БКРР / 7ДЛ" size 32 color "#65D8D0"
            text (u"CG: %d · BG: %d · Спрайты: %d · Групп дубликатов: %d"%(stock_stats['counts']['cg'],stock_stats['counts']['bg'],stock_stats['counts']['sprite'],stock_stats['duplicate_groups'])) size 24 color "#F2E4BB"
            text (u"CG обработано: %d · визуально классифицировано ИИ: %d · накладки и ограниченные файлы исключены"%(stock_stats['cg_reviewed'],stock_stats['cg_ai_reviewed'])) size 22 color "#65D8D0" xmaximum 1550
            text u"Это учёт файлов установленных источников. Метаданные и ссылки сценария не заменяют визуальную проверку CG. Изображения сюда не копируются." size 22 color "#A9B9C6" xmaximum 1550
            hbox:
                spacing 14
                for code,title in [('cg','CG'),('bg','Фоны'),('sprite','Спрайты')]:
                    textbutton title style "dg_camp_nav" action [SetScreenVariable('stock_kind',code),SetScreenVariable('stock_page',0)]
                for code,title in [(None,'Все'),('451835368','БКРР'),('3266357374','7ДЛ')]:
                    textbutton title style "dg_camp_nav" action [SetScreenVariable('stock_source',code),SetScreenVariable('stock_page',0)]
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_base_bar Solid("#243441")
                vscrollbar_thumb Solid("#65D8D0a0")
                vscrollbar_unscrollable "hide"
                xsize 1580 ysize 520 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 12 xsize 1520
                    for row in stock_rows[stock_page*40:(stock_page+1)*40]:
                        $ stock_review=stock_visual.get(row['sha256'],{})
                        $ stock_cast=stock_review.get('actors',row['actors'])
                        frame:
                            background Solid("#1c3040e8") padding (16,12) xsize 1500
                            vbox:
                                spacing 6
                                text (('БКРР' if row['source']=='451835368' else '7ДЛ')+u' · '+row['name']) size 24 color "#F2E4BB"
                                text (u"Участники: "+(', '.join(dg_rpg.NPC_NAMES.get(w,{'hero':u'герой','unknown':u'неопознанный персонаж'}.get(w,w)) for w in stock_cast) or u'не определены')+u" · "+(u'файл не читается' if row.get('readable') is False else u'есть ограничения' if row.get('restrictions') else u'нужна проверка сцены')) size 21 color "#A9B9C6" xmaximum 1420
                                text row['relative'] size 18 color "#A9B9C6" xmaximum 1420
            hbox:
                spacing 20
                textbutton u"Предыдущие" style "dg_camp_nav" sensitive stock_page>0 action SetScreenVariable('stock_page',stock_page-1)
                text (u"%d–%d из %d"%((stock_page*40+1 if stock_rows else 0),((stock_page+1)*40 if (stock_page+1)*40<len(stock_rows) else len(stock_rows)),len(stock_rows))) size 23 color "#F2E4BB" yalign .5
                textbutton u"Следующие" style "dg_camp_nav" sensitive (stock_page+1)*40<len(stock_rows) action SetScreenVariable('stock_page',stock_page+1)
            textbutton u"Назад" style "dg_camp_nav" action Return(False)
    key "K_ESCAPE" action Return(False)

screen dg_rpg_branches:
    modal True
    add dg_rpg_bg()
    add Solid("#101923e8")
    frame:
        align (.5,.5) xsize 1400 ysize 800 padding (30,30) background Solid("#101923")
        vbox:
            spacing 18
            text u"Состояния до восстановления слотов" size 32 color "#65D8D0"
            text u"При загрузке старого слота прежнее состояние сохраняется здесь. Выбор возобновляет эту ветку целиком." size 24 color "#F2E4BB" xmaximum 1300
            viewport:
                viewport_xfill True
                vscrollbar_xsize 14
                vscrollbar_unscrollable "hide"
                side_spacing 12
                xsize 1320 ysize 580 mousewheel True scrollbars "vertical"
                vbox:
                    spacing 12 xsize 1280
                    if not __import__('dg_checkpoints').branches(dg_rpg_root(),dg_rpg_state['id']):
                        text u"Архив появится после восстановления более раннего слота." size 24 color "#A9B9C6"
                    for row in __import__('dg_checkpoints').branches(dg_rpg_root(),dg_rpg_state['id']):
                        textbutton (u"День %d · "%row['day']+dg_rpg.SLOTS[row['slot']]+u" · %02d:%02d"%(row['minute']//60,row['minute']%60)+u" · "+dg_rpg.PLACE_NAMES[row['place']]+u" · силы %d"%row['energy']) style "dg_camp_nav" action Return(row['key'])
            textbutton u"Назад" style "dg_camp_nav" action Return(False)
    key "K_ESCAPE" action Return(False)


screen dg_rpg_card_table:
    modal True
    $ table=__import__('dg_cards').public(dg_rpg_state)
    add dg_rpg_bg()
    add Solid("#101923a8")
    frame:
        align (.5,.5) xsize 1400 ysize 870 padding (36,28) background dg_camp_button_surface("#101923f5","#65D8D080")
        vbox:
            spacing 16
            text (u"Турнир Электроника · раунд %d/3"%table['round']) size 34 color "#65D8D0"
            text u"Цель — набрать ближе к 21 без перебора. Туз — 11 или 1. Соперник добирает до 17. Равные суммы — ничья; ставок нет." size 24 color "#F2E4BB" xmaximum 1300
            text (u"Счёт раундов: %d : %d"%(table['wins'],table['losses'])) size 25 color "#A9B9C6"
            for caption,values in ((u"Электроник",table['dealer']+([None] if table['phase']=='playing' else [])),(u"Твои карты · %d очков"%table['hero_total'],table['hero'])):
                text caption size 26 color "#F2E4BB"
                hbox:
                    spacing 12
                    for value in values:
                        frame:
                            xsize 82 ysize 118 padding (0,0)
                            background dg_camp_button_surface("#f2e4bb" if value is not None else "#285e70","#65D8D0")
                            text (u"Т" if value==11 else str(value) if value is not None else u"?") align (.5,.5) size 38 color ("#101923" if value is not None else "#F2E4BB")
            if table['last_result']:
                text (u"Последний раунд: "+table['last_result']) size 25 color "#F2E4BB"
            hbox:
                spacing 18
                for row in __import__('dg_cards').cards(dg_rpg_state):
                    if row['ready']:
                        textbutton ({'cards:hit':u'Взять карту','cards:stand':u'Остановиться','cards:next':u'Следующий раунд','cards:leave':u'Закончить турнир'}.get(row['key'],row['title'])) style "dg_camp_action" action Return(row['key'])
            textbutton u"Вернуться в лагерь, партию пока оставить" style "dg_camp_nav" action Return(False)
    key "K_ESCAPE" action Return(False)

label dg_rpg_card_table_label:
    call screen dg_rpg_card_table
    if not _return:
        jump dg_rpg_loop
    $ dg_card_key=_return
    $ dg_rpg_apply('camp',dg_card_key)
    if dg_rpg_state['card_table']['phase']=='finished':
        call dg_rpg_vn_scene(dg_rpg_last_camp['text'],False,'el','cards:'+dg_hybrid.fingerprint(dg_rpg_state)) from dg_return_card_finale
        jump dg_rpg_loop
    $ dg_card_text=u'[narrator] '+dg_rpg_last_camp['text']+u' '+__import__('dg_cards').public(dg_rpg_state)['rules']
    $ dg_rpg_state=dg_turn.finish(dg_rpg_root(),dg_rpg_pending_turn,dg_hybrid.fingerprint(dg_rpg_pending_turn['state']),dg_card_text)
    $ dg_rpg_pending_turn=None
    jump dg_rpg_card_table_label
