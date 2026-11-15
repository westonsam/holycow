"""Operator-registered videos only; callers cannot supply URLs or file paths."""
import json
from pathlib import Path
import re


def asset(settings, asset_id, simulation=False):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', asset_id):
        raise ValueError('Unknown video')
    root = Path(settings.evidence_directory).resolve()
    try:
        registry = json.loads((root / 'manifest.json').read_text())
        entry = registry[asset_id]
        path = (root / entry['file']).resolve()
        if not path.is_relative_to(root) or path.suffix.lower() != '.mp4' or not path.is_file():
            raise ValueError('Video unavailable')
        if entry.get('simulationOnly', False) and not simulation:
            raise ValueError('Demo video cannot be used for live alerts')
        return path
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('Video unavailable') from None
