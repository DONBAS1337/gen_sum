# -*- coding: utf-8 -*-
"""Offline RPG conversations and map UI regression tests."""
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "don_gen"))
import dg_rpg
import dg_dialogue


class DialogueTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp(prefix="don-gen-dialogue-")
        self.state = dg_rpg.new_game(u"Игорь", 23, 39, u"Новичок")

    def tearDown(self):
        shutil.rmtree(self.directory)

    def test_every_character_has_interactive_branches(self):
        self.assertEqual(set(dg_rpg.NPC_NAMES), set(dg_dialogue.CHARACTERS))
        for who in dg_rpg.NPC_NAMES:
            introduction = dg_dialogue.opening(self.state, who)
            self.assertGreaterEqual(len(introduction["text"]), 80)
            self.assertGreaterEqual(len(introduction["options"]), 2)
            for ident, name in introduction["options"]:
                scene = dg_dialogue.topic(self.state, who, ident)
                self.assertGreater(len(scene["text"]), 130)
                self.assertEqual(len(scene["options"]), 3)
                answers = []
                for choice, caption in scene["options"]:
                    self.assertGreater(len(caption), 15)
                    output = dg_dialogue.outcome(self.state, who, ident, choice)
                    self.assertGreater(len(output["text"]), 120)
                    answers.append(output["text"])
                self.assertEqual(len(set(answers)), 3)

    def test_conversation_updates_stats_affinity_and_journal(self):
        self.state["social"]["incident"]["status"] = "resolved"
        dg_rpg.move(self.state, "clubs")
        self.assertEqual(dg_rpg.where_is(self.state, "mi"), "stage")
        self.state["slot"] = 1
        self.assertEqual(dg_rpg.where_is(self.state, "mi"), "clubs")
        out = dg_rpg.conversation(self.state, "mi", 0, "support")
        self.assertEqual(out["affinity_gain"], 10)
        self.assertEqual(self.state["affinity"]["mi"], 10)
        self.assertEqual(self.state["stats"]["kindness"], 2)
        self.assertIn("mi:10", self.state["milestones"])
        self.assertIn("mi", self.state["met"])
        self.assertEqual(len(self.state["dialogue_history"]), 1)
        self.assertEqual(self.state["slot"], 2)
        dg_rpg.save(self.directory, self.state)
        loaded = dg_rpg.load(self.directory, self.state["id"])
        self.assertEqual(loaded["dialogue_history"][0]["topic"], u"Музыка")
        loaded["slot"] = 1
        self.assertTrue(dg_rpg.summary_for_ai(loaded, "mi", u"Поговорить")["recent_dialogue"])

    def test_repeated_same_day_talk_has_diminishing_returns(self):
        self.state["social"]["incident"]["status"] = "resolved"
        dg_rpg.move(self.state, "clubs")
        self.state["slot"] = 1
        dg_rpg.conversation(self.state, "el", 1, "curious")
        first = self.state["affinity"]["el"]
        self.state["slot"] = 1
        dg_rpg.conversation(self.state, "el", 0, "support")
        self.assertEqual(self.state["affinity"]["el"] - first, 1)
        self.assertEqual(self.state["stats"]["curiosity"], 2)

    def test_bad_or_remote_conversation_rejected(self):
        dg_rpg.move(self.state, "gate")
        with self.assertRaises(ValueError):
            dg_rpg.conversation(self.state, "mi", 0, "support")
        with self.assertRaises(ValueError):
            dg_dialogue.outcome(self.state, "mi", 99, "support")
        with self.assertRaises(ValueError):
            dg_dialogue.outcome(self.state, "mi", 1, "invalid")

    def test_route_scenes_have_real_choices(self):
        for who in dg_rpg.NPC_NAMES:
            for milestone in dg_rpg.MILESTONES:
                scene = dg_dialogue.route_intro(self.state, who, milestone)
                self.assertGreater(len(scene["text"]), 150)
                self.assertEqual(len(scene["options"]), 3)
                outcomes = [dg_dialogue.route_conclusion(who, milestone, choice)
                            for choice, title in scene["options"]]
                self.assertEqual(len(set(outcomes)), 3)

    def test_diary_has_persistent_dialogue_and_ai_tabs(self):
        folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "don_gen"))
        with open(os.path.join(folder, "dg_rpg.rpy"), "rb") as fh:
            script = fh.read().decode("utf-8")
        self.assertIn('SetScreenVariable("view", "talks")', script)
        self.assertIn('SetScreenVariable("view", "ai")', script)
        self.assertIn('dg_rpg_state.get("dialogue_history", [])', script)
        self.assertNotIn('min(progress, goal)', script)

    def test_map_is_based_on_original_user_supplied_image(self):
        folder = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "don_gen"))
        with open(os.path.join(folder, "dg_rpg.rpy"), "rb") as fh:
            script = fh.read().decode("utf-8")
        self.assertIn('DG_RPG_MAP_IMAGE = "mods/don_gen/images/camp_map.png"', script)
        self.assertIn('("gate",175,640)', script)
        self.assertIn('DG_MAP_ATLAS = "mods/don_gen/images/don_gen_atlas.png"', script)
        self.assertIn('action Return(("cabins", slug) if slug in', script)
        self.assertIn('else ("go", slug))', script)
        self.assertIn('screen dg_rpg_dialogue(who, phase', script)
        self.assertIn('Return(("talk", who))', script)
        self.assertNotIn('min(progress, goal)', script)


if __name__ == "__main__":
    unittest.main()
