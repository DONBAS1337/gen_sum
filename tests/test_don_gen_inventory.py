# -*- coding: utf-8 -*-
import copy,os,sys,tempfile,unittest,json
from unittest import mock
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','don_gen')))
import dg_rpg,dg_inventory,dg_projects,dg_agents,dg_consistency,dg_facts,dg_intent,dg_hybrid

class InventoryAndBlueprints(unittest.TestCase):
    def setUp(self):
        self.st=dg_rpg.new_game('Герой',23,120)
        self.st['social']['incident']['status']='resolved';self.st['world']['event']=None
        dg_agents.ensure(self.st)
        self.patch=mock.patch.object(dg_agents,'tick',return_value=[]);self.patch.start();self.addCleanup(self.patch.stop)
        self.value={'title':'Общая лагерная стенгазета','item':'paper','recipient':'sl','work_place':'clubs','final_place':'square','theme':'council','participants':['sl','un']}

    def take(self,item):
        dg_rpg.move(self.st,dg_inventory.CATALOG[item]['source'])
        return dg_inventory.act(self.st,'take',item)

    def test_stock_is_finite_and_failed_take_leaves_no_partial_mutation(self):
        self.take('toolkit')
        self.assertEqual(self.st['projects']['inventory']['toolkit'],1)
        self.assertEqual(self.st['inventory_world']['stock']['clubs']['toolkit'],0)
        before=copy.deepcopy(self.st)
        with self.assertRaises(ValueError):dg_inventory.act(self.st,'take','toolkit')
        self.assertEqual(self.st,before)

    def test_lending_and_return_preserve_owner_and_quantity(self):
        self.take('pencil')
        dg_rpg.move(self.st,dg_rpg.where_is(self.st,'mi'))
        dg_inventory.act(self.st,'lend','pencil','mi')
        self.assertEqual(self.st['projects']['inventory']['pencil'],0)
        self.assertEqual(self.st['projects']['npc_inventory']['mi']['pencil'],1)
        loan=self.st['inventory_world']['loans'][0]
        self.assertEqual(loan['status'],'open');self.assertEqual(loan['owner'],'hero')
        dg_rpg.move(self.st,dg_rpg.where_is(self.st,'mi'))
        dg_inventory.act(self.st,'return','pencil','mi')
        self.assertEqual(self.st['projects']['inventory']['pencil'],1)
        self.assertEqual(self.st['inventory_world']['loans'][0]['status'],'returned')
        dg_rpg.move(self.st,dg_rpg.where_is(self.st,'mi'))
        with self.assertRaises(ValueError):dg_inventory.act(self.st,'return','pencil','mi')

    def test_crafting_consumes_materials_but_not_borrowable_tool(self):
        self.take('paper');self.take('paint');self.take('pencil');dg_rpg.move(self.st,'clubs')
        dg_inventory.act(self.st,'craft','poster')
        bag=self.st['projects']['inventory']
        self.assertEqual((bag['paper'],bag['paint'],bag['pencil'],bag['poster']),(0,0,1,1))
        with self.assertRaises(ValueError):dg_inventory.act(self.st,'craft','poster')

    def test_crafted_poster_has_a_real_location_bound_use(self):
        self.take('paper');self.take('paint');self.take('pencil');dg_rpg.move(self.st,'clubs')
        dg_inventory.act(self.st,'craft','poster')
        with self.assertRaises(ValueError):dg_inventory.act(self.st,'use','poster')
        dg_rpg.move(self.st,'square');before=self.st['world']['morale']
        dg_inventory.act(self.st,'use','poster')
        self.assertEqual(self.st['projects']['inventory']['poster'],0)
        self.assertGreater(self.st['world']['morale'],before)

    def test_use_and_meal_restock_only_on_new_day(self):
        self.take('water');self.st['energy']=30
        dg_inventory.act(self.st,'use','water')
        self.assertEqual(self.st['energy'],37)
        stock=self.st['inventory_world']['stock']['canteen']['water']
        dg_inventory.daily(self.st);self.assertEqual(self.st['inventory_world']['stock']['canteen']['water'],stock)
        self.st['day']+=1;dg_inventory.daily(self.st)
        self.assertEqual(self.st['inventory_world']['stock']['canteen']['water'],3)

    def test_legacy_resources_are_not_spawned_again_during_migration(self):
        dg_projects.ensure(self.st)['inventory']['notes']=1
        world=dg_inventory.ensure(self.st)
        self.assertEqual(world['stock']['library']['notes'],0)
        before=copy.deepcopy(self.st);dg_inventory.ensure(self.st)
        self.assertEqual(self.st,before)

    def test_custom_project_is_per_save_and_starts_without_free_items(self):
        key=dg_projects.register(self.st,self.value)
        self.assertTrue(key.startswith('custom_'))
        self.assertEqual(self.st['projects']['records'][key]['stage'],0)
        self.assertEqual(self.st['projects']['inventory'],{})
        other=dg_rpg.new_game('Другой',23,30)
        self.assertNotIn(key,dg_projects.definitions(other))
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,self.st)
            loaded=dg_rpg.load(root,self.st['id'])
            self.assertEqual(loaded,self.st)
            self.assertIn(key,dg_projects.definitions(loaded))

    def test_registration_rejects_unknown_people_items_private_places(self):
        for patch in ({'item':'magic'},{'recipient':'uv'},{'work_place':'cabin_01'},{'participants':['sl','alien']},{'title':'[python]'}):
            with self.assertRaises(ValueError):dg_projects.check_blueprint(dict(self.value,**patch))

    def test_dynamic_chain_uses_real_owned_material_and_cancellation_releases_it(self):
        key=dg_projects.register(self.st,self.value)
        self.take('paper')
        self.assertEqual(self.st['projects']['records'][key]['stage'],1)
        self.assertTrue(dg_inventory.reserved(self.st,'hero','paper'))
        dg_projects.cancel(self.st,key)
        self.assertFalse(dg_inventory.reserved(self.st,'hero','paper'))
        self.assertEqual(self.st['projects']['inventory']['paper'],1)
        dg_rpg.validate(self.st)

    def test_favorite_gifts_improve_trust_only_once_per_day(self):
        self.take('book');dg_rpg.move(self.st,dg_rpg.where_is(self.st,'un'))
        dg_inventory.act(self.st,'give','book','un')
        self.assertEqual(self.st['relationships']['people']['un']['trust'],1)
        self.take('book');dg_rpg.move(self.st,dg_rpg.where_is(self.st,'un'))
        dg_inventory.act(self.st,'give','book','un')
        self.assertEqual(self.st['relationships']['people']['un']['trust'],1)
        self.assertEqual(self.st.get('npc_visits',{}).get('romance',[]),[])

    def test_festival_art_is_not_forced_to_be_music(self):
        value=dict(self.value,theme='festival',activity='organize')
        key=dg_projects.register(self.st,value)
        self.assertEqual(dg_projects.definitions(self.st)[key]['steps'][2][0],'organize')

    def test_specialized_project_requires_a_capable_participant(self):
        value=dict(self.value,theme='radio',participants=['un','sl'])
        with self.assertRaises(ValueError):dg_projects.check_blueprint(value)
        value=dict(self.value,theme='radio',recipient='sh',participants=['sh','un'])
        self.assertEqual(dg_projects.check_blueprint(value)['recipient'],'sh')

    def test_same_scarce_material_is_not_reserved_for_two_projects(self):
        value=dict(self.value,item='notes',theme='festival',recipient='mi',participants=['mi','dv'])
        with self.assertRaises(ValueError):dg_projects.register(self.st,value)
        self.assertNotIn('custom_',str(self.st.get('projects',{}).get('blueprints',{})))

    def test_borrowed_item_cannot_be_pledged_as_own_project_material(self):
        self.take('toolkit');dg_rpg.move(self.st,dg_rpg.where_is(self.st,'mi'))
        dg_inventory.act(self.st,'lend','toolkit','mi')
        value=dict(self.value,item='toolkit',recipient='mi',participants=['mi','dv'])
        with self.assertRaises(ValueError):dg_projects.register(self.st,value)
        self.assertEqual(self.st['projects']['npc_inventory']['mi']['toolkit'],1)

    def test_natural_action_plan_can_take_existing_item_without_mutating_preview(self):
        dg_rpg.move(self.st,'library')
        row=next(row for row in dg_inventory.actions(self.st) if row[0]=='take' and row[1]=='book')
        proposal={'status':'ready','intent':'inventory','target':None,'canonical':row[3],'deferred':[],'when':None}
        proposal=dg_intent.validate(self.st,proposal)
        before=copy.deepcopy(self.st)
        plan=dg_hybrid.preview(self.st,'Взять книгу в библиотеке','free',interpretation=proposal)
        self.assertEqual(plan['status'],'ready');self.assertEqual(self.st,before)
        dg_hybrid.commit(self.st,plan)
        self.assertEqual(self.st['projects']['inventory']['book'],1)

class MachineFacts(unittest.TestCase):
    def facts(self):
        return dg_facts.contract({'scene_anchor':{'day':1,'time':'Утро','place':'Библиотека'},'present_people':['Лена'],
          'confirmed_after_state':{'shared_projects':{'inventory':{'book':1},'npc_inventory':{},'records':{'concert':{'stage':1}}}}})

    def test_machine_rejects_false_facts_even_when_reviewer_says_valid(self):
        claims=[{'kind':'presence','actor':'uv'},{'kind':'place','value':'beach'},{'kind':'slot','value':3},{'kind':'owns','actor':'hero','item':'book','count':2},{'kind':'project_stage','project':'concert','value':4}]
        raw=json.dumps({'valid':True,'issues':[],'claims':claims})
        verdict=dg_consistency.verdict(raw,self.facts())
        self.assertFalse(verdict['valid']);self.assertEqual(len(verdict['issues']),5)

    def test_approved_facts_pass_and_missing_extraction_fails_closed(self):
        claims=[{'kind':'presence','actor':'un'},{'kind':'place','value':'library'},{'kind':'slot','value':0},{'kind':'owns','actor':'hero','item':'book','count':1}]
        self.assertTrue(dg_consistency.verdict(json.dumps({'valid':True,'issues':[],'claims':claims}),self.facts())['valid'])
        with self.assertRaises(ValueError):dg_consistency.verdict('{"valid":true,"issues":[]}',self.facts())

    def test_borrowed_possession_is_not_ownership(self):
        context={'scene_anchor':{'day':1,'time':'Утро','place':'Клубы'},'present_people':['Мику'],
          'confirmed_after_state':{'shared_projects':{'inventory':{},'npc_inventory':{'mi':{'book':1}},'records':{}},
            'inventory':{'world':{'loans':[{'item':'book','owner':'hero','holder':'mi','status':'open'}]}}}}
        facts=dg_facts.contract(context)
        self.assertEqual(dg_facts.check([{'kind':'holds','actor':'mi','item':'book','count':1}],facts),[])
        self.assertTrue(dg_facts.check([{'kind':'owns','actor':'mi','item':'book','count':1}],facts))
        self.assertEqual(dg_facts.check([{'kind':'owns','actor':'hero','item':'book','count':1}],facts),[])

    def test_malformed_facts_cannot_grant_items(self):
        for claim in ({'kind':'owns','actor':'hero','item':'book','count':True},{'kind':'execute','code':'grant'},{'kind':'place','value':[]}):
            with self.assertRaises(ValueError):dg_facts.check([claim],self.facts())

if __name__=='__main__':unittest.main()
