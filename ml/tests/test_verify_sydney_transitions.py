import unittest
from unittest.mock import patch

try:
    import numpy as np
    from ml.src.verify_sydney_transitions import recognize, verify
except ImportError:
    np = None


@unittest.skipIf(np is None, 'NumPy/Pillow are required for transition verification')
class TransitionVerificationTests(unittest.TestCase):
    def setUp(self):
        self.templates = np.zeros((100, 80, 150), dtype=bool)
        for i in range(100):
            self.templates[i, i // 10 * 5:i // 10 * 5 + 4, i % 10 * 5:i % 10 * 5 + 4] = True
        self.row = {'candidate_label': '1', 'lower_bound_s': '1', 'upper_bound_s': '2'}

    def test_unique_expected_templates_match(self):
        frames = [self.templates[0].astype('uint8') * 255, self.templates[1].astype('uint8') * 255]
        with patch('ml.src.verify_sydney_transitions.read_frame', side_effect=frames):
            self.assertEqual(verify(self.row, self.templates, None, None)['status'], 'matched')

    def test_wrong_label_and_ties_require_review(self):
        wrong = self.templates[2].astype('uint8') * 255
        with patch('ml.src.verify_sydney_transitions.read_frame', return_value=wrong):
            self.assertEqual(verify(self.row, self.templates, None, None)['status'], 'needs_review')
        self.templates[1] = self.templates[0]
        label, score, margin = recognize(self.templates[0].astype('uint8') * 255, self.templates)
        self.assertEqual(margin, 0)


if __name__ == '__main__':
    unittest.main()
