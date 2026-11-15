"""Requires psycopg 3; admin DSN for DISPOSABLE fixture DB via CATTLE_TEST_DSN.
Tests actual competing transactions, not sequential ON CONFLICT calls.
Run after fixture.sql. Retry winner commits a fixture drone, removed in finally;
identity edits roll back. No remote default connection.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
import psycopg

DSN = os.environ['CATTLE_TEST_DSN']
ORG = '00000000-0000-0000-0000-000000000001'
ready, attempted = Event(), Event()
waiting_pid = {}

def assert_blocked():
    deadline = monotonic() + 5
    with psycopg.connect(DSN, autocommit=True) as observer:
        while monotonic() < deadline:
            row = observer.execute('SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s',
                                   (waiting_pid['pid'],)).fetchone()
            if row and row[0] == 'Lock':
                return
            sleep(0.02)
    raise AssertionError('second transaction never blocked on first')

def first(sql, args):
    with psycopg.connect(DSN) as conn:
        conn.execute('SET LOCAL ROLE cattle_worker')
        conn.execute("SELECT set_config('app.org_id',%s,true)", (ORG,))
        conn.execute(sql, args)
        ready.set()
        assert attempted.wait(5), 'second transaction did not attempt insert'
        assert_blocked()
        # Commit for uniqueness conflict; cleanup in finally below.
        conn.commit()

def second(sql, args):
    assert ready.wait(5)
    with psycopg.connect(DSN) as conn:
        conn.execute('SET LOCAL ROLE cattle_worker')
        conn.execute("SELECT set_config('app.org_id',%s,true)", (ORG,))
        conn.execute("SET LOCAL statement_timeout='10s'")
        waiting_pid['pid'] = conn.info.backend_pid
        attempted.set()
        row = conn.execute(sql, args).fetchone()
        assert row is None, 'retry unexpectedly created a duplicate'
        conn.rollback()

sql = '''INSERT INTO cattle.drone(org_id,source_key,name) VALUES(%s,'concurrency-fixture','test')
ON CONFLICT(org_id,source_key) DO NOTHING RETURNING id'''
try:
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(first, sql, (ORG,)), pool.submit(second, sql, (ORG,))]
        for future in futures:
            future.result(timeout=20)
    # Competing identity edits: first holds unique successor, then aborts;
    # second must wait, then succeed. Both roll back, preserving fixture.
    ready.clear(); attempted.clear()
    edit = '''INSERT INTO cattle.identity_decision(org_id,track_id,supersedes,animal_id,
decision,method_version,actor,reason) VALUES(%s,
'00000000-0000-0000-0000-000000000100','00000000-0000-0000-0000-000000000111',
'00000000-0000-0000-0000-000000000020','accepted','test','concurrency-test','test') RETURNING id'''
    def correction(leader):
        with psycopg.connect(DSN) as conn:
            conn.execute('SET LOCAL ROLE cattle_reviewer')
            conn.execute("SELECT set_config('app.org_id',%s,true)", (ORG,))
            conn.execute("SET LOCAL statement_timeout='10s'")
            if not leader:
                assert ready.wait(5)
                waiting_pid['pid'] = conn.info.backend_pid
                attempted.set()
            row = conn.execute(edit, (ORG,)).fetchone()
            assert row
            if leader:
                ready.set()
                assert attempted.wait(5)
                assert_blocked()
            conn.rollback()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(correction, True),pool.submit(correction, False)]
        for future in futures:
            future.result(timeout=20)
    print('Concurrent retry and identity-successor serialization passed.')
finally:
    # Migration admin only, fixture-only key; no evidence rows reference this drone.
    with psycopg.connect(DSN) as conn:
        conn.execute("SELECT set_config('app.org_id',%s,true)", (ORG,))
        conn.execute("DELETE FROM cattle.drone WHERE org_id=%s AND source_key='concurrency-fixture'",(ORG,))
