"""Start the laptop services and a temporary authenticated Cloudflare tunnel.

Run python -m backend.laptop_demo; Ctrl+C disconnects the public dashboard.
No API keys or service credentials are sent to visitors.
"""
from __future__ import annotations

import hmac
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen

from .run import load_local_env

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://holycow-herd-monitor.freebream261.chatgpt.site'
SETTINGS = ROOT / 'backend' / '.env.laptop.json'
STOP_REQUEST = ROOT / 'backend' / 'state' / 'laptop-demo.stop'


def target(method, path):
    """Fixed upstreams only; never forward caller-selected hosts or file paths."""
    flight = path.removeprefix('/flight')
    if path.startswith('/flight/'):
        if method == 'GET' and re.fullmatch(r'/(jobs|jobs/[a-f0-9]{32}|assets/(scene-video|reference-video))', flight):
            return 8765, flight
        if method == 'POST' and re.fullmatch(r'/(jobs|reset|jobs/[a-f0-9]{32}/reviews)', flight):
            return 8765, flight
    notification = path.removeprefix('/notifications')
    if path.startswith('/notifications/'):
        if method == 'GET' and (notification == '/v1/notifications' or re.fullmatch(r'/v/[A-Za-z0-9_-]{32}', notification)):
            return 8870, notification
        if method == 'POST' and notification == '/v1/telegram-demo':
            return 8870, notification
    return None


def gateway(token, notification_token, flight_port=8765, notification_port=8870):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Do not log bearer credentials or evidence URLs.

        def error(self, status, message):
            raw = json.dumps({'error': {'message': message}}).encode()
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
            if not hmac.compare_digest(self.headers.get('Authorization', '').encode(), f'Bearer {token}'.encode()):
                return self.error(401, 'Unauthorized')
            if self.headers.get('Origin'):
                return self.error(403, 'Use the dashboard')
            route = target(self.command, self.path)
            if not route:
                return self.error(404, 'Unknown demo operation')
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if self.headers.get('Transfer-Encoding') or not 0 <= size <= 6000:
                    return self.error(413, 'Invalid request size')
                body = self.rfile.read(size) if size else None
                headers = {'Authorization': f'Bearer {notification_token}'} if route[0] == 8870 else {}
                for name in ('Content-Type', 'Range'):
                    if self.headers.get(name):
                        headers[name] = self.headers[name]
                upstream_port = flight_port if route[0] == 8765 else notification_port
                connection = HTTPConnection('127.0.0.1', upstream_port, timeout=20)
                try:
                    connection.request(self.command, route[1], body=body, headers=headers)
                    response = connection.getresponse()
                    self.send_response(response.status)
                    for name in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges', 'Content-Disposition'):
                        if response.getheader(name):
                            self.send_header(name, response.getheader(name))
                    self.send_header('Cache-Control', 'no-store')
                    self.end_headers()
                    while chunk := response.read(65536):
                        self.wfile.write(chunk)
                finally:
                    connection.close()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except (OSError, ValueError):
                self.error(503, 'Demo backend offline. Restart it on the laptop.')
    return Handler


def register(token, url=None):
    payload = {'url': url} if url else {'offline': True}
    request = Request(f'{SITE}/api/laptop-connection', data=json.dumps(payload).encode(),
                      headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
                               'User-Agent': 'HolyCow-Demo/1.0'})
    with urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError('Dashboard registration failed')


def notification_is_running(port, token):
    import socket
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', port)) != 0:
            return False
    # Reuse only a backend that accepts the configured service credential.
    request = Request(f'http://127.0.0.1:{port}/v1/notifications',
                      headers={'Authorization': f'Bearer {token}'})
    try:
        with urlopen(request, timeout=5) as response:
            if response.status == 200 and isinstance(json.load(response).get('data'), dict):
                return True
    except (OSError, ValueError):
        pass
    raise RuntimeError('Port 8870 is occupied by a different backend. Stop it before launching the demo.')


def wait_for_public_connection(token, endpoint, children, timeout=180):
    """A tunnel can be registered before Cloudflare's resolver can reach it."""
    deadline = time.monotonic() + timeout
    last_registration = 0
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in children):
            raise RuntimeError('A demo service stopped while connecting. Check backend/state/laptop-*.log')
        try:
            if time.monotonic() - last_registration >= 20:
                register(token, endpoint)
                last_registration = time.monotonic()
            # Check the actual public control layer, including its DNS resolver,
            # rather than assuming that a locally reachable tunnel is ready.
            for path in ('/api/demo-flight/jobs', '/api/notifications/status'):
                request = Request(SITE + path, headers={'User-Agent': 'HolyCow-Demo/1.0'})
                with urlopen(request, timeout=15) as response:
                    if response.status != 200 or 'data' not in json.load(response):
                        raise ValueError('Backend is not ready')
            return
        except (OSError, ValueError):
            time.sleep(2)
    raise RuntimeError('Cloudflare could not reach the laptop within three minutes. Restart the launcher to get a new tunnel.')


def main():
    load_local_env()
    check_only = '--check' in sys.argv
    flight_port, notification_port, gateway_port = 8765, 8870, 8880
    if check_only:
        # Isolated smoke check: never start Telegram polling or send messages.
        import tempfile
        check_state = tempfile.TemporaryDirectory(prefix='holycow-connection-check-')
        import socket
        def available_port():
            with socket.socket() as candidate:
                candidate.bind(('127.0.0.1', 0))
                return candidate.getsockname()[1]
        flight_port, notification_port, gateway_port = (available_port() for _ in range(3))
        os.environ.update(HOLYCOW_MESSAGING_TRANSPORT='simulator', HOLYCOW_FEEDBACK_AGENT='commands',
                          HOLYCOW_NOTIFICATIONS_DB=str(Path(check_state.name) / 'notifications.sqlite3'),
                          HOLYCOW_DEMO_STATE=str(Path(check_state.name) / 'flight'))
    settings = json.loads(SETTINGS.read_text())
    token = settings['token']
    notification_token = os.environ.get('HOLYCOW_NOTIFICATIONS_TOKEN', '')
    if len(token) < 32 or len(notification_token) < 32:
        raise ValueError('Configure the laptop connection and notification credentials first')
    python = ROOT / 'backend/.venv/Scripts/python.exe'
    ml_python = ROOT.parent / '.cow-vision-venv/Scripts/python.exe'
    cloudflared = ROOT / 'backend/tools/cloudflared.exe'
    source = ROOT / 'ml/motion-demo-assets/playback.mp4'
    if not source.is_file():
        raise ValueError('Motion demo playback missing. Run ml/prepare_motion_demo.py first.')
    env = dict(os.environ, HOLYCOW_DEMO_SOURCE=str(source))
    children = []
    logs = []
    server = None
    registered = False
    log_directory = ROOT / 'backend/state'
    log_directory.mkdir(exist_ok=True)
    try:
        # Avoid a second Telegram poller when the user's local worker is already on.
        reuse_notifications = not check_only and notification_is_running(notification_port, notification_token)
        import socket
        for port in (flight_port, notification_port, gateway_port):
            if port == notification_port and reuse_notifications:
                continue
            with socket.socket() as check:
                check.bind(('127.0.0.1', port))
        if not check_only:
            STOP_REQUEST.unlink(missing_ok=True)
        for name, command in (
            ('notifications', [str(python), '-m', 'uvicorn', 'backend.app:create_app', '--factory', '--host', '127.0.0.1', '--port', str(notification_port), '--workers', '1', '--no-access-log']),
            ('flight', [str(ml_python), '-u', 'ml/demo_service.py', '--port', str(flight_port)]),
        ):
            if name == 'notifications' and reuse_notifications:
                print('Reusing the existing authenticated notification worker.', flush=True)
                continue
            log = (log_directory / f'laptop-{name}.log').open('w')
            logs.append(log)
            children.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=log,
                                             creationflags=subprocess.CREATE_NO_WINDOW))
        server = ThreadingHTTPServer(('127.0.0.1', gateway_port), gateway(token, notification_token, flight_port, notification_port))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        tunnel = subprocess.Popen([str(cloudflared), 'tunnel', '--url', f'http://127.0.0.1:{gateway_port}',
                                   '--protocol', 'http2', '--no-autoupdate'], cwd=ROOT,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW)
        children.append(tunnel)
        ready = threading.Event()
        endpoint = []

        def read_tunnel():
            with (log_directory / 'laptop-tunnel.log').open('w') as log:
                for line in tunnel.stderr:
                    log.write(line)
                    log.flush()
                    match = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', line)
                    if match and not endpoint:
                        endpoint.append(match[0])
                        ready.set()

        threading.Thread(target=read_tunnel, daemon=True).start()
        print('Starting laptop services and Cloudflare tunnel...', flush=True)
        if not ready.wait(45):
            raise RuntimeError('Tunnel did not connect. See backend/state/laptop-tunnel.log')
        # Wait for the local services before making them discoverable.
        for port, path in ((notification_port, '/healthz'), (flight_port, '/jobs')):
            for attempt in range(30):
                if any(process.poll() is not None for process in children):
                    raise RuntimeError('A demo service stopped. Check backend/state/laptop-*.log')
                try:
                    with urlopen(f'http://127.0.0.1:{port}{path}', timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError('A demo service did not become ready')
        register(token, endpoint[0])
        registered = True
        print('Waiting for the public dashboard to reach the laptop (a new tunnel can take a few minutes)...', flush=True)
        wait_for_public_connection(token, endpoint[0], children)
        if check_only:
            def public(path, body=None, headers=None):
                data = json.dumps(body).encode() if body is not None else None
                request = Request(SITE + path, data=data, headers={
                    'User-Agent': 'HolyCow-Demo/1.0',
                    **({'Content-Type': 'application/json', 'Origin': SITE} if data else {}), **(headers or {})})
                with urlopen(request, timeout=30) as response:
                    return response.status, response.read()
            for attempt in range(15):
                try:
                    status, raw = public('/api/demo-flight/jobs')
                    assert status == 200
                    break
                except OSError:
                    time.sleep(2)
            else:
                raise RuntimeError('Public dashboard did not reach the laptop tunnel')
            import uuid
            status, raw = public('/api/demo-flight/jobs', {'assetId': 'scene-flight', 'mode': 'precomputed', 'requestId': uuid.uuid4().hex})
            job_id = json.loads(raw)['data']['id']
            for _ in range(20):
                _, raw = public('/api/demo-flight/jobs/' + job_id)
                job = json.loads(raw)['data']
                if job['state'] == 'completed':
                    assert job['result']['trackCount'] > 0
                    break
                time.sleep(.5)
            else:
                raise RuntimeError('Prepared flight did not complete through the public dashboard')
            status, raw = public('/api/demo-flight/assets/scene-video', headers={'Range': 'bytes=0-1023'})
            assert status == 206 and len(raw) == 1024
            status, raw = public('/api/notifications/status')
            assert status == 200 and json.loads(raw)['data']['health']['transport'] == 'simulator'
            print('PASS: public dashboard -> authenticated tunnel -> prepared flight, evidence video and notification status. No Telegram messages sent.', flush=True)
            return
        print(f'CONNECTED: {SITE}\nKeep this window open. Ctrl+C turns the public backend OFF.', flush=True)
        print('Judges can process the demo flight and request the Telegram demo while connected.', flush=True)
        while True:
            for _ in range(25):
                if STOP_REQUEST.exists():
                    STOP_REQUEST.unlink(missing_ok=True)
                    raise KeyboardInterrupt
                time.sleep(1)
            if any(process.poll() is not None for process in children):
                raise RuntimeError('A service stopped; disconnecting the public backend')
            try:
                register(token, endpoint[0])
            except OSError:
                print('Connection heartbeat failed; retrying. Dashboard goes offline after 90 seconds without a heartbeat.', flush=True)
    except KeyboardInterrupt:
        print('\nDisconnecting demo backend...', flush=True)
    finally:
        if registered:
            try:
                register(token)
            except OSError:
                pass
        if server:
            server.shutdown()
            server.server_close()
        # Terminate process trees, including any inference subprocess.
        for process in reversed(children):
            if process.poll() is None:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        for log in logs:
            log.close()
        if check_only:
            check_state.cleanup()
        print('Backend OFF. The public dashboard stays online.', flush=True)


if __name__ == '__main__':
    main()
