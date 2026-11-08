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
    parser.add_argument("--out", type=Path, default=Path("work/ui-smoke"))
    parser.add_argument("--assets", type=Path, help="Private gen_assets root or maps directory")
    parser.add_argument("--workshop", type=Path, help="Installed 7DL Complete Edition Workshop root")
    parser.add_argument("--vanilla", type=Path, help="Vanilla game directory containing archive.rpa, for the scene preview")
    parser.add_argument("--screen", choices=("hub", "controls", "setup", "input", "review", "map", "places", "cabins", "journal", "picker", "scene"))
    parser.add_argument("--place", default="cabins", help="Actual RPG location for the preview")
    parser.add_argument("--slot", type=int, choices=range(4), default=0, help="0 morning, 1 day, 2 evening, 3 night")
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
    helper_names = {"dg_sprite_layer_map", "dg_7dl_sprite_layer", "dg_7dl_sprite_poses", "dg_7dl_sprite_displayable"}
    helpers = [ast.get_source_segment(init_source, node) for node in parsed.body if isinstance(node, ast.FunctionDef) and node.name in helper_names]
    (game / "sprite_helpers.rpy").write_bytes(('init 1050 python:\n    import re\n' + textwrap.indent('\n\n'.join(helpers), '    ') + '\n').encode('utf-8'))
    styles = base[base.index("style dg_text:"):base.index("screen dg_scene(")]
    (game / "styles.rpy").write_bytes(styles.encode("utf-8"))
    (game / "test.rpy").write_bytes(HARNESS.encode("utf-8"))
    env = dict(os.environ)
    env["DG_UI_SCREEN"] = args.screen or ""
    env["DG_UI_WORKSHOP"] = str(args.workshop.resolve()) if args.workshop else ""
    env["DG_UI_VANILLA"] = str(args.vanilla.resolve()) if args.vanilla else ""
    env["DG_UI_PLACE"] = args.place
    env["DG_UI_SLOT"] = str(args.slot)
    subprocess.run([str(runner), str(sdk / "renpy.py"), str(output), "ui-render"], check=True, env=env)
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
        store.dg_rpg_state = dg_rpg.new_game(u"Тестовый герой", 23, 30)
        store.dg_rpg_scene_context = dg_stage.freeze(store.dg_rpg_state)
        if dg_rpg_say_character("dv").name != u"Алиса" or dg_rpg_say_character("hero").name != u"Тестовый герой":
            raise ValueError("Incorrect native character names")
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
        store.dg_create_name = u"Тестовый герой"
        store.dg_create_age = u"23"
        store.dg_create_days = u"30"
        store.dg_create_history = u"Длинная предыстория. " * 100
        store.dg_create_source = "vanilla"
        store.dg_create_pronouns = u"он/его"
        store.dg_create_adult = False
        store.dg_rpg_action_draft = u"Помочь подготовить выступление. " * 100
        plan = dg_hybrid.preview(store.dg_rpg_state, store.dg_rpg_action_draft)
        cases = [("hub", "dg_rpg_hub", {}), ("controls", "dg_rpg_controls", {}), ("setup", "dg_rpg_setup", {}),
                 ("input", "dg_rpg_hybrid_input", {"mode":"free"}),
                 ("review", "dg_rpg_hybrid_review", {"plan":plan}),
                 ("map", "dg_rpg_map", {}), ("places", "dg_rpg_places", {}),
                 ("cabins", "dg_rpg_cabins", {"region":"cabins"}),
                 ("journal", "dg_rpg_journal", {}), ("picker", "dg_rpg_picker", {})]
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
        for filename, name, scope in cases:
            if os.environ.get("DG_UI_SCREEN") and os.environ["DG_UI_SCREEN"] != filename:
                continue
            screen = renpy.display.screen.get_screen_variant(name)
            displayable = renpy.display.screen.ScreenDisplayable(screen, name, "screens", scope={"_args":(), "_kwargs":scope})
            displayable.per_interact()
            displayable.visit_all(lambda d: d.per_interact())
            render = renpy.display.render.render(displayable, 1920, 1080, 0.0, 0.0)
            surface = renpy.display.draw.render_to_texture(render, True)
            def debug_viewport(d):
                if isinstance(d, renpy.display.viewport.Viewport):
                    if d.width <= 0 or d.height <= 0:
                        raise ValueError(filename + ": empty viewport")
            displayable.visit_all(debug_viewport)
            pygame.image.save(surface, os.path.join(config.basedir, filename + ".png"))
            print("Rendered " + filename)
        return False

    renpy.arguments.register_command("ui-render", ui_render_check, uses_display=False)

screen dg_chrome(place_name, back=None):
    text place_name xpos 100 ypos 50 color "#ffffff" size 24
    if back is not None:
        textbutton u"Назад" xpos 1650 ypos 50 action back

screen dg_ui_native_scene:
    add "images/bg/int_dining_hall_people_day.jpg"
    for who, x in dg_stage.positions(["un", "mi", "sl", "dv"], "dv"):
        add dg_rpg_sprite(who, "smile", "normal") xpos x xanchor .5 ypos 1.0 yanchor 1.0
    add "images/gui/dialogue_box/day/dialogue_box.png" xpos 174 ypos 916
    text u"Алиса" font "fonts/calibri.ttf" size 28 color "#ffaa00" xpos 204 ypos 924
    text u"«Костры»!" font "fonts/calibri.ttf" size 28 color "#f3ddb1" xpos 204 ypos 962

'''

if __name__ == "__main__":
    main()
