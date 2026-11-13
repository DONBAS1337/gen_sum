# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import copy
import os
import sys
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "don_gen"))
import dg_rpg
import dg_stage
import dg_hybrid


class NativeSceneTests(unittest.TestCase):
    def test_named_turns_and_narration_are_separate(self):
        turns = dg_stage.parse(u"[narrator] В столовой тихо.\n[un] Доброе утро.\n[mi] Привет!\n[sl] Вы уже завтракали?\n[dv] Костры!", ("un", "mi", "sl", "dv"))
        self.assertEqual([t["who"] for t in turns], [None, "un", "mi", "sl", "dv"])
        cast = dg_stage.cast(turns, ("un", "mi", "sl", "dv"))
        self.assertEqual(cast, ["un", "mi", "sl", "dv"])
        self.assertEqual(len(dg_stage.positions(cast)), 4)

    def test_long_speech_keeps_speaker_on_every_page(self):
        turns = dg_stage.parse("[dv] " + u"Длинная реплика. " * 80, ("dv",))
        self.assertGreater(len(turns), 2)
        self.assertTrue(all(t["who"] == "dv" and len(t["text"]) <= 240 for t in turns))
        self.assertTrue(all(len(t["text"]) <= 240 for t in dg_stage.parse("x" * 1500)))

    def test_unmarked_prose_does_not_become_npc_speech(self):
        turns = dg_stage.parse(u"Алиса вошла в столовую и остановилась у окна.", ("dv",), "dv")
        self.assertIsNone(turns[0]["who"])
        self.assertEqual(dg_stage.parse(u"Алиса: Костры!", ("dv",))[0]["who"], "dv")
        self.assertEqual(dg_stage.parse(u"«Привет!»", ("dv",), "dv")[0]["who"], "dv")

    def test_model_cannot_summon_absent_character_or_execute_code(self):
        text = u"[uv] Я здесь.\n[python] state.clear()\n[mi] Привет."
        turns = dg_stage.parse(text, ("mi",))
        self.assertEqual([t["who"] for t in turns], [None, None, "mi"])
        self.assertEqual(dg_stage.cast(turns, ("mi",)), ["mi"])
        self.assertIn("state.clear()", turns[1]["text"])

    def test_frozen_scene_survives_time_advancement(self):
        state = dg_rpg.new_game(u"Герой", 18, 7)
        state["slot"] = 3
        context = dg_stage.freeze(state)
        before = copy.deepcopy(context)
        dg_rpg.activity(state, "rest")
        self.assertEqual(state["day"], 2)
        self.assertEqual(context, before)
        self.assertEqual((context["day"], context["slot"]), (1, 3))

    def test_active_speaker_stays_in_crowded_frame(self):
        cast = ["un", "mi", "sl", "dv", "us", "mt"]
        placements = dg_stage.positions(cast, "mt")
        self.assertEqual(len(placements), 5)
        self.assertIn("mt", [who for who, x in placements])
        self.assertEqual(len(set(x for who, x in placements)), 5)
        self.assertEqual(dg_stage.positions([]), [])
        for speaker in cast:
            visible = [who for who, x in dg_stage.positions(cast, speaker, "mt")]
            self.assertEqual(visible, ["mt"] if speaker == "mt" else ["mt", speaker])

    def test_classic_map_has_integer_native_coordinates(self):
        import dg_map
        for slug,rect in dg_map.regions():
            self.assertTrue(all(isinstance(value,int) for value in rect))
            self.assertEqual(len(dg_map.center(rect)),2)

    def test_hybrid_narrator_requests_speaker_markup(self):
        state = dg_rpg.new_game(u"Герой", 18, 7)
        plan = dg_hybrid.preview(state, u"Исследовать местность")
        instructions, payload = dg_hybrid.build_request(state, plan)
        self.assertIn("[narrator]", instructions)
        self.assertIn("[hero]", instructions)
        self.assertIn("[mi]", instructions)

    def test_diary_text_has_names_instead_of_internal_tags(self):
        result = dg_stage.readable(u"[narrator] На площади тихо.\n[dv] Привет!\n[hero] Доброе утро.")
        self.assertNotIn("[narrator]", result)
        self.assertNotIn("[dv]", result)
        self.assertIn(u"Алиса: Привет!", result)
        self.assertIn(u"Герой: Доброе утро.", result)


if __name__ == "__main__":
    unittest.main()
