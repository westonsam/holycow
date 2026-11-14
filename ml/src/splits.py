"""Deterministic, group-disjoint assignment of original video-level records.

Split original samples before extracting frames or applying augmentation. Supply
all known animal/source identifiers: records sharing any identifier are treated
as one connected group. A missing identifier is not evidence of independence.
"""
from __future__ import annotations

from collections import Counter
import random


def group_holdout(records, fractions=(0.6, 0.2, 0.2), seed=42,
                  id_key='sample_id', group_keys=('group_id',)):
    """Return copied records with split, without cross-split identity overlap.

    Components are assigned greedily by sample count, not stratified. Inspect
    ``split_counts``; class balance and requested proportions are not guaranteed.
    """
    records = [dict(row) for row in records]
    if len(fractions) != 3 or any(x <= 0 for x in fractions) or abs(sum(fractions) - 1) > 1e-9:
        raise ValueError('fractions must contain three positive numbers summing to one')
    if not group_keys:
        raise ValueError('at least one grouping key is required')
    ids = [r.get(id_key) for r in records]
    if any(x is None or str(x).strip() == '' for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('sample IDs must be present and unique')
    parent = list(range(len(records)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    known = {}
    for i, row in enumerate(records):
        for key in group_keys:
            value = row.get(key)
            if value is None or str(value).strip() == '':
                raise ValueError(f'missing {key} for sample {ids[i]}')
            token = (key, str(value))
            if token in known:
                a, b = root(i), root(known[token])
                parent[a] = b
            else:
                known[token] = i
    groups = {}
    for i in range(len(records)):
        groups.setdefault(root(i), []).append(i)
    if len(groups) < 3:
        raise ValueError('at least three independent groups are needed')
    components = list(groups.values())
    random.Random(seed).shuffle(components)
    # Large groups first, random tie order. Ensure each split gets a group.
    components.sort(key=len, reverse=True)
    names = ('train', 'validation', 'test')
    assigned = [0, 0, 0]
    total = len(records)
    for pos, component in enumerate(components):
        if pos < 3:
            target = pos
        else:
            target = max(range(3), key=lambda j: (fractions[j] * total - assigned[j], -j))
        for i in component:
            records[i]['split'] = names[target]
        assigned[target] += len(component)
    assert_no_leakage(records, group_keys=group_keys)
    return records


def assert_no_leakage(records, group_keys=('group_id',), split_key='split'):
    """Raise on a missing identifier/split or any identity shared across splits."""
    seen = {}
    for row in records:
        split = row.get(split_key)
        if split not in ('train', 'validation', 'test'):
            raise ValueError(f'invalid split: {split!r}')
        for key in group_keys:
            value = row.get(key)
            if value is None or str(value).strip() == '':
                raise ValueError(f'missing {key}')
            token = (key, str(value))
            if token in seen and seen[token] != split:
                raise ValueError(f'group leakage in {key}: {value}')
            seen[token] = split


def split_counts(records, label_key='label'):
    """Return counts keyed by split and label, including unlabeled samples."""
    return dict(Counter((row['split'], row.get(label_key)) for row in records))
