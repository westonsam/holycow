"""Prepare browser-safe videos and provenance for the new motion demo."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'motion-demo-assets'


def encode(source, destination, rate):
    temporary = destination.with_suffix('.preparing.mp4')
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error', '-i', str(source),
        '-an', '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2',
        '-r', str(rate), '-c:v', 'libx264', '-crf', '21', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(temporary)], check=True)
    temporary.replace(destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analyze', action='store_true')
    args = parser.parse_args()
    ASSETS.mkdir(exist_ok=True)
    source = ASSETS / 'source.mov'
    encode(source, ASSETS / 'playback.mp4', 10)
    encode(ASSETS / 'provided-annotated.mp4', ASSETS / 'reference.mp4', 10)
    metadata = imageio_ffmpeg.read_frames(str(ASSETS / 'playback.mp4'))
    info = next(metadata)
    metadata.close()
    manifest = {'assetId': 'scene-flight', 'name': 'Cow motion demo', 'sourceName': source.name,
        'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'playbackSha256': hashlib.sha256((ASSETS/'playback.mp4').read_bytes()).hexdigest(),
        'fps': info['fps'], 'width': info['size'][0], 'height': info['size'][1], 'duration': info['duration'],
        'pipeline': 'YOLO11 segmentation + APT-36K ViTPose', 'illustrativeScores': True}
    (ASSETS / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    if args.analyze:
        from motion_pipeline import analyze
        result = analyze(ASSETS / 'playback.mp4', ASSETS / 'prepared.json')
        print(f"Prepared {len(result['frames'])} frames with {result['trackCount']} temporary tracks.")
