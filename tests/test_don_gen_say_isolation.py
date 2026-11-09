# -*- coding: utf-8 -*-
import ast, os, sys, textwrap, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','don_gen'))
import dg_stage
SOURCE=(Path(__file__).resolve().parents[1]/'don_gen/dg_rpg.rpy').read_text(encoding='utf-8')
TREE=ast.parse(textwrap.dedent(SOURCE.split('init 1001 python:\n',1)[1].split('\ndefault ',1)[0]))

def function(name, namespace):
    node=next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_rpg_function','exec'),namespace)
    return namespace[name]

class SayIsolation(unittest.TestCase):
    def test_literal_names_and_private_screen_never_inherit_foreign_character(self):
        creator=Mock(side_effect=lambda name,**kw:dict(name=name,**kw))
        ns=dict(Character=creator,dg_literal=lambda x:x,dg_stage=dg_stage,
                dg_rpg_scene_context={'hero_name':'Игорь. [имя] "тест"'},dg_rpg_state={'hero':{'name':'Игорь'}},
                renpy=SimpleNamespace(character=SimpleNamespace(show_display_say=object(),predict_show_display_say=object())))
        make=function('dg_rpg_say_character',ns)
        for who in list(dg_stage.NAMES)+['hero',None]:
            result=make(who)
            self.assertIs(result['dynamic'],False)
            self.assertEqual(result['screen'],'dg_rpg_say')
            self.assertNotIn('kind',result)
            self.assertIsNone(result['callback'])
            self.assertEqual(result['who_suffix'],'')
        self.assertEqual(make('hero')['name'],'Игорь. [имя] "тест"')

    def test_generation_restores_rollback_guard_after_failure(self):
        api=SimpleNamespace(suspend_rollback=Mock(),call_screen=Mock(side_effect=RuntimeError('test')))
        app=SimpleNamespace(start=Mock());store=SimpleNamespace()
        run=function('dg_rpg_run',dict(renpy=api,store=store,dg_runtime=SimpleNamespace(app=app)))
        task=object()
        with self.assertRaises(RuntimeError):run('chapter',task,'first','second')
        app.start.assert_called_once_with(task,'first','second')
        self.assertEqual([call.args for call in api.suspend_rollback.call_args_list],[(True,),(False,)])
        api.call_screen.assert_called_once_with('dg_rpg_wait',mode='chapter')

    def test_poll_closes_only_finished_request_and_refreshes_changed_status(self):
        app=SimpleNamespace(busy=True,status='Пишем')
        screen=SimpleNamespace(scope={'wait_state':None})
        api=SimpleNamespace(get_screen=Mock(return_value=screen),end_interaction=Mock(),restart_interaction=Mock())
        poll=function('dg_rpg_poll',dict(renpy=api,dg_runtime=SimpleNamespace(app=app),dg_elapsed=lambda:'00:01'))
        poll('chapter');api.end_interaction.assert_not_called();api.restart_interaction.assert_called_once()
        poll('chapter');api.restart_interaction.assert_called_once()
        app.busy=False;poll('chapter');api.end_interaction.assert_called_once_with(True)

    def test_dialogue_menu_and_generation_do_not_use_global_screens(self):
        self.assertNotIn('$ dg_run(',SOURCE)
        self.assertNotIn('        menu:\n',SOURCE)
        self.assertIn('screen="dg_rpg_choice"',SOURCE)
        self.assertIn('Hide("dg_rpg_dialogue_history") if overlay else Return(False)',SOURCE)
