# -*- coding: utf-8 -*-
"""DON-GEN v0.4: NPC stories, multi-day quests, autonomous ties and free actions."""
from __future__ import unicode_literals
import copy
import os
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "don_gen")))
import dg_rpg
import dg_social
import dg_world


class SocialSandboxTests(unittest.TestCase):
    def setUp(self):
        self.state=dg_rpg.new_game(u"Игорь",23,39,u"Любит технику")
        self.root=tempfile.mkdtemp(prefix="dongensocial-")

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_all_npcs_have_three_chapters_and_valid_scenes(self):
        self.assertEqual(set(dg_rpg.NPC_NAMES),set(dg_social.PERSONAL))
        for who, beats in dg_social.PERSONAL.items():
            self.assertEqual(len(beats),3)
            self.assertEqual(len(set(x[0] for x in beats)),3)
            self.state["affinity"][who]=70
            data=dg_social.personal_scene(self.state,who)
            self.assertIsNotNone(data)
            self.assertGreater(len(data["text"]),55)
            self.assertEqual(len(data["choices"]),3)

    def test_personal_arc_works_through_rpg_and_unlocks_plots(self):
        st=self.state
        dg_rpg.move(st,"stage")
        st["affinity"]["mi"]=9
        scene=dg_social.personal_scene(st,"mi")
        self.assertEqual(scene["stage"],0)
        self.assertIsNone(dg_social.personal_scene(st,"sh"))
        outcome=dg_rpg.personal_choice(st,"mi","support")
        self.assertEqual(outcome["stage"],1)
        self.assertEqual(st["social"]["personal"]["mi"],1)
        self.assertEqual(st["affinity"]["mi"],17)
        self.assertEqual(st["world"]["preparations"]["festival"],6)
        self.assertEqual(st["slot"],1)
        self.assertIsNone(dg_social.personal_scene(st,"mi"))
        st["affinity"]["mi"]=35
        dg_rpg.move(st,"clubs")
        dg_rpg.personal_choice(st,"mi","question")
        self.assertEqual(st["social"]["personal"]["mi"],2)
        st["affinity"]["mi"]=60
        st["slot"]=0
        dg_rpg.move(st,"stage")
        dg_rpg.personal_choice(st,"mi","initiative")
        self.assertEqual(st["social"]["personal"]["mi"],3)
        self.assertIsNone(dg_social.personal_scene(st,"mi"))

    def test_quest_three_steps_reward_and_persistent_save(self):
        st=self.state
        msg=dg_rpg.accept_contract(st,"rehearsal")
        self.assertIn(u"принято",msg)
        with self.assertRaises(ValueError):
            dg_rpg.accept_contract(st,"rehearsal")
        dg_rpg.move(st,"clubs")
        done=dg_rpg.free_action(st,u"Помочь с репетицией")
        self.assertEqual(done["status"],"done")
        self.assertEqual(st["social"]["quests"]["rehearsal"]["step"],1)
        dg_rpg.move(st,"stage")
        dg_rpg.free_action(st,u"Проверить оборудование сцены")
        self.assertEqual(st["social"]["quests"]["rehearsal"]["step"],2)
        dg_rpg.free_action(st,u"Организовать концертную площадку")
        self.assertEqual(st["social"]["quests"]["rehearsal"]["status"],"completed")
        self.assertGreaterEqual(st["world"]["preparations"]["festival"],15)
        self.assertGreater(st["affinity"]["mi"],0)
        dg_rpg.save(self.root,st)
        loaded=dg_rpg.load(self.root,st["id"])
        self.assertEqual(loaded["social"]["quests"]["rehearsal"]["status"],"completed")
        self.assertEqual(loaded["social"]["actions"][0]["intent"],"help")
        self.assertEqual(len(loaded["social"]["actions"]),3)

    def test_free_action_text_and_unrecognized_command(self):
        st=self.state
        day,slot,energy=st["day"],st["slot"],st["energy"]
        for text in (u"Поговорить с Марсианами о луне" ,u"Сделать бессмысленное действие с Леной и Мику"):
            out=dg_rpg.free_action(st,text)
            self.assertEqual(out["status"],"unknown")
            self.assertEqual((st["day"],st["slot"],st["energy"]),(day,slot,energy))
        # Deliberate unsupported verb should not cause fabricated "success".
        self.assertEqual(dg_rpg.free_action(st,u"Телепортироваться в новый мир")["status"],"unknown")
        dg_rpg.move(st,"stage")
        self.assertEqual(dg_rpg.free_action(st,u"Помочь Мику с репетицией")["status"],"done")
        self.assertGreater(st["affinity"]["mi"],0)
        self.assertEqual(st["slot"],1)

    def test_absent_target_no_time_cost_and_no_farming(self):
        st=self.state
        self.assertEqual(dg_rpg.free_action(st,u"Помочь Мику")["status"],"unknown")
        self.assertEqual(st["slot"],0)
        dg_rpg.move(st,"stage")
        first=dg_rpg.free_action(st,u"Помочь Мику")
        self.assertEqual(first["impact"],4)
        self.assertEqual(st["affinity"]["mi"],3)
        # Force same slot to exercise once-per-day diminishing rewards.
        st["slot"]=0
        second=dg_rpg.free_action(st,u"Помочь Мику")
        self.assertEqual(second["impact"],0)
        self.assertEqual(st["affinity"]["mi"],3)

    def test_npc_bonds_advance_only_on_new_days(self):
        st=self.state
        self.assertEqual(len(st["social"]["rumours"]),0)
        for _ in range(4):
            dg_rpg.activity(st,"rest")
        self.assertEqual(st["day"],2)
        self.assertEqual(len(st["social"]["rumours"]),1)
        first=copy.deepcopy(st["social"]["rumours"])
        dg_social.ensure(st)
        dg_social.npc_daily(st)
        self.assertEqual(st["social"]["rumours"],first)
        self.assertEqual(len(st["social"]["daily_seen"]),1)

    def test_mediation_shifts_npc_npc_relationship(self):
        st=self.state
        before=dg_social.bond(st,"dv","mi")
        dg_rpg.move(st,"stage")
        result=dg_rpg.free_action(st,u"Договориться с Мику")
        self.assertEqual(result["status"],"done")
        self.assertEqual(dg_social.bond(st,"dv","mi")-before,7)

    def test_quest_deadline_expires_and_changes_world(self):
        st=self.state
        dg_rpg.accept_contract(st,"shore")
        expiry=st["social"]["quests"]["shore"]["deadline"]
        while st["day"]<=expiry and not st["finished"]:
            dg_rpg.activity(st,"rest")
        self.assertEqual(st["social"]["quests"]["shore"]["status"],"failed")
        self.assertIn(u"Срок",u" ".join(row["text"] for row in st["journal"]))

    def test_preparation_unlocks_new_plot_resolution_same_day(self):
        st=self.state
        event=dg_world.current(st)
        arc=event["arc"]
        st["world"]["preparations"][arc]=12
        dg_world.refresh_open_event(st)
        refreshed=dg_world.current(st)
        self.assertIn("prepared",[x["key"] for x in refreshed["choices"]])
        dg_rpg.move(st,refreshed["place"])
        result=dg_rpg.story_choice(st,"prepared")
        self.assertIn(u"готовый",result["text"])
        self.assertEqual(st["world"]["preparations"][arc],0)
        self.assertIsNone(dg_world.current(st))

    def test_legacy_save_has_new_schema_without_reset(self):
        st=self.state
        st["day"]=7
        st["affinity"]["mi"]=63
        del st["social"]
        dg_rpg.save(self.root,st)
        recovered=dg_rpg.load(self.root,st["id"])
        self.assertEqual(recovered["day"],7)
        self.assertEqual(recovered["affinity"]["mi"],63)
        self.assertEqual(len(recovered["social"]["bonds"]),len(dg_social.PAIR_DEFS))
        self.assertEqual(len(dg_social.quest_list(recovered)),4)

    def test_renpy_wiring_for_new_gameplay(self):
        with open(os.path.join(os.path.dirname(__file__),"..","don_gen","dg_rpg.rpy"),"rb") as stream:
            script=stream.read().decode("utf-8")
        for expected in (
            "screen dg_rpg_free_input:", "screen dg_rpg_contracts:",
            "screen dg_rpg_personal(who):", "screen dg_rpg_action_result(result):",
            'Return(("free", None))', 'Return(("contracts", None))',
            'dg_rpg_apply("personal", (dg_rpg_focus, dg_rpg_personal_stance))',
            'SetScreenVariable("view", "social")'):
            self.assertIn(expected,script)


if __name__=="__main__":
    unittest.main()
