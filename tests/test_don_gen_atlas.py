# -*- coding: utf-8 -*-
"""Regressions: illustrated map topology, image assets, exit, Yulia secrecy."""
from __future__ import unicode_literals
import os
import sys
import re
import struct
import zlib
import unittest

BASE=os.path.abspath(os.path.join(os.path.dirname(__file__),".."))
sys.path.insert(0,os.path.join(BASE,"don_gen"))
import dg_rpg
import dg_social
import dg_world

def read_png(name):
    path=os.path.join(BASE,"don_gen","images",name)
    with open(path,"rb") as fh:
        stream=fh.read()
    if stream[:8]!=b"\x89PNG\r\n\x1a\n":
        raise AssertionError("Not a real PNG: "+name)
    pos=8
    headers={}
    compressed=[]
    while pos<len(stream):
        length=struct.unpack(">I",stream[pos:pos+4])[0]
        kind=stream[pos+4:pos+8]
        data=stream[pos+8:pos+8+length]
        checksum=struct.unpack(">I",stream[pos+8+length:pos+12+length])[0]
        if (zlib.crc32(kind+data)&0xffffffff)!=checksum:
            raise AssertionError("Bad CRC: "+name)
        headers[kind]=data
        if kind==b"IDAT":
            compressed.append(data)
        pos+=length+12
        if kind==b"IEND":
            break
    width,height,bit_depth,color_type,compression,filter_method,interlace=struct.unpack(">IIBBBBB",headers[b"IHDR"])
    raw=zlib.decompress(b"".join(compressed))
    channels=1 if color_type==3 else 4 if color_type==6 else 3
    assert len(raw)==height*(width*channels+1)
    assert bit_depth==8
    assert filter_method==0 and interlace==0
    return width,height,color_type,raw

class AtlasAndHiddenNPC(unittest.TestCase):
    def test_atlas_has_real_png_data_and_valid_16_9_pixels(self):
        w,h,t,raw=read_png("don_gen_atlas.png")
        self.assertEqual((w,h,t),(1280,720,3))
        self.assertGreater(len(set(raw)),25)
        for icon in ("idle","hover","selected","story","quest","encounter","character"):
            w,h,t,raw=read_png("map_"+icon+".png")
            self.assertEqual((w,h,t),(56,56,6))

    def test_every_non_cabin_place_has_visible_map_point(self):
        with open(os.path.join(BASE,"don_gen","dg_rpg.rpy"),"rb") as f:
            screen=f.read().decode("utf-8")
        start=screen.index("DG_RPG_MAP_PINS = (")
        end=screen.index("DG_RPG_SPRITE_HINTS =",start)
        coords=set(re.findall(r'\("([a-z_]+)",\s*\d+,\s*\d+\)',screen[start:end]))
        canonical=set(dg_rpg.PLACE_NAMES)-set("cabin_%02d" % n for n in range(1,32))
        self.assertEqual(coords,canonical)
        self.assertEqual(len(dg_rpg.PLACE_NAMES),70)
        self.assertIn('action SetScreenVariable("dg_map_selected", slug)',screen)
        self.assertIn('Return(("cabins", dg_map_selected))',screen)
        self.assertIn('dg_map_result[0] == "go"',screen)
        self.assertIn('dg_map_result[1] in dg_rpg.PLACE_NAMES',screen)
        self.assertIn('action Return(("close", None))',screen)
        self.assertIn('hovered SetScreenVariable("dg_map_hover", slug)',screen)

    def test_all_cabins_are_reachable_and_have_names(self):
        game=dg_rpg.new_game(u"Герой",80,14)
        for n in range(1,32):
            place="cabin_%02d" % n
            dg_rpg.move(game,place)
            self.assertEqual(game["place"],place)
            self.assertIn(u"Домик",dg_rpg.PLACE_NAMES[place])
        self.assertEqual(game["slot"],0)

    def test_unrevealed_yulia_never_in_normal_schedule(self):
        game=dg_rpg.new_game(u"Герой",80,14)
        self.assertFalse(game["mystery"]["yulia_discovered"])
        for day in range(1,14):
            game["day"]=day
            for slot in range(4):
                game["slot"]=slot
                self.assertIsNone(dg_rpg.where_is(game,"uv"))
                self.assertNotIn("uv",[x[0] for x in dg_rpg.at_place(game,"forest")])
        self.assertIsNone(dg_social.personal_scene(game,"uv"))
        self.assertNotIn("uv",[x["npc"] for x in (dg_world.current(game),) if x])

    def test_night_secret_unlocks_after_lake_arc_progress(self):
        game=dg_rpg.new_game(u"Герой",20,30)
        dg_rpg.move(game,"forest_path")
        game["slot"]=3
        game["world"]["tracks"]["lake"]["stage"]=2
        self.assertTrue(dg_rpg._try_reveal_yulia(game,"explore"))
        self.assertTrue(game["mystery"]["yulia_discovered"])
        self.assertEqual(dg_rpg.where_is(game,"uv"),"forest_path")
        self.assertFalse(dg_rpg._try_reveal_yulia(game,"explore"))

    def test_long_character_fields_and_dynamic_input_in_ui(self):
        st=dg_rpg.new_game(u"Игорь",1492,40,u"История " * 800)
        self.assertEqual(st["hero"]["age"],1492)
        self.assertGreater(len(st["hero"]["background"]),3000)
        with open(os.path.join(BASE,"don_gen","dg_rpg.rpy"),"rb") as file:
            script=file.read().decode("utf-8")
        self.assertIn('length 8000',script)
        self.assertIn('length 4000',script)
        self.assertIn('dg_rpg_preview_height(editor_text, 175, 300, 150, 55, 24)',script)
        self.assertIn('screen dg_rpg_cabins(region):',script)

if __name__=="__main__":
    unittest.main()

