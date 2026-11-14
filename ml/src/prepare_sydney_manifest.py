"""Build exploratory, guarded Sydney intervals; no frames/clips or model training.

See STAGE_2_AUDIT.md: sample labels are verified at both candidate endpoints,
not a guarantee of frame-exact transition/cow visibility. Manifest is research
only and must undergo visual quality review before being used as model input.
"""
import argparse
import csv
import hashlib
import statistics
from collections import defaultdict
from pathlib import Path

FIELDS=['passing_id','cow_id','split','score','presentation','start_s','end_s','video_path']

def read_csv(p):
    with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))

def make_manifest(split, scores, boundaries, video_path, duration, margin):
    if margin < 0.5: raise ValueError('margin must be at least 0.5 seconds')
    if [int(b['transition']) for b in boundaries] != list(range(1,100)): raise ValueError('expected transitions 1 through 99 in order')
    for b in boundaries:
        n=int(b['transition'])
        if b['status']!='matched' or int(b['expected_before'])!=n-1 or int(b['expected_after'])!=n or int(b['predicted_before'])!=n-1 or int(b['predicted_after'])!=n: raise ValueError(f'failed transition verification {n}')
        if float(b['sample_before_s'])>=float(b['sample_after_s']): raise ValueError(f'invalid boundary {n}')
    passing_scores=defaultdict(list)
    for row in scores: passing_scores[row['unique passing id']].append(row)
    if len(split)!=50 or len(passing_scores)!=50: raise ValueError('expected 50 split records and 50 scored passings')
    result=[]; seen_pass=set(); seen_presentation=set(); cows={}
    for row in split:
        pid=row['passing_id']; cow=row['cow_id']; which=row['split']; presentation=int(row['presentation_1']); pair=int(row['presentation_2'])
        if pid in seen_pass or not 0<=presentation<50 or not 50<=pair<100 or presentation in seen_presentation or which not in ('train','validation','test'): raise ValueError('duplicate or invalid split record')
        seen_pass.add(pid);seen_presentation.add(presentation)
        if cow in cows and cows[cow]!=which: raise ValueError(f'cow leakage {cow}')
        cows[cow]=which
        src=passing_scores[pid]
        if len(src)!=2 or any(r['cow id']!=cow for r in src) or {int(r['video number']) for r in src}!={presentation,pair}: raise ValueError(f'score identity mismatch {pid}')
        vals=[int(r[f'Observer {n}']) for r in src for n in range(3,8)]
        if len(vals)!=10 or any(x not in (0,1,2,3) for x in vals): raise ValueError(f'invalid scores {pid}')
        start=(0.0 if presentation==0 else float(boundaries[presentation-1]['sample_after_s']))+margin
        end=float(boundaries[presentation]['sample_before_s'])-margin
        if start<0 or end>duration or end<=start: raise ValueError(f'insufficient safe interval {pid}')
        result.append(dict(passing_id=pid,cow_id=cow,split=which,score=f'{statistics.mean(vals):.1f}',presentation=presentation,start_s=f'{start:.3f}',end_s=f'{end:.3f}',video_path=video_path))
    if seen_presentation!=set(range(50)): raise ValueError('first-round presentations not complete')
    return sorted(result,key=lambda r:int(r['passing_id']))

def main():
    p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--margin',type=float,default=1.0);args=p.parse_args()
    repo=args.repo; video='ml/data/sydney/absolute.mp4'
    if not (repo/video).is_file(): raise FileNotFoundError(repo/video)
    rows=make_manifest(read_csv(repo/'ml/splits/sydney_passing_split.csv'),read_csv(repo/'ml/data/manifests/sydney_absolute_score_rows.csv'),read_csv(repo/'ml/data/manifests/sydney_transition_verification.csv'),video,1800.601,args.margin)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open('x',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
    print('Candidate manifest',args.out,'passings',len(rows),'sha256',hashlib.sha256(args.out.read_bytes()).hexdigest())
    print('WARNING: source label checks do not establish that the target cow is visible; visual review required.')
if __name__=='__main__':main()
