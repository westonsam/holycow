import unittest
from ml.src.prepare_sydney_manifest import make_manifest

def fixtures():
    split=[];scores=[];bounds=[]
    for i in range(50):
        split.append(dict(passing_id=str(i),cow_id=str(i//2),split=('train' if i<30 else 'validation' if i<40 else 'test'),presentation_1=str(i),presentation_2=str(i+50)))
        for n in (i,i+50):
            row={'unique passing id':str(i),'cow id':str(i//2),'video number':str(n)}
            row.update({f'Observer {k}':str(i%4) for k in range(3,8)});scores.append(row)
    for n in range(1,100):
        bounds.append(dict(transition=str(n),status='matched',expected_before=str(n-1),expected_after=str(n),predicted_before=str(n-1),predicted_after=str(n),sample_before_s=str(n*15),sample_after_s=str(n*15+0.5)))
    return split,scores,bounds
class Tests(unittest.TestCase):
    def test_groups_and_margins(self):
        split,scores,bounds=fixtures(); data=make_manifest(split,scores,bounds,'video.mp4',1800.601,1.0)
        self.assertEqual(len(data),50); self.assertEqual(data[0]['start_s'],'1.000');self.assertEqual(data[0]['end_s'],'14.000');self.assertEqual(data[1]['start_s'],'16.500'); self.assertEqual(data[1]['score'],'1.0')
    def test_leakage_and_boundary_failure(self):
        split,scores,bounds=fixtures();split[1]['split']='test'
        with self.assertRaisesRegex(ValueError,'cow leakage'): make_manifest(split,scores,bounds,'video',1800.601,1)
        split,scores,bounds=fixtures();bounds[2]['status']='needs_review'
        with self.assertRaisesRegex(ValueError,'failed transition'): make_manifest(split,scores,bounds,'video',1800.601,1)
    def test_presentation_or_score_mismatch_fails(self):
        split,scores,bounds=fixtures();scores[0]['cow id']='999'
        with self.assertRaisesRegex(ValueError,'score identity mismatch'):make_manifest(split,scores,bounds,'video',1800.601,1)
if __name__=='__main__':unittest.main()
