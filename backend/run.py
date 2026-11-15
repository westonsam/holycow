"""Local launcher: python -m backend.run. Docker uses its own environment."""
import os
from pathlib import Path


def load_local_env():
    path = Path(__file__).with_name('.env')
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            key, separator, value = line.partition('=')
            if not separator or not key.strip().replace('_', '').isalnum():
                raise ValueError('Invalid backend environment file')
            os.environ.setdefault(key.strip(), value.strip())


if __name__ == '__main__':
    import uvicorn
    load_local_env()
    uvicorn.run('backend.app:create_app', factory=True, host='127.0.0.1', port=8870, workers=1, access_log=False)
