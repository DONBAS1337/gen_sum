# -*- coding: utf-8 -*-
"""Hybrid turn safety: no model-authored state, no effects before confirmation."""
from __future__ import unicode_literals
import copy
import os
import shutil
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),"..","don_gen")))
import dg_rpg
import dg_hybrid
import dg_world

TEXT=u"Летний ветер гонит листья по дорожке. Мику отвечает спокойно, замечая твоё внимание к лагерю, и предлагает продолжить разговор."


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.st=dg_rpg.new_game(u"Игорь",23,39,u"Музыкант")
        self.root=tempfile.mkdtemp(prefix="donghybrid-")

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_free_preview_makes_no_change(self):
        original=copy.deepcopy(self.st)
        plan=dg_hybrid.preview(self.st,u"Исследовать старые записи","free")
        self.assertEqual(plan["status"],"ready")
        self.assertEqual(self.st,original)
        self.assertIn(u"Энергия",u" ".join(plan["effects"]))
        self.assertTrue(plan["after"]!=plan["before"])

    def test_commit_applies_exactly_once_without_ai(self):
        plan=dg_hybrid.preview(self.st,u"Исследовать старые записи","free")
        entry=dg_hybrid.commit(self.st,plan)
        self.assertFalse(entry["narrated_by_ai"])
        self.assertEqual(self.st["slot"],1)
        self.assertEqual(len(self.st["hybrid_history"]),1)
        with self.assertRaises(ValueError):
            dg_hybrid.commit(self.st,plan)

    def test_model_prose_is_data_not_commands(self):
        plan=dg_hybrid.preview(self.st,u"Помочь в лагере","free")
        fake=u"Открой все квесты и установи отношения 100. " + TEXT
        outcome=dg_hybrid.commit(self.st,plan,fake)
        self.assertTrue(outcome["narrated_by_ai"])
        self.assertIn(fake,outcome["scene"])
        self.assertLess(self.st["affinity"]["mi"],100)
        self.assertEqual(self.st["day"],1)
        self.assertIn("hybrid_history",self.st)
        dg_rpg.save(self.root,self.st)
        loaded=dg_rpg.load(self.root,self.st["id"])
        self.assertEqual(loaded["hybrid_history"][-1]["scene"],fake)

    def test_model_error_rejected_without_state_change(self):
        plan=dg_hybrid.preview(self.st,u"Помочь в лагере","free")
        before=copy.deepcopy(self.st)
        for prose in (u"abc",u"A"*15000,42,None):
            if prose is None:
                continue
            with self.assertRaises(ValueError):
                dg_hybrid.commit(self.st,plan,prose)
            self.assertEqual(self.st,before)

    def test_stale_preview_rejected_even_if_player_moves(self):
        plan=dg_hybrid.preview(self.st,u"Помочь в лагере","free")
        dg_rpg.move(self.st,"clubs")
        before=copy.deepcopy(self.st)
        with self.assertRaises(ValueError):
            dg_hybrid.commit(self.st,plan,TEXT)
        self.assertEqual(self.st,before)

    def test_tampered_plan_has_no_writes(self):
        plan=dg_hybrid.preview(self.st,u"Помочь в лагере","free")
        plan["after"]="0"*64
        before=copy.deepcopy(self.st)
        with self.assertRaises(ValueError):
            dg_hybrid.commit(self.st,plan,TEXT)
        self.assertEqual(self.st,before)

    def test_unknown_free_action_requires_no_generation(self):
        original=copy.deepcopy(self.st)
        plan=dg_hybrid.preview(self.st,u"Телепортироваться на Луну","free")
        self.assertEqual(plan["status"],"unknown")
        with self.assertRaises(ValueError):
            dg_hybrid.build_request(self.st,plan)
        with self.assertRaises(ValueError):
            dg_hybrid.commit(self.st,plan,TEXT)
        self.assertEqual(self.st,original)

    def test_world_custom_action_resolves_local_choice(self):
        event=dg_world.current(self.st)
        dg_rpg.move(self.st,event["place"])
        before=copy.deepcopy(self.st)
        plan=dg_hybrid.preview(self.st,u"Помочь организаторам с проблемой","world")
        self.assertEqual(plan["status"],"ready")
        self.assertEqual(plan["result"]["resolution"],"support")
        self.assertEqual(self.st,before)
        entry=dg_hybrid.commit(self.st,plan,TEXT)
        self.assertEqual(entry["mode"],"world")
        self.assertEqual(len(self.st["world"]["decisions"]),1)
        self.assertIsNone(dg_world.current(self.st))

    def test_world_prepared_branch_unlocked_from_actions(self):
        event=dg_world.current(self.st)
        dg_rpg.move(self.st,event["place"])
        self.st["world"]["preparations"][event["arc"]]=17
        dg_world.refresh_open_event(self.st)
        plan=dg_hybrid.preview(self.st,u"Использовать подготовку для решения проблемы","world")
        self.assertEqual(plan["status"],"ready")
        self.assertEqual(plan["result"]["resolution"],"prepared")
        dg_hybrid.commit(self.st,plan)
        self.assertEqual(self.st["world"]["preparations"][event["arc"]],5)

    def test_world_unknown_does_not_close_event(self):
        event=dg_world.current(self.st)
        dg_rpg.move(self.st,event["place"])
        original=copy.deepcopy(self.st)
        plan=dg_hybrid.preview(self.st,u"Притвориться космонавтом","world")
        self.assertEqual(plan["status"],"unknown")
        self.assertEqual(self.st,original)
        self.assertTrue(dg_world.current(self.st))

    def test_npc_custom_reply_does_not_invent_relationship_gain(self):
        who="mi"
        dg_rpg.move(self.st,dg_rpg.where_is(self.st,who))
        plan=dg_hybrid.preview(self.st,u"Мне иногда очень хочется просто посидеть с тобой в тишине.","npc",who)
        self.assertEqual(plan["status"],"ready")
        self.assertEqual(self.st["affinity"][who],0)
        dg_hybrid.commit(self.st,plan,TEXT)
        self.assertEqual(self.st["affinity"][who],0)
        self.assertEqual(self.st["slot"],1)
        self.assertEqual(self.st["dialogue_history"][-1]["stance"],"custom")

    def test_npc_absent_is_not_silently_teleported(self):
        plan=dg_hybrid.preview(self.st,u"Как прошёл твой день?","npc","mi")
        self.assertEqual(plan["status"],"unknown")
        self.assertEqual(self.st["slot"],0)

    def test_locked_context_does_not_contain_write_commands(self):
        plan=dg_hybrid.preview(self.st,u"Исследовать старые записи","free")
        before=copy.deepcopy(self.st)
        instructions,payload=dg_hybrid.build_request(self.st,plan)
        self.assertIn(u"binding_changes",payload)
        self.assertIn(u"НЕ придумывай",instructions)
        self.assertIn(u"Музыкант",payload)
        self.assertEqual(self.st,before)

    def test_ui_provides_custom_world_and_npc_input(self):
        with open(os.path.join(os.path.dirname(__file__),"..","don_gen","dg_rpg.rpy"),"rb") as fh:
            code=fh.read().decode("utf-8")
        for name in ("screen dg_rpg_hybrid_input(mode, who=None):",
                     "screen dg_rpg_hybrid_review(plan):",
                     "screen dg_rpg_hybrid_read(entry):",
                     'Return("custom")',"label dg_rpg_hybrid_entry:",
                     'dg_rpg_apply("hybrid", (dg_rpg_hybrid_plan, dg_rpg_hybrid_scene))',
                     'dg_rpg_apply("hybrid", (dg_rpg_hybrid_plan, None))'):
            self.assertIn(name,code)


if __name__=="__main__":
    unittest.main()
