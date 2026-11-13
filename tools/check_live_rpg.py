# -*- coding: utf-8 -*-
"""Two real AI turns in a NEW test session; never opens existing playthroughs.

Uses the mod's existing auth.json, refreshing it normally if necessary.
Makes two generation requests and writes their text and test saves to --out.
Do not publish auth.json or the user's data directory with a report.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'don_gen'))
import dg_backend
import dg_hybrid
import dg_rpg


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, required=True, help='Existing DON-GEN data directory containing auth.json')
    parser.add_argument('--out', type=Path, required=True, help='Separate directory for test saves and scene text')
    args = parser.parse_args()
    if args.data_dir.resolve() == args.out.resolve():
        parser.error('--out must be separate from the real data directory')
    client = dg_backend.Client(str(args.data_dir))
    if not client.authenticated():
        parser.error('Sign in through the mod before running this check')
    args.out.mkdir(parents=True, exist_ok=True)
    state = dg_rpg.new_game(u'Тестовый герой', 23, 30)
    requests = [('free', None, u'Осмотреть ворота и разобраться, что происходит в лагере'),
                ('npc', 'dv', u'Что сейчас происходит в лагере и чем я могу помочь?')]
    for index, (mode, who, action) in enumerate(requests, 1):
        if who is not None:
            dg_rpg.move(state, dg_rpg.where_is(state, who))
        plan = dg_hybrid.preview(state, action, mode, who)
        instructions, prompt = dg_hybrid.build_request(state, plan)
        story = client.generate(instructions, prompt, fast_mode=False)
        dg_hybrid.commit(state, plan, story)
        dg_rpg.save(str(args.out), state)
        restored = dg_rpg.load(str(args.out), state['id'])
        if restored != state or restored['hybrid_history'][-1]['scene'] != story.strip():
            raise RuntimeError('Scene or state changed after reload')
        (args.out / ('scene-%d.txt' % index)).write_text(story, encoding='utf-8')
        print('Turn %d: OK; %d characters; day=%d slot=%d; reloaded' %
              (index, len(story), restored['day'], restored['slot']), flush=True)
        state = restored


if __name__ == '__main__':
    main()
