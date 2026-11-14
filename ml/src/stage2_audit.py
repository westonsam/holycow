"""Create a cow-grouped Sydney holdout from audited scoring rows, without video extraction.

The split is assigned without looking at scores. Scores are ten original ratings
per passing (five observers, two presentations); their mean is descriptive and
not a clinical diagnosis. Video boundary candidates must be reviewed before use.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from .splits import assert_no_leakage, group_holdout

OBSERVERS = tuple(f'Observer {i}' for i in range(3, 8))
FIELDS = ('passing_id', 'cow_id', 'presentation_1', 'presentation_2', 'split')


def build(rows, seed=42):
    grouped = defaultdict(list)
    for row in rows:
        try:
            presentation = int(row['video number'])
            passing = str(int(row['unique passing id']))
            cow = str(int(row['cow id']))
            ratings = [int(row[key]) for key in OBSERVERS]
            timestamp = row['passing timestamp UTC']
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError('invalid scoring row') from e
        if any(score not in range(4) for score in ratings) or not timestamp:
            raise ValueError('invalid score or timestamp')
        grouped[passing].append((presentation, cow, timestamp, ratings))
    all_numbers = [entry[0] for values in grouped.values() for entry in values]
    if len(grouped) != 50 or sorted(all_numbers) != list(range(100)):
        raise ValueError('expected 50 passings and 100 uniquely numbered presentations')
    records, means = [], {}
    for passing in sorted(grouped, key=int):
        entries = sorted(grouped[passing])
        if len(entries) != 2 or entries[0][1:3] != entries[1][1:3]:
            raise ValueError(f'inconsistent repeated passing {passing}')
        numbers = [e[0] for e in entries]
        if not (numbers[0] < 50 <= numbers[1]):
            raise ValueError(f'passing {passing} lacks one presentation per round')
        means[passing] = statistics.mean(score for entry in entries for score in entry[3])
        records.append(dict(sample_id=passing, cow_id=entries[0][1],
                            presentation_1=numbers[0], presentation_2=numbers[1]))
    assigned = group_holdout(records, group_keys=('cow_id',), seed=seed)
    assert_no_leakage(assigned, group_keys=('cow_id',))
    split_rows = [dict(passing_id=x['sample_id'], cow_id=x['cow_id'],
                       presentation_1=x['presentation_1'], presentation_2=x['presentation_2'],
                       split=x['split']) for x in assigned]
    summary = {}
    for split in ('train', 'validation', 'test'):
        subset = [r for r in split_rows if r['split'] == split]
        values = [means[r['passing_id']] for r in subset]
        # Descriptive score values only; no threshold or class is introduced.
        summary[split] = {'passings': len(subset), 'presentations': 2 * len(subset),
                          'cows': len({r['cow_id'] for r in subset}),
                          'mean_score_range': [min(values), max(values)],
                          'passing_mean_distribution': dict(sorted(Counter(f'{v:.1f}' for v in values).items()))}
    return split_rows, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scores', type=Path, default=Path('ml/data/manifests/sydney_absolute_score_rows.csv'))
    parser.add_argument('--output', type=Path, default=Path('ml/splits/sydney_passing_split.csv'))
    parser.add_argument('--summary', type=Path, default=Path('ml/splits/sydney_split_audit.json'))
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.output.exists() or args.summary.exists():
        raise FileExistsError('split artifacts already exist; preserve the locked split')
    with args.scores.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    split, summary = build(rows, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader(); writer.writerows(split)
    summary_out = {'seed': args.seed, 'algorithm': 'group_holdout cow_id; no score-based stratification',
        'source_scores_sha256': hashlib.sha256(args.scores.read_bytes()).hexdigest(),
        'split_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
        'outcome': 'mean of ten scores per passing, five observers across two presentations; exploratory continuous 0–3; no binary cutoff',
        'boundaries': 'approximate; not approved for extraction or model training',
        'split_summary': summary}
    with args.summary.open('x', encoding='utf-8') as f: json.dump(summary_out, f, indent=2); f.write('\n')
    print(json.dumps(summary_out, indent=2))


if __name__ == '__main__': main()
