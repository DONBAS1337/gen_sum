# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import copy
import hashlib
import os
import shutil
import sys
import tempfile
import unittest
import ast
import logging
import textwrap
from types import SimpleNamespace
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'don_gen'))
import dg_rpg
import dg_narrative
import dg_turn
import dg_world
import dg_stage
import dg_hybrid

TEXT = u'[narrator] ' + u'Лагерь постепенно затихал, и разговор у ворот продолжался. ' * 4
KEY = hashlib.sha256(b'test scene').hexdigest()


class TurnPersistence(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.state = dg_rpg.new_game(u'Игорь', 18, 120)
        dg_rpg.save(self.root, self.state)

    def tearDown(self):
        shutil.rmtree(self.root)

    def test_cancelled_turn_never_changes_disk(self):
        pending = dg_turn.begin(self.state)
        dg_rpg.activity(pending['state'], 'explore')
        self.assertNotEqual(pending['state']['slot'], self.state['slot'])
        self.assertEqual(dg_rpg.load(self.root, self.state['id']), self.state)

    def test_current_scene_clock_is_separate_from_next_turn(self):
        plan = dg_hybrid.preview(self.state, u'Осмотреть ворота', 'free')
        context = dg_hybrid.locked_context(self.state, plan)
        self.assertEqual(context['scene_anchor']['time'], dg_rpg.SLOTS[0])
        self.assertTrue(context['next_turn_clock_changes'])
        self.assertFalse(any(effect.startswith(u'Время:') for effect in context['binding_changes']))

    def test_absent_speaker_rejected_without_committing_turn(self):
        present = dg_stage.freeze(self.state)['present']
        absent = next(who for who in dg_stage.NAMES if who not in present)
        plan = dg_hybrid.preview(self.state, u'Осмотреть ворота', 'free')
        before = copy.deepcopy(self.state)
        with self.assertRaises(ValueError):
            dg_hybrid.commit(self.state, plan, '[' + absent + '] ' + TEXT)
        self.assertEqual(self.state, before)

    def test_effects_and_scene_survive_reload_together(self):
        pending = dg_turn.begin(self.state)
        dg_rpg.activity(pending['state'], 'explore')
        saved = dg_turn.finish(self.root, pending, KEY, TEXT)
        loaded = dg_rpg.load(self.root, self.state['id'])
        self.assertEqual(saved, loaded)
        self.assertEqual(loaded['slot'], 1)
        self.assertEqual(dg_narrative.read_scene(loaded, KEY)['text'], TEXT.strip())

    def test_invalid_generation_and_stale_turn_do_not_overwrite_save(self):
        pending = dg_turn.begin(self.state)
        for text in ('', None, 'short', 'x' * 12001):
            with self.assertRaises(ValueError):
                dg_turn.finish(self.root, pending, KEY, text)
            self.assertEqual(dg_rpg.load(self.root, self.state['id']), self.state)
        dg_rpg.activity(self.state, 'rest')
        dg_rpg.save(self.root, self.state)
        with self.assertRaises(ValueError):
            dg_turn.finish(self.root, pending, KEY, TEXT)
        self.assertEqual(dg_rpg.load(self.root, self.state['id']), self.state)

    def test_actual_renpy_action_handler_defers_world_save_until_narration(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'don_gen', 'dg_rpg.rpy')
        with open(path, encoding='utf-8') as handle:
            source = handle.read().split('init 1001 python:\n', 1)[1].split('\ndefault ', 1)[0]
        tree = ast.parse(textwrap.dedent(source))
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'dg_rpg_apply')
        store = SimpleNamespace(dg_rpg_pending_turn=None, dg_rpg_state=self.state)
        namespace = dict(dg_rpg=dg_rpg, dg_turn=dg_turn, dg_stage=dg_stage,
                         dg_narrative=dg_narrative, store=store, logging=logging,
                         dg_rpg_state=self.state, dg_rpg_root=lambda: self.root,
                         renpy=SimpleNamespace(block_rollback=lambda: None))
        exec(compile(ast.Module(body=[function], type_ignores=[]), path, 'exec'), namespace)
        event = dg_world.current(self.state)
        dg_rpg.move(self.state, event['place'])
        dg_rpg.save(self.root, self.state)
        before = copy.deepcopy(self.state)
        namespace['dg_rpg_apply']('world', event['choices'][0]['key'])
        self.assertIsNotNone(store.dg_rpg_pending_turn)
        self.assertEqual(dg_rpg.load(self.root, self.state['id']), before)
        namespace['dg_rpg_apply']('remember_narrative', (KEY, TEXT))
        self.assertIsNone(store.dg_rpg_pending_turn)
        saved = dg_rpg.load(self.root, self.state['id'])
        self.assertNotEqual(saved['slot'], before['slot'])
        self.assertEqual(dg_narrative.read_scene(saved, KEY)['text'], TEXT.strip())

    def test_120_day_session_reloads_every_turn_and_recovers_backup(self):
        turns = 0
        while not self.state['finished']:
            pending = dg_turn.begin(self.state)
            action = 'rest' if self.state['energy'] < 25 else ('explore' if turns % 2 else 'help')
            dg_rpg.activity(pending['state'], action)
            key = hashlib.sha256(str(turns).encode('ascii')).hexdigest()
            expected = dg_turn.finish(self.root, pending, key, TEXT)
            self.state = dg_rpg.load(self.root, self.state['id'])
            self.assertEqual(self.state, expected)
            self.assertLessEqual(len(self.state.get('narrative_order', [])), 48)
            self.assertTrue(0 <= self.state['energy'] <= 100)
            turns += 1
            self.assertLessEqual(turns, 480)
        self.assertEqual(turns, 480)
        with open(dg_rpg._path(self.root, self.state['id']), 'wb') as handle:
            handle.write(b'{broken')
        recovered = dg_rpg.load(self.root, self.state['id'])
        self.assertEqual(recovered['day'], 120)
        self.assertEqual(recovered['slot'], 3)
