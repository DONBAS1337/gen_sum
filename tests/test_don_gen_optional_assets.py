# -*- coding: utf-8 -*-
"""Tests for private-asset import, per-save 18+ policy and localhost ComfyUI."""
from __future__ import unicode_literals
import os,sys,tempfile,shutil,json,unittest
from unittest.mock import patch
ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
sys.path.insert(0,os.path.join(ROOT,"don_gen"))
import dg_adult,dg_rpg,dg_comfy,dg_hybrid

class OptionalFeatures(unittest.TestCase):
    def setUp(self):
        self.state=dg_rpg.new_game(u"Игрок",20,14)
        self.tmp=tempfile.mkdtemp(prefix="dg-local-")
    def tearDown(self):
        shutil.rmtree(self.tmp)
    def test_adult_mode_is_explicit_per_save_only(self):
        self.assertFalse(dg_adult.enabled(self.state))
        with self.assertRaises(ValueError):
            dg_adult.set_enabled(self.state,True)
        dg_adult.set_enabled(self.state,True,confirmed=True)
        self.assertTrue(dg_adult.enabled(self.state))
        self.assertTrue(dg_adult.can_romance(self.state,"mi"))
        self.assertFalse(dg_adult.can_romance(self.state,"us"))
        self.assertFalse(dg_adult.can_romance(self.state,"uv"))
        dg_rpg.save(self.tmp,self.state)
        loaded=dg_rpg.load(self.tmp,self.state["id"])
        self.assertTrue(dg_adult.enabled(loaded))
        dg_adult.set_enabled(loaded,False)
        self.assertFalse(dg_adult.enabled(loaded))
        self.assertTrue(dg_adult.enabled(self.state))
    def test_cannot_switch_on_for_minor(self):
        st=dg_rpg.new_game(u"Игрок",17,7)
        with self.assertRaises(ValueError):
            dg_adult.set_enabled(st,True,confirmed=True)
        self.assertFalse(dg_adult.enabled(st))
    def test_aged_up_au_does_not_include_child_coded_cast(self):
        dg_adult.set_enabled(self.state,True,confirmed=True)
        for target in ("us","uv"):
            self.assertIsNotNone(dg_adult.validate_action(self.state,u"Интимная сцена с Ульяной",target))
        self.assertIsNone(dg_adult.validate_action(self.state,u"Интимная беседа с Мику","mi"))
        self.assertIn(u"Ульян",dg_adult.scene_policy(self.state,"mi"))
    def test_hybrid_adult_action_blocked_when_off(self):
        trial=dg_hybrid.preview(self.state,u"Интимная беседа с Мику")
        self.assertEqual(trial["status"],"unknown")
        self.assertEqual(self.state["slot"],0)
        self.assertEqual(self.state["energy"],100)
    def test_comfy_local_only(self):
        for url in ("https://example.com","http://example.com:8188",
                    "http://127.0.0.1:8189","http://127.0.0.1:8188/secret",
                    "http://localhost:8188@evil.com"):
            with self.assertRaises(dg_comfy.ComfyError):
                dg_comfy._base(url)
        self.assertEqual(dg_comfy._base("http://127.0.0.1:8188"),"http://127.0.0.1:8188")
    def test_anima_workflow_uses_prompt_placeholder_not_a_guessed_checkpoint(self):
        src={"10":{"class_type":"AnimaTextEncoder","inputs":{"prompt":"__DG_PROMPT__","negative":"__DG_NEGATIVE__"}},
             "20":{"class_type":"KSampler","inputs":{"seed":"__DG_SEED__"}},
             "30":{"class_type":"SaveImage","inputs":{"images":["20",0]}}}
        result=dg_comfy.prepare_workflow(src,u"Anime lakeshore",u"watermark",seed=171)
        self.assertEqual(result["10"]["inputs"]["prompt"],"Anime lakeshore")
        self.assertEqual(result["10"]["inputs"]["negative"],"watermark")
        self.assertEqual(result["20"]["inputs"]["seed"],"171")
        self.assertEqual(src["10"]["inputs"]["prompt"],"__DG_PROMPT__")
        with self.assertRaises(dg_comfy.ComfyError):
            dg_comfy.prepare_workflow({"nodes":[]},u"test")
    def test_api_format_single_clip_encoder_fallback(self):
        data={"5":{"class_type":"CLIPTextEncode","inputs":{"text":"old","clip":["2",0]}}}
        self.assertEqual(dg_comfy.prepare_workflow(data,"new")["5"]["inputs"]["text"],"new")
        data["6"]={"class_type":"CLIPTextEncode","inputs":{"text":"another"}}
        with self.assertRaises(dg_comfy.ComfyError):
            dg_comfy.prepare_workflow(data,"new")
    def test_local_comfy_mock_without_network_or_cloud(self):
        path=os.path.join(self.tmp,"comfy_workflow_api.json")
        nodes={"9":{"class_type":"CLIPTextEncode","inputs":{"text":"__DG_PROMPT__"}},
               "11":{"class_type":"SaveImage","inputs":{"images":["9",0]}}}
        with open(path,"w") as fd:json.dump(nodes,fd)
        uid="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        calls=[]
        def fake_json(url,data=None):
            calls.append((url,data))
            if url.endswith("/prompt"):
                self.assertEqual(data["prompt"]["9"]["inputs"]["text"],u"test prompt")
                return {"prompt_id":uid}
            return {uid:{"outputs":{"11":{"images":[{"filename":"image.png","subfolder":"","type":"output"}]}}}}
        def fake_read(url,**kwargs):
            self.assertIn("/view?",url)
            return b"\x89PNG\r\n\x1a\n" + b"0"*128
        with patch.object(dg_comfy,"_json",side_effect=fake_json),patch.object(dg_comfy,"_read",side_effect=fake_read):
            result=dg_comfy.generate(path,u"test prompt","background",timeout_seconds=20)
        self.assertEqual(result[:8],b"\x89PNG\r\n\x1a\n")
        self.assertEqual(len(calls),2)
    def test_install_script_supports_local_private_repo(self):
        with open(os.path.join(ROOT,"install.ps1"),"rb") as fd:
            txt=fd.read().decode("utf-8")
        self.assertIn('$AssetsDir',txt)
        self.assertIn('map_icon_*.png',txt)
        self.assertIn('map_default.png',txt)
        with open(os.path.join(ROOT,"don_gen","dg_rpg.rpy"),"rb") as fd:
            screen=fd.read().decode("utf-8")
        self.assertIn('DG_MAP_USER = "mods/don_gen/images/gen_assets/map_default.png"',screen)
        self.assertIn('screen dg_rpg_artist_settings:',screen)
        self.assertIn('screen dg_rpg_adult_settings:',screen)

if __name__=="__main__":
    unittest.main()
