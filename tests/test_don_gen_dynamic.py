# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import copy
import json
import os
import sys
import tempfile
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'don_gen'))
import dg_gallery
import dg_hybrid
import dg_memory
import dg_narrative
import dg_rpg
import dg_stage
import dg_world
import dg_visual

SCENE = u'[narrator] ' + u'Вы обсуждаете следующий шаг, сохраняя право передумать. ' * 4


class DynamicStory(unittest.TestCase):
    def setUp(self):
        self.state = dg_rpg.new_game(u'Игорь', 23, 30, source='bkrr:mi')

    def test_cancelled_preview_creates_no_memory_or_followup(self):
        before = copy.deepcopy(self.state)
        dg_rpg.move(self.state, dg_rpg.where_is(self.state, 'mi'))
        before = copy.deepcopy(self.state)
        plan = dg_hybrid.preview(self.state, u'Помочь с репетицией', 'npc', 'mi')
        self.assertEqual(plan['status'], 'ready')
        self.assertEqual(self.state, before)
        self.assertNotIn('story_memory', self.state)

    def test_courtesy_or_refusal_does_not_invent_an_obligation(self):
        for number, action in enumerate((u'Спасибо за помощь', u'Не хочу репетировать завтра')):
            dg_memory.record(self.state, str(number), action, u'Разговор', SCENE, 'mi')
        self.assertEqual(self.state['story_memory']['threads'], [])

    def test_corrupt_memory_recovers_previous_save_instead_of_crashing_director(self):
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root, self.state)
            dg_memory.record(self.state, 'test', u'Разговор', u'Поговорили', SCENE, 'mi')
            dg_rpg.save(root, self.state)
            damaged = copy.deepcopy(self.state)
            damaged['story_memory']['episodes'][0]['place'] = 'invalid place'
            with open(dg_rpg._path(root, self.state['id']), 'w', encoding='utf-8') as handle:
                json.dump(damaged, handle)
            recovered = dg_rpg.load(root, self.state['id'])
            self.assertNotIn('story_memory', recovered)

    def test_player_intention_survives_reload_but_is_not_achievement(self):
        dg_rpg.move(self.state, dg_rpg.where_is(self.state, 'mi'))
        action = u'Попробовать научиться играть на гитаре'
        plan = dg_hybrid.preview(self.state, action, 'npc', 'mi')
        dg_hybrid.commit(self.state, plan, SCENE)
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root, self.state)
            loaded = dg_rpg.load(root, self.state['id'])
        episode = dg_memory.recall(loaded, 'mi')['relevant_episodes'][0]
        self.assertEqual(episode['intention'], action)
        self.assertNotIn(u'научился', episode['confirmed_result'])
        self.assertEqual(loaded['stats']['skill'], 0)
        self.assertEqual(loaded['story_memory']['people']['mi']['meetings'], 1)

    def test_followup_becomes_a_real_event_and_can_be_resolved(self):
        origin = copy.deepcopy(self.state)
        dg_memory.record(self.state, 'test', u'Предложить совместную репетицию', u'Обсудили намерение', SCENE, 'mi', origin)
        self.state['day'] = 2
        self.state['world']['event'] = None
        event = dg_world.current(self.state)
        self.assertIn('thread_id', event)
        dg_rpg.validate(self.state)
        self.assertEqual(dg_rpg.where_is(self.state, 'mi'), event['place'])
        dg_rpg.move(self.state, event['place'])
        dg_world.choose(self.state, 'support')
        self.assertEqual(self.state['story_memory']['threads'][0]['status'], 'resolved')
        self.assertIsNone(dg_memory.opportunity(self.state))

    def test_missed_followup_retries_then_closes_without_infinite_wait(self):
        dg_memory.record(self.state, 'test', u'Проверить старую находку', u'Намерение', SCENE)
        for day in (2, 4):
            self.state['day'] = day
            self.state['world']['event'] = None
            event = dg_world.current(self.state)
            self.assertIn('thread_id', event)
            dg_world.missed(self.state)
        self.assertEqual(self.state['story_memory']['threads'][0]['status'], 'abandoned')

    def test_followup_cannot_summon_a_secret_night_character_during_day(self):
        self.state['slot'] = 3
        self.state['place'] = 'forest_path'
        self.state['mystery']['yulia_discovered'] = True
        dg_memory.record(self.state, 'night', u'Давай исследовать тропу завтра', u'Обсудили', SCENE, 'uv')
        self.state['day'], self.state['slot'] = 2, 0
        self.assertIsNone(dg_memory.opportunity(self.state))
        self.state['slot'] = 3
        self.assertEqual(dg_memory.opportunity(self.state)['npc'], 'uv')

    def test_memory_is_separate_from_short_prose_cache_and_is_bounded(self):
        for n in range(110):
            dg_memory.record(self.state, str(n), u'Спокойная беседа', u'Разговор', SCENE, 'mi')
        self.state['narrative_scenes'] = {}
        memory = dg_memory.recall(self.state, 'mi')
        self.assertTrue(memory['relevant_episodes'])
        self.assertEqual(memory['people']['mi']['meetings'], 110)
        self.assertEqual(memory['people']['mi']['first_meeting']['id'], '0')
        self.assertEqual(len(self.state['story_memory']['episodes']), 96)

    def test_explicit_social_intent_has_bounded_mechanical_effect(self):
        dg_rpg.move(self.state, dg_rpg.where_is(self.state, 'mi'))
        plan = dg_hybrid.preview(self.state, u'Спасибо за помощь!', 'npc', 'mi')
        self.assertEqual(plan['result']['affinity_gain'], 2)
        rejected_claim = dg_hybrid.preview(self.state, u'Не буду благодарить за помощь', 'npc', 'mi')
        self.assertEqual(rejected_claim['result']['affinity_gain'], 0)


class Staging(unittest.TestCase):
    def test_negated_emotion_does_not_trigger_a_crying_sprite(self):
        self.assertEqual(dg_visual.mood(u'Мику не плачет.'), 'normal')
        self.assertEqual(dg_visual.mood(u'Мику заплакала.'), 'cry')

    def test_directions_alone_do_not_count_as_a_generated_scene(self):
        state = dg_rpg.new_game(u'Игорь', 23, 30)
        dg_rpg.move(state, dg_rpg.where_is(state, 'mi'))
        plan = dg_hybrid.preview(state, u'Привет', 'npc', 'mi')
        before = copy.deepcopy(state)
        with self.assertRaises(ValueError):
            dg_hybrid.commit(state, plan, '[stage mi smile normal 2]\n' * 8)
        self.assertEqual(state, before)

    def test_directions_persist_between_pages_without_becoming_dialogue(self):
        scene = u'[stage mi smile close 2]\n[mi] ' + u'Длинная реплика. ' * 45 + u'\n[stage mi sad normal 1]\n[narrator] Мику задумалась.'
        dg_stage.validate_speakers(scene, ('mi',))
        turns = dg_stage.parse(scene, ('mi',))
        self.assertGreater(len(turns), 2)
        self.assertEqual(turns[0]['stage']['mi'], {'emotion':'smile','distance':'close','pose':'2'})
        self.assertEqual(turns[-1]['stage']['mi']['emotion'], 'sad')
        self.assertNotIn('[stage', dg_stage.readable(scene))

    def test_invalid_or_absent_directions_cannot_change_the_cast(self):
        for directive in ('[stage uv smile close 2]', '[stage mi execute close 2]',
                          '[stage mi smile teleport 2]', '[stage mi smile close 99]'):
            with self.assertRaises(ValueError):
                dg_stage.validate_speakers(directive + SCENE, ('mi',))
        turns = dg_stage.parse('[stage uv smile close 2]\n[mi] Hello', ('mi',))
        self.assertNotIn('uv', dg_stage.cast(turns, ('mi',)))


class CgRetrieval(unittest.TestCase):
    def test_matching_requires_subject_action_place_time_and_existing_actors(self):
        row = {'actors':['mi'], 'motifs':['guitar'], 'night':False, 'sunset':False,
               'source':'451835368', 'path':'/cg/mi_guitar.jpg', 'name':'mi_guitar'}
        plan = {'kind':'cg','who':'mi','place':'music','scene_slot':1,
                'description':u'Мику играет на гитаре.'}
        self.assertIsNotNone(dg_gallery.match([row], plan))
        for change in ({'description':u'Мику читает книгу'}, {'place':'library'},
                       {'scene_slot':3}, {'kind':'cg18'}, {'who':'dv'}):
            self.assertIsNone(dg_gallery.match([row], dict(plan, **change)))
        self.assertIsNone(dg_gallery.match([dict(row, actors=['mi','un'])], plan))
        self.assertIsNone(dg_gallery.match([row], dict(plan, hero_pronouns=u'она/её')))
        self.assertIsNone(dg_gallery.match([dict(row, setting='interior')], dict(plan, setting='exterior')))

    def test_catalog_ignores_unlabelled_sensitive_and_non_cg_media(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, 'images', 'cg'))
            for name in ('mi_guitar.jpg','mi_guitar_nude.jpg','unknown.jpg','mi_guitar_night.png'):
                with open(os.path.join(root, 'images', 'cg', name), 'wb') as handle:
                    handle.write(b'placeholder')
            rows = dg_gallery.catalog([root])
            self.assertEqual(len(rows), 2)
            self.assertTrue(all('nude' not in row['path'] for row in rows))
