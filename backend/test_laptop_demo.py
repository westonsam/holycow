import json
import threading
import unittest
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from backend.laptop_demo import gateway, target, wait_for_public_connection


class ReadinessTests(unittest.TestCase):
    def test_waits_through_cloudflare_dns_error_for_both_public_routes(self):
        from io import BytesIO
        from unittest.mock import MagicMock
        def ready():
            response = MagicMock()
            response.__enter__.return_value = BytesIO(b'{"data": []}')
            response.__enter__.return_value.status = 200
            return response
        responses = [HTTPError('https://demo.example', 530, 'DNS not ready', {}, None), ready(), ready()]
        with patch('backend.laptop_demo.register') as register, \
             patch('backend.laptop_demo.urlopen', side_effect=responses) as fetch, \
             patch('backend.laptop_demo.time.sleep') as sleep:
            wait_for_public_connection('secret', 'https://demo.trycloudflare.com', [])
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(sleep.call_count, 1)
        register.assert_called_once_with('secret', 'https://demo.trycloudflare.com')
        self.assertTrue(fetch.call_args.args[0].full_url.endswith('/api/notifications/status'))


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), gateway('laptop-secret', 'private-notification-token'))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.root = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def request(self, path, token='laptop-secret', origin=None):
        headers = {'Authorization': f'Bearer {token}'}
        if origin:
            headers['Origin'] = origin
        try:
            response = urlopen(Request(self.root + path, headers=headers))
        except HTTPError as response:
            return response.code, response.read()
        with response:
            return response.status, response.read()

    def test_requires_secret_and_rejects_direct_browser_requests(self):
        self.assertEqual(self.request('/flight/jobs', token='wrong')[0], 401)
        self.assertEqual(self.request('/flight/jobs', origin='https://evil.example')[0], 403)

    def test_allowlist_excludes_ingestion_exports_and_arbitrary_files(self):
        for path in ('/notifications/v1/alerts', '/notifications/v1/training-candidates',
                     '/flight/../../etc/passwd', '/flight/jobs?url=http://evil.example'):
            self.assertEqual(self.request(path)[0], 404)
        self.assertIsNone(target('POST', '/notifications/v1/simulate-reply'))
        self.assertEqual(target('POST', '/notifications/v1/telegram-demo'), (8870, '/v1/telegram-demo'))

    def test_proxies_range_without_exposing_service_credential(self):
        seen = {}
        class Upstream(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                seen.update(path=self.path, token=self.headers.get('Authorization'), range=self.headers.get('Range'))
                self.send_response(206)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Content-Length', '3')
                self.send_header('Content-Range', 'bytes 0-2/10')
                self.end_headers()
                self.wfile.write(b'abc')
        upstream = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        threading.Thread(target=upstream.serve_forever, daemon=True).start()
        from http.client import HTTPConnection as RealConnection
        try:
            with patch('backend.laptop_demo.HTTPConnection', side_effect=lambda host, port, **kw: RealConnection(host, upstream.server_port, **kw)):
                req = Request(self.root + '/notifications/v/' + 'a'*32,
                              headers={'Authorization': 'Bearer laptop-secret', 'Range': 'bytes=0-2'})
                with urlopen(req) as response:
                    self.assertEqual(response.status, 206)
                    self.assertEqual(response.read(), b'abc')
                    self.assertIsNone(response.headers.get('Authorization'))
            self.assertEqual(seen['token'], 'Bearer private-notification-token')
            self.assertEqual(seen['range'], 'bytes=0-2')
        finally:
            upstream.shutdown()
            upstream.server_close()


if __name__ == '__main__':
    unittest.main()
