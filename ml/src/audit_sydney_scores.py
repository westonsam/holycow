"""Audit Sydney score sheets; do not infer unlabeled segment boundaries."""
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def audit(path, out):
    try:
        import openpyxl
    except ImportError as error:
        raise RuntimeError('openpyxl is needed to inspect the workbook') from error
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = wb.active
    rows = sheet.iter_rows(values_only=True)
    headings = [str(v).strip() for v in next(rows)]
    expected = ['video number', 'unique passing id', 'cow id', 'passing timestamp UTC',
                'Observer 3', 'Observer 4', 'Observer 5', 'Observer 6', 'Observer 7']
    if headings != expected:
        raise ValueError(f'unexpected headers: {headings}')
    records = []
    for values in rows:
        if all(v is None for v in values):
            continue
        if len(values) != len(expected) or any(v is None for v in values):
            raise ValueError('missing values in spreadsheet')
        item = dict(zip(expected, values))
        if any(type(item[k]) is not int or item[k] not in range(4) for k in expected[4:]):
            raise ValueError('observer scores must be integers 0–3')
        item[expected[3]] = item[expected[3]].isoformat()
        records.append(item)
    numbers = [r[expected[0]] for r in records]
    if sorted(numbers) != list(range(100)):
        raise ValueError('expected exactly one presentation numbered 0–99')
    by_passing = defaultdict(list)
    for r in records:
        by_passing[r[expected[1]]].append(r)
    if len(by_passing) != 50 or any(len(v) != 2 for v in by_passing.values()):
        raise ValueError('expected 50 passings with two presentations each')
    for passing, entries in by_passing.items():
        if len({(e[expected[2]], e[expected[3]]) for e in entries}) != 1:
            raise ValueError(f'inconsistent cow/timestamp for passing {passing}')
    cows = Counter(entries[0][expected[2]] for entries in by_passing.values())
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'sydney_absolute_score_rows.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=expected); writer.writeheader(); writer.writerows(records)
    summary = {'presentations': len(records), 'unique_passings': len(by_passing),
               'unique_cows': len(cows), 'cows_with_multiple_passings': sum(x > 1 for x in cows.values()),
               'score_scale': 'integer 0–3', 'video_segment_boundaries': 'not verified',
               'outcome_aggregation': 'not selected', 'source_workbook': str(path)}
    (out / 'sydney_absolute_score_audit.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path); parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.workbook, args.output), indent=2))


if __name__ == '__main__': main()
