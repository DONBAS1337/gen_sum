# -*- coding: utf-8 -*-
"""Isolated deterministic play-through of a full shift. No real player saves or API."""
from pathlib import Path
import argparse,copy,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'don_gen'))
import dg_rpg,dg_camp,dg_clock,dg_ensemble,dg_personality,dg_commitments,dg_hybrid,dg_checkpoints,dg_inventory,dg_turn

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--days',type=int,default=120);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    root=str(a.out.resolve());a.out.mkdir(parents=True,exist_ok=True)
    s=dg_rpg.new_game('Проверка длинной смены',24,a.days,'Музыкант и любитель техники',source='bkrr:mi',camp_life=True)
    s['id']='1'*32;dg_rpg.save(root,s)
    count=0;days=set();checkpoints=0;failures=0;commits=0;snapshot=None;last_day=0
    def execute(kind,arg):
        nonlocal s,count,commits
        before=dg_clock.absolute(s)
        if kind=='camp':
            pending=dg_turn.begin(s);r=dg_camp.act(pending['state'],arg)
            pending.update(who=r.get('who'),private=r.get('private'),intention=r['title'],result=r['text'])
            text='[narrator] '+r['text']+' '+('Подтверждены только перечисленные последствия. Остальные планы ещё не выполнены. '*3)
            s=dg_turn.finish(root,pending,dg_hybrid.fingerprint(pending['state']),text);commits+=1
        elif kind=='move':dg_rpg.move(s,arg);dg_rpg.save(root,s)
        elif kind=='rest':dg_rpg.activity(s,'rest');dg_rpg.save(root,s)
        elif kind=='talk':dg_rpg.conversation(s,arg,0,('support','curious','bold')[count%3]);dg_rpg.save(root,s)
        elif kind=='end':__import__('dg_conversation').end(s);dg_rpg.save(root,s)
        else:raise ValueError(kind)
        dg_rpg.validate(s);assert dg_clock.absolute(s)>=before
        assert dg_rpg.load(root,s['id'])==s
        count+=1
    while not s['finished']:
        if count>15000:raise ValueError('Shift did not finish within action bound')
        day=s['day'];minute=dg_clock.minute(s);days.add(day)
        if day!=last_day:
            last_day=day;print('SHIFT_DAY %d actions=%d crews=%d'%(day,count,len(dg_ensemble.records(s))),flush=True)
            if day%10==0:
                snapshot=copy.deepcopy(s)
        if snapshot is not None and day%10==1:
            future=copy.deepcopy(s);restored=dg_checkpoints.restore(root,snapshot)
            assert restored==snapshot
            s=dg_checkpoints.restore(root,future);assert dg_rpg.load(root,s['id'])==future
            checkpoints+=1;snapshot=None
        if count%29==0:
            before=copy.deepcopy(s);plan=dg_hybrid.preview(s,'Осмотреть скамейки')
            try:raise RuntimeError('Simulated generation outage before commit')
            except RuntimeError:pass
            assert s==before and dg_rpg.load(root,s['id'])==before;failures+=1
        rows=dg_camp.cards(s)
        intro=next((r for r in rows if r['key'] in ('arrival','tour_issue') or r['key'].startswith(('stamp:','join:music'))),None)
        if intro:
            if s['place']!=intro['place']:execute('move',intro['place'])
            elif intro['ready']:execute('camp',intro['key'])
            else:execute('camp','wait')
            continue
        if s['energy']<15:execute('rest',None);continue
        if s.get('dialogue_clock') and count%3==0:execute('end',None);continue
        # Keep a human-like daily routine and attend calendar events when offered.
        routine=next((r for r in rows if r['key'] in ('wash','assembly','breakfast','lunch','dinner','treatment') or r['key'].startswith('event:')),None)
        if routine:
            if s['place']!=routine['place']:execute('move',routine['place'])
            elif routine['ready']:execute('camp',routine['key'])
            else:execute('camp','wait')
            continue
        crewrows=dg_ensemble.cards(s)
        work=next((r for r in crewrows if r['key'].endswith(':work')),None)
        if 1060<=minute<1135 and work:
            if s['place']!=work['place']:execute('move',work['place'])
            elif work['ready']:execute('camp',work['key'])
            else:execute('camp','wait')
            continue
        candidate=next((r for r in crewrows if r['ready'] and (':start:' in r['key'] or ':plan:' in r['key'] or ':feedback:' in r['key'] or r['key'].endswith(':news'))),None)
        if candidate:execute('camp',candidate['key']);continue
        if 1260<=minute:
            sleep=next(r for r in rows if r['key']=='sleep')
            if s['place']!=sleep['place']:execute('move',sleep['place'])
            else:execute('camp','sleep')
            continue
        options=[r for r in dg_commitments.options(s) if r['ready'] and r['key'].startswith('invite:')]
        if day%7==1 and options:execute('camp','commit:'+options[0]['key']);continue
        meeting=next((r for r in dg_commitments.rows(s) if r['kind']=='meeting' and r['status']=='open' and r['due']-30<=dg_clock.absolute(s)<r['due']+30),None)
        if meeting:
            if s['place']!=meeting['place']:execute('move',meeting['place'])
            else:execute('camp','wait')
            continue
        # Vary places and conversations; do not fabricate friendship, items or attendance.
        people=dg_rpg.at_place(s)
        if people and count%3:
            execute('talk',people[count%len(people)][0]);continue
        objects=__import__('dg_actions').available(s)
        if objects and count%5==0:execute('camp','object:'+objects[0]['key']);continue
        dest=('music','clubs','library','square','forest_path','canteen')[count%6]
        if s['place']!=dest:execute('move',dest)
        else:execute('camp','wait')
    result={'days':len(days),'actions':count,'narrated_rule_commits':commits,'save_reload_checks':count,'outage_checks':failures,'historical_snapshot_restores':checkpoints,
            'shared_events':len(dg_ensemble.records(s)),'states':{x:sum(r['phase']==x for r in dg_ensemble.records(s)) for x in dg_ensemble.PHASES},
            'personalities':len(s.get('personality',{}).get('people',{})),'finished':s['finished'],'human_playthrough':False,'live_ai':False}
    assert result['days']==a.days and result['finished']
    (a.out/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LONG_SHIFT_OK '+json.dumps(result,sort_keys=True),flush=True)

if __name__=='__main__':main()
