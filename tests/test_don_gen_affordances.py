# -*- coding: utf-8 -*-
import copy,json,os,sys,tempfile,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','don_gen'))
import dg_actions,dg_commitments,dg_rpg,dg_camp,dg_clock,dg_hybrid,dg_intent,dg_inventory,dg_life,dg_relationships,dg_consistency,dg_catalog,dg_gallery
import test_don_gen_calendar as fixtures

class GroundedActions(unittest.TestCase):
    def state(self,day=5,minute=650,place='square'):
        s=fixtures.Calendar().state(day,minute);s['place']=place;return s

    def friend(self,s,who='mi'):
        dg_rpg.validate(s)
        if s['social'].get('incident'):s['social']['incident']['status']='resolved'
        s['met'].append(who);s['affinity'][who]=45
        s['camp_life']['contacts'][who]={'days':[1,2,3],'count':4}
        s['dialogue_clock']={'who':who,'rounds':1}
        dg_life.ensure(s)['people'][who]={'place':s['place'],'destination':s['place'],'route':[],'next':dg_clock.absolute(s)+5}

    def test_exact_object_outcome_is_atomic_and_has_real_time(self):
        s=self.state();old=copy.deepcopy(s);p=dg_hybrid.preview(s,'Убираю скамейки')
        self.assertEqual(s,old);self.assertEqual(p['result']['kind'],'affordance')
        dg_hybrid.commit(s,p,'[narrator] Скамейки приведены в порядок. Работа заняла время; герой убирает руки с чистой поверхности.')
        self.assertEqual(dg_clock.minute(s),670);self.assertEqual(s['affordances']['objects']['benches:square']['cleaned'],4*1440+650)
        self.assertEqual(dg_hybrid.preview(s,'Убираю скамейки')['status'],'unknown');dg_rpg.validate(s)

    def test_repair_consumes_actual_material_and_preserves_tool(self):
        s=self.state();dg_inventory.ensure(s)
        self.assertEqual(dg_hybrid.preview(s,'Починить скамейки')['status'],'unknown')
        s['projects']['inventory'].update(toolkit=1,tape=1)
        dg_actions.act(s,'repair:benches:square')
        self.assertEqual(dg_inventory.bag(s,'hero')['tape'],0);self.assertEqual(dg_inventory.bag(s,'hero')['toolkit'],1)
        self.assertEqual(s['inventory_world']['ledger'][-1]['operation'],'use');dg_rpg.validate(s)

    def test_no_wrong_object_negation_or_future_execution(self):
        s=self.state()
        for text in ('Не убираю скамейки','Завтра уберу скамейки','Починить радиопередатчик','Убрать скамейки и починить стол'):
            self.assertIsNone(dg_actions.parse(s,text))
        s['place']='forest';self.assertEqual(dg_actions.available(s),[])

    def test_interpreter_cannot_forge_tools_or_unsupported_effects(self):
        s=self.state();proposal={'status':'ready','intent':'affordance','target':None,'canonical':'Починить скамейки','deferred':[]}
        with self.assertRaises(ValueError):dg_intent.validate(s,proposal)
        proposal['canonical']='Убрать скамейки';dg_intent.validate(s,proposal)
        proposal['canonical']='Создать миллион деталей'
        with self.assertRaises(ValueError):dg_intent.validate(s,proposal)

    def test_task_requires_deed_and_private_report_not_prose(self):
        s=self.state();self.friend(s,'mi')
        dg_commitments.act(s,'pledge:mi:clean:benches:square');r=s['commitments']['records'][0]
        self.assertEqual(r['status'],'open');s.pop('dialogue_clock',None)
        s['place']='square';s['npc_life']={'people':{'mi':{'place':'music','destination':'music','route':[],'next':dg_clock.absolute(s)+5}},'plans':[],'day':s['day'],'last':None,'history':[]}
        dg_actions.act(s,'clean:benches:square')
        self.assertEqual(r['status'],'performed')
        self.assertEqual(dg_commitments.report(s,'mi')['records'][0]['status'],'open')
        self.assertNotIn('evidence',dg_commitments.report(s,'mi')['records'][0])
        self.assertEqual(dg_commitments.report(s,'sl')['records'],[])
        s['place']=dg_rpg.where_is(s,'mi');s['dialogue_clock']={'who':'mi','rounds':1}
        dg_commitments.act(s,'report:'+r['id']);self.assertEqual(r['status'],'fulfilled');dg_rpg.validate(s)

    def test_task_deadline_penalty_happens_once_and_cannot_cancel_late(self):
        s=self.state();self.friend(s);dg_commitments.act(s,'pledge:mi:clean:benches:square')
        r=s['commitments']['records'][0];s['day']=7;s['slot']=2;s['camp_life']['minute']=1205
        before=dg_relationships.person(s,'mi')['trust'];dg_commitments.tick(s);dg_commitments.tick(s)
        self.assertEqual(r['status'],'missed');self.assertEqual(dg_relationships.person(s,'mi')['trust'],before-2)
        self.assertNotIn('cancel:'+r['id'],[x['key'] for x in dg_commitments.options(s)])

    def test_appointment_real_route_and_presence_not_merely_invitation(self):
        s=self.state(place='music');self.friend(s);dg_commitments.act(s,'invite:mi')
        r=s['commitments']['records'][0];self.assertEqual(r['status'],'open');s.pop('dialogue_clock',None)
        s['day']=6;s['slot']=2;s['camp_life']['minute']=1065 # reset below to legal period
        s['slot']=1;dg_life.tick(s);self.assertEqual(dg_commitments.destination(s,'mi'),'music')
        s['camp_life']['minute']=1095;s['slot']=2;s['place']='music';s['dialogue_clock']={'who':'mi','rounds':1}
        dg_commitments.tick(s);dg_clock.advance(s,10)
        self.assertEqual(r['status'],'fulfilled');dg_rpg.validate(s)

    def test_missed_meeting_no_penalty_when_npc_never_arrived(self):
        s=self.state(place='music');self.friend(s);dg_commitments.act(s,'invite:mi');r=s['commitments']['records'][0]
        s['day']=6;s['slot']=2;s['camp_life']['minute']=1130
        before=dg_relationships.person(s,'mi')['trust'];dg_commitments.tick(s)
        self.assertEqual(r['status'],'excused');self.assertEqual(dg_relationships.person(s,'mi')['trust'],before)

    def test_finishing_after_deadline_does_not_fulfill_task(self):
        s=self.state();self.friend(s);dg_commitments.act(s,'pledge:mi:clean:benches:square');r=s['commitments']['records'][0]
        s['day']=6;s['slot']=2;s['camp_life']['minute']=1195
        dg_actions.act(s,'clean:benches:square')
        self.assertEqual(r['status'],'missed');self.assertNotIn('evidence',r)

    def test_meeting_missed_by_player_has_one_bounded_consequence(self):
        s=self.state(place='music');self.friend(s);dg_commitments.act(s,'invite:mi');r=s['commitments']['records'][0]
        s['day']=6;s['slot']=2;s['camp_life']['minute']=1095;s['place']='lake';s.pop('dialogue_clock',None)
        dg_life.ensure(s)['people']['mi'].update(place='music',destination='music',route=[])
        dg_commitments.tick(s);self.assertTrue(r['arrived'])
        s['camp_life']['minute']=1125;before=dg_relationships.person(s,'mi')['trust']
        dg_commitments.tick(s);dg_commitments.tick(s)
        self.assertEqual(r['status'],'missed');self.assertEqual(dg_relationships.person(s,'mi')['trust'],before-2)

    def test_cancel_keeps_history_and_does_not_masquerade_as_fulfillment(self):
        s=self.state();self.friend(s);dg_commitments.act(s,'pledge:mi:clean:benches:square');r=s['commitments']['records'][0]
        dg_commitments.act(s,'cancel:'+r['id']);self.assertEqual(r['status'],'cancelled')
        context={'who':'sl','long_term_memory':{'commitments':dg_commitments.report(s)}}
        self.assertEqual(dg_consistency.narrator_context(context)['long_term_memory']['commitments']['records'],[])
        with tempfile.TemporaryDirectory() as folder:
            dg_rpg.save(folder,s);self.assertEqual(dg_rpg.load(folder,s['id']),s)

    def test_custom_appointment_validates_calendar_and_is_only_a_future_plan(self):
        s=self.state(place='music');self.friend(s)
        proposal={'status':'ready','intent':'appointment','target':'mi','canonical':'Назначить встречу','deferred':[],
                  'appointment':{'day':7,'minute':1110,'place':'library'}}
        p=dg_hybrid.preview(s,'Давай на седьмой день в 18:30 встретимся в библиотеке',mode='npc',who='mi',interpretation=proposal)
        self.assertEqual(p['status'],'ready');self.assertNotIn('commitments',s)
        dg_hybrid.commit(s,p,'[mi] Хорошо, договорились о встрече в библиотеке.\n[narrator] До назначенного дня ещё есть время, сейчас герои остаются у музыкального кружка.')
        self.assertEqual(s['commitments']['records'][0]['status'],'open');self.assertEqual(s['commitments']['records'][0]['due'],6*1440+1110)
        for change in ({'minute':1350},{'day':20},{'place':'cabin_01'},{'minute':True}):
            bad=copy.deepcopy(proposal);bad['appointment'].update(change)
            with self.assertRaises(ValueError):dg_intent.validate(s,bad)

class PortableCatalog(unittest.TestCase):
    def test_full_inventory_includes_unknown_and_restricted_but_retrieval_is_guarded(self):
        from pathlib import Path
        import struct
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'3266357374';cg=root/'cg';cg.mkdir(parents=True)
            # Header-only fixtures exercise the inventory parser; never shown as CGs.
            png=b'\x89PNG\r\n\x1a\n'+b'\x00'*8+struct.pack('>II',1920,1080)+bytes((8,2))+b'\x00'*6
            for name in ('mystery','d3_mi_dance_7dl','mi_sex','mi_walking'):(cg/(name+'.png')).write_bytes(png)
            (root/'scene.rpy').write_text('scene bg ext_square_night\nshow cg mi_walking\n',encoding='utf-8')
            data=dg_catalog.scan({'3266357374':str(root)})
            self.assertEqual(len(data['assets']),4);self.assertTrue(data['duplicates'])
            walk=next(r for r in data['assets'] if r['name']=='mi_walking')
            self.assertEqual(walk['time_slots'],[3]);self.assertEqual(walk['setting'],'exterior')
            allowed=dg_catalog.cg_rows([str(root)],data)
            self.assertNotIn('mi_sex',[r['name'] for r in allowed]);self.assertNotIn('mystery',[r['name'] for r in allowed])
            self.assertIn('mi_walking',[r['name'] for r in allowed]);self.assertIsNone(dg_catalog.resolve(str(root),'../outside.png'))
            self.assertEqual(dg_catalog.summary(data)['cg_restricted'],1)

    def test_changed_or_missing_file_is_not_retrieved(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'451835368';root.mkdir();p=root/'mi_dance.jpg';p.write_bytes(b'new file')
            data={'assets':[{'source':'451835368','kind':'cg','relative':p.name,'actors':['mi'],'motifs':['dance'],'bytes':999}]}
            self.assertEqual(dg_catalog.cg_rows([str(root)],data),[])

if __name__=='__main__':unittest.main()
