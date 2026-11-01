# -*- coding: utf-8 -*-
"""Offline game engine regression tests; no Ren'Py, network or ChatGPT required."""
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "don_gen"))
import dg_rpg


class DONGENTests(unittest.TestCase):
    def test_standalone_mod_metadata(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(root, "don_gen", "don_gen.rpy"), "rb") as f:
            script = f.read().decode("utf-8")
        with open(os.path.join(root, "install.ps1"), "rb") as f:
            installer = f.read().decode("utf-8")
        self.assertIn('mods["don_gen"]', script)
        self.assertIn("label don_gen:", script)
        self.assertIn("label dg_rpg_main:", open(os.path.join(root, "don_gen", "dg_rpg.rpy"), "rb").read().decode("utf-8"))
        self.assertNotIn('mods["generative_summer"]', script)
        self.assertIn('Join-Path $Mods "don_gen"', installer)
        self.assertNotIn('ready_replace', installer)
        self.assertNotIn('community_fix_backup_', installer)

    def test_character_fields_have_explicit_edit_actions(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(root, "don_gen", "dg_rpg.rpy"), "rb") as stream:
            script = stream.read().decode("utf-8")
        for field in ("name", "age", "days", "history"):
            self.assertIn('Return(("edit", "' + field + '"))', script)
        self.assertIn('label dg_rpg_create_loop:', script)
        self.assertIn('screen dg_rpg_edit_field(field, current):', script)
        self.assertIn('call screen dg_rpg_edit_field(dg_edit_name, dg_edit_current)', script)
        self.assertIn('value ScreenVariableInputValue("editor_text")', script)
        self.assertIn('allow "0123456789"', script)
        self.assertIn('background Solid("#071b25")', script)
        self.assertNotIn('renpy.input(u"Имя персонажа:"', script)
        self.assertIn('sensitive dg_valid', script)
        self.assertNotIn('ScreenVariableInputValue("age")', script)
        self.assertNotIn('ScreenVariableInputValue("days")', script)

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="gs-rpg-")
        self.state = dg_rpg.new_game("Новый герой", 23, 14, "Музыкант")

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_profile_and_duration_validation(self):
        self.assertEqual(self.state["hero"]["name"], "Новый герой")
        self.assertEqual(self.state["hero"]["age"], 23)
        self.assertEqual(self.state["duration"], 14)
        for age, days in ((13, 7), (81, 7), (18, 0), (18, 121)):
            with self.assertRaises(ValueError):
                dg_rpg.new_game("Герой", age, days)
        with self.assertRaises(ValueError):
            dg_rpg.new_game("../escape", 18, 7, "bad\nhistory")

    def test_free_travel_does_not_call_ai_or_pass_time(self):
        self.state["social"]["incident"]["status"] = "resolved"
        dg_rpg.move(self.state, "square")
        self.assertEqual(self.state["day"], 1)
        self.assertEqual(self.state["slot"], 0)
        self.assertIn(("sl", "Славя"), dg_rpg.at_place(self.state))

    def test_schedule_moves_characters(self):
        self.state["social"]["incident"]["status"] = "resolved"
        self.assertEqual(dg_rpg.where_is(self.state, "mi"), "stage")
        dg_rpg.activity(self.state, "rest")
        self.assertEqual(dg_rpg.where_is(self.state, "mi"), "clubs")
        dg_rpg.activity(self.state, "rest")
        self.assertEqual(dg_rpg.where_is(self.state, "mi"), "stage")

    def test_relationship_milestones_and_route_choice(self):
        self.state["social"]["incident"]["status"] = "resolved"
        dg_rpg.move(self.state, "square")
        dg_rpg.activity(self.state, "talk", "sl")
        self.assertEqual(self.state["affinity"]["sl"], 8)
        self.assertEqual(self.state["slot"], 1)
        self.state["slot"] = 0
        dg_rpg.activity(self.state, "talk", "sl")
        self.assertIn("sl:10", self.state["milestones"])
        self.state["slot"] = 0
        choices = dg_rpg.available_route_events(self.state, "sl")
        self.assertEqual(choices[0][0], 10)
        dg_rpg.route_event(self.state, "sl", "support")
        self.assertIn("sl:10", self.state["route_events_done"])
        self.assertGreaterEqual(self.state["affinity"]["sl"], 17)
        self.assertFalse(dg_rpg.available_route_events(self.state, "sl"))

    def test_quests_and_time_limit(self):
        dg_rpg.activity(self.state, "help")
        dg_rpg.activity(self.state, "help")
        dg_rpg.activity(self.state, "help")
        self.assertIn("help", self.state["quests_done"])
        short = dg_rpg.new_game("Герой", 18, 1)
        for _ in range(4):
            dg_rpg.activity(short, "rest")
        self.assertEqual(short["day"], 2)
        self.assertTrue(short["finished"])
        self.assertIsNone(dg_rpg.where_is(short, "sl"))

    def test_persistent_save_and_fallback(self):
        dg_rpg.save(self.root, self.state)
        dg_rpg.move(self.state, "beach")
        dg_rpg.save(self.root, self.state)
        self.assertEqual(dg_rpg.load(self.root, self.state["id"])["place"], "beach")
        self.assertEqual(len(dg_rpg.list_games(self.root)), 1)
        with open(dg_rpg._path(self.root, self.state["id"]), "wb") as fp:
            fp.write(b"broken-json")
        self.assertEqual(dg_rpg.load(self.root, self.state["id"])["place"], "gate")

    def test_asset_path_security_and_alpha_png(self):
        def chunk(tag, data):
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
        # Real 256x256 transparent RGBA PNG.
        ihdr = struct.pack(">IIBBBBB", 256, 256, 8, 6, 0, 0, 0)
        pixels = b"".join(b"\x00" + b"\x00\x00\x00\x00" * 256 for _ in range(256))
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")
        rel = dg_rpg.save_asset(self.root, self.state["id"], "sprite", "mi", png)
        self.assertTrue(os.path.isfile(os.path.join(self.root, *rel.split("/"))))
        with self.assertRaises(ValueError):
            dg_rpg.asset_path(self.root, self.state["id"], "sprite", "../mi")
        with self.assertRaises(ValueError):
            dg_rpg.save_asset(self.root, self.state["id"], "sprite", "mi", b"not png")


if __name__ == "__main__":
    unittest.main()
