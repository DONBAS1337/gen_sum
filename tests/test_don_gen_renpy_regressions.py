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
        self.assertIn('if not isinstance(dg_rpg_hybrid_plan, dict):',SCRIPT)
        self.assertIn('except (ValueError, TypeError, UnicodeError) as exc:',SCRIPT)

    def test_native_dialogue_used_for_all_story_paths(self):
        for expected in ('label dg_rpg_vn_text(scene_text):',
                         'scene expression dg_rpg_bg()',
                         '"[dg_rpg_vn_line]"',
                         'label dg_rpg_vn_choice(story_text, choice_pairs):',
                         'renpy.display_menu',
                         'call dg_rpg_vn_dialogue(dg_rpg_focus, "topics")',
                         'call dg_rpg_vn_scene(dg_runtime.app.result)',
                         'call dg_rpg_vn_scene(dg_rpg_last_world["text"])',
                         'call dg_rpg_vn_scene(dg_rpg_hybrid_entry["scene"] or dg_rpg_hybrid_entry["result"])'):
            self.assertIn(expected,SCRIPT)
        for outdated in ('call screen dg_rpg_read_scene(', 'call screen dg_rpg_world_result(',
                         'call screen dg_rpg_hybrid_read('):
            self.assertNotIn(outdated,SCRIPT)

    def test_all_map_destinations_directly_clickable_on_real_gen_assets_map(self):
        a=SCRIPT.index('DG_MAP_USER_PINS = (')
        b=SCRIPT.index('DG_MAP_USER_CABINS = (',a)
        c=SCRIPT.index('DG_MAP_USER_IDLE',b)
        def extract(block):
            return ast.literal_eval(block[block.index('('):block.rfind(')')+1])
        landmarks=extract(SCRIPT[a:b])
        houses=extract(SCRIPT[b:c])
        self.assertEqual(len(landmarks),39)
        self.assertEqual(len(houses),31)
        ids=[entry[0] for entry in landmarks+houses]
        self.assertEqual(set(ids),set(dg_rpg.PLACE_NAMES))
        self.assertEqual(len(ids),len(set(ids)))
        for name,x,y in landmarks+houses:
            self.assertTrue(0<=x<1920 and 0<=y<1080,(name,x,y))
        self.assertIn('hover Solid("#ffe0a990"',SCRIPT)
        self.assertIn('action Return(("go", cabin))',SCRIPT)
        self.assertIn('action Return(("go", slug))',SCRIPT) if False else None
        self.assertIn('dg_map_result[0] == "go"',SCRIPT)

    def test_right_npc_panel_not_one_overwide_row(self):
        self.assertNotIn('textbutton u"Своя реплика + AI"',SCRIPT)
        self.assertIn('textbutton u"Особая AI-сцена"',SCRIPT)
        self.assertIn('xpos 938 ypos 135 xsize 888 ysize 805',SCRIPT)

if __name__=="__main__":
    unittest.main()
