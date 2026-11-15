"""Prepare local playback and compact boxes from actual cow_segment.py output."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import imageio_ffmpeg
from ml.above.demo_service import ASSETS, load_results

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path, help='Original 3840x2160 scene clip')
    p.add_argument('--predictions', type=Path, help='Actual pipeline JSONL; omit to retain bundled prepared results')
    p.add_argument('--metadata', type=Path)
    a = p.parse_args()
    ASSETS.mkdir(exist_ok=True)
    digest = hashlib.file_digest(a.source.open('rb'), 'sha256').hexdigest()
    if a.predictions:
        if not a.metadata:
            p.error('--metadata required with --predictions')
        result = load_results(a.predictions, a.metadata)
        result['provenance'] = {'pipeline': 'cow_segment.py', 'sourceSha256': digest,
                                'predictionsSha256': hashlib.file_digest(a.predictions.open('rb'), 'sha256').hexdigest(),
                                'description': 'Actual scene model output; compact xyxy boxes retained for every frame.'}
        (ASSETS / 'prepared.json').write_text(json.dumps(result, separators=(',', ':')))
    else:
        result = json.loads((ASSETS / 'prepared.json').read_text())
        if result['provenance']['sourceSha256'] != digest:
            p.error('Source does not match the bundled scene predictions')
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-i', str(a.source), '-an',
                    '-vf', 'scale=1280:720', '-c:v', 'libx264', '-crf', '21',
                    '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(ASSETS / 'playback.mp4')], check=True)
    print('Prepared playback and results. Set HOLYCOW_DEMO_SOURCE to the original source for inference.')
