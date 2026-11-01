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
            if who == "uv":
                self.assertIsNone(dg_social.personal_scene(self.state,who))
                self.state["mystery"]["yulia_discovered"] = True
            data=dg_social.personal_scene(self.state,who)
            self.assertIsNotNone(data)
            self.assertGreater(len(data["text"]),55)
            self.assertEqual(len(data["choices"]),3)

    def test_personal_story_and_dialogue_remember_previous_choice(self):
        import dg_dialogue
        st=self.state
        st["affinity"]["mi"]=55
        first=dg_social.personal_scene(st,"mi")
        self.assertNotIn(u"Твои прежние",first["text"])
        dg_social.resolve_personal(st,"mi","question")
        second=dg_social.personal_scene(st,"mi")
        self.assertIn(u"прежние прямые вопросы",second["text"])
        common=dg_dialogue.opening(st,"mi")
        self.assertIn(u"вопрос не выходил из головы",common["text"])

    def test_personal_arc_works_through_rpg_and_unlocks_plots(self):
        self.state["social"]["incident"]["status"]="resolved"
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

    def test_generic_help_cannot_complete_specific_quest(self):
        st=self.state
        dg_rpg.accept_contract(st,"rehearsal")
        dg_rpg.move(st,"clubs")
        result=dg_rpg.free_action(st,u"Помочь кому-нибудь")
        self.assertEqual(result["status"],"done")
        self.assertEqual(st["social"]["quests"]["rehearsal"]["step"],0)
        # Correct contextual phrase in next slot should advance.
        result=dg_rpg.free_action(st,u"Помочь с репетицией")
        self.assertEqual(result["status"],"done")
        self.assertEqual(st["social"]["quests"]["rehearsal"]["step"],1)

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
        self.state["social"]["incident"]["status"]="resolved"
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
        self.state["social"]["incident"]["status"]="resolved"
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
        self.assertEqual(len(st["social"]["rumours"]),2)
        first=copy.deepcopy(st["social"]["rumours"])
        dg_social.ensure(st)
        dg_social.npc_daily(st)
        self.assertEqual(st["social"]["rumours"],first)
        self.assertEqual(len(st["social"]["daily_seen"]),1)

    def test_mediation_shifts_npc_npc_relationship(self):
        self.state["social"]["incident"]["status"]="resolved"
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

    def test_npc_encounter_is_visible_and_choices_have_effects(self):
        st=self.state
        incident=dg_social.incident(st)
        self.assertIsNotNone(incident)
        place=incident["place"]
        a,b=incident["pair"]
        self.assertEqual(dg_rpg.where_is(st,a),place)
        self.assertEqual(dg_rpg.where_is(st,b),place)
        self.assertIn(a,[who for who,name in dg_rpg.at_place(st,place)])
        dg_rpg.move(st,place)
        initial=dg_social.bond(st,a,b)
        outcome=dg_rpg.social_encounter(st,"mediate")
        self.assertEqual(outcome["delta"],10)
        self.assertEqual(dg_social.bond(st,a,b),initial+10)
        self.assertIsNone(dg_social.incident(st))
        self.assertEqual(st["slot"],1)
        with self.assertRaises(ValueError):
            dg_rpg.social_encounter(st,"mediate")

    def test_siding_with_one_npc_can_hurt_the_other(self):
        st=self.state
        first=dg_social.incident(st)
        a,b=first["pair"]
        dg_rpg.move(st,first["place"])
        result=dg_rpg.social_encounter(st,"support_a")
        self.assertEqual(result["delta"],-5)
        self.assertEqual(st["affinity"][a],7)
        self.assertEqual(st["affinity"][b],0)

    def test_unresolved_encounter_has_real_autonomous_outcome(self):
        st=self.state
        first=copy.deepcopy(dg_social.incident(st))
        for _ in range(4):
            dg_rpg.activity(st,"rest")
        self.assertEqual(st["day"],2)
        self.assertTrue(any(item["day"]==1 and u"решили вопрос самостоятельно" in item["text"]
                            for item in st["social"]["rumours"]))
        self.assertIsNotNone(dg_social.incident(st))
        self.assertNotEqual(first["day"],dg_social.incident(st)["day"])
        self.assertIsNone(dg_social.incident_at(st,first["place"]) if
                          dg_social.incident(st)["place"]!=first["place"] else None)

    def test_renpy_wiring_for_new_gameplay(self):
        with open(os.path.join(os.path.dirname(__file__),"..","don_gen","dg_rpg.rpy"),"rb") as stream:
            script=stream.read().decode("utf-8")
        for expected in (
            "screen dg_rpg_free_input:", "screen dg_rpg_contracts:",
            "screen dg_rpg_personal(who):", "screen dg_rpg_action_result(result):",
            "screen dg_rpg_npc_incident:", 'Return(("incident", None))',
            'Return(("free", None))', 'Return(("contracts", None))',
            'dg_rpg_apply("personal", (dg_rpg_focus, dg_rpg_personal_stance))',
            'SetScreenVariable("view", "social")'):
            self.assertIn(expected,script)


if __name__=="__main__":
    unittest.main()
