import csv
import math
import tempfile
import unittest
from pathlib import Path
from ml.src.stage3_regression import regression_metrics, read_manifest, training_mean, write_predictions, require_video_review, image_frames

class RegressionTests(unittest.TestCase):
    def test_metrics_known_values(self):
        m=regression_metrics([0.,1.,2.],[0.,2.,1.])
        self.assertAlmostEqual(m['mae'], 2/3); self.assertAlmostEqual(m['rmse'],math.sqrt(2/3)); self.assertAlmostEqual(m['r2'],0.); self.assertAlmostEqual(m['pearson_r'],.5)
        self.assertIsNone(regression_metrics([1.,1.],[0.,2.])['r2'])
        with self.assertRaises(ValueError): regression_metrics([0],[float('nan')])

    def test_video_gate_requires_both_reviews(self):
        with self.assertRaisesRegex(ValueError, 'target_localization_review'):
            require_video_review({'passing_id':'5'})
        with self.assertRaisesRegex(ValueError, 'walking_visibility_review'):
            require_video_review({'passing_id':'5','target_localization_review':'approved'})
        require_video_review({'passing_id':'5','target_localization_review':'approved','walking_visibility_review':'approved'})
        with self.assertRaisesRegex(RuntimeError, 'feature extraction disabled'):
            image_frames({'passing_id':'5','target_localization_review':'approved','walking_visibility_review':'approved'}, 8)

    def test_manifest_blocks_duplicate_animals_across_splits(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'m.csv'; fields=['passing_id','cow_id','split','score','presentation','start_s','end_s','video_path']
            rows=[['1','7','train','1.2','1','1','3','foo.mp4'],['2','7','test','2.3','2','5','7','foo.mp4']]
            with p.open('w',newline='') as f:
                w=csv.writer(f); w.writerow(fields);w.writerows(rows)
            with self.assertRaisesRegex(ValueError,'cow occurs'): read_manifest(p)
            rows[1][1]='8'
            with p.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(fields);w.writerows(rows)
            values=read_manifest(p);self.assertAlmostEqual(training_mean(values),1.2)
            out=Path(d)/'pred.csv'
            m=write_predictions(out,values,[1.2,2.3],'test');self.assertAlmostEqual(m['mae'],0.)
            with self.assertRaises(FileExistsError): write_predictions(out,values,[1.2,2.3],'test')

if __name__=='__main__':unittest.main()
