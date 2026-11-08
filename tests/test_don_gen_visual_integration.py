# -*- coding: utf-8 -*-
"""Tests for real Ren'Py 7.4 crash reports and native image selection."""
from __future__ import unicode_literals
import os,sys,unittest,copy
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
sys.path.insert(0,os.path.join(ROOT,"don_gen"))
import dg_visual,dg_art,dg_rpg
with open(os.path.join(ROOT,"don_gen","dg_rpg.rpy"),"rb") as f:
    SCRIPT=f.read().decode("utf-8")

class VisualRegressionTests(unittest.TestCase):
    def setUp(self):
        self.state=dg_rpg.new_game(u"Игорь",18,39)
    def test_real_renpy_7_solid_signature(self):
        self.assertIn('idle Solid("#ffffff01", xysize=(27, 26))',SCRIPT)
        self.assertIn('hover Solid("#ffe0a990", xysize=(27, 26))',SCRIPT)
        self.assertNotIn('Solid("#ffffff01", 27, 26)',SCRIPT)
        self.assertNotIn('Solid("#ffe0a990", 27, 26)',SCRIPT)
    def test_no_old_gate_overlay_inside_novel(self):
        self.assertIn('renpy.hide_screen("dg_scene")',SCRIPT)
        self.assertNotIn('    $ dg_place("gate")',SCRIPT)
        self.assertIn('scene expression dg_rpg_bg()',SCRIPT)
        self.assertIn('renpy.show("dg_actor_" + who',SCRIPT)
        self.assertIn('dg_stage.positions(cast_ids, turn["who"])',SCRIPT)
        self.assertNotIn('focus_mask False',SCRIPT)
    def test_cg_frozen_payload_per_thread_and_validated(self):
        plan=dg_art.scene_plan(self.state,"ai",u"Неоконченная песня",
            u"Мику остановилась у сцены. В свете фонарей она показала герою свои черновые ноты и попросила помочь с репетицией.","mi")
        self.assertIsNotNone(plan)
        payload=dg_art.freeze_scene_request(plan)
        original=copy.deepcopy(plan)
        plan["kind"]="background"
        self.assertEqual(dg_art.validate_scene_request(self.state,"cg",payload),original)
        for kind in ("background","cg18"):
            with self.assertRaises(ValueError):
                dg_art.validate_scene_request(self.state,kind,payload)
        with self.assertRaises(ValueError):
            dg_art.validate_scene_request(self.state,"cg","invalid JSON")
        with self.assertRaises(ValueError):
            dg_art.validate_scene_request(self.state,"cg",{"kind":"cg","key":"bad"})
        st=copy.deepcopy(self.state);st["day"]+=1
        with self.assertRaises(ValueError):
            dg_art.validate_scene_request(st,"cg",payload)
        self.assertIn('dg_art.freeze_scene_request(dg_cg_plan)',SCRIPT)
        self.assertIn('dg_art.validate_scene_request(state,kind,key)',SCRIPT)
    def test_original_sprite_order_respects_actual_emotion_and_distance(self):
        available=["mi normal pioneer","mi smile pioneer",
                   "mi cry pioneer close","mi smile pioneer close",
                   "mi sad pioneer far","mi normal dress far",
                   "dv normal pioneer"]
        result=dg_visual.sprite_names("mi","smile","close",available)
        self.assertEqual(result[0],"mi smile pioneer close")
        result=dg_visual.sprite_names("mi","sad","far",available)
        self.assertEqual(result[0],"mi sad pioneer far")
        self.assertFalse(dg_visual.sprite_names("sh","smile","normal",available))
        self.assertIn("mi smile pioneer close",dg_visual.sprite_queries("mi","smile","close"))
    def test_emotional_and_physical_position_cues(self):
        self.assertEqual(dg_visual.mood(u"Мику улыбнулась"),"smile")
        self.assertEqual(dg_visual.mood(u"Алиса рассердилась и нахмурилась"),"angry")
        self.assertEqual(dg_visual.distance(u"Она придвинулась вплотную"),"close")
        self.assertEqual(dg_visual.distance(u"Мику отступила"),"far")
        self.assertEqual(dg_visual.distance(u"Мику стояла у сцены"),"normal")
    def test_bg_time_and_place_specific(self):
        day=dg_visual.background_names("bg ext_stage_normal_day",1)
        night=dg_visual.background_names("bg ext_stage_normal_day",3)
        self.assertEqual(day[0],"bg ext_stage_normal_day")
        self.assertEqual(night[0],"bg ext_stage_normal_night")
        self.assertIn("bg ext_stage_normal_day",night)
        self.assertNotIn("bg ext_camp_entrance_day",night)
        self.assertIn('DG_RPG_BG.get(place)',SCRIPT)
        self.assertIn('dg_visual.background_names',SCRIPT)
    def test_consequences_submission_tag_is_explicit(self):
        self.assertIn('Return(("submit", action_text.strip()))',SCRIPT)
        self.assertIn('dg_rpg_hybrid_submission[0] != "submit"',SCRIPT)
        self.assertIn('Hybrid input submitted mode=',SCRIPT)
    def test_hub_has_compact_tabs_and_native_dialogues(self):
        self.assertIn('default dg_hub_tab = "story"',SCRIPT)
        for label in (u"ИСТОРИЯ",u"ДЕЙСТВИЯ",u"НАСТРОЙКИ"):
            self.assertIn(label,SCRIPT)
        self.assertIn('action SetScreenVariable("dg_hub_tab","actions")',SCRIPT)

if __name__=="__main__":
    unittest.main()

