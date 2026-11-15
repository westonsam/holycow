"""Write only notification control bindings into ignored local Worker vars."""
import os
from pathlib import Path
from .run import load_local_env


if __name__ == '__main__':
    load_local_env()
    token = os.environ.get('HOLYCOW_NOTIFICATIONS_TOKEN', '')
    if len(token) < 32 or any(c in token for c in ('\n', '\r', '"')):
        raise ValueError('Configure a valid backend token first')
    path = Path(__file__).resolve().parents[1] / 'web' / 'dist' / 'server' / '.dev.vars'
    if not path.parent.is_dir():
        raise ValueError('Build web first')
    bindings = {
        'HOLYCOW_NOTIFICATIONS_URL': 'http://127.0.0.1:8870',
        'HOLYCOW_NOTIFICATIONS_TOKEN': token,
        'HOLYCOW_DEMO_SERVICE_URL': 'http://127.0.0.1:8765',
    }
    lines = path.read_text().splitlines() if path.exists() else []
    lines = [line for line in lines if line.partition('=')[0] not in bindings]
    lines.extend(f'{key}="{value}"' for key, value in bindings.items())
    path.write_text('\n'.join(lines)+'\n')
    print('Configured local Worker bindings. No provider credentials were copied.')
