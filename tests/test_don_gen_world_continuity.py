# -*- coding: utf-8 -*-
import copy,os,sys,tempfile,threading,time,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','don_gen'))
import dg_rpg,dg_checkpoints,dg_turn,dg_epistemic,dg_life,dg_clock,dg_agents,dg_cards,dg_camp,dg_clues,dg_hybrid,dg_intent,dg_inventory,dg_runtime
import test_don_gen_calendar as fixtures
import test_don_gen_risk_clues as cases

class WorldContinuity(unittest.TestCase):
    def test_native_snapshot_restores_every_subsystem_and_archives_displaced_future(self):
        s=fixtures.Calendar().state();dg_inventory.ensure(s);dg_epistemic.record(s,'recognition','shirt:'+s['id'],{'owner':'hero'},['mi','hero'])
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,s);old=copy.deepcopy(s);future=copy.deepcopy(s);future['energy']=12;future['affinity']['mi']=90;dg_rpg.save(root,future)
            restored=dg_checkpoints.restore(root,old)
            self.assertEqual(restored,old);self.assertEqual(dg_rpg.load(root,s['id']),old)
            rows=dg_checkpoints.branches(root,s['id']);self.assertEqual(len(rows),1)
            recovered=dg_checkpoints.recover(root,s['id'],rows[0]['key']);self.assertEqual(recovered,future)

    def test_unfinished_native_turn_restores_origin_not_uncommitted_effects(self):
        s=fixtures.Calendar().state()
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,s);p=dg_turn.begin(s);p['state']['energy']=0
            restored=dg_checkpoints.restore(root,p['state'],p);self.assertEqual(restored,s)
            with self.assertRaises(ValueError):dg_checkpoints.restore(root,s,{'before':'unknown','state':s})

    def test_private_fact_and_belief_are_distinct_and_recognition_survives_history_cap(self):
        s=fixtures.Calendar().state();dg_epistemic.record(s,'recognition','unique-shirt',{'marker':'шов'},['mi','hero'])
        dg_epistemic.believe(s,'mi','identity','возможно, это герой',40)
        for i in range(270):dg_epistemic.record(s,'account',str(i),{'claim':'text'},['sh'])
        self.assertTrue(dg_epistemic.knows(s,'mi','recognition','unique-shirt'))
        self.assertEqual(dg_epistemic.recall(s,'sl')['facts'],[])
        self.assertEqual(dg_epistemic.recall(s,'mi')['beliefs'][0]['status'],'uncertain');dg_rpg.validate(s)

    def test_physical_instance_keeps_owner_during_loan_and_custody_on_return(self):
        s=fixtures.Calendar().state(5,650);s['place']='clubs';dg_inventory.ensure(s)
        item=next(r for r in s['inventory_world']['instances'] if r['item']=='shirt');key=item['id']
        dg_inventory.act(s,'lend','shirt','sh')
        item=next(r for r in s['inventory_world']['instances'] if r['id']==key)
        self.assertEqual((item['owner'],item['holder']),('hero','sh'))
        s['place']=dg_rpg.where_is(s,'sh');dg_inventory.act(s,'return','shirt','sh')
        item=next(r for r in s['inventory_world']['instances'] if r['id']==key)
        self.assertEqual(item['holder'],'hero');self.assertEqual(len(item['custody']),2)

    def test_route_advances_one_real_edge_in_five_minutes(self):
        s=fixtures.Calendar().state(5,650);dg_agents.ensure(s)
        dg_agents.ensure(s)['people']['un']['goal']['place']='library'
        now=dg_clock.absolute(s);dg_life.ensure(s)['people']['un']={'place':'gate','destination':'gate','route':[],'next':now+5}
        dg_life.tick(s);dg_clock.advance(s,5)
        self.assertEqual(dg_rpg.where_is(s,'un'),'clubs');self.assertNotEqual(dg_rpg.where_is(s,'un'),'library')

    def test_mandatory_medical_job_and_conversation_are_not_abandoned(self):
        s=fixtures.Calendar().state(5,650);s['place']='music';s['dialogue_clock']={'who':'mi','rounds':1}
        dg_clock.advance(s,25)
        self.assertEqual(dg_rpg.where_is(s,'mi'),'music');self.assertEqual(dg_rpg.where_is(s,'cs'),'infirmary')

    def test_daily_appointment_is_known_only_to_its_participants(self):
        s=fixtures.Calendar().state(5,650);dg_life.tick(s);plan=s['npc_life']['plans'][0]
        outsider=next(w for w in dg_life.PEERS if w not in plan['pair'])
        self.assertEqual(dg_life.report(s,outsider)['appointments'],[])
        self.assertEqual(dg_life.report(s,plan['pair'][0])['appointments'][0]['status'],'planned')

    def test_story_requires_multiple_steps_and_real_testimony(self):
        s=cases.ContextEvents().clue_fixture();dg_clues.refresh(s);s['place']='showers'
        with self.assertRaises(ValueError):dg_clues.act(s,'clue:resolve')
        dg_clues.act(s,'clue:listen');dg_clues.act(s,'clue:explain')
        self.assertEqual(s['clues']['active']['phase'],'account')
        dg_clues.act(s,'clue:record')
        with self.assertRaises(ValueError):dg_clues.act(s,'clue:resolve')
        s['place']=dg_rpg.where_is(s,'sh');dg_clues.act(s,'clue:witness')
        s['place']=dg_rpg.where_is(s,'mi');dg_clues.act(s,'clue:resolve')
        self.assertIsNone(s['clues']['active']);self.assertEqual(dg_epistemic.recall(s,'mi')['beliefs'][0]['status'],'refuted')

    def test_dishonest_account_does_not_rewrite_custody_and_can_be_exposed(self):
        s=cases.ContextEvents().clue_fixture();dg_clues.refresh(s);s['place']='showers'
        dg_clues.act(s,'clue:listen');dg_clues.act(s,'clue:lie');self.assertEqual(s['inventory_world']['loans'][0]['holder'],'sh')
        original=s['day']
        while s['day']==original:dg_clock.advance(s,60)
        while dg_clock.minute(s)<540:dg_clock.advance(s,5)
        self.assertEqual(s['clues']['active']['phase'],'lie_discovered')

    def test_card_game_conserves_deck_and_never_exposes_hidden_card(self):
        s=fixtures.Calendar().state(2,960);s['place']='canteen';dg_cards.act(s,'cards:start')
        self.assertEqual(len(dg_cards.public(s)['dealer']),1)
        clone=copy.deepcopy(s);dg_cards.act(s,'cards:hit');dg_cards.act(clone,'cards:hit');self.assertEqual(s,clone)
        while s['card_table']['phase']!='finished':
            dg_cards.act(s,'cards:stand' if s['card_table']['phase']=='playing' else 'cards:next')
            dg_rpg.validate(s)
        self.assertEqual(s['card_table']['round'],3);self.assertFalse(any(r['key']=='cards:start' for r in dg_cards.cards(s)))

    def test_semantic_camp_action_is_checked_against_available_local_steps(self):
        s=fixtures.Calendar().state(5,650);s['place']='washrooms'
        row=next(r for r in dg_camp.cards(s) if r['key']=='wash')
        proposal={'status':'ready','intent':'camp','target':None,'canonical':row['title'],'deferred':[]}
        p=dg_hybrid.preview(s,row['title'],'free',interpretation=proposal)
        self.assertEqual(p['status'],'ready');before=copy.deepcopy(s);dg_hybrid.commit(s,p)
        self.assertNotEqual(s,before)
        with self.assertRaises(ValueError):dg_intent.validate(s,proposal)

    def test_private_turn_memory_does_not_broadcast_to_other_people(self):
        s=fixtures.Calendar().state();s['place']='square'
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,s);p=dg_turn.begin(s);p.update(who='mi',private=True,intention='Объяснение',result='Личный разговор')
            result=dg_turn.finish(root,p,'f'*64,'[mi] '+('Это разговор только между нами. '*8))
            row=result['story_memory']['episodes'][-1];self.assertEqual(row['witnesses'],['mi']);self.assertFalse(row['public'])

    def test_restored_session_ignores_result_of_abandoned_worker(self):
        with tempfile.TemporaryDirectory() as root:
            app=dg_runtime.Runtime(root,{})
            started=threading.Event();release=threading.Event()
            def old():started.set();release.wait(2);return 'old'
            old_thread=app.start(old);self.assertTrue(started.wait(1));app.invalidate();app.start(lambda:'new')
            deadline=time.time()+2
            while app.busy and time.time()<deadline:time.sleep(.01)
            release.set();old_thread.join(1);self.assertFalse(old_thread.is_alive());self.assertEqual(app.result,'new');self.assertFalse(app.busy)

    def test_complete_shift_simulation_stays_valid(self):
        s=fixtures.Calendar().state(3,600)
        steps=0
        while not s['finished']:
            dg_clock.advance(s,60);dg_rpg.validate(s);steps+=1
        self.assertEqual(s['day'],31);self.assertLess(steps,550)

    def test_narrator_does_not_receive_secret_custody_but_auditor_keeps_it(self):
        import dg_narrative,dg_consistency,json
        s=cases.ContextEvents().clue_fixture();dg_clues.refresh(s)
        rules,raw=dg_narrative.request(s,'npc_topics','mi','private-question','Обычный разговор.')
        original=json.loads(raw);visible=dg_consistency.narrator_context(original)
        self.assertTrue(original['scene_identity']['inventory']['world']['loans'])
        self.assertEqual(visible['scene_identity']['inventory']['world'],{})
        self.assertNotIn('sh',visible['scene_identity']['inventory']['people'])
        self.assertEqual(visible['scene_identity']['shared_projects']['inventory'],original['scene_identity']['shared_projects']['inventory'])

    def test_native_pending_snapshot_rejects_wrong_origin(self):
        s=fixtures.Calendar().state()
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,s);p=dg_turn.begin(s);p['origin']['energy']=0
            with self.assertRaises(ValueError):dg_checkpoints.restore(root,p['state'],p)
            self.assertEqual(dg_rpg.load(root,s['id']),s)

    def test_risk_requires_real_location_and_lighting_respects_disco_snapshot(self):
        import dg_risk,dg_visual
        s=fixtures.Calendar().state(6,1200);s['place']='square';scene={'place':'square','day':6,'slot':2,'minute':1200}
        s['camp_life']['minute']=1300
        self.assertEqual(dg_visual.light_slot(s,scene),3);self.assertEqual(dg_visual.light_slot(s),2)
        s['place']='library'
        with self.assertRaises(ValueError):dg_risk.resolve(s,'risk:swim','плыву через озеро')

    def test_night_emergency_calls_doctor_even_if_their_home_schedule_differs(self):
        s=fixtures.Calendar().state(5,1340);s['place']='infirmary'
        s['health']={'kind':'fall','until':dg_clock.absolute(s)+1000,'treated':False,'day':5}
        self.assertEqual(dg_rpg.where_is(s,'cs'),'infirmary')
        self.assertTrue(next(r for r in dg_camp.cards(s) if r['key']=='treatment')['ready'])
