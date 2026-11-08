# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import copy
import os
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'don_gen'))
import dg_bkrr
import dg_hybrid
import dg_narrative
import dg_rpg
import dg_world


class MikuProfile(unittest.TestCase):
    def test_miku_is_present_for_the_new_musical_opportunity(self):
        for unused in range(20):
            state = dg_rpg.new_game(u'Игорь', 23, 30, source=dg_bkrr.SOURCE)
            event = dg_world.current(state)
            self.assertEqual(dg_rpg.where_is(state, 'mi'), event['place'])
            incident = state['social'].get('incident')
            if incident and 'mi' in incident['pair']:
                self.assertEqual(incident['place'], event['place'])
                for who in incident['pair']:
                    self.assertEqual(dg_rpg.where_is(state, who), event['place'])

    def test_musical_arc_has_its_own_situations_and_moves_finale_to_stage(self):
        state = dg_rpg.new_game(u'Игорь', 23, 30, source=dg_bkrr.SOURCE)
        for stage, chapter in enumerate(dg_bkrr.CHAPTERS):
            state['world']['tracks']['festival']['stage'] = stage
            event = dg_world.make_event(state)
            self.assertEqual(event['title'], chapter[0])
            self.assertEqual(event['place'], 'stage' if stage == 4 else 'music')
            self.assertEqual(event['npc'], 'mi')
            self.assertEqual([item['text'] for item in event['choices'][:3]], list(chapter[2:]))

    def test_switching_direction_preserves_existing_game_and_invalidates_prose_key(self):
        state = dg_rpg.new_game(u'Игорь', 23, 30)
        before = copy.deepcopy(state)
        old_key = dg_narrative.context(state, 'result', 'mi', 'scene')['scene_id']
        dg_rpg.set_source(state, dg_bkrr.SOURCE)
        self.assertNotEqual(old_key, dg_narrative.context(state, 'result', 'mi', 'scene')['scene_id'])
        before['source'] = dg_bkrr.SOURCE
        self.assertEqual(state, before)
        with self.assertRaises(ValueError):
            dg_rpg.set_source(state, 'invalid profile')
        self.assertEqual(state, before)

    def test_profile_persists_without_replacing_player_identity(self):
        state = dg_rpg.new_game(u'Игорь', 23, 30, source=dg_bkrr.SOURCE)
        self.assertEqual(dg_world.current(state)['arc'], 'festival')
        self.assertEqual(dg_world.current(state)['title'], dg_bkrr.CHAPTERS[0][0])
        self.assertEqual(dg_world.current(state)['place'], 'music')
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root, state)
            restored = dg_rpg.load(root, state['id'])
        self.assertEqual(restored, state)
        self.assertEqual(restored['hero']['name'], u'Игорь')
        self.assertEqual(restored['affinity']['mi'], 0)

    def test_both_narrators_receive_direction_without_donor_installation(self):
        state = dg_rpg.new_game(u'Игорь', 23, 30, source=dg_bkrr.SOURCE)
        instructions, prompt = dg_narrative.request(state, 'result', 'mi', 'test', u'Разговор')
        self.assertEqual(json.loads(prompt)['scene_identity']['route_style'], list(dg_bkrr.PROFILE))
        plan = dg_hybrid.preview(state, u'Осмотреть ворота', 'free')
        instructions, prompt = dg_hybrid.build_request(state, plan)
        self.assertEqual(json.loads(prompt)['narrative_variation']['route_style'], list(dg_bkrr.PROFILE))

    def test_local_board_is_media_only_and_missing_install_is_optional(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(dg_bkrr.find_root(root, environ={}))
            path = os.path.join(root, 'bkrr')
            os.makedirs(os.path.join(path, 'images', 'ui', 'menu'))
            with open(os.path.join(path, 'bkrr.rpy'), 'w') as handle:
                handle.write('raise RuntimeError("MUST NEVER EXECUTE")')
            image = os.path.join(path, 'images', 'ui', 'menu', 'base.png')
            with open(image, 'wb') as handle:
                handle.write(b'fake image')
            detected = dg_bkrr.find_root(root, environ={'DON_GEN_BKRR_ROOT':path})
            self.assertEqual(detected, os.path.abspath(root))
            self.assertEqual(dg_bkrr.board(detected), image.replace('\\', '/'))
