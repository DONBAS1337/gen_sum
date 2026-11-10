# -*- coding: utf-8 -*-
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','don_gen'))
import test_don_gen_calendar as fixtures
import dg_rpg,dg_risk,dg_hybrid,dg_clock,dg_camp,dg_clues,dg_inventory,dg_social,dg_visual,dg_gallery,dg_comfy,dg_world

class ContextEvents(unittest.TestCase):
    def state(self):
        s=fixtures.Calendar().state(5,650);__import__("dg_visits").ensure(s);return s

    def test_custom_tree_needs_no_random_roof_encounter_and_does_not_mutate_preview(self):
        s=self.state();s['place']='forest';before=copy.deepcopy(s)
        p=dg_hybrid.preview(s,'Напился и полез на дерево','free')
        self.assertEqual(p['status'],'ready');self.assertEqual(s,before)
        dg_hybrid.commit(s,p)
        self.assertTrue(dg_risk.impaired(s));self.assertEqual(s['camp_life']['minute'],670)

    def test_tree_is_not_available_indoors_or_for_repeat_or_negation(self):
        s=self.state();s['place']='library'
        self.assertEqual(dg_hybrid.preview(s,'лезу на дерево','free')['status'],'unknown')
        self.assertIsNone(dg_risk.intent('Не лезу на дерево'))
        s['place']='forest';dg_risk.resolve(s,'risk:tree','лезу на дерево')
        with self.assertRaises(ValueError):dg_risk.resolve(s,'risk:tree')

    def test_impairment_expires_and_is_saved(self):
        s=self.state();dg_risk.resolve(s,'risk:drink','выпил пива')
        self.assertTrue(dg_risk.impaired(s))
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,s);s=dg_rpg.load(root,s['id']);self.assertTrue(dg_risk.impaired(s))
        dg_clock.advance(s,180);self.assertFalse(dg_risk.impaired(s))

    def test_electronic_requests_antenna_and_work_requires_clubs(self):
        s=fixtures.Calendar().encounter();s['place']='square'
        self.assertEqual(dg_rpg.where_is(s,'el'),'square')
        self.assertIn('антенн',dg_risk.cards(s)[0]['story'])
        with self.assertRaises(ValueError):dg_risk.resolve(s,'risk:climb')
        s['place']='clubs';self.assertEqual(dg_rpg.where_is(s,'el'),'clubs')
        dg_risk.resolve(s,'risk:safe');self.assertFalse(dg_risk.injured(s))

    def test_shirt_has_one_owner_and_loan_remembers_only_present_witnesses(self):
        s=self.state();s['place']='clubs';dg_inventory.ensure(s)
        self.assertEqual(dg_inventory.bag(s,'hero')['shirt'],1)
        dg_inventory.act(s,'lend','shirt','sh')
        loan=s['inventory_world']['loans'][0]
        self.assertNotIn('mi',loan['witnesses']);self.assertEqual(dg_inventory.bag(s,'hero')['shirt'],0)
        dg_inventory.ensure(s);self.assertEqual(dg_inventory.bag(s,'hero')['shirt'],0)
        dg_inventory.act(s,'return','shirt','sh');self.assertEqual(dg_inventory.bag(s,'hero')['shirt'],1)

    def clue_fixture(self):
        s=self.state();s['place']='clubs';dg_inventory.ensure(s);dg_inventory.act(s,'lend','shirt','sh')
        s['npc_visits']['romance']=['mi'];s['slot']=2;s['camp_life']['minute']=1295
        dg_social.ensure(s)['bonds'][dg_social._pair('sh','un')]=70
        loan=s['inventory_world']['loans'][0]
        s['id']=next('%032x'%i for i in range(1000) if dg_world._seed('%032x'%i,s['day'],loan['id'],'clue')%8==0)
        return s

    def test_borrowed_garment_is_private_question_not_automatic_cheating(self):
        s=self.clue_fixture();before=copy.deepcopy(s['affinity']);dg_clues.refresh(s)
        self.assertIsNotNone(dg_clues.known(s,'mi'));self.assertIsNone(dg_clues.known(s,'sl'))
        self.assertEqual(before,s['affinity']);s['place']='showers'
        dg_clues.act(s,'clue:explain');self.assertIsNone(s['clues']['active'])
        self.assertEqual(before,s['affinity']);dg_rpg.validate(s)

    def test_known_loan_or_no_romance_does_not_create_misunderstanding(self):
        s=self.clue_fixture();s['inventory_world']['loans'][0]['witnesses'].append('mi');dg_clues.refresh(s)
        self.assertIsNone(s['clues']['active'])
        s=self.clue_fixture();s['npc_visits']['romance']=[];dg_clues.refresh(s);self.assertIsNone(s['clues']['active'])

    def test_plain_conversation_and_unwitnessed_gesture_do_not_create_jealousy(self):
        s=self.state();s['npc_visits']['romance']=['mi','un'];dg_clues.ensure(s)['exclusive']=['mi']
        s['affection']={'history':[{'who':'un','day':5,'kind':'hand','consent':True,'witnesses':['un']}],'cooldowns':{}}
        dg_clues.refresh(s);self.assertIsNone(s['clues']['active'])
        s['affection']['history'][0].update(kind='hug',witnesses=['un','mi']);dg_clues.refresh(s)
        self.assertIsNone(s['clues']['active'])

    def test_explicit_agreement_breach_requires_witness_and_is_rate_limited(self):
        s=self.state();s['npc_visits']['romance']=['mi','un'];dg_clues.ensure(s)['exclusive']=['mi']
        s['affection']={'history':[{'who':'un','day':5,'kind':'hand','consent':True,'witnesses':['mi','un']}],'cooldowns':{}}
        dg_clues.refresh(s);self.assertEqual(s['clues']['active']['cause'],'agreement')
        s['place']=dg_rpg.where_is(s,'mi');dg_clues.act(s,'clue:explain')
        dg_clues.refresh(s);self.assertIsNone(s['clues']['active']);self.assertEqual(len(s['clues']['history']),1)

    def test_disco_clothes_respect_frozen_scene_and_fallback(self):
        s=fixtures.Calendar().state(6,1200);s['place']='square'
        scene=dict(day=6,slot=2,place='square',minute=1200)
        s['camp_life']['minute']=1300
        self.assertEqual(dg_visual.clothing(s,'mi',scene),'dress')
        self.assertEqual(dg_visual.clothing(s,'mi'),'pioneer')
        self.assertEqual(dg_visual.sprite_queries('mi','smile',clothes='dress')[0],'mi smile dress')

    def test_real_dance_metadata_is_scoped_to_place_and_time(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'451835368/bkrr/images/cg';folder.mkdir(parents=True)
            (folder/'d7_mi_dance.png').write_bytes(b'image');dg_gallery._cache.clear()
            rows=dg_gallery.catalog([str(Path(root)/'451835368')])
            plan={'kind':'cg','who':'mi','place':'square','scene_slot':2,'setting':'exterior','description':'Мику и герой танцуют на дискотеке.'}
            self.assertEqual(len(dg_gallery.candidates(rows,plan)),1)
            self.assertEqual(dg_gallery.candidates(rows,dict(plan,scene_slot=0)),[])
            self.assertEqual(dg_gallery.candidates(rows,dict(plan,place='clubhouse',setting='interior')),[])

    def test_supplied_workflows_accept_runtime_prompt_and_numeric_seed(self):
        for kind in ('background','cg','cg18'):
            path=Path(__file__).resolve().parents[1]/'don_gen'/('comfy_workflow_%s_api.json'%kind)
            original=json.loads(path.read_text(encoding='utf-8'));p=dg_comfy.prepare_workflow(original,'test scene','test negative',seed=123)
            self.assertEqual(p['90:77']['inputs']['text'],'test scene');self.assertEqual(p['90:76']['inputs']['seed'],123)
            self.assertEqual(original['90:77']['inputs']['text'],'__DG_PROMPT__')
