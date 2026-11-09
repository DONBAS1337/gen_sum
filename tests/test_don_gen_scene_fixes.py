# -*- coding: utf-8 -*-
import copy, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'don_gen'))
import dg_rpg, dg_hybrid, dg_conversation, dg_stage, dg_audio, dg_source_bkrr

class SceneFixes(unittest.TestCase):
    def state(self):
        state=dg_rpg.new_game('Игрок',23,30,source='bkrr:mi')
        state['social']['incident']['status']='resolved'
        state['place']=dg_rpg.where_is(state,'mi')
        return state

    def test_silent_nearby_character_visible_on_hub_and_in_dialogue(self):
        self.assertEqual(dg_stage.cast([],['mi','dv'],'mi'),['mi','dv'])
        cast=dg_stage.cast(dg_stage.parse('[mi] Привет.', ['mi','dv']),['mi','dv'],'mi')
        self.assertEqual(cast,['mi','dv'])
        self.assertEqual(len(dg_stage.positions(cast,'mi')),2)
        self.assertNotIn('un',cast)

    def test_bkrr_bom_reader_does_not_require_sig_codec(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'bkrr/days';folder.mkdir(parents=True)
            (folder/'bkrr_day4.rpy').write_bytes(('\ufefflabel start:\n    mi "Давай настроим эту гитару вместе."\n').encode('utf-8'))
            with patch.object(dg_source_bkrr.io,'open',side_effect=LookupError('unknown encoding: utf-8-sig')):
                rows=dg_source_bkrr.context(root,['mi'],'гитару',4)['examples']
            self.assertEqual(len(rows),1)

    def test_six_committed_replies_share_one_period(self):
        state=self.state();original_slot=state['slot']
        for n in range(6):
            plan=dg_hybrid.preview(state,'Привет, как проходит день?','npc','mi')
            self.assertEqual(plan['status'],'ready')
            dg_hybrid.commit(state,plan,'[mi] Рада тебя видеть. Давай поговорим о сегодняшнем дне и музыке. Сейчас у меня есть немного свободного времени.')
            self.assertEqual(state['slot'],original_slot+(1 if n==5 else 0))
        self.assertEqual(dg_conversation.rounds(state),0)
        self.assertEqual(state['energy'],64)

    def test_cancelled_preview_does_not_spend_exchange(self):
        state=self.state();before=copy.deepcopy(state)
        dg_hybrid.preview(state,'Привет!','npc','mi')
        self.assertEqual(state,before)

    def test_finish_and_movement_charge_partial_session_once(self):
        state=self.state();dg_conversation.consume(state,'mi')
        self.assertTrue(dg_conversation.end(state))
        self.assertFalse(dg_conversation.end(state))
        self.assertEqual(state['slot'],1)
        dg_conversation.consume(state,'mi');dg_rpg.move(state,'gate')
        self.assertEqual(state['slot'],2)
        self.assertEqual(dg_conversation.rounds(state),0)
        dg_rpg.move(state,'square');self.assertEqual(state['slot'],2)

    def test_save_load_preserves_remaining_exchanges(self):
        state=self.state();dg_conversation.consume(state,'mi')
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,state);loaded=dg_rpg.load(root,state['id'])
        self.assertEqual(dg_conversation.rounds(loaded),1)
        dg_rpg.activity(loaded,'rest')
        self.assertEqual(loaded['slot'],1)
        self.assertEqual(dg_conversation.rounds(loaded),0)

    def test_last_night_finish_ends_shift_and_invalid_clock_rejected(self):
        state=self.state();state['day']=state['duration'];state['slot']=3
        dg_conversation.consume(state,'mi');dg_conversation.end(state)
        self.assertTrue(state['finished'])
        for rounds in (True,-1,6,100):
            state['dialogue_clock']={'rounds':rounds,'who':'mi'}
            with self.assertRaises(ValueError):dg_conversation.validate(state)

    def test_audio_follows_location_time_and_explicit_romance(self):
        state=self.state();state['place']='gate';before=copy.deepcopy(state)
        day=dg_audio.plan(state,'mi');self.assertEqual(state,before)
        self.assertEqual(day['ambience'][0],'ambience_camp_entrance_day')
        state['slot']=3;night=dg_audio.plan(state,'mi')
        self.assertNotEqual(day['music'],night['music'])
        self.assertEqual(night['ambience'][0],'ambience_camp_entrance_night')
        state['npc_visits']={'romance':['mi']}
        self.assertEqual(dg_audio.plan(state,'mi')['music'][0],'what_do_you_think_of_me')

    def test_missing_audio_is_skipped_and_effect_requires_real_move(self):
        self.assertIsNone(dg_audio.resolve({'x':'missing'},['x'],lambda p:False))
        self.assertEqual(dg_audio.resolve({'x':'missing','y':'exists'},['x','y'],lambda p:p=='exists'),'exists')
        self.assertEqual(dg_audio.movement('library','library'),[])
        self.assertTrue(dg_audio.movement('gate','library'))
