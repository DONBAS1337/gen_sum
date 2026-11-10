# -*- coding: utf-8 -*-
"""Conservative local CG retrieval. No donor code is imported or executed."""
from __future__ import unicode_literals
import os
import re

IDS = ('3266357374', '3446961537', '2585264824', '3706101137', '451835368')
ACTORS = ('mi', 'dv', 'un', 'sl', 'us', 'mt', 'cs', 'mz', 'el', 'sh', 'uv')
MOTIFS = {
    'sing':(u'поёт',u'поет',u'петь',u'песню'), 'picnic':(u'пикник',), 'confession':(u'признание в любви',u'признаться в любви'), 'draw':(u'рисует',u'рисовать',u'рисунок'),
    'guitar':(u'гитар',), 'piano':(u'пианино',u'фортепиано',u'роял'),
    'rehearsal':(u'репетиц',), 'book':(u'книг',u'читает',u'читать'),
    'campfire':(u'костр',u'костёр'), 'tea':(u'чай',u'чаепит'),
    'cards':(u'карточ',u'турнир'), 'concert':(u'концерт',u'выступлен'), 'walk':(u'прогул',u'гуля'), 'hug':(u'обня',u'объят'), 'dance':(u'танц',u'танец',u'дискотек'), 'rain':(u'дожд',), 'beach':(u'пляж',u'берег')}
PLACES = {'guitar':('music','stage','outdoor_stage'), 'piano':('music',),
          'sing':('music','stage','outdoor_stage','campfire','square'), 'picnic':('beach','lake','forest','campfire'), 'confession':('music','square','beach','lake','forest','forest_path','cabins'), 'draw':('library','lake','beach','music'),
          'rehearsal':('music','stage','outdoor_stage'), 'book':('library',),
          'campfire':('campfire',), 'tea':('canteen','cabins','music'),
          'cards':('canteen','clubs','clubhouse'),'concert':('stage','music','clubhouse'),'walk':('square','forest','forest_path','beach','lake','cabins'),'hug':('square','music','clubs','library','beach','lake','cabins','forest_path'),'dance':('square','clubhouse'), 'rain':('square','gate','forest','forest_path'), 'beach':('beach','lake')}
EXCLUDE = ('nude','naked','sex','ero','bath','shower','underwear','pant','breast',
           'sleep','kiss','hentai','dead','blood','ghost','ending','catday')
_cache = {}


def roots(seven_dl_root):
    if not seven_dl_root:
        return []
    parent = os.path.dirname(os.path.abspath(seven_dl_root))
    return [os.path.join(parent, ident) for ident in IDS
            if os.path.isdir(os.path.join(parent, ident))]


def catalog(directories,include_index=True):
    key = tuple(sorted(os.path.realpath(root) for root in directories))
    cache_key=(key,include_index)
    if cache_key in _cache:
        return _cache[cache_key]
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
                annotated_dance=os.path.basename(root)=='451835368' and stem=='d7_mi_dance' or os.path.basename(root)=='3266357374' and stem in ('d3_mi_dance_7dl','d3_mi_dance_bordo_7dl')
                result.append({'time_slots':(2,3) if annotated_dance else None,'path':path.replace('\\','/'), 'actors':actors, 'motifs':motifs,
                               'night':('night' in words), 'sunset':('sunset' in words),
                               'source':os.path.basename(root), 'name':stem,
                               'setting':('exterior' if annotated_dance else 'exterior' if words.intersection(('ext','outside','verandah','beach','campfire')) else
                                          'interior' if words.intersection(('int','club','library','piano')) else None)})
    import dg_catalog
    inventory=dg_catalog.load() if include_index else {'assets':[]}
    indexed=dg_catalog.cg_rows(key,inventory)
    indexed_paths=set((r['source'],r['relative']) for r in inventory.get('assets',[]) if r['kind']=='cg')
    # Known overlays/restricted files must not sneak back through the filename fallback.
    result=[r for r in result if not any((os.path.basename(root),os.path.relpath(r['path'],root).replace('\\','/')) in indexed_paths for root in key)]
    seen=set(r['path'] for r in result)
    result.extend(r for r in indexed if r['path'] not in seen)
    _cache[cache_key] = result
    return result


def candidates(rows, plan, allow_uncertain=False):
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
        if plan.get('setting') and row.get('setting') != plan['setting'] and not (allow_uncertain and row.get('setting') is None):
            continue
        if plan['who'] not in row['actors'] or not set(row['actors']).issubset(present):
            continue
        if row.get('time_slots') and slot not in row['time_slots']:continue
        if slot is None and (row['night'] or row['sunset']):
            continue
        if (row['night'] and slot != 3) or (row['sunset'] and slot != 2):
            continue
        # An unspecified daytime illustration is not substituted into a night scene.
        if slot in (2,3) and not (row['night'] or row['sunset'] or row.get('time_slots')) and not allow_uncertain:
            continue
        topics = [motif for motif in row['motifs']
                  if place in PLACES[motif] and any(stem in text for stem in MOTIFS[motif])]
        if not topics:
            continue
        score = len(topics) * 10 + (2 if row['source'] == '451835368' and plan.get('profile') == 'bkrr:mi' else 0)
        if row.get('metadata_status')=='curated':score+=12
        if row.get('metadata_status')=='visual':score+=14
        if row.get('setting')==plan.get('setting') and row.get('setting') is not None:score+=3
        if slot is not None and row.get('time_slots') and slot in row['time_slots']:score+=3
        ranked.append((score, row['path'], row))
    ranked.sort(key=lambda item:(-item[0],item[1]))
    unique=[];seen=set()
    for item in ranked:
        identity=item[2].get('sha256') or item[1]
        if identity in seen:continue
        seen.add(identity);unique.append(item)
        if len(unique)==3:break
    return [dict(item[2], confidence='requires_visual_check' if allow_uncertain else 'metadata_match') for item in unique]


def match(rows, plan):
    rows = candidates(rows,plan)
    return rows[0] if rows else None
