# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import copy,os,sys,tempfile,unittest
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','don_gen')))
import dg_rpg,dg_visits,dg_agents,dg_turn,dg_hybrid

class Visits(unittest.TestCase):
    def state(self):
        state=dg_rpg.new_game('Герой',23,120)
        state['social']['incident']['status']='resolved'
        state['world']['event']=None
        state['affinity']['mi']=75
        state['met']=['mi']
        dg_agents.ensure(state)
        return state

    def offer(self,state,who='mi',kind='visit'):
        system=dg_visits.ensure(state)
        system['active']={'id':'test:'+who,'who':who,'kind':kind,'moment':dg_visits.moment(state),'route':['gate','clubs','square'],'from':'gate','destination':'square','place':None,'status':'travelling','seen':False,'goal_id':state['npc_agendas']['people'][who]['goal']['id']}
        dg_visits.arrive(state)
        return system['active']

    def test_actual_tick_causes_invitation_and_reads_never_reroll(self):
        state=self.state()
        state['npc_agendas']['people']['mi']['goal']['progress']=2
        dg_rpg.activity(state,'rest')
        self.assertIsNotNone(dg_visits.current(state))
        self.assertEqual(dg_rpg.where_is(state,'mi'),state['place'])
        before=copy.deepcopy(state)
        for _ in range(20):
            dg_visits.current(state);dg_rpg.at_place(state)
        self.assertEqual(state,before)
        with tempfile.TemporaryDirectory() as folder:
            dg_rpg.save(folder,state)
            self.assertEqual(dg_rpg.load(folder,state['id']),state)

    def test_intersection_is_real_and_no_off_route_teleport(self):
        state=self.state();state['place']='library'
        self.offer(state)
        self.assertIsNone(dg_visits.current(state))
        self.assertNotEqual(dg_rpg.where_is(state,'mi'),'library')
        dg_rpg.move(state,'clubs')
        self.assertEqual(dg_visits.current(state)['place'],'clubs')
        self.assertEqual(dg_rpg.where_is(state,'mi'),'clubs')
        self.assertEqual(dg_visits.route('cabin_23','music')[0],'cabin_23')
        self.assertEqual(dg_visits.route('cabin_23','music')[-1],'music')

    def test_no_visit_to_other_private_cabin(self):
        state=self.state();state['place']='cabin_05'
        dg_visits.tick(state,{'mi':'music'})
        self.assertIsNone(state['npc_visits']['active'])
        state['place']=state['housing']['cabin']
        state['npc_visits']['last_turn']=None
        dg_visits.tick(state,{'mi':'music'})
        self.assertIsNotNone(dg_visits.current(state))

    def test_busy_and_night_do_not_spawn_visits(self):
        state=self.state()
        state['social']['incident'].update(status='open',pair=['mi','dv'],place='stage')
        dg_visits.tick(state,{'mi':'music'})
        self.assertIsNone(state['npc_visits']['active'])
        state=self.state();state['slot']=3
        dg_visits.tick(state,{'mi':'music'})
        self.assertIsNone(state['npc_visits']['active'])

    def test_later_and_decline_cost_nothing_and_do_not_reset_cooldown(self):
        state=self.state();event=self.offer(state)
        state['npc_visits']['cooldowns']['mi']=0
        before=(state['slot'],state['energy'],state['affinity']['mi'])
        dg_visits.respond(state,'later')
        self.assertTrue(dg_visits.current(state)['seen'])
        dg_visits.respond(state,'decline')
        self.assertIsNone(dg_visits.current(state))
        self.assertEqual(dg_rpg.where_is(state,'mi'),'gate')
        self.assertEqual((state['slot'],state['energy'],state['affinity']['mi']),before)
        self.assertEqual(state['npc_visits']['cooldowns']['mi'],0)
        with self.assertRaises(ValueError): dg_visits.respond(state,'accept')

    def test_affinity_is_not_romance_date_requires_explicit_choice(self):
        state=self.state();self.offer(state)
        self.assertEqual(state['npc_visits']['romance'],[])
        self.assertIn('date',dict(dg_visits.choices(state,dg_visits.current(state))))
        dg_visits.respond(state,'accept')
        self.assertEqual(state['npc_visits']['romance'],[])
        state=self.state();self.offer(state)
        dg_visits.respond(state,'date')
        self.assertEqual(state['npc_visits']['romance'],['mi'])
        self.assertEqual(state['slot'],1)
        self.assertEqual(state['energy'],92)

    def test_help_discussion_clears_obstacle_but_does_not_repair_remote_equipment(self):
        state=self.state();person=state['npc_agendas']['people']['sh']
        person['goal'].update(status='blocked',blocked_turns=1,progress=0)
        event=self.offer(state,'sh','help')
        dg_visits.respond(state,'accept')
        self.assertEqual(person['goal']['blocked_turns'],0)
        self.assertEqual(person['goal']['progress'],0)
        self.assertNotEqual(person['goal']['status'],'completed')

    def test_failed_narration_leaves_acceptance_and_romance_uncommitted(self):
        state=self.state();self.offer(state)
        with tempfile.TemporaryDirectory() as root:
            dg_rpg.save(root,state)
            before=copy.deepcopy(state)
            pending=dg_turn.begin(state)
            dg_visits.respond(pending['state'],'date')
            self.assertEqual(dg_rpg.load(root,state['id']),before)
            with self.assertRaises(ValueError): dg_turn.finish(root,pending,'test','too short')
            self.assertEqual(dg_rpg.load(root,state['id']),before)

    def test_help_request_is_scheduled_along_route_to_real_task(self):
        state=self.state();state['place']='square'
        state['npc_agendas']['people']['sh']['goal'].update(status='blocked',blocked_turns=1,place='clubs')
        dg_visits.tick(state,{'mi':'stage','sh':'gate'})
        self.assertEqual(state['npc_visits']['active']['who'],'sh')
        self.assertEqual(state['npc_visits']['active']['kind'],'help')
        self.assertIsNone(dg_visits.current(state))
        dg_rpg.move(state,'clubs')
        self.assertEqual(dg_visits.current(state)['who'],'sh')

    def test_partner_has_priority_without_inventing_romance_for_other_friends(self):
        state=self.state();state['affinity']['dv']=90;state['met'].append('dv')
        dg_visits.ensure(state)['romance']=['mi']
        dg_visits.tick(state,{'mi':'stage','dv':'cabins'})
        self.assertEqual(state['npc_visits']['active']['who'],'mi')
        self.assertEqual(state['npc_visits']['romance'],['mi'])

    def test_exhausted_acceptance_is_rejected_without_changes(self):
        state=self.state();self.offer(state);state['energy']=0
        before=copy.deepcopy(state)
        with self.assertRaises(ValueError): dg_visits.respond(state,'date')
        self.assertEqual(state,before)

    def test_long_session_bounded_and_valid(self):
        state=self.state()
        for _ in range(479):
            state['social']['incident']['status']='resolved'
            dg_rpg.activity(state,'rest')
            if dg_visits.current(state): dg_visits.respond(state,'decline')
            dg_rpg.validate(state)
        self.assertLessEqual(len(state['npc_visits']['history']),64)

if __name__=='__main__': unittest.main()
