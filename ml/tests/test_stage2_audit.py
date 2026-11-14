import unittest
from ml.src.stage2_audit import build


def sample_rows():
    rows = []
    for i in range(50):
        for n in (i, i + 50):
            row = {'video number': str(n), 'unique passing id': str(i),
                   'cow id': str(i // 2), 'passing timestamp UTC': f'2018-12-13T00:{i:02}:00'}
            row.update({f'Observer {j}': str(i % 4) for j in range(3, 8)})
            rows.append(row)
    return rows


class Stage2AuditTests(unittest.TestCase):
    def test_split_is_reproducible_and_links_repeated_animals(self):
        rows = sample_rows()
        assigned, summary = build(rows)
        self.assertEqual((assigned, summary), build(rows))
        by_cow = {}
        for row in assigned:
            by_cow.setdefault(row['cow_id'], set()).add(row['split'])
            self.assertEqual(row['presentation_2'] - row['presentation_1'], 50)
        self.assertTrue(all(len(splits) == 1 for splits in by_cow.values()))
        self.assertEqual(sum(s['passings'] for s in summary.values()), 50)
        self.assertEqual(sum(s['presentations'] for s in summary.values()), 100)
        self.assertTrue(all(s['cows'] > 0 for s in summary.values()))

    def test_missing_or_inconsistent_repeated_presentations_fail(self):
        rows = sample_rows()
        rows[1]['cow id'] = '999'
        with self.assertRaises(ValueError):
            build(rows)
        with self.assertRaises(ValueError):
            build(sample_rows()[:-1])

    def test_split_assignment_does_not_depend_on_scores(self):
        rows = sample_rows()
        before, _ = build(rows)
        for row in rows:
            row['Observer 3'] = '3'
        after, _ = build(rows)
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
