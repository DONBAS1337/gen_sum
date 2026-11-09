# -*- coding: utf-8 -*-
"""Conservative local CG retrieval. No donor code is imported or executed."""
from __future__ import unicode_literals
import os
import re

IDS = ('3266357374', '3446961537', '2585264824', '3706101137', '451835368')
ACTORS = ('mi', 'dv', 'un', 'sl', 'us', 'mt', 'cs', 'mz', 'el', 'sh', 'uv')
MOTIFS = {
    'guitar':(u'гитар',), 'piano':(u'пианино',u'фортепиано',u'роял'),
    'rehearsal':(u'репетиц',), 'book':(u'книг',u'читает',u'читать'),
    'campfire':(u'костр',u'костёр'), 'tea':(u'чай',u'чаепит'),
    'rain':(u'дожд',), 'beach':(u'пляж',u'берег')}
PLACES = {'guitar':('music','stage','outdoor_stage'), 'piano':('music',),
          'rehearsal':('music','stage','outdoor_stage'), 'book':('library',),
          'campfire':('campfire',), 'tea':('canteen','cabins','music'),
          'rain':('square','gate','forest','forest_path'), 'beach':('beach','lake')}
EXCLUDE = ('nude','naked','sex','ero','bath','shower','underwear','pant','breast',
           'sleep','kiss','hentai','dead','blood','ghost','ending','catday')
_cache = {}


def roots(seven_dl_root):
    if not seven_dl_root:
        return []
    parent = os.path.dirname(os.path.abspath(seven_dl_root))
    return [os.path.join(parent, ident) for ident in IDS
            if os.path.isdir(os.path.join(parent, ident))]


def catalog(directories):
    key = tuple(sorted(os.path.realpath(root) for root in directories))
    if key in _cache:
        return _cache[key]
    result = []
    for root in key:
        for folder, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in ('.git','cache','video','music','sounds','sound'))
            components = folder.replace('\\','/').lower().split('/')
            if not any(part in ('cg','cgs','custom_sg','custom_cg') for part in components):
                continue
            for name in sorted(files):
                stem, ext = os.path.splitext(name.lower())
                if ext not in ('.png','.jpg','.jpeg','.webp') or any(token in stem for token in EXCLUDE):
                    continue
                words = set(re.split(r'[^a-z]+', stem))
                actors = sorted(words.intersection(ACTORS))
                motifs = sorted(words.intersection(MOTIFS))
                if not actors or not motifs:
                    continue
                path = os.path.realpath(os.path.join(folder, name))
                if not os.path.normcase(path).startswith(os.path.normcase(root + os.sep)):
                    continue
                result.append({'path':path.replace('\\','/'), 'actors':actors, 'motifs':motifs,
                               'night':('night' in words), 'sunset':('sunset' in words),
                               'source':os.path.basename(root), 'name':stem,
                               'setting':('exterior' if words.intersection(('ext','outside','verandah','beach','campfire')) else
                                          'interior' if words.intersection(('int','club','library','piano')) else None)})
    _cache[key] = result
    return result


def candidates(rows, plan):
    if not plan or plan.get('kind') != 'cg' or not plan.get('who'):
        return []
    # Many labelled donor CGs also depict the original male protagonist.
    # Without manual solo-cast annotations, abstain for a different hero.
    if plan.get('hero_pronouns', u'он/его') != u'он/его':
        return []
    import dg_stage
    text = dg_stage.readable(plan.get('description',u'')).lower()
    present = set(plan.get('cast') or (plan['who'],))
    present.add(plan['who'])
    place = plan.get('scene_place', plan['place'])
    slot = plan.get('scene_slot')
    ranked = []
    for row in rows:
        if plan.get('setting') and row.get('setting') != plan['setting']:
            continue
        if plan['who'] not in row['actors'] or not set(row['actors']).issubset(present):
            continue
        if slot is None and (row['night'] or row['sunset']):
            continue
        if (row['night'] and slot != 3) or (row['sunset'] and slot != 2):
            continue
        # An unspecified daytime illustration is not substituted into a night scene.
        if slot in (2,3) and not (row['night'] or row['sunset']):
            continue
        topics = [motif for motif in row['motifs']
                  if place in PLACES[motif] and any(stem in text for stem in MOTIFS[motif])]
        if not topics:
            continue
        score = len(topics) * 10 + (2 if row['source'] == '451835368' and plan.get('profile') == 'bkrr:mi' else 0)
        ranked.append((score, row['path'], row))
    ranked.sort(key=lambda item:(-item[0],item[1]))
    return [dict(item[2], confidence='metadata_match') for item in ranked[:3]]


def match(rows, plan):
    rows = candidates(rows,plan)
    return rows[0] if rows else None
