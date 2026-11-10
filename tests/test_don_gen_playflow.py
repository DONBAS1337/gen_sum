# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os,sys,unittest,copy,json,tempfile,shutil
sys.path.insert(0,os.path.abspath(os.path.join(os.path.dirname(__file__),'..','don_gen')))
import dg_rpg,dg_hybrid,dg_presentation,dg_stage,dg_visual,dg_narrative,dg_camp,dg_consistency

class PlayflowRegressions(unittest.TestCase):
    def setUp(self):
        self.s=dg_rpg.new_game('Игорь',23,30,camp_life=True)
        self.s['place']=dg_rpg.where_is(self.s,'mi')
    def test_custom_introduction_survives_reload_and_advances_scene_identity(self):
        root=tempfile.mkdtemp()
        try:
            old=dg_narrative.context(self.s,'npc_topics','mi','mi:0:topics:0')['scene_id']
            plan=dg_hybrid.preview(self.s,'Привет, я Игорь. Давай познакомимся.','npc','mi')
            dg_hybrid.commit(self.s,plan)
            dg_rpg.save(root,self.s);s=dg_rpg.load(root,self.s['id'])
            self.assertIn('mi',s['met']);self.assertEqual(s['dialogue_counts']['1:mi'],1)
            self.assertIn('Знакомы',dg_presentation.status(s,'mi'))
            new=dg_narrative.context(s,'npc_topics','mi','mi:0:topics:1')['scene_id']
            self.assertNotEqual(old,new)
            _,prompt=dg_hybrid.build_request(s,dg_hybrid.preview(s,'Что тебе нравится слушать?','npc','mi'))
            self.assertIn('mi',json.loads(prompt)['met'])
        finally:shutil.rmtree(root)
    def test_history_keeps_long_sentence_and_speaker_order(self):
        text='[narrator] '+('Начало предложения и его продолжение. '*20)+'[mi] Последняя реплика.'
        dg_presentation.record(self.s,'first',text)
        dg_presentation.record(self.s,'second','[hero] Следующий ход.')
        rows=dg_presentation.history_display(self.s)
        self.assertEqual(rows[0]['scene'],'second')
        previous=[r for r in rows if r['scene']=='first']
        self.assertIsNone(previous[0]['who']);self.assertEqual(previous[-1]['who'],'mi')
        self.assertEqual(' '.join(r['text'] for r in previous if r['who'] is None),('Начало предложения и его продолжение. '*20).strip())
    def test_invalid_screen_results_cannot_be_unpacked_or_delete_shift(self):
        for value in (True,False,None,(),('load',),42,'load'):
            self.assertEqual(dg_presentation.command(value),('back',None))
        self.assertEqual(dg_presentation.command(('load','abc')),('load','abc'))
        for value in (True,False,None):self.assertEqual(dg_presentation.creation_command(value),('cancel',None))
        self.assertEqual(dg_presentation.creation_command(('start',)),('start',None))
    def test_music_entrance_is_distinct_from_membership_and_resets_after_travel(self):
        self.s['place']='music'
        self.assertIsNone(dg_visual.door_intent(self.s,'Можно войти в музыкальный кружок?'))
        self.assertIsNone(dg_visual.door_intent(self.s,'Не хочу зайти внутрь кружка'))
        before=copy.deepcopy(self.s)
        plan=dg_hybrid.preview(self.s,'Зайти внутрь музыкального кружка','free')
        self.assertEqual(before,self.s);self.assertEqual(plan['status'],'ready')
        dg_hybrid.commit(self.s,plan)
        self.assertTrue(self.s['music_inside']);self.assertTrue(dg_stage.freeze(self.s)['music_inside'])
        self.assertIsNone(self.s['camp_life']['club'])
        dg_rpg.move(self.s,'square');self.assertFalse(self.s.get('music_inside',False))
        dg_rpg.validate(self.s)
    def test_repetition_detected_but_genuine_answer_allowed(self):
        old='[mi] '+' '.join('слово%d'%i for i in range(100))
        self.assertTrue(dg_presentation.repeats_scene(old,[old]))
        self.assertFalse(dg_presentation.repeats_scene('[mi] Хорошо, я запомнила твоё имя. Продолжим разговор о музыке.',[old]))
    def test_private_scene_is_not_added_to_another_npc_context(self):
        dg_presentation.record(self.s,'private','[un] Это личная история Лены. [hero] Я сохраню её в тайне.')
        self.assertEqual(dg_presentation.recent_scenes(self.s,'mi'),[])
    def test_repeat_repaired_before_any_semantic_audit(self):
        old='[mi] '+' '.join('слово%d'%i for i in range(100))
        new='[mi] '+' '.join('ответ%d'%i for i in range(100))
        class Client:
            def __init__(self):self.calls=0
            def generate(self,*args,**kwargs):
                self.calls+=1
                return [old,new,json.dumps({'valid':True,'issues':[],'claims':[]})][self.calls-1]
        client=Client()
        result=dg_consistency.generate(client,'Write',json.dumps({'previous_scene_texts':[old]}),['mi'])
        self.assertEqual(result,new);self.assertEqual(client.calls,3)
