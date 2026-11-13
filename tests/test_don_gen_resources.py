# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "don_gen"))
import dg_resources


class WorkshopResources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp(prefix="dg-resources-")
        self.root = os.path.join(self.temp, "CE resources")
        self.maps = os.path.join(self.root, "scenario_alt", "Pics", "gui", "maps")
        os.makedirs(self.maps)
        self.game = os.path.join(self.temp, "different library", "game")
        self.config = os.path.join(self.temp, "resource_sources.json")

    def tearDown(self):
        shutil.rmtree(self.temp)

    def file(self, name):
        path = os.path.join(self.maps, name)
        with open(path, "wb") as stream:
            stream.write(b"resource fixture")
        return path

    def test_explicit_root_works_across_steam_libraries(self):
        with io.open(self.config, "w", encoding="utf-8") as stream:
            stream.write(u"\ufeff" + json.dumps({"seven_dl_root": self.root}))
        self.assertEqual(dg_resources.detect_root(self.game, self.config, {}), self.root)
        self.assertEqual(dg_resources.valid_root(os.path.join(self.root, "scenario_alt")), self.root)

    def test_environment_has_precedence_over_saved_config(self):
        with io.open(self.config, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"seven_dl_root": "missing"}))
        self.assertEqual(dg_resources.detect_root(self.game, self.config, {"DON_GEN_7DL_ROOT": self.root}), self.root)

    def test_missing_or_corrupt_config_is_optional(self):
        with io.open(self.config, "w", encoding="utf-8") as stream:
            stream.write("not json")
        self.assertIsNone(dg_resources.detect_root(self.game, self.config, {}))
        self.assertIsNone(dg_resources.valid_root(None))
        self.assertIsNone(dg_resources.valid_root(123))

    def test_same_library_workshop_is_found(self):
        game = os.path.join(self.temp, "steamapps", "common", "Everlasting Summer", "game")
        donor = os.path.join(self.temp, "steamapps", "workshop", "content", "331470", dg_resources.WORKSHOP_ID)
        os.makedirs(os.path.join(donor, "scenario_alt", "Pics"))
        self.assertEqual(dg_resources.detect_root(game, environ={}), donor)

    def test_original_numbered_icons_are_mapped_by_character(self):
        miku = self.file("map_icon_n02.png")
        hero = self.file("map_icon_n01.png")
        self.assertEqual(dg_resources.map_icon(self.root, "mi"), miku.replace("\\", "/"))
        self.assertEqual(dg_resources.map_icon(self.root, "hero"), hero.replace("\\", "/"))
        self.assertIsNone(dg_resources.map_icon(self.root, "unknown"))
        self.assertEqual(dg_resources.map_asset(self.root, "map_bg.jpg"), None)
        bg = self.file("map_bg.jpg")
        self.assertEqual(dg_resources.map_asset(self.root, "map_bg.jpg"), bg.replace("\\", "/"))

    def test_only_media_inside_the_donor_root_can_be_resolved(self):
        self.file("script.rpy")
        self.assertIsNone(dg_resources.asset(self.root, "scenario_alt/Pics/gui/maps/script.rpy"))
        self.assertIsNone(dg_resources.asset(self.root, "../outside.jpg"))
        self.assertIsNone(dg_resources.asset(self.root, self.file("absolute.jpg")))

    def test_manifest_paths_are_absolute_without_mounting_scripts(self):
        path = self.file("map_bg.jpg")
        relative = "scenario_alt/Pics/gui/maps/map_bg.jpg"
        manifest = {"backgrounds": {"bg fixture": relative}, "sprite_layers": {"normal": {"mi": {"1": {"body": relative}}}}}
        converted = dg_resources.absolute_assets(self.root, manifest)
        self.assertEqual(converted["backgrounds"]["bg fixture"], path.replace("\\", "/"))
        self.assertNotIn("\\", converted["backgrounds"]["bg fixture"])
        self.assertEqual(converted["sprite_layers"]["normal"]["mi"]["1"]["body"], path.replace("\\", "/"))
        self.assertEqual(manifest["backgrounds"]["bg fixture"], relative)

    def test_night_does_not_use_a_day_only_donor_background(self):
        manifest = {"backgrounds": {"bg ext_warehouse_day_7dl": "day.jpg", "bg ext_warehouse_sunset_7dl": "sunset.jpg"}}
        self.assertEqual(dg_resources.background(manifest, "warehouse", 1), "day.jpg")
        self.assertEqual(dg_resources.background(manifest, "warehouse", 2), "sunset.jpg")
        self.assertIsNone(dg_resources.background(manifest, "warehouse", 3))


if __name__ == "__main__":
    unittest.main()
