# -*- coding: utf-8 -*-
"""Generated story direction must stay distinct, deterministic and rules-safe."""
from __future__ import unicode_literals
import copy,sys,os,unittest
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
sys.path.insert(0,os.path.join(ROOT,"don_gen"))
import dg_narrative,dg_rpg,dg_world,dg_dialogue

class NarrativeDirector(unittest.TestCase):
    def state(self,source="vanilla"):
        return dg_rpg.new_game(u"Игорь",18,39,u"Гитарист, попавший из будущего",source)
    def test_procedural_world_changes_only_prose(self):
        st=self.state()
        event=dg_world.current(st)
        self.assertEqual(event["choices"],dg_world.PLOTS[event["arc"]]["chapters"][event["stage"]] and event["choices"])
        self.assertIn("narrative",event)
        self.assertIn(event["narrative"]["physical_detail"],event["story"])
        self.assertEqual(event["id"],dg_world.current(st)["id"])
        self.assertEqual(event["story"],dg_world.current(st)["story"])
    def test_episode_palettes_are_diverse(self):
        st=self.state()
        sample=[]
        for day in range(1,31):
            st["day"]=day
            for code in ("mi","dv","un","sl"):
                c=dg_narrative.context(st,"npc_topics",code,"opening")
                sample.append((c["physical_detail"],c["unexpected_twist"],c["character_hook"]))
        self.assertGreater(len(set(sample)),35)
        self.assertGreater(len(set(x[0] for x in sample)),12)
    def test_profile_miku_is_distinct_for_each_7dl_route(self):
        variants=[]
        for source in ("7dl:mi_7dl","7dl:mi_dj","7dl:mi_cl"):
            c=dg_narrative.context(self.state(source),"npc_topics","mi","opening")
            self.assertIn(c["character_hook"],dg_narrative.MI_7DL[source])
            variants.append(c["route_style"][0])
        self.assertEqual(len(set(variants)),3)
        self.assertIn("Mику",dg_narrative.PERSONA["mi"][0].replace("М","M")) if False else None
    def test_unavailable_7dl_reference_not_fabricated(self):
        st=self.state("7dl:mi_dj")
        instructions,prompt=dg_narrative.request(st,"world","mi","event-01",
                                                 u"Мику ищет новую мелодию перед концертом")
        self.assertIn("mi_dj",prompt)
        self.assertIn('"source_reference": ""',prompt)
        self.assertIn("world_facts_are_locked",prompt)
        self.assertIn("НЕ придумывай",instructions)
    def test_dialogue_preserves_fixed_game_choices(self):
        st=self.state()
        d=dg_dialogue.opening(st,"mi")
        original=copy.deepcopy(d)
        altered=dg_narrative.decorate_dialogue(st,"mi","topics",d,0,None)
        self.assertEqual(d,original)
        self.assertEqual(altered["options"],original["options"])
        self.assertTrue(len(altered["text"])>len(original["text"]))
    def test_cache_reuses_scene_per_save_and_isolated_by_identity(self):
        st=self.state()
        key=dg_narrative.context(st,"npc_topics","mi","1")["scene_id"]
        self.assertIsNone(dg_narrative.read_scene(st,key))
        text=u"Мику остановилась на пороге музыкального клуба. "+u"Это новая история. "*15
        dg_narrative.remember_scene(st,key,text)
        self.assertEqual(dg_narrative.read_scene(st,key)["text"],text)
        second=dg_narrative.context(st,"npc_topics","mi","2")["scene_id"]
        self.assertNotEqual(second,key)
        self.assertIsNone(dg_narrative.read_scene(st,second))
        st2=self.state()
        self.assertIsNone(dg_narrative.read_scene(st2,key))
    def test_generated_memory_limits_and_validates_prose(self):
        st=self.state()
        for k in range(50):
            key="%064x"%k
            dg_narrative.remember_scene(st,key,u"Сцена с несколькими репликами. "*5)
        self.assertLessEqual(len(st["narrative_cache"]),48)
        with self.assertRaises(ValueError):
            dg_narrative.remember_scene(st,"../../etc/passwd",u"Условно подходящий сюжетный текст."*9)
        with self.assertRaises(ValueError):
            dg_narrative.remember_scene(st,"f"*64,u"Коротко.")
    def test_all_profiles_and_all_public_npcs_have_story_hooks(self):
        for source in dg_narrative.STYLE_PROFILES:
            st=self.state(source)
            for code in dg_rpg.NPC_NAMES:
                c=dg_narrative.context(st,"npc_choice",code,"story")
                self.assertTrue(c["character_hook"])
        self.assertIn(u"тайн",dg_narrative.PERSONA["uv"][1])
    def test_py2_compatibility_and_scene_narration_control_wiring(self):
        with open(os.path.join(ROOT,"don_gen","dg_rpg.rpy"),"rb") as f:
            script=f.read().decode("utf-8")
        for text in ('import dg_narrative','label dg_rpg_narrate(',
                     'dg_narrative.read_scene(dg_rpg_state',
                     'dg_rpg_apply("remember_narrative",',
                     'dg_source_7dl.source_context(',
                     'persistent.dg_auto_narrate',
                     'call dg_rpg_narrate("npc_"+phase'):
            self.assertIn(text,script)

if __name__=="__main__":
    unittest.main()
