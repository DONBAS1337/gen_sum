# -*- coding: utf-8 -*-
import copy,json,os,sys,tempfile,unittest
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','don_gen')))
import dg_rpg,dg_housing,dg_visual,dg_hybrid,dg_narrative,dg_resources,dg_art

class HousingTests(unittest.TestCase):
    def test_selection_survives_reload_and_reaches_both_narrators(self):
        state=dg_rpg.new_game('Герой',23,30,cabin='cabin_23',roommate='mi')
        self.assertEqual(state['housing'],{'cabin':'cabin_23','roommate':'mi'})
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,state)
            self.assertEqual(dg_rpg.load(root,state['id'])['housing'],state['housing'])
        plan=dg_hybrid.preview(state,'Исследовать записи','free')
        self.assertEqual(dg_hybrid.locked_context(state,plan)['housing'],state['housing'])
        self.assertEqual(dg_narrative.context(state,'special')['housing'],state['housing'])
        self.assertEqual(state['affinity']['mi'],0)

    def test_roommate_returns_at_night_but_not_from_story_event(self):
        state=dg_rpg.new_game('Герой',23,30,cabin='cabin_23',roommate='mi')
        state['social']['incident']['status']='resolved'
        state['slot']=3
        self.assertEqual(dg_rpg.where_is(state,'mi'),'cabin_23')
        state['social']['incident'].update(status='open',pair=['mi','dv'],place='stage')
        self.assertEqual(dg_rpg.where_is(state,'mi'),'stage')
        state['slot']=1
        self.assertIsNone(dg_housing.location(state,'mi'))

    def test_alone_old_saves_and_bad_choices(self):
        state=dg_rpg.new_game('Герой',23,30,roommate=None)
        state['slot']=3
        self.assertIsNone(dg_housing.location(state,'mi'))
        state.pop('housing')
        before=copy.deepcopy(state)
        dg_rpg.validate(state)
        self.assertNotIn('housing',state)
        for cabin,who in [('cabin_32','mi'),('cabin_01','uv'),('../bad','mt')]:
            with self.assertRaises(ValueError): dg_housing.assign(state,cabin,who)
        state['housing']={'cabin':'bad','roommate':'mi'}
        with self.assertRaises(ValueError): dg_rpg.validate(state)

class VisualTimeTests(unittest.TestCase):
    def test_day_evening_night_have_separate_generated_files(self):
        state=dg_rpg.new_game('Герой',23,30)
        paths=[dg_rpg.asset_path('',state['id'],'background',dg_visual.background_key('music',slot)) for slot in range(4)]
        self.assertEqual(paths[0],paths[1])
        self.assertEqual(len(set(paths)),3)
        self.assertNotEqual(paths[1],dg_rpg.asset_path('',state['id'],'background','music'))
        with self.assertRaises(ValueError): dg_rpg.asset_path('',state['id'],'background','../music_night')
        with self.assertRaises(ValueError): dg_visual.background_key('music',4)

    def test_narration_changes_only_named_reaction(self):
        self.assertEqual(dg_visual.narrated_moods('Мику злится, Алиса смеётся. Лена молчит.',['mi','dv','un']),{'mi':'angry','dv':'laugh'})
        self.assertEqual(dg_visual.narrated_moods('Мику не злится. Алиса не смеётся.',['mi','dv']),{})
        self.assertEqual(dg_visual.narrated_moods('Мику и Алиса спорят и смеются.',['mi','dv']),{})
        self.assertEqual(dg_visual.narrated_moods('Мику смеётся.',['dv']),{})

class LocalMapsTests(unittest.TestCase):
    def test_explicit_map_pack_is_resolved_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='private maps ') as root:
            maps=os.path.join(root,'maps');os.mkdir(maps)
            for name in ('map_bg.jpg','map_avaliable.jpg','map_selected.jpg','map_icon_mi.png'):
                with open(os.path.join(maps,name),'wb') as handle: handle.write(b'local')
            config=os.path.join(root,'resources.json')
            with open(config,'w',encoding='utf-8-sig') as handle: json.dump({'maps_root':root},handle)
            resolved=dg_resources.local_map_root(config,environ={})
            self.assertEqual(os.path.normpath(resolved),os.path.normpath(maps))
            self.assertTrue(dg_resources.local_map_asset(resolved,'map_icon_mi.png'))
            self.assertIsNone(dg_resources.local_map_asset(resolved,'map_icon_../../outside.png'))
            self.assertIsNone(dg_resources.local_map_asset(resolved,'script.rpy'))
            os.unlink(os.path.join(maps,'map_selected.jpg'))
            self.assertIsNone(dg_resources.local_map_root(config,environ={}))

if __name__=='__main__': unittest.main()
