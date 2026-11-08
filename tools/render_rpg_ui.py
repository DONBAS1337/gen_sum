# -*- coding: utf-8 -*-
"""Render RPG screens in RenPy 7 without opening a window or using game saves.

Usage: python tools/render_rpg_ui.py --sdk PATH_TO_RENPY_7_SDK
Outputs use placeholders for vanilla backgrounds/sprites and for authentication.
The render exercises actual RPG screen code, not an HTML recreation.
"""
import argparse
from pathlib import Path
import os
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("work/ui-smoke"))
    parser.add_argument("--assets", type=Path, help="Private gen_assets root or maps directory")
    parser.add_argument("--screen", choices=("hub", "setup", "input", "review", "map", "places", "cabins", "journal", "picker"))
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
    styles = base[base.index("style dg_text:"):base.index("screen dg_scene(")]
    (game / "styles.rpy").write_bytes(styles.encode("utf-8"))
    (game / "test.rpy").write_bytes(HARNESS.encode("utf-8"))
    env = dict(os.environ)
    env["DG_UI_SCREEN"] = args.screen or ""
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

init 1100 python:
    class TestClient(object):
        def authenticated(self):
            return True
    class TestApp(object):
        client = TestClient()
    class TestRuntime(object):
        app = TestApp()
    dg_runtime = TestRuntime()
    DG_PAPER = Solid("#f3e6cf")
    def dg_literal(value):
        return value.replace("{", "{{").replace("[", "[[")
    def dg_rpg_root():
        return os.path.join(config.gamedir, "test-saves")
    def dg_rpg_bg():
        return Solid("#253f42")
    def dg_rpg_sprite(*args):
        return None
    def dg_rpg_bg_status():
        return {"status": "original"}
    def dg_detect_7dl_root():
        return None
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
        assert dg_rpg_say_character("dv").name == u"Алиса"
        assert dg_rpg_say_character("hero").name == u"Тестовый герой"
        dg_rpg.move(store.dg_rpg_state, "cabins")
        store.dg_create_name = u"Тестовый герой"
        store.dg_create_age = u"23"
        store.dg_create_days = u"30"
        store.dg_create_history = u"Длинная предыстория. " * 100
        store.dg_create_source = "vanilla"
        store.dg_create_pronouns = u"он/его"
        store.dg_create_adult = False
        store.dg_rpg_action_draft = u"Помочь подготовить выступление. " * 100
        plan = dg_hybrid.preview(store.dg_rpg_state, store.dg_rpg_action_draft)
        cases = [("hub", "dg_rpg_hub", {}), ("setup", "dg_rpg_setup", {}),
                 ("input", "dg_rpg_hybrid_input", {"mode":"free"}),
                 ("review", "dg_rpg_hybrid_review", {"plan":plan}),
                 ("map", "dg_rpg_map", {}), ("places", "dg_rpg_places", {}),
                 ("cabins", "dg_rpg_cabins", {"region":"cabins"}),
                 ("journal", "dg_rpg_journal", {}), ("picker", "dg_rpg_picker", {})]
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
                    assert d.width > 0 and d.height > 0, filename + ": empty viewport"
            displayable.visit_all(debug_viewport)
            pygame.image.save(surface, os.path.join(config.basedir, filename + ".png"))
            print("Rendered " + filename)
        return False

    renpy.arguments.register_command("ui-render", ui_render_check, uses_display=False)

screen dg_chrome(place_name, back=None):
    text place_name xpos 100 ypos 50 color "#ffffff" size 24
    if back is not None:
        textbutton u"Назад" xpos 1650 ypos 50 action back

'''

if __name__ == "__main__":
    main()
