# -*- coding: utf-8 -*-
import json, os, sys, unittest
from unittest.mock import Mock
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','don_gen'))
import dg_rpg,dg_audio,dg_dialogue,dg_narrative,dg_consistency

class TopicsAudio(unittest.TestCase):
    def setUp(self):self.state=dg_rpg.new_game('Игрок',23,30,source='bkrr:mi')

    def test_exterior_buildings_never_use_indoor_recordings(self):
        for place in ('music','library','clubs','cabin_01','canteen','infirmary'):
            self.state['place']=place
            for slot in range(4):
                self.state['slot']=slot
                keys=dg_audio.plan(self.state,'mi','exterior')['ambience']
                self.assertFalse(any(any(word in key for word in ('library','music_club','inside','dining_hall','int_cabin')) for key in keys),(place,keys))

    def test_interior_library_retains_appropriate_recording(self):
        import dg_world
        # This case verifies dry indoor recordings; rain has its own test.
        self.state['id']=next('%032x'%i for i in range(100) if dg_world.weather(dict(self.state,id='%032x'%i))[0]!='rain')
        self.state['place']='library'
        self.assertEqual(dg_audio.plan(self.state,None,'interior')['ambience'][0],'ambience_library_day')
        self.state['place']='music'
        self.assertEqual(dg_audio.plan(self.state,None,'interior')['ambience'][0],'ambience_music_club_day')

    def test_door_not_played_between_two_exteriors(self):
        self.assertEqual(dg_audio.movement('gate','library','exterior','exterior'),[])
        self.assertTrue(dg_audio.movement('gate','library','exterior','interior'))

    def test_topics_separates_inspiration_from_confirmed_events(self):
        seed='Обещанная помощь задерживается, Мику держит листок.'
        rules,raw=dg_narrative.request(self.state,'npc_topics','mi','topics',seed,choices=[('yes','Обещаю помочь')])
        context=json.loads(raw)
        self.assertEqual(context['scene_seed_untrusted'],seed)
        self.assertNotIn('помощь задерживается',context['anchor_scene'])
        self.assertEqual(context['dialogue_phase'],'npc_topics')
        self.assertIn('90–160',rules)
        self.assertIn('ещё НЕ выбранные',rules)

    def test_dialogue_decoration_does_not_turn_random_twist_into_history(self):
        original=dg_dialogue.opening(self.state,'mi')
        decorated=dg_narrative.decorate_dialogue(self.state,'mi','topics',original)
        self.assertEqual(decorated['text'],original['text'])
        self.assertIn('narrative',decorated)

    def test_repair_receives_previous_draft_but_audit_keeps_original_facts(self):
        text='[narrator] '+('Они стоят у музклуба и разговаривают. '*5)
        client=Mock();client.generate.side_effect=[text,json.dumps({'valid':False,'issues':[{'code':'time','text':'Вечер вместо дня.'}]}),text,json.dumps({'valid':True,'issues':[]})]
        dg_consistency.generate(client,'rules','{"locked":true}',['mi'])
        repaired=json.loads(client.generate.call_args_list[2][0][1])
        self.assertEqual(repaired['scene_to_repair_untrusted'],text)
        audited=json.loads(client.generate.call_args_list[3][0][1])
        self.assertEqual(audited['locked_context'],{'locked':True})
