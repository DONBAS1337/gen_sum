# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'don_gen'))
import dg_rpg, dg_memory, dg_characters, dg_narrative, dg_source_bkrr

class CharacterKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.state = dg_rpg.new_game('Игрок', 20, 30, 'Музыкант')

    def test_private_conversation_does_not_reach_other_character(self):
        dg_memory.record(self.state, 'secret', 'Наедине обсудить секрет скрипки', 'Поговорили', '[mi] Хорошо.', 'mi')
        self.assertTrue(dg_memory.recall(self.state, 'mi')['relevant_episodes'])
        self.assertEqual(dg_memory.recall(self.state, 'dv')['relevant_episodes'], [])
        self.assertNotIn('секрет скрипки', json.dumps(dg_narrative.context(self.state, 'dialogue', 'dv'), ensure_ascii=False))
        dg_memory.validate(self.state)

    def test_witness_and_public_knowledge(self):
        dg_memory.record(self.state, 'shared', 'Поговорить', 'Поговорили', '[mi] Хорошо.', 'mi')
        row = self.state['story_memory']['episodes'][0]
        row['witnesses'] = ['mi', 'dv']
        self.assertTrue(dg_memory.recall(self.state, 'dv')['relevant_episodes'])
        self.assertFalse(dg_memory.recall(self.state, 'un')['relevant_episodes'])
        row['public'] = True
        self.assertTrue(dg_memory.recall(self.state, 'un')['relevant_episodes'])

    def test_old_memory_is_conservatively_private(self):
        dg_memory.record(self.state, 'old', 'Поговорить', 'Поговорили', '[mi] Хорошо.', 'mi')
        row = self.state['story_memory']['episodes'][0]
        del row['witnesses']; del row['public']
        self.assertFalse(dg_memory.recall(self.state, 'dv')['relevant_episodes'])
        dg_memory.validate(self.state)

    def test_affinity_does_not_invent_romance(self):
        self.state['affinity']['mi'] = 100
        card = dg_characters.cards(self.state, ['mi'])[0]
        self.assertFalse(card['romance_confirmed'])
        self.assertIn('knowledge', card)

    def test_bkrr_reader_never_executes_or_uses_future_dialogue(self):
        with tempfile.TemporaryDirectory() as root:
            folder = os.path.join(root, 'bkrr', 'days'); os.makedirs(folder)
            for day in (4, 8):
                with open(os.path.join(folder, 'bkrr_day%d.rpy' % day), 'w', encoding='utf-8') as handle:
                    handle.write('label example:\n    $ raise Exception("EXECUTED")\n    show mi smile\n    mi "Давай проверим звучание этой гитары."\n    mi "Я люблю тебя навсегда!"\n    mi "Привет, [player_name]!"\n')
            self.assertEqual(dg_source_bkrr.context(root, ['mi'], 'гитары', 1)['examples'], [])
            rows = dg_source_bkrr.context(root, ['mi'], 'гитары', 4)['examples']
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['day'], 4)
            self.assertEqual(rows[0]['expression'], 'smile')
            self.assertEqual(rows[0]['who'], 'mi')

    def test_all_input_screens_enable_paste_and_block_rollback(self):
        import re
        for name in ('dg_rpg.rpy', 'don_gen.rpy'):
            with open(os.path.join(os.path.dirname(__file__), '..', 'don_gen', name), encoding='utf-8') as handle:
                source = handle.read()
            for block in re.split(r'(?m)^screen ', source)[1:]:
                block = re.split(r'(?m)^(?:label |init |style |default |transform )', block)[0]
                if not re.search(r'(?m)^\s+input(?:\s|:)', block): continue
                self.assertIn('key "rollback" action NullAction()', block, block.splitlines()[0])
                for field in re.split(r'(?m)^\s+input(?:\s|:)', block)[1:]:
                    self.assertIn('copypaste True', '\n'.join(field.splitlines()[:10]), block.splitlines()[0])

    def test_7dl_references_exclude_future_days_and_other_speakers(self):
        import dg_source_7dl
        from unittest.mock import patch
        index = {'scenes': [dict(kind='scenario', route='mi_7dl', label='scene%d' % day,
            day=day, characters=['mi', 'dv'], file='test.rpy', story_text='mi: Давай проверим настройку гитары.\ndv: Совсем другая реплика Алисы.') for day in (1, 6)]}
        with patch.object(dg_source_7dl, 'load_or_build', return_value=index):
            context = json.loads(dg_source_7dl.source_context('unused', 'unused', 'mi_7dl', 'гитары', day=1, voices_only=True, characters=['dv']))
        self.assertTrue(context['examples'])
        self.assertTrue(all(row['who'] == 'dv' and row['day'] == 1 for row in context['examples']))

    def test_character_prompt_includes_state_without_mutation(self):
        import copy
        __import__('dg_relationships').person(self.state, 'mi')['tension'] = 9
        before = copy.deepcopy(self.state)
        card = dg_characters.cards(self.state, ['mi'])[0]
        self.assertEqual(card['tension'], 9)
        self.assertEqual(before, self.state)

