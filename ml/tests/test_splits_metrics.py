import importlib.util
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[1] / 'src'

def module(name):
    spec = importlib.util.spec_from_file_location(name, SRC / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded

splits = module('splits')
metrics = module('metrics')


class SplitTests(unittest.TestCase):
    def test_transitively_linked_sources_never_cross_splits(self):
        # A and B share a source; B and C share an animal.
        rows = [
            {'sample_id': 'a', 'animal': 'x', 'source': '1', 'label': 0},
            {'sample_id': 'b', 'animal': 'y', 'source': '1', 'label': 1},
            {'sample_id': 'c', 'animal': 'y', 'source': '2', 'label': 1},
        ] + [{'sample_id': str(i), 'animal': str(i), 'source': str(i + 10), 'label': i % 2} for i in range(9)]
        result = splits.group_holdout(rows, seed=7, group_keys=('animal', 'source'))
        self.assertEqual(result, splits.group_holdout(rows, seed=7, group_keys=('animal', 'source')))
        self.assertEqual(len({r['split'] for r in result[:3]}), 1)
        self.assertEqual({r['split'] for r in result}, {'train', 'validation', 'test'})
        self.assertNotIn('split', rows[0])
        splits.assert_no_leakage(result, ('animal', 'source'))

    def test_leakage_and_unknown_identity_fail_closed(self):
        with self.assertRaisesRegex(ValueError, 'leakage'):
            splits.assert_no_leakage([{'group_id': 'x', 'split': 'train'}, {'group_id': 'x', 'split': 'test'}])
        with self.assertRaisesRegex(ValueError, 'missing'):
            splits.group_holdout([{'sample_id': 'a', 'group_id': ''}])
        with self.assertRaisesRegex(ValueError, 'unique'):
            splits.group_holdout([{'sample_id': 'a', 'group_id': str(i)} for i in range(3)])


class MetricsTests(unittest.TestCase):
    def test_hand_calculated_binary_metrics(self):
        result = metrics.binary_metrics([1, 1, 0, 0], [0.9, 0.4, 0.6, 0.1])
        self.assertEqual((result['tp'], result['tn'], result['fp'], result['fn']), (1, 1, 1, 1))
        for key in ('accuracy', 'balanced_accuracy', 'sensitivity', 'specificity', 'precision', 'f1'):
            self.assertAlmostEqual(result[key], 0.5)
        self.assertAlmostEqual(result['auroc'], 0.75)
        self.assertAlmostEqual(result['auprc'], 5 / 6)

    def test_ties_single_class_and_input_validation(self):
        m = metrics.binary_metrics([0, 1], [0.5, 0.5])
        self.assertEqual(m['auroc'], 0.5)
        self.assertEqual(m['auprc'], 0.5)
        single = metrics.binary_metrics([0, 0], [0.1, 0.4])
        self.assertIsNone(single['auroc'])
        self.assertIsNone(single['auprc'])
        self.assertIsNone(single['balanced_accuracy'])
        for scores in ([float('nan')], [1.1]):
            with self.assertRaises(ValueError):
                metrics.binary_metrics([1], scores)

    def test_group_bootstrap_counts_degenerate_replicates(self):
        result = metrics.grouped_bootstrap([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9], ['a', 'a', 'b', 'b'], n_bootstrap=100, seed=1)
        self.assertEqual(result['n_groups'], 2)
        auc = result['intervals']['auroc']
        self.assertTrue(0 < auc['valid_replicates'] < 100)
        self.assertEqual((auc['low'], auc['high']), (1.0, 1.0))
        self.assertEqual(result, metrics.grouped_bootstrap([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9], ['a', 'a', 'b', 'b'], n_bootstrap=100, seed=1))


if __name__ == '__main__':
    unittest.main()
