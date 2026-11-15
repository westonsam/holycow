"""Prepare a five-second simulator-only video from the existing scene playback."""
import json
from pathlib import Path
import subprocess
import imageio_ffmpeg


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    source = root / 'ml/demo-assets/playback.mp4'
    if not source.is_file():
        raise ValueError('Prepare the flight playback using ml/prepare_demo.py first')
    destination = root / 'backend/evidence'
    destination.mkdir(exist_ok=True)
    manifest = destination / 'manifest.json'
    registry = json.loads(manifest.read_text()) if manifest.exists() else {}
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-i', str(source),
                    '-t', '5', '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
                    str(destination / 'demo-scene.mp4')], check=True)
    registry['demo-scene'] = {'file': 'demo-scene.mp4', 'simulationOnly': True,
        'description': 'Sample stock scene only; not evidence of a registered animal identity or the synthetic movement flag.'}
    manifest.write_text(json.dumps(registry, indent=2))
    print('Prepared five-second simulator video. No inference was run.')
