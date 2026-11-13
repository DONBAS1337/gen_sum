# -*- coding: utf-8 -*-
"""Live conversation -> reload -> next-day consequence -> live resolution.

Creates an isolated new game under --out. Uses existing DON-GEN auth normally.
Makes two real generation requests; never modifies existing game sessions.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'don_gen'))
import dg_backend
import dg_hybrid
import dg_memory
import dg_rpg
import dg_stage
import dg_world


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.data_dir.resolve() == args.out.resolve():
        parser.error('Use a separate test output directory')
    args.out.mkdir(parents=True, exist_ok=True)
    client = dg_backend.Client(str(args.data_dir))
    state = dg_rpg.new_game(u'Тестовый герой', 23, 14, source='bkrr:mi')
    dg_rpg.move(state, dg_rpg.where_is(state, 'mi'))
    for number in (1, 2):
        if number == 1:
            mode, who, action = 'npc', 'mi', u'Спасибо за помощь. Хочу продолжить репетицию и научиться играть на гитаре.'
        else:
            while state['day'] == 1:
                dg_rpg.activity(state, 'rest')
            event = dg_world.current(state)
            if not event.get('thread_id'):
                raise RuntimeError('Previous action did not produce a follow-up')
            dg_rpg.move(state, event['place'])
            mode, who, action = 'world', None, u'Помочь с продолжением репетиции и вместе разобрать трудное место.'
        plan = dg_hybrid.preview(state, action, mode, who)
        if plan['status'] != 'ready':
            raise RuntimeError('Test action was rejected')
        instructions, prompt = dg_hybrid.build_request(state, plan)
        text = client.generate(instructions, prompt, fast_mode=False)
        dg_hybrid.commit(state, plan, text)
        dg_rpg.save(str(args.out), state)
        loaded = dg_rpg.load(str(args.out), state['id'])
        if loaded != state:
            raise RuntimeError('State changed after reload')
        state = loaded
        (args.out / ('scene-%d.txt' % number)).write_text(text, encoding='utf-8')
        print('Live turn %d: committed and reloaded; stage directions=%d' %
              (number, len(dg_stage.STAGING.findall(text))), flush=True)
    statuses = [row['status'] for row in state['story_memory']['threads']]
    if 'resolved' not in statuses:
        raise RuntimeError('Follow-up did not resolve')
    (args.out / 'result.json').write_text(json.dumps({'statuses':statuses,
        'memory_episodes':len(state['story_memory']['episodes'])}), encoding='utf-8')
    print('Follow-up resolved; persistent memory retained', flush=True)


if __name__ == '__main__':
    main()
