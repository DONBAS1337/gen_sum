# -*- coding: utf-8 -*-
"""Nonlinear world simulation, consequences and old-save compatibility tests."""
import copy
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "don_gen"))
import dg_rpg
import dg_world


class WorldDirectorTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="don-gen-world-")
        self.state = dg_rpg.new_game(u"Игорь", 23, 39, u"Музыкант")

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_day_one_plot_and_location(self):
        event = dg_world.current(self.state)
        self.assertTrue(event)
        self.assertEqual(event["day"], 1)
        self.assertEqual(len(event["choices"]), 3)
        self.assertIn(event["arc"], dg_world.PLOT_ORDER)
        self.assertIn(event["place"], dg_rpg.PLACE_NAMES)
        self.assertGreater(len(event["story"]), 160)
        self.assertIn("world", self.state)

    def test_choices_are_consequential_and_unrepeatable(self):
        source = copy.deepcopy(self.state)
        a, b = copy.deepcopy(source), copy.deepcopy(source)
        where = dg_world.current(a)["place"]
        dg_rpg.move(a, where)
        dg_rpg.move(b, where)
        first = dg_rpg.story_choice(a, "support")
        second = dg_rpg.story_choice(b, "investigate")
        self.assertNotEqual(first["text"], second["text"])
        self.assertGreater(a["world"]["morale"], b["world"]["morale"])
        self.assertGreater(b["world"]["knowledge"], a["world"]["knowledge"])
        self.assertGreater(a["affinity"][first["npc"]], b["affinity"][second["npc"]])
        self.assertEqual(len(a["world"]["decisions"]), 1)
        self.assertIsNone(dg_world.current(a))
        with self.assertRaises(ValueError):
            dg_rpg.story_choice(a, "support")
        self.assertEqual(len(a["world"]["chronicle"]), 1)
        self.assertEqual(a["world"]["tracks"][first["arc"]]["stage"], 1)

    def test_story_decisions_persist_across_saves(self):
        target = dg_world.current(self.state)["place"]
        dg_rpg.move(self.state, target)
        dg_rpg.story_choice(self.state, "independent")
        dg_rpg.save(self.root, self.state)
        restored = dg_rpg.load(self.root, self.state["id"])
        self.assertEqual(restored["world"]["decisions"], self.state["world"]["decisions"])
        self.assertIsNone(dg_world.current(restored))
        self.assertEqual(restored["world"]["tracks"], self.state["world"]["tracks"])

    def test_missed_day_has_penalty_and_next_day_continues(self):
        initial = dg_world.current(self.state)
        old_morale = self.state["world"]["morale"]
        for _ in range(4):
            dg_rpg.activity(self.state, "rest")
        self.assertEqual(self.state["day"], 2)
        self.assertEqual(self.state["world"]["morale"], old_morale - 2)
        self.assertEqual(self.state["world"]["chronicle"][0]["status"], "missed")
        self.assertNotEqual(dg_world.current(self.state)["id"], initial["id"])

    def test_old_save_migrates_without_resetting_relationships(self):
        original = dg_rpg.new_game(u"Маруся", 20, 16)
        original["affinity"]["mi"] = 48
        original["day"] = 7
        del original["world"]
        dg_rpg.save(self.root, original)
        loaded = dg_rpg.load(self.root, original["id"])
        self.assertEqual(loaded["affinity"]["mi"], 48)
        self.assertEqual(loaded["day"], 7)
        self.assertIn("world", loaded)
        self.assertEqual(loaded["world"]["tracks"]["festival"]["stage"], 0)
        self.assertEqual(dg_world.current(loaded)["day"], 7)

    def test_bad_choice_or_remote_event_not_allowed(self):
        event = dg_world.current(self.state)
        with self.assertRaises(ValueError):
            dg_rpg.story_choice(self.state, "fake")
        if event["place"] != "gate":
            with self.assertRaises(ValueError):
                dg_rpg.story_choice(self.state, "support")
        dg_rpg.move(self.state, event["place"])
        with self.assertRaises(ValueError):
            dg_rpg.story_choice(self.state, "fake")

    def test_skills_unlock_additional_branch(self):
        self.state["stats"]["skill"] = 13
        self.state["world"]["event"] = None
        evt = dg_world.current(self.state)
        self.assertIn("specialist", [x["key"] for x in evt["choices"]])
        dg_rpg.move(self.state, evt["place"])
        dg_rpg.story_choice(self.state, "specialist")
        self.assertEqual(self.state["stats"]["skill"], 14)

    def test_all_120_days_and_epilogues(self):
        state = dg_rpg.new_game(u"Игорь", 23, 120)
        for day in range(1, 121):
            self.assertEqual(state["day"], day)
            evt = dg_world.current(state)
            self.assertIsNotNone(evt)
            dg_rpg.move(state, evt["place"])
            dg_rpg.story_choice(state, ("support", "investigate", "independent")[day % 3])
            # Three more time slots complete the day.
            for _ in range(3):
                dg_rpg.activity(state, "rest")
        self.assertTrue(state["finished"])
        self.assertEqual(state["day"], 121)
        self.assertEqual(len(state["world"]["decisions"]), 120)
        for arc in dg_world.PLOT_ORDER:
            self.assertEqual(state["world"]["tracks"][arc]["stage"], 5)
            self.assertIn(u"Завершено", dg_world.story_status(state, arc))
        self.assertIsNone(dg_world.current(state))
        stats = dg_world.world_report(state)
        self.assertEqual(stats["resolved"], 120)
        self.assertEqual(len(stats["tracks"]), 4)

    def test_ending_changes_with_world_and_relationships(self):
        hopeful = copy.deepcopy(self.state)
        difficult = copy.deepcopy(self.state)
        hopeful["world"]["morale"] = 89
        hopeful["world"]["knowledge"] = 93
        hopeful["affinity"]["mi"] = 75
        difficult["world"]["morale"] = 18
        difficult["world"]["freedom"] = 88
        positive = dg_world.finale(hopeful)
        gloomy = dg_world.finale(difficult)
        self.assertIn(u"Мику", positive)
        self.assertNotEqual(positive, gloomy)
        self.assertIn(u"Фестиваль Совёнка", positive)
        self.assertIn(u"Тайна радиокружка", positive)

    def test_daily_motif_variety(self):
        self.assertEqual(len(dg_world.DAILY_MOTIFS), len(dg_world.DAILY_CHOICES))
        self.assertGreaterEqual(len(dg_world.DAILY_MOTIFS), 16)
        for group in dg_world.DAILY_CHOICES:
            self.assertEqual(len(group), 3)
            self.assertEqual(len(set(group)), 3)
        self.assertGreaterEqual(sum(len(x) for x in dg_world.DAILY_CHOICES), 48)

    def test_hero_backstory_is_in_world_story(self):
        self.assertIn(u"Игорь", dg_world.current(self.state)["story"])
        self.assertIn(u"Музыкант", dg_world.current(self.state)["story"])

    def test_weather_changes_npc_evening_schedule(self):
        state = copy.deepcopy(self.state)
        rainy = None
        for day in range(2, 121):
            state["day"] = day
            if dg_world.weather(state)[0] == "rain" and day % 3 != 0:
                rainy = day
                break
        self.assertIsNotNone(rainy)
        state["slot"] = 2
        self.assertEqual(dg_rpg.where_is(state, "mi"), "clubs")
        self.assertIn(dg_world.weather(state)[1], [entry[1] for entry in dg_world.WEATHER])

    def test_ui_has_editor_and_world_story_and_diary(self):
        directory = os.path.join(os.path.dirname(__file__), "..", "don_gen")
        with open(os.path.join(directory, "dg_rpg.rpy"), "rb") as source:
            code = source.read().decode("utf-8")
        self.assertIn("screen dg_rpg_edit_field(field, current):", code)
        self.assertIn('default_focus True', code)
        self.assertIn('background Solid("#071b25")', code)
        self.assertNotIn('renpy.input(u"Возраст', code)
        self.assertIn("screen dg_rpg_world_event:", code)
        self.assertIn("screen dg_rpg_finale:", code)
        self.assertIn("screen dg_rpg_world_result(result):", code)
        self.assertIn('SetScreenVariable("view", "world")', code)
        self.assertIn('dg_rpg_apply("world", dg_rpg_world_stance)', code)


if __name__ == "__main__":
    unittest.main()
