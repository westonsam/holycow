"""Check a rendered video and its source-coordinate prediction sidecar."""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('video',type=Path)
    p.add_argument('--predictions',type=Path)
    p.add_argument('--metadata',type=Path)
    a=p.parse_args()
    metadata=json.loads((a.metadata or a.video.with_suffix('.metadata.json')).read_text())
    assert metadata['complete'], 'Render did not complete'
    width,height=metadata['source_width'],metadata['source_height']
    counts=[]
    with (a.predictions or a.video.with_suffix('.jsonl')).open() as records:
        for index,line in enumerate(records):
            row=json.loads(line)
            assert row['frame']==metadata['start_frame']+index
            assert abs(row['time_seconds']-row['frame']/metadata['fps'])<1e-6
            ids=[d['track_id'] for d in row['detections']]
            assert len(ids)==len(set(ids)), 'Duplicate track in one frame'
            for detection in row['detections']:
                x1,y1,x2,y2=detection['box']
                assert 0<=x1<x2<=width and 0<=y1<y2<=height
                polygon=np.array(detection['polygon'])
                assert len(polygon)>=3 and np.isfinite(polygon).all()
                assert polygon[:,0].min()>=0 and polygon[:,0].max()<width
                assert polygon[:,1].min()>=0 and polygon[:,1].max()<height
                assert 0<=detection['score']<=1
            counts.append(len(ids))
    capture=cv2.VideoCapture(str(a.video))
    fps=capture.get(cv2.CAP_PROP_FPS)
    output_width,output_height=int(capture.get(3)),int(capture.get(4))
    decoded=0
    while True:
        ok,frame=capture.read()
        if not ok:
            break
        assert frame.shape[:2]==(output_height,output_width)
        decoded+=1
    capture.release()
    assert decoded==len(counts)==metadata['frames_processed']
    assert abs(fps-metadata['fps'])<1e-6
    summary={'frames':decoded,'fps':fps,'dimensions':[output_width,output_height],
             'duration_seconds':decoded/fps,'predictions_min':min(counts),
             'predictions_max':max(counts),'coordinates_valid':True,
             'note':'Mechanical validation only; no detection accuracy measurement'}
    a.video.with_suffix('.validation.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
