"""Dashboard adapter for the supplied YOLO11 + APT-36K ViTPose prototype.

Detection, segmentation and keypoints are model outputs. The per-track 0-5
values are fixed illustrations from the supplied app, never health measurements.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / 'models' / 'motion'
ASSETS = ROOT / 'motion-demo-assets'
POSE_URL = 'https://huggingface.co/JunkyByte/easy_ViTPose/resolve/main/onnx/apt36k/vitpose-s-apt36k.onnx'
SKELETON = [(0,2),(1,2),(2,3),(3,5),(5,6),(6,7),(3,8),(8,9),(9,10),(3,4),(4,11),(11,12),(12,13),(4,14),(14,15),(15,16)]


def models():
    CACHE.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / 'work' / 'yolo-config'))
    os.environ.setdefault('TORCH_HOME', str(CACHE))
    from ultralytics import YOLO
    from rtmlib import ViTPose
    pose_path = CACHE / 'vitpose-s-apt36k.onnx'
    if not pose_path.exists():
        from urllib.request import urlretrieve
        temporary = pose_path.with_suffix('.downloading')
        print('Downloading APT-36K pose weights...', flush=True)
        urlretrieve(POSE_URL, temporary)
        temporary.replace(pose_path)
    detector = YOLO(str(CACHE / 'yolo11n-seg.pt'))
    animal = ViTPose(str(pose_path), model_input_size=(192,256), backend='onnxruntime', device='cpu', to_openpose=False)
    return detector, animal


def analyze(source, output, detector=None, animal=None, confidence=.25, threshold=.3):
    import cv2
    import numpy as np
    from motion_tracking import Tracker
    if detector is None or animal is None:
        detector, animal = models()
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise ValueError('Could not decode the prepared raw video')
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if not 0 < fps <= 120 or not 0 < total <= 36000 or width <= 0 or height <= 0:
        capture.release()
        raise ValueError('Unsupported video metadata')
    tracker = Tracker()
    frames = []
    started = time.monotonic()
    try:
        while True:
            ok, image = capture.read()
            if not ok:
                break
            index = len(frames)
            prediction = detector.predict(image, classes=[19], conf=confidence, verbose=False, device='cpu')[0]
            boxes = prediction.boxes.xyxy.cpu().numpy() if prediction.boxes is not None else np.empty((0,4))
            identities = tracker.update(boxes)
            points, scores = animal(image, bboxes=boxes.tolist()) if len(boxes) else ([], [])
            polygons = prediction.masks.xy if prediction.masks is not None else []
            detections = []
            for i, box in enumerate(boxes):
                ident = identities[i]
                keypoints = [[round(float(p[0]),2), round(float(p[1]),2), round(float(score),4)]
                             for p, score in zip(points[i], scores[i])] if i < len(points) else []
                detections.append({'id': f'{index}-{ident}', 'track': ident,
                    'box': [round(float(value),2) for value in box], 'keypoints': keypoints,
                    'polygon': [[round(float(p[0]),2), round(float(p[1]),2)] for p in polygons[i][::3]] if i < len(polygons) else [],
                    'illustrativeScore': [0.6,0.8,0.5,1.0,0.7,0.9][(ident-1)%6]})
            frames.append({'frame': index, 'time': index/fps, 'detections': detections})
            print(f'{len(frames)}/{total} frames', flush=True)
    finally:
        capture.release()
    if len(frames) != total:
        raise ValueError('Input video did not decode completely')
    result = {'width': width, 'height': height, 'fps': fps, 'duration': len(frames)/fps,
        'trackCount': len({d['track'] for f in frames for d in f['detections']}),
        'frames': frames, 'skeleton': SKELETON, 'keypointThreshold': threshold,
        'pipeline': 'YOLO11 segmentation + APT-36K ViTPose', 'illustrativeScores': True,
        'provenance': {'sourceSha256': hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                       'sourceName': Path(source).name, 'scores': 'fixed illustrative values; not lameness measurements',
                       'elapsedSeconds': round(time.monotonic()-started,2)}}
    temporary = Path(output).with_suffix('.preparing.json')
    temporary.write_text(json.dumps(result, separators=(',', ':')), encoding='utf-8')
    temporary.replace(output)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    analyze(args.source, args.output)
