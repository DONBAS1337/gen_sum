# -*- coding: utf-8 -*-
import copy,json,os,sys,tempfile,unittest
from unittest import mock
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','don_gen')))
import dg_rpg,dg_agents,dg_projects,dg_relationships,dg_consistency,dg_presentation,dg_hybrid,dg_turn,dg_stage
TEXT='[narrator] '+('В музыкальном кружке было тихо. Мику перебирала страницы, а герой слушал её и обдумывал следующий шаг. '*3)

class ProjectAndRelations(unittest.TestCase):
    def setUp(self):
        self.st=dg_rpg.new_game('Герой',23,120)
        self.st['social']['incident']['status']='resolved';self.st['world']['event']=None
        dg_agents.ensure(self.st)
        self.st['npc_agendas']['people']['mi']['active']=True
        self.st['npc_agendas']['people']['mi']['goal'].update(place='music',kind='music')
        self.tick=mock.patch.object(dg_agents,'tick',return_value=[]);self.tick.start();self.addCleanup(self.tick.stop)

    def test_owned_notes_delivery_and_distinct_rehearsal_contributors(self):
        dg_rpg.move(self.st,'music')
        original=copy.deepcopy(self.st)
        with self.assertRaises(ValueError):dg_projects.act(self.st,'concert')
        self.assertEqual(self.st,original)
        dg_rpg.move(self.st,'library');dg_projects.act(self.st,'concert')
        self.assertEqual(self.st['projects']['inventory']['notes'],1)
        self.assertEqual(self.st['projects']['records']['concert']['stage'],1)
        dg_rpg.move(self.st,'music');dg_projects.act(self.st,'concert')
        self.assertEqual(self.st['projects']['inventory']['notes'],0)
        dg_projects.act(self.st,'concert')
        before=copy.deepcopy(self.st)
        with self.assertRaises(ValueError):dg_projects.act(self.st,'concert')
        self.assertEqual(before,self.st)
        goal=dg_projects.offer_goal(self.st,'dv')
        self.assertEqual(goal['place'],'music')
        self.assertTrue(dg_projects.npc_complete(self.st,'dv',goal))
        self.assertEqual(self.st['projects']['records']['concert']['stage'],3)
        dg_rpg.move(self.st,'stage');dg_projects.act(self.st,'concert')
        goal=dg_projects.offer_goal(self.st,'mi')
        self.assertTrue(dg_projects.npc_complete(self.st,'mi',goal))
        self.assertEqual(self.st['projects']['records']['concert']['stage'],4)
        dg_rpg.validate(self.st)

    def test_npc_finds_and_carries_resource_instead_of_player(self):
        goal=dg_projects.offer_goal(self.st,'un')
        self.assertTrue(dg_projects.npc_complete(self.st,'un',goal))
        system=self.st['projects']
        self.assertEqual(system['npc_inventory']['un']['notes'],1)
        self.assertEqual(system['inventory'].get('notes',0),0)
        delivery=dg_projects.offer_goal(self.st,'un')
        self.assertEqual(delivery['place'],'music')
        self.assertTrue(dg_projects.npc_complete(self.st,'un',delivery))
        self.assertEqual(system['npc_inventory']['un']['notes'],0)
        self.assertEqual(system['records']['concert']['stage'],2)

    def test_absent_recipient_cannot_receive_resource(self):
        goal=dg_projects.offer_goal(self.st,'un');dg_projects.npc_complete(self.st,'un',goal)
        delivery=dg_projects.offer_goal(self.st,'un')
        self.st['npc_agendas']['people']['mi']['active']=False
        self.assertNotEqual(dg_rpg.where_is(self.st,'mi'),'music')
        self.assertFalse(dg_projects.npc_complete(self.st,'un',delivery))
        self.assertEqual(self.st['projects']['npc_inventory']['un']['notes'],1)

    def test_courier_handover_can_finish_between_individual_work_ticks(self):
        goal=dg_projects.offer_goal(self.st,'un');dg_projects.npc_complete(self.st,'un',goal)
        courier=dg_projects.offer_goal(self.st,'un')
        recipient=dg_projects.offer_goal(self.st,'mi')
        for who,data in (('un',courier),('mi',recipient)):
            person=self.st['npc_agendas']['people'][who]
            person['goal'].update(data);person['goal'].update(progress=2,status='working')
            person['active']=True
        dg_projects.meetings(self.st)
        self.assertEqual(self.st['projects']['records']['concert']['stage'],2)
        self.assertEqual(self.st['projects']['npc_inventory']['un']['notes'],0)
        before=copy.deepcopy(self.st)
        dg_projects.meetings(self.st)
        self.assertEqual(self.st,before)

    def test_no_project_or_items_from_promises_negations_or_preview(self):
        before=copy.deepcopy(self.st)
        self.assertIsNone(dg_projects.parse(self.st,'Обещаю найти ноты в библиотеке'))
        self.assertIsNone(dg_projects.parse(self.st,'Не найти ноты в библиотеке'))
        dg_rpg.move(self.st,'library');before=copy.deepcopy(self.st)
        plan=dg_hybrid.preview(self.st,'Найти ноты в библиотеке','free')
        self.assertEqual(plan['status'],'ready');self.assertEqual(before,self.st)
        self.assertIn('Ноты',str(plan['effects']))

    def test_promise_changes_trust_only_after_real_personal_contribution(self):
        dg_rpg.move(self.st,'music');dg_relationships.act(self.st,'mi','promise','concert')
        self.assertEqual(self.st['relationships']['promises'][0]['status'],'open')
        self.assertEqual(self.st.get('projects',{}).get('inventory',{}),{})
        dg_rpg.move(self.st,'library');dg_projects.act(self.st,'concert')
        self.assertEqual(self.st['relationships']['promises'][0]['status'],'fulfilled')
        self.assertEqual(self.st['relationships']['people']['mi']['trust'],3)

    def test_broken_promise_apology_does_not_rewrite_history(self):
        dg_rpg.move(self.st,'music');dg_relationships.act(self.st,'mi','promise','concert')
        self.st['day']=5;dg_relationships.tick(self.st)
        self.assertEqual(self.st['relationships']['promises'][0]['status'],'broken')
        before=self.st['relationships']['people']['mi']['trust']
        dg_relationships.act(self.st,'mi','apologize')
        self.assertEqual(self.st['relationships']['people']['mi']['trust'],before)
        self.assertEqual(self.st['relationships']['promises'][0]['status'],'broken')
        dg_rpg.move(self.st,dg_rpg.where_is(self.st,'mi'))
        with self.assertRaises(ValueError):dg_relationships.act(self.st,'mi','apologize')

    def test_boundaries_and_romance_are_explicit_and_saved(self):
        dg_rpg.move(self.st,'music');dg_relationships.act(self.st,'mi','home_visits')
        self.assertFalse(self.st['relationships']['people']['mi']['home_visits'])
        dg_relationships.act(self.st,'mi','invitations')
        self.assertFalse(self.st['relationships']['people']['mi']['invitations'])
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,self.st);self.assertEqual(dg_rpg.load(root,self.st['id']),self.st)

    def test_semantic_promise_proposal_creates_obligation_without_doing_work(self):
        import dg_intent
        dg_rpg.move(self.st,'music')
        row=next(row for row in dg_relationships.available_promises(self.st) if row['target']=='mi' and row['project']=='concert')
        proposal={'status':'ready','intent':'promise','target':'mi','canonical':row['caption'],'deferred':[],'when':None}
        proposal=dg_intent.validate(self.st,proposal)
        before=copy.deepcopy(self.st)
        plan=dg_hybrid.preview(self.st,'Обещаю Мику найти ноты для нашего номера','npc','mi',interpretation=proposal)
        self.assertEqual(plan['status'],'ready');self.assertEqual(self.st,before)
        dg_hybrid.commit(self.st,plan,TEXT)
        self.assertEqual(self.st['relationships']['promises'][0]['status'],'open')
        self.assertEqual(self.st.get('projects',{}).get('inventory',{}).get('notes',0),0)
        self.assertEqual(dg_projects.step(self.st,'concert')[0],0)

    def test_corrupt_items_and_relationships_are_rejected(self):
        dg_projects.ensure(self.st)['inventory']['notes']=-1
        with self.assertRaises(ValueError):dg_rpg.validate(self.st)
        self.st.pop('projects');dg_relationships.person(self.st,'mi')['trust']=999
        with self.assertRaises(ValueError):dg_rpg.validate(self.st)

class AutonomousProjects(unittest.TestCase):
    def test_npcs_can_finish_both_dependent_projects_without_player_contribution(self):
        state=dg_rpg.new_game('Герой',23,120)
        state['id']='a'*32
        for _ in range(479):dg_rpg.activity(state,'rest')
        self.assertEqual({key:row['stage'] for key,row in state['projects']['records'].items()},{'concert':4,'radio':4})
        self.assertEqual(state['projects']['inventory'],{})
        dg_rpg.validate(state)

class SemanticAudit(unittest.TestCase):
    def test_accepts_clean_scene_with_second_independent_request(self):
        client=mock.Mock();client.generate.side_effect=[TEXT,json.dumps({'valid':True,'issues':[]})]
        self.assertEqual(dg_consistency.generate(client,'rules','{}',['mi']),TEXT.strip())
        self.assertEqual(client.generate.call_count,2)
        self.assertIn('scene_untrusted',json.loads(client.generate.call_args_list[1][0][1]))

    def test_repair_once_and_no_silent_failure_open(self):
        wrong={'valid':False,'issues':[{'code':'items','text':'Ноты ещё не получены.'}]}
        client=mock.Mock();client.generate.side_effect=[TEXT,json.dumps(wrong),TEXT,json.dumps({'valid':True,'issues':[]})]
        dg_consistency.generate(client,'rules','{}',['mi'])
        self.assertEqual(client.generate.call_count,4)
        client=mock.Mock();client.generate.side_effect=[TEXT,json.dumps(wrong),TEXT,json.dumps(wrong)]
        with self.assertRaises(ValueError):dg_consistency.generate(client,'rules','{}',['mi'])
        self.assertEqual(client.generate.call_count,4)

    def test_absent_actor_is_rejected_before_semantic_call(self):
        client=mock.Mock();client.generate.side_effect=['[uv] '+TEXT,TEXT,json.dumps({'valid':True,'issues':[]})]
        dg_consistency.generate(client,'rules','{}',['mi'])
        self.assertEqual(client.generate.call_count,3)

    def test_invalid_audit_schema_never_approves_scene(self):
        for verdict in ({'valid':'true','issues':[]},{'valid':True,'issues':[{'code':'time','text':'wrong'}]},{'valid':False,'issues':[]}):
            with self.assertRaises(ValueError):dg_consistency.verdict(json.dumps(verdict))

class Presentation(unittest.TestCase):
    def test_history_bounded_deduplicated_tags_removed_and_saved(self):
        state=dg_rpg.new_game('Герой',23,30)
        for n in range(200):dg_presentation.record(state,str(n),'[stage mi smile normal 1][mi] Привет!')
        self.assertEqual(len(dg_presentation.history(state)),180)
        dg_presentation.record(state,'199','[mi] Другая запись')
        self.assertEqual(len(dg_presentation.history(state)),180)
        self.assertNotIn('[stage',json.dumps(dg_presentation.history(state)))
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,state);self.assertEqual(dg_rpg.load(root,state['id']),state)

    def test_committed_dialogue_history_uses_scene_start_clock(self):
        state=dg_rpg.new_game('Герой',23,30)
        plan=dg_hybrid.preview(state,'Осмотреть ворота','free')
        dg_hybrid.commit(state,plan,TEXT)
        self.assertEqual(state['slot'],1)
        self.assertTrue(all(row['slot']==0 for row in dg_presentation.history(state)))

    def test_narrator_sees_owned_items_after_the_confirmed_action(self):
        state=dg_rpg.new_game('Герой',23,30)
        state['social']['incident']['status']='resolved'
        dg_rpg.move(state,'library')
        plan=dg_hybrid.preview(state,'Найти ноты в библиотеке','free')
        context=dg_hybrid.locked_context(state,plan)
        self.assertEqual(context['confirmed_after_state']['shared_projects']['inventory']['notes'],1)
        self.assertEqual(state.get('projects',{}).get('inventory',{}),{})

    def test_event_badge_reads_are_pure_and_seen_is_explicit(self):
        state=dg_rpg.new_game('Герой',23,30);before=copy.deepcopy(state)
        self.assertTrue(dg_presentation.unread(state));self.assertEqual(state,before)
        dg_presentation.seen(state);self.assertFalse(dg_presentation.unread(state))
        state['day']+=1;self.assertTrue(dg_presentation.unread(state))

if __name__=='__main__':unittest.main()
