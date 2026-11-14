"""Inspect local files without assuming how source videos map to scores."""
import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inspect(path):
    result = {'path': str(path), 'size_bytes': path.stat().st_size, 'sha256': sha256(path)}
    if path.suffix.lower() in {'.mp4', '.mov', '.avi', '.mkv'}:
        try:
            probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                'format=duration:stream=codec_name,width,height,avg_frame_rate',
                '-of', 'json', str(path)], capture_output=True, text=True, check=True)
            result['video_probe'] = json.loads(probe.stdout)
        except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            result['video_probe_error'] = str(error)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error('directory does not exist')
    records = [inspect(p) for p in sorted(args.directory.rglob('*')) if p.is_file()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2) + '\n')
    print(f'Inspected {len(records)} files; review probe errors and source labels before modeling.')


if __name__ == '__main__':
    main()
