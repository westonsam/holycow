"""Loopback-only hackathon backend. No browser CORS or arbitrary media paths."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'demo-assets'
ID = re.compile(r'^[a-f0-9]{32}$')


class Problem(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


def load_results(path, metadata):
    meta = json.loads(metadata.read_text())
    if not meta['complete']:
        raise ValueError('Incomplete pipeline output')
    frames = []
    for line in path.read_text().splitlines():
        row = json.loads(line)
        frames.append({'frame': row['frame'], 'time': row['time_seconds'],
                       'detections': [{'id': f"{row['frame']}-{d['track_id']}",
                                       'track': d['track_id'], 'box': d['box']}
                                      for d in row['detections']]})
    return {'width': meta['source_width'], 'height': meta['source_height'],
            'fps': meta['fps'], 'duration': meta['frames_processed']/meta['fps'],
            'trackCount': len({d['track'] for f in frames for d in f['detections']}),
            'frames': frames}


class Store:
    def __init__(self, directory, runner=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.db = self.directory / 'demo.sqlite3'
        self.lock = threading.RLock()
        self.runner = runner or self.infer
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, mode TEXT NOT NULL, state TEXT NOT NULL,
                progress REAL, error TEXT, result TEXT, request_id TEXT UNIQUE,
                created TEXT DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS reviews (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT NOT NULL,
                detection TEXT NOT NULL, action TEXT NOT NULL, note TEXT NOT NULL,
                created TEXT DEFAULT CURRENT_TIMESTAMP);''')
            db.execute("UPDATE jobs SET state='failed', error='Service restarted during processing. Start a new job.' WHERE state IN ('queued','running')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, job_id):
        if not ID.fullmatch(job_id):
            raise Problem('Invalid job ID')
        with self.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if not row:
                raise Problem('Job not found', 404)
            reviews = [dict(r) for r in db.execute('SELECT * FROM reviews WHERE job=? ORDER BY seq', (job_id,))]
        result = json.loads(row['result']) if row['result'] else None
        return {'id': row['id'], 'mode': row['mode'], 'state': row['state'],
                'progress': row['progress'], 'error': row['error'], 'created': row['created'],
                'result': result, 'reviews': reviews}

    def list(self):
        with self.connect() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM jobs ORDER BY created DESC, rowid DESC LIMIT 50')]
        return [self.get(i) | {'result': None, 'summary': self.summary(i)} for i in ids]

    def summary(self, job_id):
        result = self.get(job_id)['result']
        return {k: result[k] for k in ('duration', 'trackCount')} if result else None

    def start(self, body):
        if not isinstance(body, dict) or set(body) != {'assetId', 'mode', 'requestId'}:
            raise Problem('Select a prepared flight and processing mode')
        if body['assetId'] != 'scene-flight' or body['mode'] not in ('inference', 'precomputed'):
            raise Problem('Unsupported flight or mode')
        if not isinstance(body['requestId'], str) or not ID.fullmatch(body['requestId']):
            raise Problem('Invalid request ID')
        with self.lock, self.connect() as db:
            existing = db.execute("SELECT id FROM jobs WHERE request_id=? OR state IN ('queued','running') ORDER BY rowid LIMIT 1", (body['requestId'],)).fetchone()
            if existing:
                return self.get(existing[0])
            job_id = uuid.uuid4().hex
            db.execute("INSERT INTO jobs(id, mode, state, request_id) VALUES (?,?,'queued',?)", (job_id, body['mode'], body['requestId']))
        # Return the queued snapshot; processing never blocks the HTTP request.
        queued = self.get(job_id)
        threading.Thread(target=self.run, args=(job_id, body['mode']), daemon=True).start()
        return queued

    def update(self, job_id, **values):
        with self.connect() as db:
            db.execute('UPDATE jobs SET '+','.join(k+'=?' for k in values)+' WHERE id=?', (*values.values(), job_id))

    def run(self, job_id, mode):
        try:
            self.update(job_id, state='running')
            if mode == 'precomputed':
                result = json.loads((ASSETS / 'prepared.json').read_text())
            else:
                result = self.runner(job_id)
            self.update(job_id, state='completed', progress=1, result=json.dumps(result))
        except Exception:
            self.update(job_id, state='failed', error='Processing unavailable or evidence invalid. Check local service logs; prepared-results mode can be used without inference.')
            import traceback
            traceback.print_exc()

    def infer(self, job_id):
        source = Path(os.environ.get('HOLYCOW_DEMO_SOURCE', ASSETS / 'source.mp4'))
        prepared = json.loads((ASSETS / 'prepared.json').read_text())
        with source.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != prepared['provenance']['sourceSha256']:
                raise ValueError('Only the original prepared scene is supported')
        output = self.directory / f'{job_id}.mp4'
        command = [sys.executable, '-u', str(ROOT / 'cow_segment.py'), str(source), '--output', str(output)]
        with (self.directory / f'{job_id}.log').open('w') as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=log, text=True)
            for line in process.stdout:
                log.write(line)
                log.flush()
                match = re.match(r'(\d+)/(\d+) frames', line)
                if match:
                    self.update(job_id, progress=min(.999, int(match[1])/int(match[2])))
            if process.wait() != 0:
                raise RuntimeError('Pipeline failed')
        return load_results(output.with_suffix('.jsonl'), output.with_suffix('.metadata.json'))

    def review(self, job_id, body):
        with self.lock:
            job = self.get(job_id)
            if not isinstance(body, dict) or set(body) != {'detectionId', 'action', 'note', 'expectedSeq'}:
                raise Problem('Invalid review payload')
            detection, action, note = body['detectionId'], body['action'], body['note']
            if not isinstance(detection, str) or not isinstance(action, str) or action not in ('flag', 'resolve', 'reject') or not isinstance(note, str) or not 1 <= len(note.strip()) <= 2000:
                raise Problem('Choose an action and add a note (1–2000 characters)')
            if job['state'] != 'completed' or not any(d['id'] == detection for f in job['result']['frames'] for d in f['detections']):
                raise Problem('Detection not found', 404)
            history = [r for r in job['reviews'] if r['detection'] == detection]
            last = history[-1] if history else None
            if type(body['expectedSeq']) is not int or body['expectedSeq'] != (last['seq'] if last else 0):
                raise Problem('Review changed. Reload before saving.', 409)
            if (action == 'flag' and last and last['action'] == 'flag') or (action != 'flag' and (not last or last['action'] != 'flag')):
                raise Problem('Flag this observation before resolving or rejecting it', 409)
            with self.connect() as db:
                db.execute('INSERT INTO reviews(job,detection,action,note) VALUES (?,?,?,?)', (job_id, detection, action, note.strip()))
            return self.get(job_id)

    def reset(self):
        with self.lock, self.connect() as db:
            if db.execute("SELECT 1 FROM jobs WHERE state IN ('queued','running')").fetchone():
                raise Problem('Wait for processing to finish before resetting', 409)
            db.execute('DELETE FROM reviews')
            db.execute('DELETE FROM jobs')
        return {'reset': True}


def handler(store):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, data, status=200):
            raw = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.dispatch()

        def do_POST(self):
            self.dispatch()

        def dispatch(self):
            try:
                # No browser access: only the same-origin web control layer calls this service.
                if self.headers.get('Origin'):
                    raise Problem('Use the web control layer', 403)
                path = self.path
                if self.command == 'GET' and path == '/assets/scene-video':
                    return self.video()
                body = None
                if self.command == 'POST':
                    if 'application/json' not in self.headers.get('Content-Type', ''):
                        raise Problem('JSON required', 415)
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 6000:
                        raise Problem('Invalid body size', 413)
                    body = json.loads(self.rfile.read(size))
                if path == '/jobs' and self.command == 'GET':
                    result = store.list()
                elif path == '/jobs' and self.command == 'POST':
                    result = store.start(body)
                elif path == '/reset' and self.command == 'POST' and body == {}:
                    result = store.reset()
                elif re.fullmatch(r'/jobs/[^/]+', path) and self.command == 'GET':
                    result = store.get(path.split('/')[2])
                elif re.fullmatch(r'/jobs/[^/]+/reviews', path) and self.command == 'POST':
                    result = store.review(path.split('/')[2], body)
                else:
                    raise Problem('Endpoint not found', 404)
                self.respond({'data': result})
            except Problem as error:
                self.respond({'error': {'message': str(error)}}, error.status)
            except (ValueError, TypeError):
                self.respond({'error': {'message': 'Invalid JSON or request'}}, 400)
            except Exception:
                self.respond({'error': {'message': 'Local demo service could not complete the request'}}, 503)

        def video(self):
            path = ASSETS / 'playback.mp4'
            if not path.is_file():
                raise Problem('Prepared playback asset unavailable; run prepare_demo.py', 503)
            size = path.stat().st_size
            start, end, status = 0, size-1, 200
            header = self.headers.get('Range')
            if header:
                match = re.fullmatch(r'bytes=(\d+)-(\d*)', header)
                if not match:
                    raise Problem('Unsupported byte range', 416)
                start = int(match[1])
                end = min(int(match[2]) if match[2] else end, size-1)
                if start > end:
                    raise Problem('Invalid byte range', 416)
                status = 206
            self.send_response(status)
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Content-Length', str(end-start+1))
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            with path.open('rb') as stream:
                stream.seek(start)
                remaining = end-start+1
                while remaining:
                    chunk = stream.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    store = Store(os.environ.get('HOLYCOW_DEMO_STATE', ROOT / 'demo-state'))
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(store))
    print(f'HolyCow local demo service http://127.0.0.1:{args.port}', flush=True)
    server.serve_forever()
