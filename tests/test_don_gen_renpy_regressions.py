# -*- coding: utf-8 -*-
"""Real Ren'Py 7.4.11 traceback regressions reported by DON-GEN playtester."""
from __future__ import unicode_literals
import ast
import os
import re
import sys
import tempfile
import shutil
import unittest

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
sys.path.insert(0,os.path.join(ROOT,"don_gen"))
import dg_rpg
import dg_art
import dg_hybrid

SCRIPT_PATH=os.path.join(ROOT,"don_gen","dg_rpg.rpy")
with open(SCRIPT_PATH,"rb") as handle:
    SCRIPT=handle.read().decode("utf-8")

class ReportedTracebacks(unittest.TestCase):
    def setUp(self):
        self.state=dg_rpg.new_game(u"Игорь",18,39,u"Новичок в лагере")
        self.root=tempfile.mkdtemp(prefix="dg-renpy-")
    def tearDown(self):
        shutil.rmtree(self.root)

    def test_text_input_accepts_utf8_bytes_as_from_renpy_py2(self):
        command=u"Исследовать неизвестные рукописи"
        self.assertEqual(dg_hybrid._clean_action(command.encode("utf-8")),command)
        plan=dg_hybrid.preview(self.state,command.encode("utf-8"),"free")
        self.assertEqual(plan["status"],"ready")
        self.assertEqual(self.state["slot"],0)

    def test_invalid_utf8_can_be_handled_without_mutating_save(self):
        snapshot=self.state.copy()
        with self.assertRaises(UnicodeDecodeError):
            dg_hybrid._clean_action(b"\xff\xfe\xff")
        self.assertEqual(snapshot,self.state)

    def test_cg_id_from_sha1_hexdigest_is_accepted(self):
        prose=u"Мику и Алиса спорят перед концертом, пока Игорь пытается помочь договориться и успокоить обоих."
        plan=dg_art.scene_plan(self.state,"ai",u"Репетиция",prose,"mi")
        self.assertEqual(len(plan["key"]),40)
        self.assertEqual(dg_rpg.asset_path(self.root,self.state["id"],plan["kind"],plan["key"]),
                         "_rpg/assets/%s/cg_%s.png" % (self.state["id"],plan["key"]))

    def test_python2_str_accepted_even_if_text_type_is_distinct(self):
        class PretendUnicode(str):
            pass
        plan=dg_art.scene_plan(self.state,"world",u"День",u"В этот день ребята отправляются на прогулку и спорят о музыкальном концерте в лагере.","mi")
        original=dg_rpg.text_type
        try:
            # Simulate the Python 2 str/unicode type distinction only at the
            # CG key check, without disrupting unrelated name/save validators.
            dg_rpg.text_type=PretendUnicode
            self.assertIn("/cg_",dg_art.asset_location(self.root,self.state["id"],"cg",plan["key"]))
        finally:
            dg_rpg.text_type=original

    def test_edit_and_hybrid_fields_do_not_call_shadowed_min_max(self):
        self.assertIn('def dg_rpg_preview_height(value, low, high, base, chars_per_row, row_height):',SCRIPT)
        for snippet in ("min(365", "min(310", "min(300", "max(195", "max(140"):
            self.assertNotIn(snippet,SCRIPT)
        for screen in ("screen dg_rpg_edit_field(", "screen dg_rpg_hybrid_input(",
                       "screen dg_rpg_free_input:"):
            self.assertIn(screen,SCRIPT)

    def test_hybrid_plan_created_on_errors_not_undefined(self):
        self.assertIn("default dg_rpg_hybrid_plan = None",SCRIPT)
        self.assertIn('store.dg_rpg_hybrid_plan = plan',SCRIPT)
        self.assertIn('if not isinstance(dg_rpg_hybrid_plan, dg_rpg.DICT_TYPE):',SCRIPT)
        self.assertIn('except (ValueError, TypeError, UnicodeError) as exc:',SCRIPT)

    def test_native_dialogue_used_for_all_story_paths(self):
        for expected in ('label dg_rpg_vn_text(scene_text, who=None):',
                         'scene expression dg_rpg_bg()',
                         'renpy.say(dg_rpg_say_character(dg_rpg_vn_turn["who"]), dg_rpg_vn_line)',
                         'label dg_rpg_vn_choice(story_text, choice_pairs, who=None, scene_identity=None):',
                         'renpy.display_menu',
                         'call dg_rpg_vn_dialogue(dg_rpg_focus, "topics")',
                         'call dg_rpg_vn_scene(dg_runtime.app.result, True, dg_rpg_focus)',
                         'call dg_rpg_vn_scene(dg_rpg_last_world["text"], True, dg_world_active["npc"], "outcome:"+dg_world_active["id"]+":"+dg_rpg_world_stance)',
                         'call dg_rpg_vn_scene(dg_rpg_hybrid_entry["scene"] or dg_rpg_hybrid_entry["result"])'):
            self.assertIn(expected,SCRIPT)
        self.assertIn('renpy.show("dg_actor_" + who',SCRIPT)
        self.assertIn('__cancel__',SCRIPT)
        for outdated in ('call screen dg_rpg_read_scene(', 'call screen dg_rpg_world_result(',
                         'call screen dg_rpg_hybrid_read('):
            self.assertNotIn(outdated,SCRIPT)

    def test_classic_map_cabin_numbers_match_the_roofs(self):
        import dg_map
        houses=dict((name,(x,y)) for name,x,y in dg_map.CLASSIC_CABINS)
        self.assertEqual(len(houses),31)
        self.assertEqual(houses["cabin_12"],(1045,276))
        self.assertEqual(houses["cabin_13"],(831,176))
        self.assertEqual(houses["cabin_23"],(735,643))
        self.assertEqual(houses["cabin_31"],(514,790))
        for slug,rect in dg_map.regions():
            x,y,w,h=rect
            self.assertTrue(0<=x<x+w<=1920 and 0<=y<y+h<=1080)
            self.assertIn(slug,dg_rpg.PLACE_NAMES)
        self.assertIn('hotspot rect:',SCRIPT)
        self.assertIn('action Return(("go", slug))',SCRIPT)

    def test_right_npc_panel_not_one_overwide_row(self):
        self.assertNotIn('textbutton u"Своя реплика + AI"',SCRIPT)
        self.assertIn('textbutton u"Особая AI-сцена"',SCRIPT)
        self.assertIn('xpos 1172 ypos 178 xsize 700 ysize 736',SCRIPT)
        self.assertIn('xsize 608 spacing 22',SCRIPT)

if __name__=="__main__":
    unittest.main()

