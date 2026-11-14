import csv
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from keypoints import JointObservation, evaluate_keypoints, read_observations, validate_observations


class KeypointEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.a = JointObservation("image1", "cow1", "hoof", 10, 10, 2, 10, 13, 14, 100, 100)
        self.b = JointObservation("image1", "cow1", "head", 20, 20, 1, 10, None, None, 100, 100)
        self.c = JointObservation("image1", "cow1", "tail", 0, 0, 0, 10, 0, 0, 100, 100)

    def test_pck_occlusion_and_missing(self):
        result = evaluate_keypoints([self.a, self.b, self.c], [0, .5, 1], normalization_name="box width")
        self.assertEqual(result["overall"]["pck"], [0, .5, .5])
        self.assertEqual(result["overall"]["missing"], 1)
        self.assertEqual(result["per_joint"]["hoof"]["mean_normalized_error"], .5)
        self.assertIsNone(result["per_joint"]["head"]["mean_normalized_error"])
        visible = evaluate_keypoints([self.a, self.b, self.c], [.5], normalization_name="box width", include_occluded=False)
        self.assertEqual(visible["overall"]["pck"], [1])
        self.assertEqual(visible["overall"]["eligible"], 1)

    def test_validation_rejects_misalignment(self):
        for rows in ([self.a, self.a], [replace(self.a, visibility=3)], [replace(self.a, gt_x=101)],
                     [replace(self.a, pred_y=None)], [replace(self.a, normalizer=0)]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                validate_observations(rows)
        with self.assertRaises(ValueError):
            validate_observations([self.a], expected_joints=["hoof", "head"])
        with self.assertRaises(ValueError):
            evaluate_keypoints([self.a], [.5, .5], normalization_name="box")

    def test_csv_missing_predictions_and_optional_dimensions(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "rows.csv"
            with path.open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["image_id", "subject_id", "joint", "gt_x", "gt_y", "visibility", "normalizer", "pred_x", "pred_y"])
                writer.writerow(["1", "cow1", "hoof", "2", "3", "2", "10", "", ""])
            row = read_observations(path)[0]
            self.assertIsNone(row.pred_x)
            self.assertEqual(evaluate_keypoints([row], [.5], normalization_name="box")["overall"]["pck"], [0])


if __name__ == "__main__":
    unittest.main()
