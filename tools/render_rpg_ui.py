# -*- coding: utf-8 -*-
"""Render RPG screens in RenPy 7 without opening a window or using game saves.

Usage: python tools/render_rpg_ui.py --sdk PATH_TO_RENPY_7_SDK
Outputs use placeholders for vanilla backgrounds/sprites and for authentication.
The render exercises actual RPG screen code, not an HTML recreation.
"""
import argparse
import ast
from pathlib import Path
import os
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--engine-root", type=Path, help="Use the installed game RenPy runtime for compatibility checks")
    parser.add_argument("--out", type=Path, default=Path("work/ui-smoke"))
    parser.add_argument("--assets", type=Path, help="Private gen_assets root or maps directory")
    parser.add_argument("--workshop", type=Path, help="Installed 7DL Complete Edition Workshop root")
    parser.add_argument("--vanilla", type=Path, help="Vanilla game directory containing archive.rpa, for the scene preview")
    parser.add_argument("--screen", choices=("hub", "controls", "setup", "input", "review", "map", "places", "cabins", "journal", "picker", "scene", "staging", "cg", "agendas", "cg-check", "intent-review", "housing", "emotions", "visit", "projects", "relationship", "history", "hidden", "inventory", "project-review", "editor", "party", "error", "dialogue", "dialogue-choice", "waiting", "arrival", "camp-day", "context", "flow", "calendar", "injury", "disco", "native-save", "card-table", "investigation", "branches"))
    # Additional production screens are accepted below by extending the existing action.
    parser._option_string_actions['--screen'].choices += ('deeds','commitments','stock-catalog','crew','pacing','shift-trash','shift-confirm','shift-purge','shift-flow','menu-audio','hybrid-flow','music-entry')
    parser.add_argument("--place", default="cabins", help="Actual RPG location for the preview")
    parser.add_argument("--slot", type=int, choices=range(4), default=0, help="0 morning, 1 day, 2 evening, 3 night")
    parser.add_argument("--source", default="vanilla", choices=("vanilla", "bkrr:mi", "7dl:mi_7dl", "7dl:mi_dj", "7dl:mi_cl"))
    parser.add_argument("--focus", choices=("mi", "dv", "un", "sl"), help="Preview at this character's actual current location")
    args = parser.parse_args()
    sdk = args.sdk.resolve()
    runner = sdk / "lib/py2-windows-x86_64/python.exe"
    if not runner.is_file():
        parser.error("Expected a Windows RenPy 7 SDK with lib/py2-windows-x86_64/python.exe")
    root = Path(__file__).resolve().parents[1] / "don_gen"
    output = args.out.resolve()
    game = output / "game"
    modules = game / "mods/don_gen"
    images = modules / "images"
    images.mkdir(parents=True, exist_ok=True)
    for source in root.glob("*.py"):
        shutil.copyfile(source, modules / source.name)
    if (root / 'stock_catalog.json').is_file():
        shutil.copyfile(root / 'stock_catalog.json', modules / 'stock_catalog.json')
    if (root / 'stock_visual.json').is_file():
        shutil.copyfile(root / 'stock_visual.json', modules / 'stock_visual.json')
    shutil.copyfile(root / "dg_rpg.rpy", game / "dg_rpg.rpy")
    for source in (root / "images").glob("*.png"):
        shutil.copyfile(source, images / source.name)
    assets = args.assets or root / "images/gen_assets"
    if args.assets and (assets / "maps").is_dir():
        assets = assets / "maps"
    if assets.is_dir():
        target = images / "gen_assets"
        target.mkdir(exist_ok=True)
        for name in ("map_bg.jpg", "map_avaliable.jpg", "map_selected.jpg"):
            if (assets / name).is_file():
                shutil.copyfile(assets / name, target / name)
        for source in assets.glob("map_icon_*.png"):
            shutil.copyfile(source, target / source.name)
    fonts = game / "fonts"
    fonts.mkdir(exist_ok=True)
    for name in ("calibri.ttf", "corbel.ttf", "corbeli.ttf", "gothic.ttf"):
        source = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if not source.is_file():
            source = sdk / "renpy/common/DejaVuSans.ttf"
        shutil.copyfile(source, fonts / ("gothic.TTF" if name == "gothic.ttf" else name))
    base = (root / "don_gen.rpy").read_text(encoding="utf-8")
    import textwrap
    init_source = textwrap.dedent(base.split('init 1000 python:\n', 1)[1].split('\ndefault persistent.', 1)[0])
    parsed = ast.parse(init_source)
    helper_names = {"dg_menu_audio", "dg_sprite_layer_map", "dg_7dl_sprite_layer", "dg_7dl_sprite_poses", "dg_7dl_sprite_displayable"}
    helpers = [ast.get_source_segment(init_source, node) for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in helper_names]
    (game / "sprite_helpers.rpy").write_bytes(('init 1050 python:\n    import re\n    renpy.music.register_channel("ambience", mixer="sfx", loop=True)\n    renpy.music.register_channel("dg_theme", mixer="music", loop=True)\n    renpy.music.register_channel("dg_nature", mixer="sfx", loop=True)\n' + textwrap.indent('\n\n'.join(helpers), '    ') + '\n').encode('utf-8'))
    styles = base[base.index("style dg_text:"):base.index("screen dg_scene(")]
    (game / "styles.rpy").write_bytes(styles.encode("utf-8"))
    (game / "test.rpy").write_bytes(HARNESS.encode("utf-8"))
    env = dict(os.environ)
    env["DG_UI_SCREEN"] = args.screen or ""
    if args.assets:
        env["DON_GEN_MAP_ROOT"] = str(args.assets.resolve())
    env["DG_UI_WORKSHOP"] = str(args.workshop.resolve()) if args.workshop else ""
    env["DG_UI_VANILLA"] = str(args.vanilla.resolve()) if args.vanilla else ""
    env["DG_UI_PLACE"] = args.place
    env["DG_UI_SLOT"] = str(args.slot)
    env["DG_UI_SOURCE"] = args.source
    env["DG_UI_FOCUS"] = args.focus or ""
    launcher = sdk / "renpy.py"
    if args.engine_root:
        engine = args.engine_root.resolve()
        runner = engine / "lib/windows-x86_64/python.exe"
        if not runner.is_file() or not (engine / "renpy/bootstrap.py").is_file():
            parser.error("Expected an installed Windows RenPy game runtime")
        launcher = output / "native-launcher.py"
        shim = ("from __future__ import print_function\nimport sys,types\nsys.dont_write_bytecode=True\n"
                "root=%r\nsys.path.insert(0,root)\nmodule=types.ModuleType('native_test_launcher')\n"
                "module.__file__=%r\nsys.modules[module.__name__]=module\n"
                "exec(compile(open(module.__file__,'rb').read(),module.__file__,'exec'),module.__dict__)\n"
                "module.path_to_renpy_base=lambda:root\nsys.modules['__main__']=module\nmodule.main()\n") % (str(engine),str(sdk / "renpy.py"))
        launcher.write_bytes(shim.encode('utf-8'))
    subprocess.run([str(runner), str(launcher), str(output), "ui-render"], check=True, env=env)
    print("Rendered UI screenshots:", output)


HARNESS = r'''# -*- coding: utf-8 -*-
init -1000 python:
    import os, sys
    sys.path.insert(0, os.path.join(config.gamedir, "mods", "don_gen"))
    config.screen_width = 1920
    config.screen_height = 1080
    config.window_title = "DON-GEN UI test harness"
    config.save_directory = None
    config.sound = False
    config.performance_test = False
    config.default_fullscreen = False
    config.gl_resize = False
    config.gl2 = False
    if hasattr(config,"physical_width"):
        config.physical_width = 1280
        config.physical_height = 720
    vanilla_root = os.environ.get("DG_UI_VANILLA")
    if vanilla_root and os.path.isfile(os.path.join(vanilla_root, "archive.rpa")):
        config.archives.append(os.path.join(vanilla_root, "archive").replace("\\", "/"))
        renpy.loader.index_archives()

init 1100 python:
    class TestClient(object):
        def authenticated(self):
            return True
    class TestApp(object):
        client = TestClient()
        catalog = {"source_roots": {}, "source_assets": {}}
        status = u"Пишем диалог и проверяем согласованность сцены…"
        busy = True
    class TestRuntime(object):
        app = TestApp()
        original_images = {}
        original_sprite_layers = {}
        source_images = {}
    dg_runtime = TestRuntime()
    if vanilla_root:
        import re
        for archive_path, archive_index in renpy.loader.archives:
            for path in archive_index:
                if path.startswith("images/bg/") and path.endswith((".jpg", ".png")):
                    name = "bg " + os.path.splitext(os.path.basename(path))[0]
                    dg_runtime.original_images[name] = Image(path)
                match = re.match(r"^images/sprites/(normal|far|close)/([^/]+)/([^/]+)$", path)
                if not match:
                    continue
                distance, who, filename = match.groups()
                layer = re.match(r"^([A-Za-z_]+)_([0-9]+)_(.+)\.png$", filename)
                if layer and layer.group(1) == who:
                    dg_runtime.original_sprite_layers.setdefault(distance, {}).setdefault(who, {}).setdefault(layer.group(2), {})[layer.group(3)] = path
    workshop_root = dg_resources.valid_root(os.environ.get("DG_UI_WORKSHOP"))
    if workshop_root:
        import dg_source_7dl
        dg_runtime.app.catalog["source_roots"]["7dl"] = workshop_root
        dg_runtime.app.catalog["source_assets"]["7dl"] = dg_resources.absolute_assets(
            workshop_root, dg_source_7dl.asset_manifest(workshop_root))
    DG_PAPER = Solid("#f3e6cf")
    def dg_elapsed():
        return u"Прошло 00:12"
    def dg_literal(value):
        return value.replace("{", "{{").replace("[", "[[")
    def dg_rpg_root():
        return os.path.join(config.gamedir, "test-saves")
    dg_test_native_sprite = dg_rpg_sprite
    def dg_rpg_sprite(*args):
        return dg_test_native_sprite(*args) if vanilla_root else None
    def dg_detect_7dl_root():
        return workshop_root
    def ui_capture(name):
        renpy.screenshot(os.path.join(config.basedir, name + ".png"))

    def ui_render_check():
        import pygame_sdl2 as pygame
        import renpy.display.swdraw
        renpy.exports.execute_default_statement(True)
        renpy.game.context().init_phase = False
        renpy.display.render.render_ready()
        renpy.display.draw = renpy.display.swdraw.SWDraw()
        renpy.display.draw.screen = pygame.Surface((1920, 1080), pygame.SRCALPHA, 32)
        renpy.display.draw.window = renpy.display.draw.screen
        renpy.display.draw.draw_to_virt = renpy.display.render.Matrix2D(1, 0, 0, 1)
        renpy.display.draw.virt_to_draw = renpy.display.render.Matrix2D(1, 0, 0, 1)
        renpy.display.draw.draw_per_virt = 1.0
        store.dg_rpg_state = dg_rpg.new_game(u"Тестовый герой", 23, 30, source=os.environ.get("DG_UI_SOURCE", "vanilla"))
        store.dg_rpg_scene_context = dg_stage.freeze(store.dg_rpg_state)
        if dg_rpg_say_character("dv").name != u"Алиса" or dg_rpg_say_character("hero").name != u"Тестовый герой":
            raise ValueError("Incorrect native character names")
        # Reproduce the reported inherited DynamicCharacter failure using the
        # real Character call path, while only capturing the final display.
        old_native=getattr(store,'mi',None)
        store.mi=DynamicCharacter(u"Мику. (не Python!)",screen="foreign_say")
        checked=dg_rpg_say_character('mi')
        if checked.dynamic or checked.screen!='dg_rpg_say':
            raise ValueError("Inherited a foreign dynamic character or screen")
        # This measurement occurs during automatic layout; never draw polygons
        # onto a zero-height native canvas.
        dg_camp_button_surface("#101923","#65D8D0").render(100,0,0,0)
        received=[]
        checked.do_display=lambda who,what,**kwargs:received.append(who)
        checked.do_done=lambda *args,**kwargs:None
        checked(u"Проверка буквального имени.",interact=False)
        store.mi=old_native
        if received!=[u'Мику']:
            raise ValueError("Literal character name failed in actual say call")
        print("Checked actual Character call with poisoned DynamicCharacter: literal name and private screen")
        for speaker in [None,"hero"]+sorted(dg_stage.NAMES):
            character = dg_rpg_say_character(speaker)
            if character.what_args.get("color") != "#F2E4BB" or character.what_args.get("font") != "fonts/calibri.ttf":
                raise ValueError("Incorrect narration typography")
            if speaker is not None and not character.who_args.get("bold"):
                raise ValueError("Character name must be bold")
            captured=[]
            character.do_display=lambda who,what,**kwargs:captured.append(who)
            character.do_done=lambda *args,**kwargs:None
            character(u"Проверка отображения реплики.",interact=False)
            if captured!=[character.name] or character.dynamic or character.screen!='dg_rpg_say':
                raise ValueError("Name evaluated or foreign screen used: "+repr(speaker))
        print("Checked actual say calls for all 11 NPCs, narrator and hero")
        dg_rpg.move(store.dg_rpg_state, os.environ.get("DG_UI_PLACE", "cabins"))
        store.dg_rpg_state["slot"] = int(os.environ.get("DG_UI_SLOT", "0"))
        store.dg_rpg_scene_context = dg_stage.freeze(store.dg_rpg_state)
        if vanilla_root:
            # Exercise production background selection, including a prior scene's
            # snapshot: the camp hub must always use the new current location.
            backgrounds = []
            for place, slot in (("gate", 0), ("canteen", 1), ("beach", 1), ("gate", 3)):
                store.dg_rpg_state["place"] = place
                store.dg_rpg_state["slot"] = slot
                native = dg_rpg_bg_native(place)
                if native is None:
                    raise ValueError("Missing actual background for " + place)
                backgrounds.append(native)
            if len(set(backgrounds)) != 4:
                raise ValueError("Location/time transitions did not change the background")
            store.dg_rpg_state["place"] = os.environ.get("DG_UI_PLACE", "cabins")
            store.dg_rpg_state["slot"] = int(os.environ.get("DG_UI_SLOT", "0"))
        if os.environ.get("DG_UI_FOCUS"):
            focus = os.environ["DG_UI_FOCUS"]
            dg_rpg.move(store.dg_rpg_state, dg_rpg.where_is(store.dg_rpg_state, focus))
        store.dg_rpg_scene_context = dg_stage.freeze(store.dg_rpg_state)
        store.dg_create_name = u"Тестовый герой"
        store.dg_create_age = u"23"
        store.dg_create_days = u"30"
        store.dg_create_history = u"Длинная предыстория. " * 100
        store.dg_create_source = os.environ.get("DG_UI_SOURCE", "vanilla")
        store.dg_create_pronouns = u"он/его"
        store.dg_create_adult = False
        store.dg_rpg_action_draft = u"Помочь подготовить выступление. " * 100
        plan = dg_hybrid.preview(store.dg_rpg_state, store.dg_rpg_action_draft)
        cases = [("hub", "dg_rpg_hub", {}), ("controls", "dg_rpg_controls", {}), ("setup", "dg_rpg_setup", {}),
                 ("input", "dg_rpg_hybrid_input", {"mode":"free"}),
                 ("editor", "dg_rpg_edit_field", {"field":"history", "current":u"Биография"}),
                 ("review", "dg_rpg_hybrid_review", {"plan":plan}),
                 ("map", "dg_rpg_map", {}), ("places", "dg_rpg_places", {}),
                 ("cabins", "dg_rpg_cabins", {"region":"cabins"}),
                 ("journal", "dg_rpg_journal", {}), ("picker", "dg_rpg_picker", {})]
        if os.environ.get("DG_UI_SCREEN") in ('arrival','camp-day','context','calendar','injury','disco','card-table','investigation'):
            state=dg_rpg.new_game(u'Тестовый герой',23,30,source='bkrr:mi',camp_life=True)
            if os.environ.get("DG_UI_SCREEN")=='card-table':
                import dg_cards
                state['day']=2;state['slot']=1;state['camp_life'].update(arrival=4,minute=960)
                state['place']='canteen';dg_cards.act(state,'cards:start')
                cases=[('card-table','dg_rpg_card_table',{})]
            elif os.environ.get("DG_UI_SCREEN")=='investigation':
                import dg_clues,dg_inventory,dg_epistemic,dg_world,dg_social,dg_visits
                state['day']=5;state['camp_life'].update(arrival=4,minute=650,tour_issued=True,stamps=[p for p,w in dg_camp.TOUR],club='music')
                state['id']=next('%032x'%i for i in range(1000) if dg_world._seed('%032x'%i,5,1,'clue')%8==0)
                state['place']='clubs';dg_inventory.ensure(state)
                dg_epistemic.record(state,'recognition','shirt:'+state['id'],{'marker':u'контрастный шов'},['hero','mi'])
                dg_inventory.act(state,'lend','shirt','sh');dg_visits.ensure(state)['romance']=['mi']
                state['slot']=2;state['camp_life']['minute']=1295;state['place']='showers'
                dg_social.ensure(state)['bonds'][dg_social._pair('sh','un')]=70
                dg_clues.refresh(state);dg_clues.act(state,'clue:listen');dg_clues.act(state,'clue:explain');dg_clues.act(state,'clue:record')
                state['place']=dg_rpg.where_is(state,'mi');cases=[('investigation','dg_rpg_camp',{})]
            elif os.environ.get("DG_UI_SCREEN")=='camp-day':
                state['day']=2;state['camp_life'].update(arrival=4,minute=600,tour_issued=True)
                state['met']=['sl','mt'];state['place']='library'
                cases=[('camp-day','dg_rpg_camp',{})]
            elif os.environ.get("DG_UI_SCREEN")=='disco':
                import dg_world
                state['day']=6;state['slot']=2;state['camp_life'].update(arrival=4,minute=1200,tour_issued=True,stamps=[p for p,w in dg_camp.TOUR],club='music')
                state['id']=next('%032x'%i for i in range(1000) if dg_world.weather(dict(state,id='%032x'%i))[0]!='rain')
                state['place']='square';cases=[('disco','dg_rpg_hub',{})]
            elif os.environ.get("DG_UI_SCREEN") in ('calendar','injury'):

                import dg_world,dg_risk
                state['day']=5;state['slot']=2;state['camp_life'].update(arrival=4,minute=1200,tour_issued=True,stamps=[p for p,w in dg_camp.TOUR],club='music')
                state['id']=next('%032x'%i for i in range(1000) if dg_world.weather(dict(state,id='%032x'%i))[0]=='rain')
                state['place']='clubhouse'
                if os.environ.get("DG_UI_SCREEN")=='injury':
                    state['place']='infirmary';state['health']={'kind':'fall','until':__import__('dg_clock').absolute(state)+1000,'treated':False,'day':5}
                cases=[(os.environ.get("DG_UI_SCREEN"),'dg_rpg_camp',{})]
            elif os.environ.get("DG_UI_SCREEN")=='context':
                state['day']=3;state['camp_life'].update(arrival=4,minute=600,tour_issued=True,stamps=[p for p,w in dg_camp.TOUR],club='music')
                state['met']=['mi'];state['affinity']['mi']=60
                state['camp_life']['contacts']['mi']={'days':[1,2,3],'count':8}
                dg_relationships.person(state,'mi')['trust']=5
                state['place']=dg_rpg.where_is(state,'mi')
                cases=[('context','dg_rpg_context',{'who':'mi'})]
            else:cases=[('arrival','dg_rpg_hub',{})]
            store.dg_rpg_state=state
            store.dg_rpg_scene_context=dg_stage.freeze(state)
        if os.environ.get("DG_UI_SCREEN") in ('deeds','commitments'):
            import dg_commitments,dg_life,dg_clock
            state=dg_rpg.new_game(u'Тестовый герой',23,30,source='bkrr:mi',camp_life=True)
            state['day']=5;state['place']='square';state['camp_life'].update(arrival=4,minute=650,tour_issued=True,stamps=[p for p,w in dg_camp.TOUR],club='music')
            state['met']=['mi'];state['affinity']['mi']=50;state['camp_life']['contacts']['mi']={'days':[1,2,3],'count':8}
            state['dialogue_clock']={'who':'mi','rounds':1}
            dg_life.ensure(state)['people']['mi']={'place':'square','destination':'square','route':[],'next':dg_clock.absolute(state)+5}
            dg_commitments.act(state,'invite:mi')
            store.dg_rpg_state=state;store.dg_rpg_scene_context=dg_stage.freeze(state)
            cases=[(os.environ['DG_UI_SCREEN'],'dg_rpg_deeds',{'selection':('objects' if os.environ['DG_UI_SCREEN']=='deeds' else 'commitments',None)})]
        if os.environ.get("DG_UI_SCREEN")=='menu-audio':
            # Both init blocks share store: dg_audio is the RPG module here.
            assert not callable(dg_audio) and callable(dg_menu_audio)
            store.DG_PLACES={'gate': ('unused', 'missing_ambience', 'day')}
            store.DG_THEME='missing_theme'
            store.music_list={}
            store.dg_audio_pauses=None
            persistent.dg_atmosphere_sound=True
            Function(dg_menu_audio,'gate')()
            assert dg_audio_pauses is not None
            Function(dg_menu_audio,None)()
            assert dg_audio_pauses is None
            print('NATIVE_MENU_AUDIO_OK: RPG module and menu callbacks coexist; enter/leave restored channels')
            cases=[('menu-audio','dg_rpg_hub',{})]
        if os.environ.get("DG_UI_SCREEN")=='crew':
            import dg_ensemble,dg_life,dg_clock
            state=dg_rpg.new_game(u'Тестовый герой',23,30,source='bkrr:mi',camp_life=True)
            state['day']=3;state['place']='music';state['camp_life'].update(arrival=4,minute=650,tour_issued=True,stamps=[p for p,w in dg_camp.TOUR],club='music')
            dg_rpg.validate(state)
            if state['social'].get('incident'):state['social']['incident']['status']='resolved'
            state['met']=['mi','dv','el']
            for w in state['met']:dg_life.ensure(state)['people'][w]={'place':'music','destination':'music','route':[],'next':dg_clock.absolute(state)+5}
            dg_ensemble.act(state,'crew:start:concert');dg_ensemble.act(state,'crew:1:plan:acoustic')
            state['slot']=2;state['camp_life']['minute']=1095;state['place']='music'
            for w in ('mi','dv'):dg_life.ensure(state)['people'][w].update(place='music',destination='music',route=[])
            store.dg_rpg_state=state;store.dg_rpg_scene_context=dg_stage.freeze(state)
            cases=[('crew','dg_rpg_deeds',{'selection':('crew',None)})]
        if os.environ.get("DG_UI_SCREEN")=='stock-catalog':
            store.min=u'host character min';store.max=u'host character max'
            cases=[('stock-catalog','dg_rpg_stock_catalog',{})]
        if os.environ.get("DG_UI_SCREEN")=='pacing':
            cases=[('pacing','dg_rpg_controls',{'initial_tab':'settings'})]
        if os.environ.get("DG_UI_SCREEN") in ('shift-trash','shift-confirm','shift-purge','shift-flow'):
            import dg_sessions
            state=dg_rpg.new_game(u'Архивная смена Игоря',24,60,camp_life=True)
            dg_rpg.save(dg_rpg_root(),state)
            if os.environ['DG_UI_SCREEN']=='shift-flow':
                api=dg_rpg_say_character.func_globals['renpy'];original_call=api.call_screen;original_notify=api.notify
                original_stop=store.dg_rpg_audio_stop;store.dg_rpg_audio_stop=lambda:None
                dg_runtime.app.busy=False;notify=[];api.notify=lambda text:notify.append(text)
                other=dg_rpg.new_game(u'Другая смена',24,14);dg_rpg.save(dg_rpg_root(),other)
                screens=[];pickers=[0];confirms=[0];trashes=[0]
                def shift_call(name,*args,**kwargs):
                    screens.append(name)
                    if name=='dg_rpg_picker':
                        pickers[0]+=1;n=pickers[0]
                        if n==1:return ('delete_shift',state['id'])
                        if n==2:
                            if dg_rpg.load(dg_rpg_root(),state['id'])!=state:raise ValueError('Cancel deleted shift')
                            return ('delete_shift',state['id'])
                        if n in (3,5):
                            if any(r['id']==state['id'] for r in dg_rpg.list_games(dg_rpg_root())):raise ValueError('Trashed shift still visible')
                            return ('trash',None)
                        if n==4:
                            if dg_rpg.load(dg_rpg_root(),state['id'])!=state:raise ValueError('Restore changed shift')
                            return ('delete_shift',state['id'])
                        if n==6:
                            if dg_sessions.deleted(dg_rpg_root()) or not dg_sessions.removed(dg_rpg_root(),state['id']):raise ValueError('Purge incomplete')
                            if dg_rpg.load(dg_rpg_root(),other['id'])!=other:raise ValueError('Other shift changed')
                            api.jump('dg_ui_flow_done')
                        raise ValueError('Shift picker loop did not terminate')
                    if name=='dg_rpg_shift_confirm':
                        confirms[0]+=1;return confirms[0]!=1
                    if name=='dg_rpg_shift_trash':
                        trashes[0]+=1;row=dg_sessions.deleted(dg_rpg_root())[0]
                        return ('restore' if trashes[0]==1 else 'purge',row['key'])
                    raise ValueError('Unexpected shift screen '+name)
                try:
                    api.call_screen=shift_call;api.call_in_new_context('dg_rpg_picker_label')
                    if len(notify)!=4:raise ValueError('Shift operation was not completed: '+repr(notify))
                    print('SCRIPT_SHIFT_MANAGEMENT_OK cancel=True trash=True restore=True purge=True other_shift_untouched=True')
                finally:api.call_screen=original_call;api.notify=original_notify;store.dg_rpg_audio_stop=original_stop
                return False
            dg_sessions.trash(dg_rpg_root(),state['id'])
            if os.environ['DG_UI_SCREEN']=='shift-trash':cases=[('shift-trash','dg_rpg_shift_trash',{})]
            else:cases=[(os.environ['DG_UI_SCREEN'],'dg_rpg_shift_confirm',{'name':state['hero']['name'],'permanent':os.environ['DG_UI_SCREEN']=='shift-purge'})]
        if os.environ.get("DG_UI_SCREEN")=='music-entry':
            state=dg_rpg.new_game(u'Игорь',23,30,source='bkrr:mi',camp_life=True)
            state['place']='music';store.dg_rpg_state=state;store.dg_rpg_stage_active=False
            dg_rpg.save(dg_rpg_root(),state)
            outside=dg_rpg_visual_brief(state)['setting']
            dg_rpg_apply('music_door',True)
            inside=dg_rpg_visual_brief(store.dg_rpg_state)['setting']
            if outside!='exterior' or inside!='interior' or store.dg_rpg_state['camp_life']['club'] is not None:
                raise ValueError('Music door did not change the actual BG: '+repr((outside,inside)))
            dg_rpg_apply('music_door',False)
            if dg_rpg_visual_brief(store.dg_rpg_state)['setting']!='exterior':raise ValueError('Music exit failed')
            print('NATIVE_MUSIC_DOOR_OK actual exterior/interior BG and frozen context; no fabricated membership')
            cases=[('music-entry','dg_rpg_hub',{})]
        if os.environ.get("DG_UI_SCREEN")=='hybrid-flow':
            state=dg_rpg.new_game(u'Игорь',23,30,source='bkrr:mi',camp_life=True)
            state['place']=dg_rpg.where_is(state,'mi')
            dg_rpg.save(dg_rpg_root(),state)
            store.dg_rpg_state=state;store.dg_rpg_pending_turn=None;store.dg_rpg_scene_context=dg_stage.freeze(state)
            store.dg_rpg_hybrid_mode='npc';store.dg_rpg_hybrid_who='mi';store.dg_rpg_hybrid_topic=None
            store.dg_rpg_action_context=('npc','mi',None)
            store.dg_rpg_hybrid_plan=dg_hybrid.preview(state,u'Привет, я Игорь. Давай познакомимся.','npc','mi')
            api=dg_rpg_say_character.func_globals['renpy']
            original_call=api.call_screen;original_say=api.say;original_menu=api.display_menu;original_with=api.with_statement
            original_audio=store.dg_rpg_audio_sync;original_run=store.dg_rpg_run
            counts={'input':0,'review':0,'menu':0,'hub':0}
            def hybrid_call(name,*args,**kwargs):
                if name=='dg_rpg_hybrid_review':counts['review']+=1;return 'ai'
                if name=='dg_rpg_hybrid_input':
                    counts['input']+=1
                    if store.dg_rpg_action_draft:raise ValueError('Previous draft leaked into continuation')
                    return ('submit',u'А какую музыку тебе нравится слушать?')
                if name=='dg_rpg_hub':counts['hub']+=1;api.jump('dg_ui_flow_done')
                raise ValueError('Unexpected continuation screen '+name)
            def hybrid_menu(items,**kwargs):
                counts['menu']+=1
                return items[0 if counts['menu']==1 else 1][1]
            def hybrid_run(*args):
                dg_runtime.app.error=None
                dg_runtime.app.result=u'[mi] Приятно познакомиться, Игорь. Я запомнила твоё имя и то, что ты играешь на гитаре. Давай немного поговорим, если ты не спешишь к вожатой. [narrator] Мику отложила папку и выслушала вопрос.'
            try:
                api.call_screen=hybrid_call;api.say=lambda *args,**kwargs:None;api.display_menu=hybrid_menu;api.with_statement=lambda *args,**kwargs:None
                store.dg_rpg_audio_sync=lambda *args:None;store.dg_rpg_run=hybrid_run
                api.call_in_new_context('dg_rpg_hybrid_review_label')
                saved=dg_rpg.load(dg_rpg_root(),state['id'])
                if counts!={'input':1,'review':2,'menu':2,'hub':1} or saved['dialogue_counts']['1:mi']!=2 or 'mi' not in saved['met']:
                    raise ValueError('Continuation failed '+repr(counts))
                print('NATIVE_HYBRID_CONTINUE_OK two commits; introduction persisted; input reopened; returned to hub')
            finally:
                api.call_screen=original_call;api.say=original_say;api.display_menu=original_menu;api.with_statement=original_with
                store.dg_rpg_audio_sync=original_audio;store.dg_rpg_run=original_run
            return False
        if os.environ.get("DG_UI_SCREEN")=='branches':
            import dg_checkpoints,copy
            state=dg_rpg.new_game(u'Тестовый герой',23,30,camp_life=True)
            future=copy.deepcopy(state);future['energy']=25;dg_rpg.save(dg_rpg_root(),future)
            store.dg_rpg_state=dg_checkpoints.restore(dg_rpg_root(),state)
            cases=[('branches','dg_rpg_branches',{})]
        if os.environ.get("DG_UI_SCREEN")=='native-save':
            import copy,dg_checkpoints
            if not os.path.abspath(config.savedir).lower().startswith(os.path.abspath(config.basedir).lower()):raise ValueError('Native test save must stay in isolated project')
            renpy.game.context().rollback=True
            renpy.game.context().goto_label('dg_rpg_loop')
            renpy.game.log.begin(force=True)
            state=dg_rpg.new_game(u'Тестовый герой',23,30,camp_life=True)
            store.dg_rpg_state=state;store.dg_rpg_pending_turn=None;store.dg_rpg_active=True
            store.dg_rpg_vn_line=u'Страница 2';store.dg_rpg_stage_active=True
            store.dg_rpg_scene_context=dg_stage.freeze(state)
            dg_rpg.save(dg_rpg_root(),state)
            renpy.loadsave.save('dg-native-probe')
            payload=renpy.loadsave.location.load('dg-native-probe')
            roots,log=renpy.loadsave.loads(payload[0] if isinstance(payload,tuple) else payload)
            names=[name for name in roots if 'dg_rpg_state' in name]
            if not names:raise ValueError('Native slot did not contain RPG state: '+repr(roots.keys()))
            embedded=roots[names[0]];future=copy.deepcopy(state);future['energy']=25;dg_rpg.save(dg_rpg_root(),future)
            store.dg_rpg_state=embedded
            store.dg_rpg_after_load()
            if store.dg_rpg_state['energy']!=100 or dg_rpg.load(dg_rpg_root(),state['id'])['energy']!=100:raise ValueError('Native checkpoint overwritten by future JSON')
            if store.dg_rpg_vn_line!=u'Страница 2' or not store.dg_rpg_stage_active:raise ValueError('Native dialogue position discarded')
            if len(dg_checkpoints.branches(dg_rpg_root(),state['id']))!=1:raise ValueError('Displaced future not archived')
            print('NATIVE_SAVE_OK embedded=True exact_state=True dialogue_page_preserved=True future_archived=True')
            cases=[]
        if os.environ.get("DG_UI_SCREEN")=='flow':
            import dg_narrative
            api=dg_rpg_say_character.func_globals['renpy']
            methods=('call_screen','say','display_menu','with_statement')
            original=dict((name,getattr(api,name)) for name in methods)
            original_read=dg_narrative.read_scene
            original_audio=store.dg_rpg_audio_sync
            store.dg_rpg_audio_sync=lambda *args:None
            prose=u'[narrator] У музыкального кружка тихо. На веранде стоят Мику и герой. Никто ещё не принял решений.\n[mi] Привет! Как проходит твой день? Я могу немного поговорить, прежде чем вернуться к своим занятиям.\n[hero] Здравствуй. Я хотел узнать немного больше о лагере и о том, чем здесь обычно занимаются.'
            try:
                for modern,interrupted in ((False,False),(False,True),(True,False),(True,True)):
                    state=dg_rpg.new_game(u'Тестовый герой',23,30,source='bkrr:mi',camp_life=modern)
                    if state['social'].get('incident'):state['social']['incident']['status']='resolved'
                    dg_rpg.move(state,dg_rpg.where_is(state,'mi'))
                    store.dg_rpg_state=state;store.dg_rpg_pending_turn=None;store.dg_rpg_interrupt=False
                    dg_rpg.save(dg_rpg_root(),state)
                    counts={'hub':0,'say':0,'menu':0,'cache':0}
                    def screen_call(name,*args,**kwargs):
                        if name!='dg_rpg_hub':raise ValueError('Unexpected screen in flow: '+name)
                        counts['hub']+=1
                        if counts['hub']==1:return ('talk','mi')
                        api.jump('dg_ui_flow_done')
                    def menu_call(items,**kwargs):
                        if kwargs.get('screen')!='dg_rpg_choice':raise ValueError('Foreign choice screen')
                        counts['menu']+=1
                        return '0' if counts['menu']==1 else 'support'
                    def say_call(character,text,*args,**kwargs):
                        counts['say']+=1
                        if character.dynamic or character.screen!='dg_rpg_say':raise ValueError('Foreign character in real label flow')
                        if interrupted and counts['say']==2:store.dg_rpg_interrupt=True
                    def cache(*args):
                        counts['cache']+=1
                        return {'text':prose}
                    api.call_screen=screen_call;api.say=say_call;api.display_menu=menu_call;api.with_statement=lambda *args,**kwargs:None
                    dg_narrative.read_scene=cache
                    api.call_in_new_context('dg_rpg_loop')
                    saved=dg_rpg.load(dg_rpg_root(),state['id'])
                    if counts['hub']!=2 or not store.save_name.startswith(u'DON-GEN'):raise ValueError('Did not return to DON-GEN hub')
                    if interrupted:
                        if counts['say']!=2 or saved['dialogue_history']:raise ValueError('Interrupted opening committed a conversation')
                    elif counts['cache']!=3 or counts['say']!=9 or len(saved['dialogue_history'])!=1 or store.dg_rpg_pending_turn is not None:
                        raise ValueError('Three-page dialogue failed to complete: '+repr(counts))
                    print('SCRIPT_FLOW_OK modern='+str(modern)+' interrupted='+str(interrupted)+' counts='+repr(counts)+' returned_to_hub=True')
                # The first scene of a fresh UI-created shift must happen before
                # ordinary hub interaction, and commit only after narration.
                interrupted=False
                state=dg_rpg.new_game(u'Тестовый герой',23,30,source='bkrr:mi',camp_life=True)
                store.dg_rpg_state=state;store.dg_rpg_pending_turn=None;store.dg_rpg_interrupt=False;store.dg_rpg_intro_attempted=[]
                dg_rpg.save(dg_rpg_root(),state)
                counts={'hub':0,'say':0,'menu':0,'cache':0}
                prose=u'[narrator] У ворот лагеря нового пионера встречает Славя. Она останавливается, чтобы познакомиться и объяснить дорогу.\n[sl] Привет! Меня зовут Славя. Вожатая ждёт тебя в домике. Я объясню, как туда пройти.\n[hero] Спасибо. Я только приехал и пока не знаю лагеря.'
                def arrival_hub(name,*args,**kwargs):
                    if name!='dg_rpg_hub':raise ValueError('Unexpected arrival screen')
                    counts['hub']+=1;api.jump('dg_ui_flow_done')
                api.call_screen=arrival_hub
                api.call_in_new_context('dg_rpg_loop')
                saved=dg_rpg.load(dg_rpg_root(),state['id'])
                if saved['camp_life']['arrival']!=1 or saved['met']!=['sl'] or counts['hub']!=1 or counts['say']<3 or store.dg_rpg_pending_turn is not None:
                    raise ValueError('Automatic arrival failed: '+repr(counts))
                print('SCRIPT_AUTO_ARRIVAL_OK Slavya=True committed=True returned_to_hub=True')
                import dg_cards
                state=dg_rpg.new_game(u'Тестовый герой',23,30,source='bkrr:mi',camp_life=True)
                state['day']=2;state['slot']=1;state['camp_life'].update(arrival=4,minute=960)
                state['place']='canteen';dg_cards.act(state,'cards:start')
                store.dg_rpg_state=state;store.dg_rpg_pending_turn=None;store.dg_rpg_interrupt=False
                dg_rpg.save(dg_rpg_root(),state)
                counts={'hub':0,'say':0,'menu':0,'cache':0,'cards':0}
                prose=u'[narrator] Турнир завершён. Игроки убирают карты со стола и освобождают место. Результат трёх раундов уже записан; никто не меняет правила задним числом.\n[el] Спасибо за игру! Теперь можно немного отдохнуть и заняться другими делами.'
                def card_screen(name,*args,**kwargs):
                    if name=='dg_rpg_hub':
                        counts['hub']+=1;api.jump('dg_ui_flow_done')
                    if name!='dg_rpg_card_table':raise ValueError('Unexpected card screen: '+name)
                    counts['cards']+=1
                    if counts['cards']>12:raise ValueError('Card table loop did not terminate')
                    keys=[r['key'] for r in dg_cards.cards(store.dg_rpg_state) if r['ready']]
                    return 'cards:stand' if 'cards:stand' in keys else 'cards:next'
                api.call_screen=card_screen
                api.call_in_new_context('dg_rpg_card_table_label')
                saved=dg_rpg.load(dg_rpg_root(),state['id'])
                if saved['card_table']['phase']!='finished' or store.dg_rpg_pending_turn is not None or counts['hub']!=1:
                    raise ValueError('Card table did not commit and return to hub: '+repr(counts))
                print('SCRIPT_CARD_TABLE_OK three_rounds=True committed=True returned_to_hub=True')
                state=dg_rpg.new_game(u'Тестовый герой',23,30,source='bkrr:mi',camp_life=True)
                state['day']=5;state['place']='square';state['camp_life'].update(arrival=4,minute=650,tour_issued=True,stamps=[p for p,w in dg_camp.TOUR],club='music')
                store.dg_rpg_state=state;store.dg_rpg_pending_turn=None;store.dg_rpg_interrupt=False
                dg_rpg.save(dg_rpg_root(),state)
                counts={'hub':0,'say':0,'menu':0,'cache':0,'deeds':0}
                prose=u'[narrator] Герой протёр скамейки на площади. Работа заняла двадцать минут. Уборка закончена; инструменты и вещи лагеря не стали личной собственностью героя. Теперь можно вернуться к остальным делам.'
                def deed_screen(name,*args,**kwargs):
                    if name=='dg_rpg_hub':
                        counts['hub']+=1
                        if counts['hub']==1:return ('deeds',('objects',None))
                        api.jump('dg_ui_flow_done')
                    if name=='dg_rpg_deeds':
                        counts['deeds']+=1;return ('camp_do','object:clean:benches:square')
                    raise ValueError('Unexpected deed screen: '+name)
                api.call_screen=deed_screen
                api.call_in_new_context('dg_rpg_loop')
                saved=dg_rpg.load(dg_rpg_root(),state['id'])
                if counts['hub']!=2 or counts['deeds']!=1 or saved['affordances']['done'].get('clean:benches:square')!=5 or store.dg_rpg_pending_turn is not None:
                    raise ValueError('Object action did not commit through production dispatcher: '+repr(counts))
                print('SCRIPT_OBJECT_ACTION_OK dispatcher=True narration=True committed=True returned_to_hub=True')
                import dg_ensemble,dg_life,dg_clock
                state=dg_rpg.new_game(u'Тестовый герой',23,30,source='bkrr:mi',camp_life=True)
                state['day']=3;state['place']='music';state['camp_life'].update(arrival=4,minute=650,tour_issued=True,stamps=[p for p,w in dg_camp.TOUR],club='music')
                dg_rpg.validate(state)
                if state['social'].get('incident'):state['social']['incident']['status']='resolved'
                state['met']=['mi','dv','el']
                for w in state['met']:dg_life.ensure(state)['people'][w]={'place':'music','destination':'music','route':[],'next':dg_clock.absolute(state)+5}
                dg_ensemble.act(state,'crew:start:concert');dg_ensemble.act(state,'crew:1:plan:acoustic')
                state['slot']=2;state['camp_life']['minute']=1095;state['place']='music'
                for w in ('mi','dv'):dg_life.ensure(state)['people'][w].update(place='music',destination='music',route=[])
                store.dg_rpg_state=state;store.dg_rpg_pending_turn=None;store.dg_rpg_interrupt=False
                dg_rpg.save(dg_rpg_root(),state)
                counts={'hub':0,'say':0,'menu':0,'cache':0}
                prose=u'[narrator] Мику и Алиса вместе с героем закончили репетицию. Работа заняла двадцать минут. Номер подготовлен к будущему концерту; выступление ещё не состоялось. Вклад участников записан отдельно от планов.'
                def crew_screen(name,*args,**kwargs):
                    if name=='dg_rpg_hub':
                        counts['hub']+=1
                        if counts['hub']==1:return ('deeds',('crew',None))
                        api.jump('dg_ui_flow_done')
                    if name=='dg_rpg_deeds':return ('camp_do','crew:1:work')
                    raise ValueError('Unexpected crew screen: '+name)
                api.call_screen=crew_screen;api.call_in_new_context('dg_rpg_loop')
                saved=dg_rpg.load(dg_rpg_root(),state['id'])
                if saved['ensemble']['records'][0]['phase']!='ready' or counts['hub']!=2 or store.dg_rpg_pending_turn is not None:
                    raise ValueError('Shared event dispatcher failed: '+repr(counts))
                print('SCRIPT_SHARED_EVENT_OK dispatcher=True group_work=True committed=True returned_to_hub=True')
            finally:
                for name,value in original.items():setattr(api,name,value)
                dg_narrative.read_scene=original_read
                store.dg_rpg_audio_sync=original_audio
            return False
        if os.environ.get("DG_UI_SCREEN") in ('dialogue','dialogue-choice','waiting'):
            state=store.dg_rpg_state
            state['place']='music'
            state['social']['incident'].update(pair=['mi','dv'],place='music',status='open',day=state['day'])
            store.dg_rpg_scene_context=dg_stage.freeze(state)
            if os.environ.get("DG_UI_SCREEN")=='dialogue':
                cases=[('dialogue','dg_ui_consistent_dialogue',{})]
            elif os.environ.get("DG_UI_SCREEN")=='dialogue-choice':
                class Entry(object):
                    def __init__(self,caption,value): self.caption=caption;self.action=Return(value)
                rows=[Entry(u'Давай я послушаю твою репетицию. Можешь ошибаться сколько угодно.','support'),Entry(u'А что именно тебя привлекло в этой мелодии?','curious'),Entry(u'Написать свою реплику','custom'),Entry(u'Завершить разговор','cancel')]
                cases=[('dialogue-choice','dg_ui_consistent_choice',{'items':rows})]
            else:
                cases=[('waiting','dg_rpg_wait',{})]
        if os.environ.get("DG_UI_SCREEN") == "error":
            store.dg_rpg_state['place']='music'
            store.dg_rpg_scene_context=dg_stage.freeze(store.dg_rpg_state)
            dg_runtime.app.error=u"Не удалось согласовать сцену с игрой (предметы). Ход не сохранён; можно повторить генерацию."
            cases=[("error","dg_rpg_error",{})]
        if os.environ.get("DG_UI_SCREEN") == "party":
            state=store.dg_rpg_state
            state['source']='bkrr:mi'
            state['place']='music'
            state['slot']=1
            state['social']['incident'].update(pair=['mi','dv'],place='music',status='open',day=state['day'])
            present=[who for who,name in dg_rpg.at_place(state)]
            visible=dg_stage.cast([],present,'mi')
            if not all(who in [actor for actor,x in dg_stage.positions(visible,'mi')] for who in ('mi','dv')):
                raise ValueError("Nearby actors missing from hub")
            for actor in ('mi','dv'):
                if dg_rpg_sprite(actor) is None: raise ValueError("Actual sprite missing: "+actor)
            # Execute production audio direction with real archive paths. Capture
            # scheduling instead of accessing speakers in the headless renderer.
            audio_api=dg_rpg_audio_sync.func_globals['renpy']
            methods=('play','stop','get_pause','set_pause')
            original=dict((name,getattr(audio_api.music,name)) for name in methods)
            calls=[]
            try:
                audio_api.music.play=lambda path,**kw:calls.append((path,kw))
                audio_api.music.stop=lambda **kw:None
                audio_api.music.get_pause=lambda **kw:False
                audio_api.music.set_pause=lambda *args,**kw:None
                store.dg_rpg_audio_pauses=None
                dg_rpg_audio_sync('mi')
                if len(calls)!=2 or not all(audio_api.loadable(path) for path,kw in calls):
                    raise ValueError("Production audio could not resolve music and atmosphere")
                nature=[path for path,kw in calls if kw.get('channel')=='dg_nature']
                if len(nature)!=1 or 'camp_center_day' not in nature[0]:
                    raise ValueError("Music club veranda must use outdoor ambience: "+repr(nature))
                if not all(kw.get('if_changed') and kw.get('loop') for path,kw in calls):
                    raise ValueError("Audio would restart on each dialogue")
                dg_rpg_audio_stop()
                if store.dg_rpg_audio_pauses is not None:raise ValueError("Host channels not restored")
                print("Checked production audio: actual music and ambience files; host channel restoration")
            finally:
                for name,value in original.items():setattr(audio_api.music,name,value)
            import dg_source_bkrr
            donor=os.path.join(os.path.dirname(workshop_root),'451835368') if workshop_root else None
            if donor and os.path.isdir(donor):
                samples=dg_source_bkrr.context(donor,['mi','dv'],u'музыка',4)['examples']
                if not samples:raise ValueError("BKRR source reader failed in actual RenPy runtime")
                print("Checked BKRR text reader in actual RenPy runtime: "+str(len(samples))+" references")
            store.dg_rpg_scene_context=dg_stage.freeze(state)
            cases=[("party","dg_rpg_hub",{})]
        if os.environ.get("DG_UI_SCREEN") == "visit":
            store.dg_rpg_state['source']='vanilla'
            store.dg_rpg_state['social']['incident']['status']='resolved'
            store.dg_rpg_state['world']['event']=None
            store.dg_rpg_state['affinity']['mi']=75
            store.dg_rpg_state['met']=['mi']
            store.dg_rpg_state['place']='gate'
            for person in dg_agents.ensure(store.dg_rpg_state)['people'].values():person['goal']['progress']=2
            dg_rpg.activity(store.dg_rpg_state,'rest')
            if not dg_visits.current(store.dg_rpg_state):
                raise ValueError('NPC visit did not arrive')
            cases = [("visit","dg_rpg_hub",{})]
        if os.environ.get("DG_UI_SCREEN") == "hidden":
            cases=[("hidden","dg_rpg_hub",{"initial_show":False})]
        if os.environ.get("DG_UI_SCREEN") == "inventory":
            store.dg_rpg_state["place"]="library"
            cases=[("inventory","dg_rpg_inventory",{})]
        if os.environ.get("DG_UI_SCREEN") == "project-review":
            value={'title':u'Лагерная стенгазета','item':'paper','recipient':'sl','work_place':'clubs','final_place':'square','theme':'council','participants':['sl','un']}
            cases=[("project-review","dg_rpg_project_review",{"proposal":{"blueprint":value}})]
        if os.environ.get("DG_UI_SCREEN") == "projects":
            cases=[("projects","dg_rpg_projects",{})]
        if os.environ.get("DG_UI_SCREEN") == "relationship":
            cases=[("relationship","dg_rpg_relationship",{"who":"mi"})]
        if os.environ.get("DG_UI_SCREEN") == "history":
            dg_presentation.record(store.dg_rpg_state,"example",u"[narrator] Ветер шуршал нотами на столе. [mi] Давай попробуем ещё раз — теперь вместе.")
            cases=[("history","dg_rpg_dialogue_history",{})]
        if os.environ.get("DG_UI_SCREEN") == "housing":
            cases = [("housing","dg_rpg_housing_picker",{})]
        if os.environ.get("DG_UI_SCREEN") == "emotions":
            cases = [("emotions","dg_ui_emotions",{})]
        if os.environ.get("DG_UI_SCREEN") == "agendas":
            dg_rpg.activity(store.dg_rpg_state,"rest")
            cases = [("agendas", "dg_rpg_journal", {"initial_view":"social"})]
        if os.environ.get("DG_UI_SCREEN") == "intent-review":
            proposal = {'status':'ready','intent':'search','target':None,'canonical':u'Исследовать старые записи',
                        'deferred':[u'Завтра показать найденные ноты Мику.'],'when':None}
            plan = dg_hybrid.preview(store.dg_rpg_state,u'Сначала поискать записи, а завтра поговорить с Мику','free',interpretation=proposal)
            cases = [("intent-review", "dg_rpg_hybrid_review", {"plan":plan})]
        if os.environ.get("DG_UI_SCREEN") == "cg-check":
            dg_rpg.save(dg_rpg_root(),store.dg_rpg_state)
            plan = dg_art.scene_plan(store.dg_rpg_state,'hybrid',u'Репетиция Мику',u'Мику играет на гитаре в музыкальном кружке. Герой слушает её музыку рядом с окном.', 'mi')
            plan.update(cast=['mi'],scene_slot=0,setting='interior',hero_pronouns=u'он/его')
            cases = [("cg-check", "dg_rpg_cg_art", {"plan":plan})]
        if os.environ.get("DG_UI_SCREEN") == "scene":
            if not vanilla_root:
                raise ValueError("--vanilla is required for the scene preview")
            for path in ("images/bg/int_dining_hall_people_day.jpg", "images/gui/dialogue_box/day/dialogue_box.png"):
                if not renpy.exports.loadable(path):
                    raise ValueError("Missing vanilla preview resource: " + path)
            for actor in ("un", "mi", "sl", "dv"):
                if dg_rpg_sprite(actor, "smile", "normal") is None:
                    raise ValueError("Missing sprite: " + actor)
            cases = [("scene", "dg_ui_native_scene", {})]
        if os.environ.get("DG_UI_SCREEN") == "staging":
            for distance, pose, emotion in (("normal", "1", "normal"), ("close", "2", "smile")):
                if dg_rpg_sprite("mi", emotion, distance, pose) is None:
                    raise ValueError("Missing staged sprite")
                if not any(value and key.startswith("mi ") and key.endswith("|pose:" + pose)
                           and ((" close|" in key) == (distance == "close"))
                           for key, value in dg_runtime.source_images.items()):
                    raise ValueError("Requested pose fell back: %s/%s/%s; available=%r; body=%r cloth=%r face=%r" %
                        (distance, pose, emotion, dg_7dl_sprite_poses(distance, "mi"),
                         dg_7dl_sprite_layer(distance,"mi",pose,"body"),
                         dg_7dl_sprite_layer(distance,"mi",pose,"pioneer"),
                         dg_7dl_sprite_layer(distance,"mi",pose,emotion)))
            turns = dg_stage.parse(u"[stage mi smile close 2]\n[mi] Привет!", ("mi",))
            if turns[0]["stage"]["mi"]["pose"] != "2":
                raise ValueError("Direction lost during parsing")
            # Execute the production actor director without opening a window.
            # Image composition above is real; only scene-layer I/O is captured.
            actor_api = dg_rpg_stage_actors.func_globals['renpy']
            original = dict((name, getattr(actor_api, name, None)) for name in ("show", "hide", "with_statement"))
            shown, transitions = [], []
            try:
                actor_api.show = lambda tag, **kwargs: shown.append((tag, kwargs))
                actor_api.hide = lambda tag: None
                actor_api.with_statement = lambda transition: transitions.append(transition)
                store.dg_rpg_actor_moods = {}
                store.dg_rpg_visual_cast = None
                staged = dg_stage.parse(u"[stage mi normal normal 1]\n[mi] Привет!\n[stage mi smile close 2]\n[mi] Хорошо!", ("mi",))
                for turn in staged:
                    dg_rpg_stage_actors(staged, ["mi"], turn)
                if len(transitions) != 2 or len(shown) != 2:
                    raise ValueError("Actor director did not apply both stage changes")
                narrated = dg_stage.parse(u"[narrator] Мику злится, Алиса смеётся.",("mi","dv"))
                dg_rpg_stage_actors(narrated,["mi","dv"],narrated[0])
                if store.dg_rpg_actor_moods.get("mi") != "angry" or store.dg_rpg_actor_moods.get("dv") != "laugh":
                    raise ValueError("Named narrated reactions did not reach the actor director")
            finally:
                for name, value in original.items():
                    if value is None:
                        delattr(actor_api, name)
                    else:
                        setattr(actor_api, name, value)
            cases = [("staging", "dg_ui_staging", {})]
        if os.environ.get("DG_UI_SCREEN") == "cg":
            import dg_gallery
            rows = dg_gallery.catalog(dg_gallery.roots(workshop_root))
            example = {'kind':'cg', 'who':'mi', 'description':u'Мику играет на гитаре в музыкальном кружке.',
                       'place':'music', 'scene_slot':1, 'profile':'bkrr:mi', 'cast':['mi']}
            selected = dg_gallery.match(rows, example)
            if not selected:
                raise ValueError("No suitable CG found in actual Workshop resources")
            store.dg_ui_cg = selected['path']
            cases = [("cg", "dg_ui_cg", {})]
        for filename, name, scope in cases:
            if os.environ.get("DG_UI_SCREEN") and os.environ["DG_UI_SCREEN"] != filename:
                continue
            screen = renpy.display.screen.get_screen_variant(name)
            displayable = renpy.display.screen.ScreenDisplayable(screen, name, "screens", scope={"_args":(), "_kwargs":scope})
            displayable.per_interact()
            displayable.visit_all(lambda d: d.per_interact())
            render = renpy.display.render.render(displayable, 1920, 1080, 0.0, 0.0)
            renpy.display.render.invalidate(displayable)
            render = renpy.display.render.render(displayable, 1920, 1080, .3, .3)
            surface = renpy.display.draw.render_to_texture(render, True)
            pygame.image.save(surface, os.path.join(config.basedir, filename + ".png"))
            def debug_viewport(d):
                if isinstance(d, renpy.display.viewport.Viewport):
                    if d.width <= 0 or d.height <= 0:
                        raise ValueError(filename + ": empty viewport "+repr((d.width,d.height)))
            displayable.visit_all(debug_viewport)
            if filename=='stock-catalog':
                for variant,changes in [('last',{'stock_page':99999}),('empty',{'stock_source':'missing','stock_page':0})]:
                    displayable.scope.update(changes)
                    displayable.per_interact()
                    extra=renpy.display.render.render(displayable,1920,1080,.6,.6)
                    pygame.image.save(renpy.display.draw.render_to_texture(extra,True),os.path.join(config.basedir,'catalog-'+variant+'.png'))
                print('NATIVE_CATALOG_OK first/last/empty; host min/max are strings')
            if filename=='pacing':
                views=[]
                displayable.visit_all(lambda d:views.append(d) if isinstance(d,renpy.display.viewport.Viewport) else None)
                for viewport in views:
                    viewport.yadjustment.change(min(viewport.yadjustment.range,700))
                    renpy.display.render.invalidate(viewport)
                renpy.display.render.invalidate(displayable)
                scroll_render=renpy.display.render.render(displayable,1920,1080,.6,.6)
                pygame.image.save(renpy.display.draw.render_to_texture(scroll_render,True),os.path.join(config.basedir,'pacing-scrolled.png'))
            if filename == "inventory":
                import dg_inventory
                buttons = []
                displayable.visit_all(lambda d: buttons.append(d) if isinstance(d, renpy.display.behavior.Button) else None)
                results = [renpy.display.behavior.run(d.clicked) for d in buttons if isinstance(d.clicked, Return)]
                if False not in results or any(result is True for result in results):
                    raise ValueError("Inventory cancellation did not return False")
                commands = [dg_inventory.command(result) for result in results if result is not False]
                if not commands or any(command is None for command in commands):
                    raise ValueError("Inventory buttons did not return valid commands")
                escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=u'', repeat=False)
                if displayable.event(escape, 0, 0, .3) is not False:
                    raise ValueError("Inventory Escape did not cancel")
                print("Checked actual inventory buttons and Escape: valid commands or False")
            if filename in ("input", "editor"):
                # Synthetic clipboard, never reads or writes the user's clipboard.
                inputs = []
                displayable.visit_all(lambda d: inputs.append(d) if isinstance(d, renpy.display.behavior.Input) else None)
                if len(inputs) != 1:
                    raise ValueError("Expected one production input")
                widget = inputs[0]
                old_get = pygame.scrap.get
                try:
                    pygame.scrap.get = lambda kind: u"Проверка вставки".encode("utf-8")
                    widget.editable = True
                    widget.update_text(u"Начало конец", True)
                    widget.caret_pos = 7
                    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v, mod=pygame.KMOD_CTRL, unicode=u'v', repeat=False)
                    try:
                        widget.event(event, 0, 0, .3)
                    except renpy.display.core.IgnoreEvent:
                        pass
                    if widget.content != u"Начало Проверка вставкиконец":
                        raise ValueError("Ctrl+V failed at caret: " + repr(widget.content))
                    pygame.scrap.get = lambda kind: (u"я" * 9000).encode("utf-8")
                    try:
                        widget.event(event, 0, 0, .3)
                    except renpy.display.core.IgnoreEvent:
                        pass
                    if len(widget.content) != (8000 if filename == "editor" else 4000):
                        raise ValueError("Paste length limit failed")
                    before = widget.content
                    wheel = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=4, pos=(0,0), mod=0, repeat=False)
                    try:
                        displayable.event(wheel, 0, 0, .3)
                    except renpy.display.core.IgnoreEvent:
                        pass
                    else:
                        raise ValueError("Rollback wheel escaped input screen")
                    if widget.content != before:
                        raise ValueError("Wheel changed draft")
                    print("Checked Ctrl+V at caret, field length limit and rollback wheel")
                finally:
                    pygame.scrap.get = old_get
            pygame.image.save(surface, os.path.join(config.basedir, filename + ".png"))
            print("Rendered " + filename)
        return False

    renpy.arguments.register_command("ui-render", ui_render_check, uses_display=False)

screen dg_chrome(place_name, back=None):
    text place_name xpos 100 ypos 50 color "#ffffff" size 24
    if back is not None:
        textbutton u"Назад" xpos 1650 ypos 50 action back

label dg_ui_flow_done:
    return

screen dg_ui_consistent_choice(items):
    use dg_ui_consistent_dialogue
    use dg_rpg_choice(items)

screen dg_ui_consistent_dialogue:
    add dg_rpg_bg()
    add dg_rpg_sprite("mi","smile","normal") xpos .28 xanchor .5 ypos 1.0 yanchor 1.0
    add dg_rpg_sprite("dv","normal","normal") xpos .72 xanchor .5 ypos 1.0 yanchor 1.0
    use dg_rpg_say(u"Алиса",u"Правда. Особенно если знакомство начинается с футляра и загадочного следа.")

screen dg_ui_native_scene:
    add "images/bg/int_dining_hall_people_day.jpg"
    for who, x in dg_stage.positions(["un", "mi", "sl", "dv"], "dv"):
        add dg_rpg_sprite(who, "smile", "normal") xpos x xanchor .5 ypos 1.0 yanchor 1.0
    add "images/gui/dialogue_box/day/dialogue_box.png" xpos 174 ypos 916
    text u"Алиса" style "dg_camp_name" color "#ffaa00" xpos 204 ypos 924
    text u"«Костры»!" style "dg_camp_narration" xpos 204 ypos 962

screen dg_ui_emotions:
    add "images/bg/int_dining_hall_people_day.jpg"
    for index, emotion in enumerate(("angry","laugh","sad","shy")):
        add dg_rpg_sprite("mi",emotion,"normal") xpos (.15+index*.23) xanchor .5 ypos 1.0 yanchor 1.0
        text emotion xpos (150+index*440) ypos 55 size 36 color "#ffe0a2"

screen dg_ui_staging:
    add "images/bg/int_dining_hall_people_day.jpg"
    add dg_rpg_sprite("mi", "normal", "normal", "1") xpos .28 xanchor .5 ypos 1.0 yanchor 1.0
    add dg_rpg_sprite("mi", "smile", "close", "2") xpos .72 xanchor .5 ypos 1.0 yanchor 1.0
    add Solid("#071914d0") xpos 40 ypos 30 xsize 1840 ysize 80
    text u"Проверка ресурсов: средний план / поза 1 — крупный план / поза 2" font "fonts/calibri.ttf" size 30 color "#f3d887" xpos 70 ypos 50

screen dg_ui_cg:
    add Solid("#000000")
    add dg_rpg_fit_cg(dg_ui_cg) align (.5,.5)

'''

if __name__ == "__main__":
    main()

