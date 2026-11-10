# -*- coding: utf-8 -*-
import copy,os,sys,tempfile,unittest
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','don_gen'))
import dg_rpg,dg_camp,dg_clock,dg_schedule,dg_world,dg_risk,dg_hero,dg_hybrid,dg_audio,dg_bkrr,dg_stage

class Calendar(unittest.TestCase):
    def state(self,day=5,minute=1200,rain=False,background='Обычный пионер'):
        s=dg_rpg.new_game('Игорь',23,30,background,source='bkrr:mi',camp_life=True)
        s['day']=day;s['slot']=0 if minute<720 else 1 if minute<1080 else 2 if minute<1320 else 3
        s['camp_life'].update(arrival=4,tour_issued=True,stamps=[p for p,w in dg_camp.TOUR],club='music',minute=minute)
        s['id']=next('%032x'%i for i in range(1000) if (dg_world.weather(dict(s,id='%032x'%i))[0]=='rain')==rain)
        return s

    def encounter(self,hurt=True,background='Обычный пионер'):
        for day in (3,4,5,8,9,10):
            for i in range(200):
                s=self.state(day,650,background=background);s['id']='%032x'%i
                rows=dg_risk.cards(s)
                if not rows:continue
                s['place']=rows[0]['place'];shadow=copy.deepcopy(s)
                dg_camp.act(shadow,'risk:climb')
                if dg_risk.injured(shadow)==hurt:return s
        self.fail('No encounter fixture')

    def test_weekly_repeat_and_no_third_day_disco(self):
        for day,expected in ((5,'event:concert'),(12,'event:concert'),(6,'event:weekly_disco'),(13,'event:weekly_disco')):
            s=self.state(day);self.assertIn(expected,[r['key'] for r in dg_schedule.events(s)])
        self.assertNotIn('event:weekly_disco',[r['key'] for r in dg_schedule.events(self.state(3))])

    def test_tournament_time_location_and_no_replay(self):
        s=self.state(2,950);self.assertNotIn('event:cards',[r['key'] for r in dg_camp.cards(s)])
        s['camp_life']['minute']=960;s['place']='canteen'
        self.assertEqual(dg_rpg.where_is(s,'el'),'canteen')
        result=dg_camp.act(s,'event:cards');self.assertIn('Электроника',result['text'])
        self.assertEqual(s['camp_life']['minute'],1010)
        with self.assertRaises(ValueError):dg_camp.act(s,'event:cards')

    def test_rain_moves_concert_and_outing_with_cast(self):
        s=self.state(5,rain=True);self.assertEqual(dg_rpg.where_is(s,'mi'),'clubhouse')
        self.assertEqual(dg_schedule.events(s)[0]['place'],'clubhouse')
        s=self.state(7,930,True);r=dg_schedule.events(s)[0]
        self.assertEqual(r['place'],'clubhouse');self.assertEqual(dg_rpg.where_is(s,'mt'),'clubhouse')
        self.assertIn('дождя',r['story'])
        dry=self.state(7,930);self.assertEqual(dg_schedule.events(dry)[0]['place'],'beach')

    def test_weather_stable_after_save_and_audio_indoors(self):
        s=self.state(rain=True)
        self.assertEqual(dg_audio.plan(dict(s,place='clubhouse'),setting='interior')['ambience'][0],'ambience_hard_rain_inside')
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,s);loaded=dg_rpg.load(root,s['id'])
            self.assertEqual(dg_world.weather(loaded),dg_world.weather(s))

    def test_rain_dance_occurs_in_hall_only(self):
        import dg_affection
        s=self.state(6,rain=True);s['met']=['mi'];s['place']='square'
        self.assertNotIn(('dance',dg_affection.LABELS['dance']),dg_affection.options(s,'mi'))
        s['place']='clubhouse';self.assertIn(('dance',dg_affection.LABELS['dance']),dg_affection.options(s,'mi'))

    def test_background_tags_negation_and_no_free_rewards(self):
        s=self.state(background='Я не музыкант, не спортсмен. Умею паять. Боюсь высоты.')
        self.assertEqual(set(dg_hero.profile(s)['tags']),{'technical','height_fear'})
        self.assertEqual(s['stats']['skill'],0);self.assertEqual(s['met'],[])

    def test_background_changes_tournament_threshold_on_same_roll(self):
        novice=self.state(2,960);expert=copy.deepcopy(novice);expert['hero']['background']='Играю в карты'
        ident=next('%032x'%i for i in range(1000) if 35<=dg_world._seed('%032x'%i,2,'cards')%100<65)
        novice['id']=expert['id']=ident;novice['place']=expert['place']='canteen'
        self.assertNotEqual(dg_camp.act(novice,'event:cards')['text'],dg_camp.act(expert,'event:cards')['text'])

    def test_concert_role_requires_actual_club_and_music(self):
        s=self.state(background='Играю на гитаре');s['place']='stage';s['activity_counts']['practice']=2
        self.assertIn('партию',dg_camp.act(s,'event:concert')['text'])
        s=self.state(background='Играю на гитаре');s['camp_life']['club']='sports';s['place']='stage'
        self.assertIn('слушал',dg_camp.act(s,'event:concert')['text'])

    def test_safe_and_decline_choices_have_no_injury_or_penalty(self):
        original=self.encounter()
        for kind in ('safe','decline'):
            s=copy.deepcopy(original);before=copy.deepcopy(s['affinity']);dg_camp.act(s,'risk:'+kind)
            self.assertFalse(dg_risk.injured(s));self.assertEqual(before,s['affinity']);self.assertEqual(dg_risk.cards(s),[])

    def test_fall_moves_to_infirmary_and_recovery_is_not_instant(self):
        s=self.encounter();r=dg_camp.act(s,'risk:climb')
        self.assertEqual(s['place'],'infirmary');self.assertEqual(r['who'],'cs');self.assertTrue(dg_risk.injured(s))
        with self.assertRaises(ValueError):dg_rpg.activity(s,'explore')
        dg_camp.act(s,'treatment');self.assertTrue(dg_risk.injured(s))
        with self.assertRaises(ValueError):dg_camp.act(s,'treatment')
        dg_clock.advance(s,1440);self.assertFalse(dg_risk.injured(s));dg_rpg.validate(s)

    def test_successful_risk_does_not_fabricate_injury(self):
        s=self.encounter(False);dg_camp.act(s,'risk:climb');self.assertFalse(dg_risk.injured(s))

    def test_risk_preview_no_mutation_replay_and_medical_scene(self):
        s=self.encounter();before=copy.deepcopy(s);p=dg_hybrid.preview(s,'лезу на крышу','free')
        self.assertEqual(s,before);self.assertEqual(p['status'],'ready')
        scene=dg_hybrid.scene_state(s,p);self.assertEqual(scene['place'],'infirmary')
        context=dg_hybrid.locked_context(s,p);self.assertEqual(context['scene_anchor']['place'],dg_rpg.PLACE_NAMES['infirmary'])
        dg_hybrid.commit(s,p,'[cs] Сейчас тебе нужен отдых. Осмотр закончен, а ушиб пройдёт со временем. Не спеши возвращаться к нагрузкам.')
        self.assertTrue(dg_risk.injured(s));dg_rpg.validate(s)
        with self.assertRaises(ValueError):dg_hybrid.commit(s,p)

    def test_risky_future_negation_and_wrong_place(self):
        self.assertIsNone(dg_risk.intent('не лезу на крышу'))
        s=self.encounter();s['place']='infirmary'
        p=dg_hybrid.preview(s,'лезу на крышу','free');self.assertEqual(p['status'],'unknown')

    def test_health_corruption_rejected(self):
        s=self.state();s['health']={'kind':'fall','until':True,'day':1,'treated':False}
        with self.assertRaises(ValueError):dg_rpg.validate(s)

    def test_profile_is_in_both_narrator_contracts(self):
        import dg_narrative
        s=self.state(background='Музыкант и радиолюбитель')
        self.assertIn('music',dg_narrative.context(s,'result',None,'test')['hero_profile']['tags'])
        p=dg_hybrid.preview(s,'смотрю на небо','free')
        self.assertIn('technical',dg_hybrid.locked_context(s,p)['hero_profile']['tags'])

    def test_technical_background_reduces_real_preparation_time(self):
        for bio,expected in (('Обычный пионер',20),('Умею паять',15)):
            s=self.state(2,600,background=bio)
            s['place']=dg_rpg.where_is(s,'mt');dg_camp.act(s,'job_issue')
            job=s['camp_life']['jobs']['2'];self.assertEqual(job['minutes'],expected)
            s['place']='warehouse';before=dg_clock.minute(s);dg_camp.act(s,'job:2')
            self.assertEqual(dg_clock.minute(s)-before,expected);self.assertEqual(job['place'],'stage')

    def test_injury_survives_load_and_low_energy_cannot_commit_climb(self):
        s=self.encounter();s['energy']=0;before=copy.deepcopy(s)
        with self.assertRaises(ValueError):dg_camp.act(s,'risk:climb')
        self.assertEqual(s,before)
        s['energy']=100;dg_camp.act(s,'risk:climb')
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,s);loaded=dg_rpg.load(root,s['id'])
            self.assertTrue(dg_risk.injured(loaded));self.assertEqual(loaded['health'],s['health'])

    def test_rain_background_never_uses_wrong_scene_or_embedded_character(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'bkrr/images/bg';folder.mkdir(parents=True)
            (folder/'ext_forest_day_rainy.jpg').write_bytes(b'image')
            self.assertTrue(dg_bkrr.rain_background(root,'forest',0).endswith('ext_forest_day_rainy.jpg'))
            self.assertIsNone(dg_bkrr.rain_background(root,'forest',3))
            self.assertIsNone(dg_bkrr.rain_background(root,'music',0))
