# -*- coding: utf-8 -*-
import ast,textwrap,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
SOURCE=(Path(__file__).resolve().parents[1]/'don_gen/dg_rpg.rpy').read_text(encoding='utf-8')

class NativeResume(unittest.TestCase):
    def handler(self,own=True):
        tree=ast.parse(textwrap.dedent(SOURCE.split('init 1001 python:\n',1)[1].split('\ndefault ',1)[0]))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='dg_rpg_after_load')
        store=SimpleNamespace(dg_rpg_state={'id':'saved'},dg_rpg_active=False,dg_rpg_pending_turn={'stale':True})
        api=SimpleNamespace(game=SimpleNamespace(context=lambda:SimpleNamespace(current='old'),script=SimpleNamespace(lookup=lambda value:SimpleNamespace(filename='game/mods/don_gen/dg_rpg.rpy' if own else 'game/foreign.rpy'))),jump=Mock())
        opened=Mock(side_effect=lambda ident:setattr(store,'dg_rpg_state',{'id':ident,'confirmed':True}))
        ns=dict(dg_rpg=SimpleNamespace(DICT_TYPE=dict),store=store,renpy=api,dg_rpg_open=opened,dg_stage=SimpleNamespace(freeze=lambda state:dict(state)))
        exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_resume','exec'),ns)
        return ns['dg_rpg_after_load'],store,api,opened

    def test_own_native_save_resumes_confirmed_session_and_drops_stale_presentation(self):
        handler,store,api,opened=self.handler();handler()
        opened.assert_called_once_with('saved');api.jump.assert_called_once_with('dg_rpg_resume_loaded')
        self.assertIsNone(store.dg_rpg_pending_turn)
        self.assertFalse(store.dg_rpg_stage_active)
        self.assertEqual(store.dg_rpg_scene_context,{'id':'saved','confirmed':True})

    def test_foreign_mod_save_is_left_alone(self):
        handler,store,api,opened=self.handler(own=False);handler()
        opened.assert_not_called();api.jump.assert_not_called()

    def test_native_save_names_and_script_return_sites_are_owned(self):
        self.assertIn('save_name = u"DON-GEN · "',SOURCE)
        self.assertIn('renpy.set_return_stack([])',SOURCE)
        for line in SOURCE.splitlines():
            if line.strip().startswith('call dg_'):
                self.assertIn(' from dg_return_',line)
