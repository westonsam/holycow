"""Cow instance segmentation and bounding-box video export.

No footage is uploaded. Predictions are model outputs, not hand placed boxes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time

import cv2
import imageio_ffmpeg
import numpy as np
from scene_model import SceneSegmenter


ROOT = Path(__file__).resolve().parent


def box_iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2-x1) * max(0, y2-y1)
    union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
    return intersection / max(union, 1e-6)


class Tracker:
    """Short-lived geometric track IDs; these are not animal identification."""

    def __init__(self):
        self.previous = []
        self.next_id = 1

    def update(self, detections):
        pairs = sorted((box_iou(old['box'], new['box']), i, j)
                       for i, old in enumerate(self.previous)
                       for j, new in enumerate(detections))
        used_old, used_new = set(), set()
        for overlap, i, j in reversed(pairs):
            if overlap < .15 or i in used_old or j in used_new:
                continue
            detections[j]['track_id'] = self.previous[i]['track_id']
            used_old.add(i)
            used_new.add(j)
        for detection in detections:
            if 'track_id' not in detection:
                detection['track_id'] = self.next_id
                self.next_id += 1
        self.previous = detections
        return detections


def propagate(previous_gray, gray, detections):
    """Move detections with local optical flow between inference frames."""
    result = []
    for d in detections:
        polygon = np.array(d['polygon'], dtype=np.float32)
        region = np.zeros(previous_gray.shape, np.uint8)
        cv2.fillPoly(region, [polygon.astype(np.int32)], 255)
        points = cv2.goodFeaturesToTrack(previous_gray, maxCorners=30, qualityLevel=.01,
                                         minDistance=3, mask=region)
        if points is None or len(points) < 3:
            continue
        moved, status, _ = cv2.calcOpticalFlowPyrLK(previous_gray, gray, points, None,
                                                  winSize=(21, 21), maxLevel=3)
        if moved is None:
            continue
        back, reverse_status, _ = cv2.calcOpticalFlowPyrLK(gray, previous_gray, moved, None,
                                                         winSize=(21, 21), maxLevel=3)
        if back is None:
            continue
        valid = (status.ravel() == 1) & (reverse_status.ravel() == 1)
        valid &= np.linalg.norm(back.reshape(-1, 2) - points.reshape(-1, 2), axis=1) < 1.5
        if valid.sum() < 3:
            continue
        delta = np.median((moved - points).reshape(-1, 2)[valid], axis=0)
        box = np.array(d['box']) + np.tile(delta, 2)
        box[[0, 2]] = box[[0, 2]].clip(0, gray.shape[1]-1)
        box[[1, 3]] = box[[1, 3]].clip(0, gray.shape[0]-1)
        polygon += delta
        polygon[:, 0] = polygon[:, 0].clip(0, gray.shape[1]-1)
        polygon[:, 1] = polygon[:, 1].clip(0, gray.shape[0]-1)
        result.append({**d, 'box': box.tolist(), 'polygon': polygon.tolist()})
        if 'mask_center' in d:
            result[-1]['mask_center']=(np.array(d['mask_center'])+delta).tolist()
    return result


def draw(frame, detections, show_masks, scale):
    result = cv2.resize(frame, None, fx=scale, fy=scale) if scale != 1 else frame.copy()
    thickness = max(2, round(result.shape[1]/900))
    if show_masks:
        overlay=result.copy()
        for detection in detections:
            polygon=np.round(np.array(detection['polygon'])*scale).astype(np.int32)
            cv2.fillPoly(overlay,[polygon],(93,230,117))
        cv2.addWeighted(overlay,.25,result,.75,0,dst=result)
    for d in detections:
        color = (93, 230, 117)
        polygon = np.round(np.array(d['polygon'])*scale).astype(np.int32)
        if show_masks:
            cv2.polylines(result, [polygon], True, color, 1, cv2.LINE_AA)
        x1, y1, x2, y2 = np.round(np.array(d['box'])*scale).astype(int)
        cv2.rectangle(result, (x1,y1), (x2,y2), color, thickness, cv2.LINE_AA)
        label = f"C{d['track_id']:02d}"
        font_scale = max(.38, result.shape[1]/3200)
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 1)
        label_y = max(th+8, y1)
        cv2.rectangle(result, (x1,label_y-th-8), (min(result.shape[1]-1,x1+tw+8),label_y), color, -1)
        cv2.putText(result,label,(x1+4,label_y-5),cv2.FONT_HERSHEY_SIMPLEX,font_scale,(20,35,20),1,cv2.LINE_AA)
    cv2.rectangle(result,(12,12),(385,75),(22,32,25),-1)
    cv2.putText(result, f"COWS VISIBLE: {len(detections)}", (25,41), cv2.FONT_HERSHEY_SIMPLEX,.65,(240,250,240),2,cv2.LINE_AA)
    cv2.putText(result,'Model predictions | review required',(25,63),cv2.FONT_HERSHEY_SIMPLEX,.43,(180,200,180),1,cv2.LINE_AA)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--output', type=Path, default=ROOT/'outputs'/'cows-boxed.mp4')
    p.add_argument('--confidence', type=float, default=.55)
    p.add_argument('--model-dir', type=Path, default=ROOT/'scene-cattle')
    p.add_argument('--stride', type=int, default=1, help='Run model every N frames; optical flow between frames')
    p.add_argument('--output-width', type=int, default=1920, help='0 preserves input dimensions')
    p.add_argument('--masks', action='store_true', help='Also show instance masks')
    p.add_argument('--start', type=float, default=0)
    p.add_argument('--duration', type=float)
    p.add_argument('--threads', type=int, default=6)
    a = p.parse_args()
    if not a.source.is_file():
        p.error('Source video does not exist')
    if a.source.resolve() == a.output.resolve():
        p.error('Output must not overwrite source video')
    if a.stride < 1 or not 0 < a.confidence <= 1:
        p.error('Invalid stride or confidence')
    if a.output_width < 0 or a.start < 0 or a.threads < 1 or (a.duration is not None and a.duration <= 0):
        p.error('Invalid size, start, or duration')
    cv2.setNumThreads(a.threads)
    capture = cv2.VideoCapture(str(a.source))
    if not capture.isOpened():
        raise RuntimeError('Could not open video')
    fps = capture.get(cv2.CAP_PROP_FPS)
    width, height = int(capture.get(3)), int(capture.get(4))
    if fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError('Invalid video metadata')
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    start_frame = round(a.start*fps)
    count = max(0,total-start_frame)
    if a.duration is not None:
        count = min(count, round(a.duration*fps))
    if count <= 0:
        p.error('Selected range contains no frames')
    capture.set(cv2.CAP_PROP_POS_FRAMES,start_frame)
    segmenter = SceneSegmenter(a.model_dir, a.confidence)
    scale = min(1,a.output_width/width) if a.output_width else 1
    ow, oh = round(width*scale)//2*2, round(height*scale)//2*2
    a.output.parent.mkdir(parents=True,exist_ok=True)
    # The rendered demo is silent; source audio is deliberately not synthesized.
    command = [imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','rawvideo','-vcodec','rawvideo',
               '-s',f'{ow}x{oh}','-pix_fmt','bgr24','-r',str(fps),'-i','pipe:0',
               '-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p',
               '-movflags','+faststart',str(a.output)]
    log = a.output.with_suffix('.ffmpeg.log').open('w')
    writer = subprocess.Popen(command,stdin=subprocess.PIPE,stderr=log)
    tracker, previous_gray, detections = Tracker(), None, []
    counts, elapsed, processed = [], time.perf_counter(), 0
    metadata = {'source':str(a.source.resolve()), 'model':'scene-specific random forest segmentation',
                'weights':str(a.model_dir),
                'source_width':width,'source_height':height,'fps':fps,'start_frame':start_frame,
                'pixel_vote_threshold':a.confidence,'stride':a.stride,'device':str(segmenter.device),
                'coordinate_system':'source pixels, xyxy boxes; polygons approximate mask boundaries and joined fragments',
                'track_ids':'temporary geometric associations, not persistent animal identities',
                'scores':'scene model scores are random-forest vote fractions, not calibrated confidence',
                'audio':'silent output'}
    sidecar = a.output.with_suffix('.jsonl')
    print(f'Processing {count} frames on {segmenter.device}',flush=True)
    success = False
    try:
        with sidecar.open('w') as records:
            for i in range(count):
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError(f'Decode failed at frame {start_frame+i}')
                gray = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
                inferred = i % a.stride == 0 or previous_gray is None
                if inferred:
                    detections = tracker.update(segmenter.predict(frame))
                else:
                    detections = propagate(previous_gray,gray,detections)
                    tracker.previous = detections
                row = {'frame':start_frame+i,'time_seconds':(start_frame+i)/fps,
                       'method':'model' if inferred else 'optical_flow', 'detections':detections}
                records.write(json.dumps(row,separators=(',',':'))+'\n')
                annotated = draw(frame,detections,a.masks,scale)
                if annotated.shape[:2] != (oh,ow):
                    annotated = cv2.resize(annotated,(ow,oh))
                writer.stdin.write(annotated.tobytes())
                if i in {0,count//2,count-1}:
                    cv2.imwrite(str(a.output.with_name(f'{a.output.stem}-frame-{start_frame+i:04d}.jpg')),annotated)
                segmenter.previous_centers=[d['mask_center'] for d in detections if 'mask_center' in d]
                previous_gray = gray
                counts.append(len(detections))
                processed += 1
                if i % 10 == 0 or i == count-1:
                    seconds = time.perf_counter()-elapsed
                    print(f'{i+1}/{count} frames | {len(detections)} cows | {seconds:.1f}s elapsed',flush=True)
        success = True
    finally:
        capture.release()
        writer.stdin.close()
        code = writer.wait()
        log.close()
        metadata.update({'complete':success and code==0,'frames_processed':processed,
                         'runtime_seconds':time.perf_counter()-elapsed,
                         'visible_count_min':min(counts,default=0),'visible_count_max':max(counts,default=0),
                         'detections_file':sidecar.name})
        a.output.with_suffix('.metadata.json').write_text(json.dumps(metadata,indent=2))
    if code != 0:
        raise RuntimeError(f'FFmpeg failed; see {log.name}')
    print(f'Saved {a.output}',flush=True)


if __name__ == '__main__':
    main()
