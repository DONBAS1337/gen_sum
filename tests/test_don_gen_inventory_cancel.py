# -*- coding: utf-8 -*-
import ast, copy, os, sys, textwrap, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'don_gen'))
import dg_inventory, dg_rpg
from types import SimpleNamespace
from pathlib import Path

class InventoryCancellationTests(unittest.TestCase):
    def test_cancel_and_malformed_results_are_not_commands(self):
        for value in (True, False, None, '', 'take', (), ('take',), ('take','book'),
                      ('take','book',None,True), ('unknown','book',None), ('take',{},None), ('take','book',[])):
            self.assertIsNone(dg_inventory.command(value), repr(value))

    def test_valid_screen_command_preserved(self):
        self.assertEqual(dg_inventory.command(('take','book',None)), ('take','book',None))
        self.assertEqual(dg_inventory.command(['give','book','mi']), ('give','book','mi'))

    def test_actual_handler_cancel_does_not_load_or_change_game(self):
        path = Path(__file__).resolve().parents[1] / 'don_gen/dg_rpg.rpy'
        source = path.read_text(encoding='utf-8').split('init 1001 python:\n',1)[1].split('\ndefault ',1)[0]
        function = next(node for node in ast.parse(textwrap.dedent(source)).body if isinstance(node,ast.FunctionDef) and node.name=='dg_rpg_apply')
        state = dg_rpg.new_game('Игрок',20,30)
        store = SimpleNamespace(dg_rpg_state=state, dg_rpg_pending_turn=None)
        before = copy.deepcopy(store.__dict__)
        namespace = {'dg_inventory':dg_inventory, 'store':store}
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(path),'exec'),namespace)
        for value in (True,False,None,(),('take',)):
            self.assertIs(namespace['dg_rpg_apply']('inventory',value),False)
            self.assertEqual(before,store.__dict__)

    def test_rpg_cancel_buttons_do_not_use_renpy_true_sentinel(self):
        source = (Path(__file__).resolve().parents[1] / 'don_gen/dg_rpg.rpy').read_text(encoding='utf-8')
        self.assertNotIn('Return(None)',source)
        self.assertNotIn('Return()',source)
        self.assertEqual(source.count('dg_item_action=dg_inventory.command(_return)'),2)
