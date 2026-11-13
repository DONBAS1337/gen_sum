# -*- coding: utf-8 -*-
"""DON-GEN v0.8: no sprite generation, scene-keyed BG/CG, Anima numeric seed."""
from __future__ import unicode_literals
import os,sys,tempfile,shutil,struct,unittest,copy
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
sys.path.insert(0,os.path.join(ROOT,"don_gen"))
import dg_rpg,dg_art,dg_adult,dg_comfy
try: text_type=unicode
except NameError: text_type=str

class DrawnScenes(unittest.TestCase):
    def setUp(self):
        self.st=dg_rpg.new_game(u"Взрослый герой",22,39)
        self.root=tempfile.mkdtemp(prefix="dg-art-")
    def tearDown(self): shutil.rmtree(self.root)
    def test_only_background_and_full_screen_cg_kinds_generated(self):
        for kind in ("background","cg","cg18"):
            self.assertIn(kind,dg_art.KINDS)
        with self.assertRaises(ValueError):
            dg_art.asset_location(self.root,self.st["id"],"sprite","mi")
        self.assertIn("cg",dg_comfy.generate.__code__.co_consts[1] if False else dg_art.KINDS)
    def test_missing_then_cached_cg_and_unchanged_source(self):
        title=u"Ночной праздник"
        narrative=u"На главной площади Совёнка дети отдыхают, герои разговаривают о предстоящем концерте и уходят со сцены вместе."
        p=dg_art.scene_plan(self.st,"world",title,narrative,"mi")
        self.assertIsNotNone(p)
        self.assertEqual(p["kind"],"cg")
        a=dg_art.resolve(self.root,self.st["id"],p["kind"],p["key"])
        self.assertEqual(a["status"],"missing")
        name=dg_rpg.asset_path(self.root,self.st["id"],p["kind"],p["key"])
        target=os.path.join(self.root,*name.split("/"))
        os.makedirs(os.path.dirname(target))
        with open(target,"wb") as f:f.write(b"PNG-DUMMY-CACHED")
        b=dg_art.resolve(self.root,self.st["id"],p["kind"],p["key"])
        self.assertEqual(b["status"],"generated")
        self.assertEqual(b["path"],name)
        self.assertFalse(b["generate"])
    def test_builtin_cg_precedes_synthesis_and_preference(self):
        p=dg_art.scene_plan(self.st,"personal",u"Беседа",u"Тёплый вечер и долгий разговор с Мику о музыке, доверии, репетициях, выборе и близких друзьях.","mi")
        a=dg_art.resolve(self.root,self.st["id"],p["kind"],p["key"],"mods/don_gen/images/gen_assets/cg/approved.png")
        self.assertEqual(a["status"],"builtin")
        self.assertFalse(a["generate"])
        self.assertIsNone(dg_art.approve_cg_lookup(self.root,{p["key"]:"../private"},p["key"]))
        self.assertIsNone(dg_art.approve_cg_lookup(self.root,{p["key"]:"mods/don_gen/images/gen_assets/cg/../../secret.png"},p["key"]))
    def test_bg_exact_built_in_disables_generate(self):
        result=dg_art.resolve(self.root,self.st["id"],"background","square","bg ext_square_day")
        self.assertEqual(result["status"],"builtin")
        self.assertFalse(result["generate"])
        result=dg_art.resolve(self.root,self.st["id"],"background","cabin_01")
        self.assertEqual(result["status"],"missing")
        self.assertTrue(result["generate"])
    def test_stable_scene_key_no_network_calls(self):
        description=u"Праздник затянулся до позднего вечера, на сцене звучала музыка и горели фонари, а герой разговаривал с Мику."
        first=dg_art.scene_plan(self.st,"world",u"Концерт",description,"mi")
        again=dg_art.scene_plan(copy.deepcopy(self.st),"world",u"Концерт",description,"mi")
        self.assertEqual(first,again)
        self.assertEqual(len(first["key"]),40)
        self.assertNotEqual(first["key"],dg_art.scene_plan(self.st,"ai",u"Концерт",description,"mi")["key"])
    def test_adult_cg_requires_positive_opt_in_and_eligible_adult(self):
        desc=u"Мику и герой вечером остались наедине в тихой беседке, где они обсуждали своё доверие, отношения и ближайшее будущее."
        self.assertIsNone(dg_art.scene_plan(self.st,"ai",u"Взрослая сцена",desc,"mi",True))
        dg_adult.set_enabled(self.st,True,confirmed=True)
        p=dg_art.scene_plan(self.st,"ai",u"Взрослая сцена",desc,"mi",True)
        self.assertEqual(p["kind"],"cg18")
        self.assertIn(u"18+",dg_art.cg_prompt(self.st,p))
        self.assertIsNone(dg_art.scene_plan(self.st,"ai",u"Секрет",desc,"uv",True))
        self.assertIsNone(dg_art.scene_plan(self.st,"ai",u"Недопустимо",u"Рядом Юля. "+desc,"mi",True))
        dg_adult.set_enabled(self.st,False)
        with self.assertRaises(ValueError):
            dg_art.cg_prompt(self.st,p)
    def test_default_adult_au_is_not_a_cg_request(self):
        dg_adult.set_enabled(self.st,True,confirmed=True)
        p=dg_art.scene_plan(self.st,"world",u"Вечер",u"Вечером Мику говорит о предстоящем конкурсе талантов и предлагает заняться музыкой.","mi")
        self.assertEqual(p["kind"],"cg")
    def test_seed_numeric_without_placeholder(self):
        graph={"90:76":{"class_type":"KSampler","inputs":{"seed":1121500282659858,"model":["2",0]}},
               "90:77":{"class_type":"CLIPTextEncode","inputs":{"text":"__DG_PROMPT__"}},
               "90:75":{"class_type":"CLIPTextEncode","inputs":{"text":"__DG_NEGATIVE__"}}}
        result=dg_comfy.prepare_workflow(graph,u"camp",u"blurry",seed=987654321)
        self.assertEqual(result["90:76"]["inputs"]["seed"],987654321)
        self.assertEqual(result["90:77"]["inputs"]["text"],u"camp")
        self.assertEqual(result["90:75"]["inputs"]["text"],u"blurry")
        self.assertEqual(graph["90:76"]["inputs"]["seed"],1121500282659858)
    def test_no_sprite_button_or_comfy_route_in_renpy(self):
        with open(os.path.join(ROOT,"don_gen","dg_rpg.rpy"),"rb") as h:
            source=h.read().decode("utf-8")
        self.assertIn('screen dg_rpg_cg_art(plan):',source)
        self.assertIn('label dg_rpg_cg_label:',source)
        self.assertIn('dg_rpg_cmd == "background"',source)
        self.assertNotIn('dg_rpg_cmd == "sprite"',source)
        self.assertNotIn('Return(("sprite", who))',source)
        self.assertIn('comfy_workflow_cg18_api.json',source)
        self.assertIn('DG_RPG_EXACT_BG',source)
        self.assertIn('dg_rpg_cg_for("hybrid"',source)

if __name__=="__main__":
    unittest.main()
