"""Prepare demo-only Telegram footage; --source keeps a custom clip's full duration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import imageio_ffmpeg
from .run import load_local_env


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    source = args.source or root / 'ml/demo-assets/playback.mp4'
    if not source.is_file():
        raise ValueError('Source video unavailable')
    load_local_env()
    destination = Path(os.environ.get('HOLYCOW_EVIDENCE_DIRECTORY', str(root / 'backend/evidence')))
    destination.mkdir(parents=True, exist_ok=True)
    manifest = destination / 'manifest.json'
    registry = json.loads(manifest.read_text()) if manifest.exists() else {}
    temporary = destination / 'demo-scene.preparing.mp4'
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-i', str(source)]
    if not args.source:
        command += ['-t', '5']
    command += ['-an', '-vf', 'scale=1280:1280:force_original_aspect_ratio=decrease:force_divisible_by=2',
                '-r', '30', '-c:v', 'libx264', '-crf', '23', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                str(temporary)]
    subprocess.run(command, check=True)
    if temporary.stat().st_size > 49_000_000:
        raise ValueError('Prepared video exceeds the backend upload limit')
    temporary.replace(destination / 'demo-scene.mp4')
    registry['demo-scene'] = {'file': 'demo-scene.mp4', 'simulationOnly': True,
        'description': 'Illustrative demo footage only; not evidence of a registered animal identity or the synthetic movement flag.',
        'sourceName': source.name, 'sourceSha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    manifest_tmp = destination / 'manifest.preparing.json'
    manifest_tmp.write_text(json.dumps(registry, indent=2))
    manifest_tmp.replace(manifest)
    print('Prepared Telegram demo video. No inference was run and no message was sent.')
