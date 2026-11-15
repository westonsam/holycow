"""Run with python -m unittest discover -s ml -p test_demo_service.py."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
import uuid
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from demo_service import ASSETS, Problem, Store, handler


def command(mode='precomputed'):
    return {'assetId': 'scene-flight', 'mode': mode, 'requestId': uuid.uuid4().hex}


def finished(store, job_id):
    for _ in range(200):
        job = store.get(job_id)
        if job['state'] in ('completed', 'failed'):
            return job
        time.sleep(.025)
    raise AssertionError('Job did not finish')


class DemoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_prepared_without_inference_and_durable_review(self):
        self.store.runner = lambda _: self.fail('Prepared mode ran inference')
        request = command()
        queued = self.store.start(request)
        self.assertEqual(queued['state'], 'queued')
        job = finished(self.store, queued['id'])
        self.assertEqual(job['state'], 'completed')
        self.assertEqual(len(job['result']['frames']), len(json.loads((ASSETS / 'prepared.json').read_text())['frames']))
        self.assertTrue(job['result']['illustrativeScores'])
        self.assertEqual(len(job['result']['frames'][0]['detections'][0]['keypoints']), 17)
        self.assertEqual(self.store.start(request)['id'], job['id'])
        payload = {'detectionId': job['result']['frames'][0]['detections'][0]['id'], 'action': 'flag', 'note': 'Check edge of mask', 'expectedSeq': 0}
        flagged = self.store.review(job['id'], payload)
        self.assertEqual(len(flagged['reviews']), 1)
        with self.assertRaises(Problem) as conflict:
            self.store.review(job['id'], payload)
        self.assertEqual(conflict.exception.status, 409)
        restarted = Store(self.temp.name)
        self.assertEqual(restarted.get(job['id'])['reviews'], flagged['reviews'])
        payload.update(action='resolve', note='Reviewed source; observation confirmed', expectedSeq=flagged['reviews'][0]['seq'])
        resolved = restarted.review(job['id'], payload)
        self.assertEqual([r['action'] for r in resolved['reviews']], ['flag', 'resolve'])
        self.assertEqual(Store(self.temp.name).get(job['id'])['reviews'], resolved['reviews'])
        prepared = (ASSETS / 'prepared.json').read_bytes()
        restarted.reset()
        self.assertEqual(restarted.list(), [])
        self.assertEqual(prepared, (ASSETS / 'prepared.json').read_bytes())

    def test_running_progress_duplicate_and_failure(self):
        ready, release = threading.Event(), threading.Event()
        def runner(job_id):
            self.store.update(job_id, progress=.25)
            ready.set()
            release.wait(5)
            raise RuntimeError('deliberate test failure')
        self.store.runner = runner
        queued = self.store.start(command('inference'))
        try:
            self.assertTrue(ready.wait(3))
            running = self.store.get(queued['id'])
            self.assertEqual((running['state'], running['progress']), ('running', .25))
            self.assertEqual(self.store.start(command())['id'], queued['id'])
            with self.assertRaises(Problem):
                self.store.reset()
        finally:
            release.set()
        failed = finished(self.store, queued['id'])
        self.assertEqual(failed['state'], 'failed')
        self.assertIsNone(failed['result'])

    def test_restart_marks_interrupted_jobs_failed(self):
        job_id = uuid.uuid4().hex
        with self.store.connect() as db:
            db.execute("INSERT INTO jobs(id,mode,state) VALUES (?,'inference','running')", (job_id,))
        self.assertEqual(Store(self.temp.name).get(job_id)['state'], 'failed')

    def test_replaced_playback_cannot_reuse_old_predictions(self):
        replacement = Path(self.temp.name) / 'replacement'
        replacement.mkdir()
        (replacement / 'prepared.json').write_bytes((ASSETS / 'prepared.json').read_bytes())
        (replacement / 'manifest.json').write_bytes((ASSETS / 'manifest.json').read_bytes())
        (replacement / 'playback.mp4').write_bytes(b'not-the-video-that-was-analyzed')
        with patch('demo_service.ASSETS', replacement):
            job = finished(self.store, self.store.start(command())['id'])
        self.assertEqual(job['state'], 'failed')
        self.assertIsNone(job['result'])

    def test_unavailable_inference_still_allows_prepared_results(self):
        with patch.dict(os.environ, {'HOLYCOW_DEMO_SOURCE': str(Path(self.temp.name) / 'missing.mp4')}):
            job = finished(self.store, self.store.start(command('inference'))['id'])
        self.assertEqual(job['state'], 'failed')
        self.assertEqual(finished(self.store, self.store.start(command())['id'])['state'], 'completed')

    def test_invalid_inputs_and_review_lifecycle(self):
        for invalid in ('../source.mp4', 'nope', 'A'*32):
            with self.assertRaises(Problem): self.store.get(invalid)
        with self.assertRaises(Problem) as missing: self.store.get('a'*32)
        self.assertEqual(missing.exception.status, 404)
        for body in ({}, command() | {'assetId': '../../secret'}, command() | {'mode': 'fake'}, command() | {'requestId': 'bad'}):
            with self.assertRaises(Problem): self.store.start(body)
        job = finished(self.store, self.store.start(command())['id'])
        payload = {'detectionId': '0-1', 'action': 'flag', 'note': 'Review', 'expectedSeq': 0}
        for change in ({'note': ''}, {'note': 'x'*2001}, {'detectionId': '999999-1'}, {'expectedSeq': True}, {'action': 'diagnose'}, {'action': 'reject'}, {'extra': 'untrusted'}):
            with self.assertRaises(Problem): self.store.review(job['id'], payload | change)
        job = self.store.review(job['id'], payload)
        payload.update(action='reject', expectedSeq=job['reviews'][-1]['seq'], note='False positive')
        self.assertEqual(self.store.review(job['id'], payload)['reviews'][-1]['action'], 'reject')

    def test_http_known_assets_ranges_and_boundary(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.store))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            for path, status in (('/jobs/invalid', 400), ('/jobs/'+'a'*32, 404), ('/assets/secret', 404), ('/assets/../../source.mov', 404)):
                with self.assertRaises(urllib.error.HTTPError) as error: urllib.request.urlopen(base+path)
                self.assertEqual(error.exception.code, status)
            with self.assertRaises(urllib.error.HTTPError) as origin:
                urllib.request.urlopen(urllib.request.Request(base+'/jobs', headers={'Origin': 'http://foreign.test'}))
            self.assertEqual(origin.exception.code, 403)
            if (ASSETS / 'playback.mp4').exists():
                response = urllib.request.urlopen(urllib.request.Request(base+'/assets/scene-video', headers={'Range': 'bytes=0-99'}))
                self.assertEqual(response.status, 206)
                self.assertEqual(len(response.read()), 100)
                reference = urllib.request.urlopen(urllib.request.Request(base+'/assets/reference-video', headers={'Range':'bytes=0-99'}))
                self.assertEqual(reference.status, 206)
                self.assertEqual(len(reference.read()), 100)
            request = urllib.request.Request(base+'/jobs', data=json.dumps(command()).encode(), headers={'Content-Type': 'application/json'})
            job = json.load(urllib.request.urlopen(request))['data']
            self.assertEqual(finished(self.store, job['id'])['state'], 'completed')
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
