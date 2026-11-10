# -*- coding: utf-8 -*-
import copy, os, sys, tempfile, unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','don_gen'))
import dg_rpg,dg_camp,dg_clock,dg_dialogue,dg_conversation,dg_hybrid,dg_turn,dg_world,dg_affection,dg_relationships,dg_agents

class CampLife(unittest.TestCase):
    def state(self):return dg_rpg.new_game('Игорь',23,30,source='bkrr:mi',camp_life=True)

    def arrival(self,state):
        for _ in range(4):
            row=next(r for r in dg_camp.cards(state) if r['key']=='arrival')
            dg_rpg.move(state,row['place']);dg_camp.act(state,'arrival');dg_rpg.validate(state)

    def day2(self,state):
        self.arrival(state);state['slot']=3;state['camp_life']['minute']=1320
        dg_rpg.move(state,state['housing']['cabin']);dg_camp.act(state,'sleep')

    def familiar(self):
        s=self.state();s['day']=3;s['camp_life'].update(arrival=4,minute=600,tour_issued=True,stamps=[p for p,w in dg_camp.TOUR],club='music')
        s['met']=['mi'];s['affinity']['mi']=60;s['camp_life']['contacts']['mi']={'days':[1,2,3],'count':5}
        dg_relationships.person(s,'mi')['trust']=5;s['place']=dg_rpg.where_is(s,'mi')
        return s

    def test_arrival_has_slavya_and_no_premature_concert(self):
        s=self.state()
        self.assertEqual(dg_rpg.at_place(s),[('sl','Славя')])
        self.assertIsNone(dg_world.current(s))
        self.assertEqual(dg_camp.cards(s)[0]['key'],'arrival')
        self.arrival(s)
        self.assertEqual(s['met'],['sl','mt']);self.assertEqual(s['camp_life']['arrival'],4)
        self.assertIsNone(s['camp_life']['club'])

    def test_day2_tour_requires_all_five_visits_and_free_club_choice(self):
        s=self.state();self.day2(s);self.assertEqual(s['day'],2)
        dg_camp.act(s,'tour_issue')
        self.assertFalse(any(r['key'].startswith('join:') for r in dg_camp.cards(s)))
        s['camp_life']['minute']=600
        for place,who in dg_camp.TOUR:
            dg_rpg.move(s,place);dg_camp.act(s,'stamp:'+place)
        dg_rpg.move(s,'music');dg_camp.act(s,'join:music')
        self.assertEqual(s['camp_life']['club'],'music')
        self.assertEqual(set(s['camp_life']['stamps']),set(p for p,w in dg_camp.TOUR))
        self.assertEqual(dg_camp.stage(s,'mi'),'acquaintance');dg_rpg.validate(s)

    def test_tour_cannot_be_forged_at_wrong_place_or_repeated(self):
        s=self.state()
        with self.assertRaises(ValueError):dg_camp.act(s,'tour_issue')
        self.day2(s);dg_camp.act(s,'tour_issue')
        with self.assertRaises(ValueError):dg_camp.act(s,'tour_issue')
        with self.assertRaises(ValueError):dg_camp.act(s,'stamp:music')

    def test_minutes_advance_without_whole_period_jump(self):
        s=self.state();dg_rpg.activity(s,'explore')
        self.assertEqual((s['slot'],s['camp_life']['minute']),(0,570))
        dg_rpg.move(s,'square');self.assertEqual(s['camp_life']['minute'],575)
        s['camp_life']['minute']=710;dg_clock.advance(s,15)
        self.assertEqual((s['slot'],s['camp_life']['minute']),(1,725))

    def test_reply_costs_five_minutes_and_finishing_has_no_extra_cost(self):
        s=self.state();s['place']=dg_rpg.where_is(s,'mi')
        before=s['camp_life']['minute']
        for _ in range(3):dg_conversation.consume(s,'mi')
        self.assertEqual(s['camp_life']['minute'],before+15)
        dg_conversation.end(s);self.assertEqual(s['camp_life']['minute'],before+15)
        self.assertEqual(dg_conversation.rounds(s),0)

    def test_midnight_wraps_to_next_morning_and_preserves_extra_minutes(self):
        s=self.state();s['slot']=3;s['camp_life']['minute']=1435
        dg_clock.advance(s,10)
        self.assertEqual((s['day'],s['slot'],s['camp_life']['minute']),(2,0,425));dg_rpg.validate(s)

    def test_wash_assembly_and_breakfast_have_real_locations_and_state(self):
        s=self.state();self.day2(s)
        dg_rpg.move(s,'washrooms');dg_camp.act(s,'wash')
        self.assertFalse(any(r['key']=='assembly' for r in dg_camp.cards(s)))
        s['camp_life']['minute']=510;dg_rpg.move(s,'square');dg_camp.act(s,'assembly')
        dg_rpg.move(s,'canteen');dg_camp.act(s,'breakfast')
        self.assertTrue(dg_camp._done(s,'breakfast'))
        self.assertFalse(any(r['key']=='breakfast' for r in dg_camp.cards(s)))

    def test_missed_assembly_has_one_bounded_consequence(self):
        s=self.state();self.day2(s);s['camp_life']['minute']=715
        morale=s['world']['morale'];dg_clock.advance(s,10);after=s['world']['morale']
        self.assertLess(after,morale)
        for _ in range(4):dg_camp.refresh(s)
        self.assertEqual(s['world']['morale'],after)

    def test_job_delivery_requires_both_endpoints(self):
        s=self.state();self.day2(s)
        row=next(r for r in dg_camp.cards(s) if r['key']=='job_issue')
        dg_rpg.move(s,row['place']);dg_camp.act(s,'job_issue')
        job=s['camp_life']['jobs']['2'];self.assertEqual(job['kind'],'equipment')
        dg_rpg.move(s,'warehouse');dg_camp.act(s,'job:2')
        self.assertEqual(job['status'],'active');self.assertEqual(job['place'],'stage')
        with self.assertRaises(ValueError):dg_camp.act(s,'job:2')
        dg_rpg.move(s,'stage');dg_camp.act(s,'job:2');self.assertEqual(job['status'],'done')

    def test_disco_has_days_and_time_window(self):
        s=self.familiar();s['slot']=2;s['camp_life']['minute']=1200
        self.assertTrue(any(r['key']=='disco' for r in dg_camp.cards(s)))
        dg_rpg.move(s,'square');dg_camp.act(s,'disco')
        self.assertFalse(any(r['key']=='disco' for r in dg_camp.cards(s)))

    def test_early_dialogue_is_introduction_not_joint_project(self):
        s=self.state();opening=dg_dialogue.opening(s,'mi')
        self.assertEqual(opening['options'],[('0','Личное знакомство')])
        result=dg_dialogue.outcome(s,'mi',0,'support')
        self.assertEqual(result['affinity'],3)
        self.assertIn('ещё не близость',result['text'])

    def test_hug_is_locked_for_stranger_and_consent_is_per_action(self):
        s=self.state();self.assertEqual(dg_affection.options(s,'mi'),[])
        s=self.familiar();out=dg_affection.act(s,'mi','hug');self.assertTrue(out['consent'])
        self.assertNotIn('mi',s.get('npc_visits',{}).get('romance',[]))
        self.assertNotIn(('hug',dg_affection.LABELS['hug']),dg_affection.options(s,'mi'))

    def test_tired_npc_can_decline_without_touch_or_penalty(self):
        s=self.familiar();dg_agents.ensure(s);s['npc_agendas']['people']['mi']['energy']=10
        before=s['affinity']['mi'];out=dg_affection.act(s,'mi','hug')
        self.assertFalse(out['consent']);self.assertEqual(s['affinity']['mi'],before)

    def test_accepted_walk_follows_player_and_expires(self):
        s=self.familiar();dg_affection.act(s,'mi','walk');dg_rpg.move(s,'lake')
        self.assertEqual(dg_rpg.where_is(s,'mi'),'lake')
        dg_clock.advance(s,40);self.assertNotIn('companion',s['camp_life'])

    def test_cancelled_camp_generation_keeps_durable_state(self):
        s=self.state()
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,s);pending=dg_turn.begin(s);dg_camp.act(pending['state'],'arrival')
            self.assertEqual(dg_rpg.load(root,s['id']),s)
            saved=dg_turn.finish(root,pending,'a'*64,'[narrator] '+('Славя встретила новичка у ворот и объяснила дорогу к вожатой. '*4))
            self.assertEqual(saved['camp_life']['arrival'],1);self.assertEqual(saved,dg_rpg.load(root,s['id']))

    def test_minute_clock_and_tour_survive_save_load(self):
        s=self.state();self.day2(s);dg_camp.act(s,'tour_issue')
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,s);self.assertEqual(s,dg_rpg.load(root,s['id']))

    def test_existing_mode_is_explicit_and_does_not_reset_old_progress(self):
        s=dg_rpg.new_game('Игрок',23,30);s['day']=5;s['slot']=2;s['met']=['mi'];s['affinity']['mi']=50
        dg_camp.enable(s,arrival=False)
        self.assertEqual((s['day'],s['slot'],s['met'],s['affinity']['mi']),(5,2,['mi'],50))
        self.assertEqual(s['camp_life']['arrival'],4)

    def test_reject_corrupt_minute_and_companion_data(self):
        s=self.state();s['camp_life']['minute']=800
        with self.assertRaises(ValueError):dg_rpg.validate(s)

    def test_dialogue_variation_counter_never_becomes_time_of_day(self):
        import dg_narrative
        s=self.state();s['slot']=1;s['camp_life']['minute']=800
        for count in (1,2,50,100):
            s['dialogue_counts']={'1:mi':count}
            row=dg_narrative.decorate_dialogue(s,'mi','result',{'text':'Готово','options':[]})
            self.assertEqual(row['narrative']['slot'],1)
            self.assertEqual(row['narrative']['time_of_day'],'День')
        s=self.state();s['camp_life']['companion']={'who':'nobody','until':1000}
        with self.assertRaises(ValueError):dg_rpg.validate(s)

    def test_scene_cache_is_scoped_to_location_and_minute(self):
        import dg_narrative
        s=self.state();first=dg_narrative.context(s,'npc_topics','mi','same')['scene_id']
        s['place']='music';second=dg_narrative.context(s,'npc_topics','mi','same')['scene_id']
        dg_clock.advance(s,5);third=dg_narrative.context(s,'npc_topics','mi','same')['scene_id']
        self.assertEqual(len(set((first,second,third))),3)

    def test_all_four_club_choices_are_available_after_tour(self):
        for club in dg_camp.CLUBS:
            s=self.state();self.day2(s);dg_camp.act(s,'tour_issue');s['camp_life']['minute']=600
            for place,who in dg_camp.TOUR:
                dg_rpg.move(s,place);dg_camp.act(s,'stamp:'+place)
            dg_rpg.move(s,club);dg_camp.act(s,'join:'+club)
            self.assertEqual(s['camp_life']['club'],club)

    def test_one_day_of_high_affinity_does_not_unlock_close_gestures(self):
        s=self.familiar();s['camp_life']['contacts']['mi']['days']=[3];s['affinity']['mi']=100
        self.assertEqual(dg_camp.stage(s,'mi'),'acquaintance')
        self.assertNotIn(('hug',dg_affection.LABELS['hug']),dg_affection.options(s,'mi'))

    def test_disco_music_and_dance_are_contextual_and_do_not_start_romance(self):
        import dg_audio
        s=self.familiar();s['slot']=2;s['camp_life']['minute']=1200;s['place']='square'
        self.assertEqual(dg_rpg.where_is(s,'mi'),'square')
        self.assertEqual(dg_audio.plan(s,'mi','exterior')['music'][0],'lightness_radio')
        self.assertIn(('dance',dg_affection.LABELS['dance']),dg_affection.options(s,'mi'))
        out=dg_affection.act(s,'mi','dance');self.assertTrue(out['consent'])
        self.assertEqual(s['camp_life']['minute'],1210)
        self.assertNotIn('mi',s.get('npc_visits',{}).get('romance',[]))

    def test_missed_job_changes_trust_context_only_once(self):
        s=self.state();self.day2(s)
        row=next(r for r in dg_camp.cards(s) if r['key']=='job_issue');dg_rpg.move(s,row['place']);dg_camp.act(s,'job_issue')
        s['day']=4;dg_camp.refresh(s)
        self.assertEqual(s['camp_life']['jobs']['2']['status'],'missed')
        tension=s['relationships']['people']['mt']['tension']
        self.assertGreater(tension,0);dg_camp.refresh(s)
        self.assertEqual(s['relationships']['people']['mt']['tension'],tension)

    def test_exhausted_work_is_rejected_without_state_change(self):
        s=self.state();self.day2(s)
        row=next(r for r in dg_camp.cards(s) if r['key']=='job_issue');dg_rpg.move(s,row['place']);dg_camp.act(s,'job_issue')
        dg_rpg.move(s,'warehouse');s['energy']=0;before=copy.deepcopy(s)
        with self.assertRaises(ValueError):dg_camp.act(s,'job:2')
        self.assertEqual(before,s)

    def test_romance_needs_more_than_first_day_affinity(self):
        import dg_visits
        s=self.familiar();s['affinity']['mi']=80;s['camp_life']['contacts']['mi']['days']=[3]
        dg_visits.ensure(s);event={'who':'mi','kind':'visit'}
        self.assertNotIn('date',[key for key,title in dg_visits.choices(s,event)])
