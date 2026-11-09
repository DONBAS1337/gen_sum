# -*- coding: utf-8 -*-
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','don_gen')))
import dg_rpg, dg_agents, dg_hybrid, dg_intent, dg_cgvision, dg_backend

class AutonomousWorld(unittest.TestCase):
    def state(self):
        state=dg_rpg.new_game('Герой',23,120)
        state['social']['incident']['status']='resolved'
        return state

    def test_decisions_are_persistent_and_once_per_turn(self):
        state=self.state()
        dg_agents.tick(state)
        before=copy.deepcopy(state)
        self.assertEqual(dg_agents.tick(state),[])
        for _ in range(20):
            dg_rpg.at_place(state)
            dg_agents.report(state)
        self.assertEqual(before,state)
        with tempfile.TemporaryDirectory() as folder:
            dg_rpg.save(folder,state)
            self.assertEqual(dg_rpg.load(folder,state['id']),state)

    def test_full_shift_goals_complete_without_player_help(self):
        state=self.state()
        completed=False
        for _ in range(479):
            dg_rpg.activity(state,'rest')
            dg_rpg.validate(state)
            completed |= any(row['status']=='completed' for row in state['npc_agendas']['history'])
        self.assertTrue(completed)
        self.assertLessEqual(len(state['npc_agendas']['history']),64)
        self.assertTrue(all(0<=p['energy']<=100 for p in state['npc_agendas']['people'].values()))
        self.assertTrue(all(0<=n<=100 for n in state['world']['preparations'].values()))

    def test_preview_cancellation_does_not_advance_npc(self):
        state=self.state()
        before=copy.deepcopy(state)
        dg_hybrid.preview(state,'Исследовать старые записи','free')
        self.assertEqual(state,before)

    def test_help_completes_goal_only_when_present_and_applicable(self):
        state=self.state()
        person=dg_agents.ensure(state)['people']['mi']
        person['goal'].update(kind='music',place='music',arc='festival',progress=2)
        person['active']=True
        self.assertIsNone(dg_agents.assist(state,'mi','practice'))
        dg_rpg.move(state,'music')
        self.assertIsNone(dg_agents.assist(state,'mi','search'))
        self.assertIsNotNone(dg_agents.assist(state,'mi','practice'))
        self.assertEqual(person['goal']['status'],'completed')
        preparations=state['world']['preparations']['festival']
        self.assertIsNone(dg_agents.assist(state,'mi','practice'))
        self.assertEqual(preparations,state['world']['preparations']['festival'])

    def test_absence_night_and_corrupt_save(self):
        state=self.state()
        system=dg_agents.ensure(state)
        self.assertNotIn('uv',system['people'])
        state['slot']=3
        dg_agents.tick(state)
        self.assertIsNone(dg_agents.location(state,'mi'))
        system['people']['mi']['goal']['progress']='bad'
        with self.assertRaises(ValueError): dg_rpg.validate(state)

class ComplexIntent(unittest.TestCase):
    def setUp(self):
        self.state=dg_rpg.new_game('Герой',23,30)
        self.state['social']['incident']['status']='resolved'
        dg_rpg.move(self.state,'stage')
        self.proposal={'status':'ready','intent':'help','target':'mi','canonical':'Помочь Мику с репетицией',
                       'deferred':['Завтра поискать записи'],'when':None}

    def test_conditional_and_future_need_semantics(self):
        for text in ('Если пойдёт дождь, останусь читать','Обещаю завтра помочь Мику','Сначала помогу, потом отдохну'):
            self.assertTrue(dg_intent.needs_ai(text,'npc'))
        self.assertFalse(dg_intent.needs_ai('Спасибо за музыку','npc'))

    def test_only_first_step_commits_and_future_is_remembered(self):
        before=copy.deepcopy(self.state)
        plan=dg_hybrid.preview(self.state,'Сначала помогу Мику, потом поищу записи','free',interpretation=self.proposal)
        self.assertEqual(plan['status'],'ready')
        self.assertEqual(self.state,before)
        entry=dg_hybrid.commit(self.state,plan)
        self.assertEqual(self.state['slot'],1)
        self.assertEqual(entry['deferred'],self.proposal['deferred'])
        self.assertEqual(self.state['story_memory']['episodes'][-1]['deferred'],self.proposal['deferred'])
        self.assertEqual(self.state['stats']['curiosity'],before['stats']['curiosity'])

    def test_false_condition_and_absent_target_do_nothing(self):
        original=copy.deepcopy(self.state)
        self.proposal['when']={'weather':'rain','not':False}
        with self.assertRaises(ValueError): dg_intent.validate(self.state,self.proposal)
        self.proposal['when']=None
        self.proposal['target']='uv'
        with self.assertRaises(ValueError): dg_intent.validate(self.state,self.proposal)
        self.assertEqual(self.state,original)

    def test_mismatched_or_unclear_proposals_and_stale_state(self):
        self.proposal['intent']='search'
        with self.assertRaises(ValueError): dg_intent.validate(self.state,self.proposal)
        self.assertEqual(dg_intent.validate(self.state,{'status':'clarify','question':'Что сделать первым?'})['status'],'clarify')
        self.proposal['intent']='help'
        self.proposal['_state']='bad'
        with self.assertRaises(ValueError):
            dg_hybrid.preview(self.state,'Помочь Мику','free',interpretation=self.proposal)

    def test_promising_help_does_not_complete_help(self):
        self.proposal.update(intent='talk',canonical='Обещаю Мику помочь завтра')
        plan=dg_hybrid.preview(self.state,'Обещаю Мику помочь завтра','npc','mi',interpretation=self.proposal)
        self.assertEqual(plan['result']['kind'],'custom_npc')
        self.assertNotIn('impact',plan['result'])

class VisualMatching(unittest.TestCase):
    def setUp(self):
        self.plan={'who':'mi','cast':['mi'],'scene_slot':1,'setting':'interior','description':'Мику играет на гитаре','hero_pronouns':'он/его'}
        self.verdict={'match':True,'confidence':.98,'ambiguous':False,'actors':['mi','hero'],'setting':'interior',
                      'time':'day','action_tags':['guitar'],'reasons':['Мику играет на гитаре.']}

    def test_matching_is_allowed_but_cast_action_and_time_must_match(self):
        self.assertTrue(dg_cgvision.judge(self.verdict,self.plan)['accepted'])
        for field,value in [('actors',['mi','dv']),('actors',['unknown']),('time','night'),('setting','exterior'),
                            ('action_tags',['book']),('ambiguous',True),('confidence',.8)]:
            wrong=dict(self.verdict,**{field:value})
            self.assertFalse(dg_cgvision.judge(wrong,self.plan)['accepted'],field)

    def test_malformed_or_missing_image_abstains(self):
        for patch in ({'confidence':True},{'ambiguous':'false'},{'actors':'mi'},{'action_tags':['bogus']}):
            with self.assertRaises(ValueError): dg_cgvision.judge(dict(self.verdict,**patch),self.plan)
        self.assertIsNone(dg_cgvision.cached('missing','missing.png',self.plan))

    def test_cache_is_specific_to_image_and_scene_including_rejections(self):
        with tempfile.TemporaryDirectory() as folder:
            path=os.path.join(folder,'candidate.png')
            with open(path,'wb') as handle: handle.write(b'fake-image')
            client=mock.Mock()
            client.generate.return_value=json.dumps(dict(self.verdict,match=False))
            self.assertFalse(dg_cgvision.verify(client,path,self.plan,folder)['accepted'])
            dg_cgvision.verify(client,path,self.plan,folder)
            self.assertEqual(client.generate.call_count,1)
            dg_cgvision.verify(client,path,dict(self.plan,scene_slot=2),folder)
            self.assertEqual(client.generate.call_count,2)
            with open(path,'wb') as handle: handle.write(b'different-image')
            dg_cgvision.verify(client,path,self.plan,folder)
            self.assertEqual(client.generate.call_count,3)
            with open(os.path.join(folder,'cg_vision.json')) as handle:
                self.assertNotIn('base64',handle.read())

    def test_backend_sends_image_but_redacts_trace(self):
        client=dg_backend.Client(tempfile.gettempdir())
        client._models=[{'slug':'test','supported_reasoning_levels':[]}]
        trace={}
        with mock.patch.object(client,'_authorized',return_value=io.BytesIO()),mock.patch.object(dg_backend,'_response_text',return_value='{}'):
            client.generate('rules','scene',model='test',trace=trace,images=['data:image/png;base64,YWJj'])
            body=json.loads(client._authorized.call_args[0][1].decode('utf-8'))
        self.assertEqual(body['input'][0]['content'][1]['type'],'input_image')
        self.assertNotIn('YWJj',json.dumps(trace))

if __name__=='__main__': unittest.main()
