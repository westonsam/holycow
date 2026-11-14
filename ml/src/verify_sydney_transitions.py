"""Cross-check candidate transition timestamps against 100 human-reviewed label crops.

Requires ffmpeg and numpy/Pillow. The label montage must be a 10x10 grid of
150x80 source crops in numeric order 0..99, visually reviewed by a person.
A pass means the expected number was recognized at two sampled times; it is not
independent proof of the exact transition frame or clinical data correctness.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import csv
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image


def templates_from_montage(path):
    image = np.asarray(Image.open(path).convert('L'))
    if image.shape != (800, 1500):
        raise ValueError('expected a 1500 x 800 montage of 100 reviewed 150 x 80 crops')
    return np.stack([image[(i//10)*80:(i//10+1)*80, (i%10)*150:(i%10+1)*150] > 200 for i in range(100)])


def recognize(frame, templates):
    mask = frame > 200
    intersection = np.logical_and(templates, mask).sum(axis=(1, 2))
    union = np.logical_or(templates, mask).sum(axis=(1, 2))
    scores = intersection / np.maximum(union, 1)
    best = int(scores.argmax())
    runner_up = float(np.partition(scores, -2)[-2])
    return best, float(scores[best]), float(scores[best] - runner_up)


def read_frame(ffmpeg, video, seconds):
    cmd = [str(ffmpeg), '-v', 'error', '-ss', str(seconds), '-i', str(video),
           '-frames:v', '1', '-vf', 'crop=150:80:1808:48,format=gray', '-f', 'rawvideo', '-']
    p = subprocess.run(cmd, capture_output=True, timeout=90)
    if p.returncode or len(p.stdout) != 150 * 80:
        raise RuntimeError('frame decode failed: ' + p.stderr.decode(errors='replace')[:300])
    return np.frombuffer(p.stdout, dtype=np.uint8).reshape(80, 150)


def verify(row, templates, ffmpeg, video):
    expected = int(row['candidate_label'])
    lo, hi = float(row['lower_bound_s']), float(row['upper_bound_s'])
    result = {'transition': expected, 'sample_before_s': lo, 'sample_after_s': hi,
              'expected_before': expected - 1, 'expected_after': expected}
    try:
        for side, timestamp in [('before', lo), ('after', hi)]:
            label, score, margin = recognize(read_frame(ffmpeg, video, timestamp), templates)
            result.update({f'predicted_{side}': label, f'{side}_similarity': round(score, 4),
                           f'{side}_margin': round(margin, 4)})
        passed = (result['predicted_before'] == expected - 1 and result['predicted_after'] == expected
                  and min(result['before_similarity'], result['after_similarity']) >= 0.75
                  and min(result['before_margin'], result['after_margin']) >= 0.08)
        result['status'] = 'matched' if passed else 'needs_review'
        result['detail'] = 'Two nominal timestamps matched; exact frame boundary unverified' if passed else 'ambiguous label or unexpected number'
    except Exception as error:
        result['status'] = 'needs_review'
        result['detail'] = str(error)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', type=Path, required=True)
    parser.add_argument('--montage', type=Path, required=True)
    parser.add_argument('--candidates', type=Path, required=True)
    parser.add_argument('--ffmpeg', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    if args.output.exists(): raise FileExistsError('refusing to overwrite existing audit')
    with args.candidates.open(newline='') as f: rows = list(csv.DictReader(f))
    if [int(x['candidate_label']) for x in rows] != list(range(1, 100)):
        raise ValueError('expected candidate transitions 1–99')
    templates = templates_from_montage(args.montage)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda row: verify(row, templates, args.ffmpeg, args.video), rows))
    fields = ['transition','sample_before_s','sample_after_s','expected_before','expected_after',
              'predicted_before','predicted_after','before_similarity','after_similarity',
              'before_margin','after_margin','status','detail']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(results)
    print('matched:',sum(r['status']=='matched' for r in results),
          'needs review:',sum(r['status']!='matched' for r in results))
    for r in results:
        if r['status'] != 'matched': print('transition',r['transition'],r['detail'])


if __name__ == '__main__': main()
