# -*- coding: utf-8 -*-
import copy,os,sys,tempfile,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','don_gen'))
import dg_rpg,dg_camp,dg_clock,dg_life,dg_ensemble as crew,dg_personality as personality,dg_characters,dg_hybrid,dg_inventory,dg_relationships,dg_schedule,dg_checkpoints
import test_don_gen_calendar as fixtures

class SharedEvents(unittest.TestCase):
    def state(self,day=3,minute=650,place='music'):
        s=fixtures.Calendar().state(day,minute);s['place']=place;dg_rpg.validate(s)
        if s['social'].get('incident'):s['social']['incident']['status']='resolved'
        s['world']['event']=None;s['met']=['mi','dv','el','sh','sl','un','mz','mt']
        for w in s['met']:s['camp_life']['contacts'][w]={'days':[1,2,3],'count':5};s['affinity'][w]=45
        self.present(s,['mi','dv'],'music');return s

    def present(self,s,people,place):
        for w in people:dg_life.ensure(s)['people'][w]={'place':place,'destination':place,'route':[],'next':dg_clock.absolute(s)+5}

    def start(self,s,kind='concert',variant='acoustic'):
        lead=crew.SPECS[kind]['lead'];self.present(s,[lead],s['place'])
        crew.act(s,'crew:start:'+kind);r=s['ensemble']['records'][-1]
        crew.act(s,'crew:'+r['id']+':plan:'+variant);return r

    def work(self,s,row,day=None):
        if day:s['day']=day
        s['slot']=2;s['camp_life']['minute']=1095;s['energy']=100
        place,people,cost,title=crew._step(s,row);s['place']=place;self.present(s,people,place)
        return crew.act(s,'crew:'+row['id']+':work')

    def test_concert_is_multistage_and_followup_is_next_day(self):
        s=self.state();r=self.start(s);self.assertEqual(r['phase'],'rehearsal')
        self.work(s,r);self.assertEqual(r['phase'],'ready');self.assertIn('hero',r['contributions']['rehearsal'])
        self.assertEqual(s['projects']['records'].get('concert',{}).get('stage',0),0)
        s['day']=5;s['slot']=2;s['camp_life']['minute']=1200;s['place']=crew._venue(s,r)
        outcome=crew.calendar_result(s,'concert');self.assertTrue(outcome);self.assertEqual(r['phase'],'feedback')
        self.assertNotIn('crew:'+r['id']+':feedback:learn',[a['key'] for a in crew.cards(s)])
        s['day']=6;s['camp_life']['minute']=650;s['slot']=0;s['place']=dg_rpg.where_is(s,'mi')
        crew.act(s,'crew:'+r['id']+':feedback:learn');self.assertEqual(r['phase'],'closed');dg_rpg.validate(s)
        nextrow=crew.act(s,'crew:start:concert');new=s['ensemble']['records'][-1]
        self.assertEqual(new['lesson_from'],r['id']);self.assertEqual(new['phase'],'plan');self.assertEqual(new['quality'],1)

    def test_missing_people_cannot_rehearse_and_preview_is_pure(self):
        s=self.state();r=self.start(s);s['slot']=2;s['camp_life']['minute']=1095
        self.present(s,['dv'],'clubs');before=copy.deepcopy(s)
        with self.assertRaises(ValueError):crew.act(s,'crew:'+r['id']+':work')
        self.assertEqual(s,before)

    def test_amplified_concert_needs_material_not_generated_claim(self):
        s=self.state();r=self.start(s,variant='amplified');self.work(s,r)
        self.assertEqual(r['phase'],'technical');s['camp_life']['minute']=1095;s['place']='clubs';self.present(s,['el'],'clubs')
        self.assertFalse(crew._can_work(s,r,True));dg_inventory.ensure(s);s['projects']['inventory']['tape']=1
        self.work(s,r,4);self.assertEqual(s['projects']['inventory']['tape'],0);self.assertEqual(r['phase'],'ready');dg_rpg.validate(s)

    def test_autonomous_work_requires_real_continuous_attendance(self):
        s=self.state();r=self.start(s);s['place']='lake';s['slot']=2;s['camp_life']['minute']=1095
        self.present(s,['mi','dv'],'music');crew.tick(s)
        for minute in (1100,1105,1110,1115):s['camp_life']['minute']=minute;crew.tick(s)
        self.assertEqual(r['phase'],'ready');self.assertNotIn('hero',r['contributions']['rehearsal']);self.assertEqual(r['hero_steps'],['plan'])

    def test_interruption_resets_npc_work_and_private_progress_is_not_public(self):
        s=self.state();r=self.start(s);s['place']='lake';s['slot']=2;s['camp_life']['minute']=1095
        self.present(s,['mi','dv'],'music');crew.tick(s);s['camp_life']['minute']=1100;crew.tick(s)
        self.present(s,['dv'],'clubs');s['camp_life']['minute']=1105;crew.tick(s)
        self.assertEqual(r['progress'],0);self.assertEqual(crew.report(s,'mz')['events'],[])
        r['phase']='ready';self.assertEqual(crew.report(s)['events'][0]['phase'],'rehearsal')
        self.assertEqual(crew.report(s,'mi')['events'][0]['phase'],'ready')

    def test_rain_outing_uses_indoor_preparation_and_calendar_outcome(self):
        s=self.state(day=4,place='library');s['id']=next('%032x'%i for i in range(1000) if __import__('dg_world').weather(dict(s,id='%032x'%i))[0]=='rain')
        r=self.start(s,'outing','quiet');self.assertEqual(crew._step(s,r)[0],'library')
        self.work(s,r);self.assertEqual(r['phase'],'ready')
        s['day']=crew._day(r);s['slot']=1;s['camp_life']['minute']=900;s['place']=crew._venue(s,r)
        result=crew.calendar_result(s,'outing');self.assertTrue(result);self.assertEqual(r['phase'],'feedback')

    def test_radio_requires_research_technical_and_real_broadcast_attendance(self):
        s=self.state(place='clubs');r=self.start(s,'radio','interview')
        self.work(s,r);self.assertEqual(r['phase'],'technical');self.work(s,r,4);self.assertEqual(r['phase'],'ready')
        s['day']=crew._day(r);s['slot']=2;s['camp_life']['minute']=1230;s['place']='radio';self.present(s,r['people'],'radio')
        crew.tick(s);self.assertEqual(r['phase'],'feedback');self.assertTrue(r['outcome']['hero_present'])

    def test_unprepared_concert_has_setback_and_no_retroactive_success(self):
        s=self.state();r=self.start(s);s['day']=5;s['slot']=2;s['camp_life']['minute']=1200;s['place']='lake';crew.tick(s)
        self.assertEqual(r['phase'],'feedback');self.assertFalse(r['outcome']['prepared']);self.assertFalse(r['outcome']['hero_present'])
        self.assertEqual(crew.report(s)['events'][0]['phase'],'feedback')
        self.assertNotIn('rehearsal',r['contributions'])

    def test_shared_event_survives_native_world_branch_restore(self):
        s=self.state();r=self.start(s)
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,s);old=copy.deepcopy(s);self.work(s,r);dg_rpg.save(root,s)
            restored=dg_checkpoints.restore(root,old)
            self.assertEqual(restored['ensemble']['records'][0]['phase'],'rehearsal')
            self.assertEqual(len(dg_checkpoints.branches(root,s['id'])),1)

    def test_late_attendance_does_not_claim_participation_at_start(self):
        s=self.state();r=self.start(s);s['day']=5;s['slot']=2;s['camp_life']['minute']=1200;s['place']='lake';crew.tick(s)
        self.assertFalse(r['outcome']['hero_present']);s['place']=r['outcome']['place'];s['camp_life']['minute']=1205
        crew.calendar_result(s,'concert')
        self.assertTrue(r['outcome']['hero_present']);self.assertEqual(r['outcome']['joined_late'],4*1440+1205)
        self.assertNotIn('rehearsal',r['hero_steps'])

class Individuality(unittest.TestCase):
    def test_same_stance_has_different_preferences(self):
        s=SharedEvents().state();self.assertGreater(personality.stance(s,'dv','bold'),personality.stance(s,'un','bold'))
        self.assertNotEqual(personality.brief(s,'dv')['priorities']['repair'],personality.brief(s,'un')['priorities']['repair'])

    def test_no_farming_and_pressure_has_contextual_consent_consequences(self):
        s=SharedEvents().state();p=personality.react(s,'un','pressure','one')
        self.assertEqual(personality.react(s,'un','pressure','different')['gain'],0)
        for day in (4,5,6):s['day']=day;personality.react(s,'un','pressure',str(day));personality.react(s,'un','insult','insult:'+str(day))
        self.assertFalse(personality.consent(s,'un','hug')[0]);self.assertFalse(personality.brief(s,'un').get('romance_confirmed',False))
        before=personality.brief(s,'un')['stress'];s['day']+=2;personality.tick(s);self.assertLess(personality.brief(s,'un')['stress'],before)

    def test_other_people_do_not_receive_private_emotional_memories(self):
        s=SharedEvents().state();personality.react(s,'mi','setback','private','Секретная неудача Мику')
        cards=dg_characters.cards(s,['dv']);self.assertNotIn('Секретная',str(cards));self.assertEqual(personality.classify('Я не заставлю тебя'),None)
        SharedEvents().present(s,['mi','dv'],'music')
        directed=dg_characters.directions(s,'dv')
        secondary=next(r for r in directed if r['who']=='mi')
        self.assertIn('voice',secondary);self.assertNotIn('personality',secondary)
        self.assertNotIn('Секретная',str(directed))

class Infrastructure(unittest.TestCase):
    def test_every_catalogued_cg_has_a_visual_review_or_an_explicit_exclusion(self):
        import dg_catalog,re
        catalog=dg_catalog.load();visual=dg_catalog.visual()['images']
        cgs=[r for r in catalog['assets'] if r['kind']=='cg'];self.assertEqual(len(cgs),1362)
        for row in cgs:
            self.assertRegex(row['sha256'],r'^[0-9a-f]{64}$');self.assertIn(row['sha256'],visual)
            review=visual[row['sha256']]
            self.assertIn(review['review'],('excluded','ai_reviewed'))
            if review['review']=='excluded':
                self.assertTrue(row['restrictions'] or row['alpha'] or not row['readable'])
            else:
                self.assertIsInstance(review['safe'],bool);self.assertIsInstance(review['whole_scene'],bool)
                self.assertTrue(0<=review['confidence']<=1)
                self.assertNotIn(review['time'],('morning','evening'))

    def test_transient_windows_share_violation_is_retried_with_bound(self):
        from unittest.mock import patch
        import dg_atomic
        count=[0]
        def operation():
            count[0]+=1
            if count[0]<3:
                error=OSError('sharing violation');error.winerror=32;raise error
            return 'saved'
        with patch.object(dg_atomic.os,'name','nt'),patch.object(dg_atomic.time,'sleep'):
            self.assertEqual(dg_atomic.retry(operation),'saved');self.assertEqual(count[0],3)

    def test_permanent_save_failure_preserves_last_world(self):
        from unittest.mock import patch
        import dg_atomic
        s=SharedEvents().state()
        with tempfile.TemporaryDirectory() as folder:
            dg_rpg.save(folder,s);old=copy.deepcopy(s);s['energy']=30
            with patch.object(dg_atomic,'replace',side_effect=OSError('disk unavailable')):
                with self.assertRaises(OSError):dg_rpg.save(folder,s)
            self.assertEqual(dg_rpg.load(folder,s['id']),old)

    def test_pacing_changes_actual_dialogue_time_and_visit_interval(self):
        import dg_pacing,dg_conversation
        s=SharedEvents().state();s['pacing']={'dialogue_minutes':3,'visits':'rare'};before=dg_clock.absolute(s)
        dg_conversation.consume(s,'mi');self.assertEqual(dg_clock.absolute(s)-before,3)
        self.assertGreater(dg_pacing.visit_gap(s),dg_pacing.visit_gap(dict(s,pacing={'visits':'often'})))
        s['pacing']['dialogue_minutes']=True
        with self.assertRaises(ValueError):dg_pacing.validate(s)

    def test_visual_batch_rejects_wrong_identity_and_uncertain_cast_is_withheld(self):
        import importlib.util,dg_catalog
        from pathlib import Path
        spec=importlib.util.spec_from_file_location('review_stock',Path(__file__).resolve().parents[1]/'tools/review_stock_catalog.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        row={'id':'C1','actors':['mi','unknown'],'tags':['dance'],'setting':'exterior','time':'night','safe':True,'whole_scene':True,'confidence':.95,'clothes':'dress'}
        self.assertEqual(module.verdict([row],['C1'])['C1']['review'],'ai_reviewed')
        with self.assertRaises(ValueError):module.verdict([row],['C2'])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'451835368';root.mkdir();(root/'cg.jpg').write_bytes(b'fixture')
            data={'assets':[{'kind':'cg','source':'451835368','relative':'cg.jpg','sha256':'sha','bytes':7,'actors':['mi'],'motifs':['dance']}]}
            visual={'images':{'sha':dict(row,review='ai_reviewed')}}
            self.assertEqual(dg_catalog.cg_rows([str(root)],data,visual),[])
            visual['images']['sha']['actors']=['mi','hero'];self.assertEqual(len(dg_catalog.cg_rows([str(root)],data,visual)),1)

if __name__=='__main__':unittest.main()
