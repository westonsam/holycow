import hashlib
import json
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from .evidence import asset


class Conflict(Exception):
    pass


def uid():
    return uuid.uuid4().hex


class Store:
    def __init__(self, settings):
        self.settings = settings
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS alerts(
                    id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, event TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL, digest TEXT NOT NULL, recipient TEXT NOT NULL,
                    state TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS messages(
                    id TEXT PRIMARY KEY, alert TEXT, direction TEXT NOT NULL, kind TEXT NOT NULL,
                    body TEXT NOT NULL, recipient TEXT NOT NULL, transport TEXT NOT NULL,
                    state TEXT NOT NULL, provider_sid TEXT UNIQUE, attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt REAL NOT NULL, created REAL NOT NULL, error TEXT);
                CREATE TABLE IF NOT EXISTS inbox(
                    sid TEXT PRIMARY KEY, sender TEXT NOT NULL, body TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'queued', created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS feedback(
                    id TEXT PRIMARY KEY, alert TEXT NOT NULL, inbox_sid TEXT UNIQUE NOT NULL,
                    verdict TEXT NOT NULL, note TEXT NOT NULL, method TEXT NOT NULL,
                    agent_version TEXT NOT NULL, created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS pending(
                    sender TEXT NOT NULL, alert TEXT NOT NULL, verdict TEXT NOT NULL,
                    note TEXT NOT NULL, agent_version TEXT NOT NULL, expires REAL NOT NULL,
                    PRIMARY KEY(sender,alert));
                CREATE TABLE IF NOT EXISTS subscriptions(
                    recipient TEXT PRIMARY KEY, opted_out INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS delivery_events(
                    sid TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL,
                    UNIQUE(sid,state));
                CREATE TABLE IF NOT EXISTS runtime(key TEXT PRIMARY KEY, value REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS conversation(
                    sender TEXT PRIMARY KEY, alert TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS routing(
                    sender TEXT PRIMARY KEY, body TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS video_links(
                    token_hash TEXT PRIMARY KEY, asset TEXT NOT NULL, simulation INTEGER NOT NULL,
                    expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS telegram_offsets(
                    bot_id TEXT PRIMARY KEY, next_update INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS cow_lookup_context(
                    sender TEXT PRIMARY KEY, cow TEXT NOT NULL, expires REAL NOT NULL);
            ''')
            # Additive migration: preserve old messages and their original text.
            if 'reply_to' not in {r[1] for r in db.execute('PRAGMA table_info(inbox)')}:
                db.execute('ALTER TABLE inbox ADD COLUMN reply_to TEXT')
            if 'reply_explicit' not in {r[1] for r in db.execute('PRAGMA table_info(inbox)')}:
                db.execute('ALTER TABLE inbox ADD COLUMN reply_explicit INTEGER NOT NULL DEFAULT 0')
            if 'reply_sid' not in {r[1] for r in db.execute('PRAGMA table_info(messages)')}:
                db.execute('ALTER TABLE messages ADD COLUMN reply_sid TEXT')
            if 'sent_at' not in {r[1] for r in db.execute('PRAGMA table_info(messages)')}:
                db.execute('ALTER TABLE messages ADD COLUMN sent_at REAL')
            # A provider might already have accepted these. Never blindly resend.
            db.execute("UPDATE messages SET state='unknown', error='Service restarted during send; reconcile with provider before retrying.' WHERE state='sending'")
            db.execute("UPDATE alerts SET state='unknown' WHERE id IN (SELECT alert FROM messages WHERE kind='alert' AND state='unknown')")
            db.execute("UPDATE inbox SET state='queued' WHERE state='processing'")
            db.execute("DELETE FROM runtime WHERE key='telegram_heartbeat'")
            db.execute('''UPDATE messages SET alert=(SELECT alert FROM feedback WHERE inbox_sid=messages.provider_sid)
                          WHERE direction='incoming' AND alert IS NULL
                          AND EXISTS(SELECT 1 FROM feedback WHERE inbox_sid=messages.provider_sid)''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.settings.database, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def heartbeat(self):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO runtime VALUES ('heartbeat',?)", (time.time(),))

    def health(self):
        with self.connect() as db:
            row = db.execute("SELECT value FROM runtime WHERE key='heartbeat'").fetchone()
        healthy = bool(row and time.time()-row[0] < 30)
        mode = 'openai' if self.settings.uses_llm else 'local fallback'
        with self.connect() as db:
            telegram = db.execute("SELECT value FROM runtime WHERE key='telegram_heartbeat'").fetchone()
        return {'ready': healthy, 'transport': self.settings.transport, 'agent': mode,
                'telegramConfigured': bool(self.settings.telegram_token and self.settings.telegram_chat_id),
                'telegramReceiverReady': bool(telegram and time.time()-telegram[0] < 90),
                'telegramUpdates': self.settings.telegram_updates}

    def telegram_offset(self):
        with self.connect() as db:
            row = db.execute('SELECT next_update FROM telegram_offsets WHERE bot_id=?', (self.settings.telegram_token.split(':')[0],)).fetchone()
        return row[0] if row else 0

    def telegram_checkpoint(self, next_update):
        with self.connect() as db:
            db.execute('''INSERT INTO telegram_offsets VALUES (?,?) ON CONFLICT(bot_id)
                          DO UPDATE SET next_update=MAX(next_update,excluded.next_update)''',
                       (self.settings.telegram_token.split(':')[0], next_update))

    def telegram_heartbeat(self):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO runtime VALUES ('telegram_heartbeat',?)", (time.time(),))

    def outgoing(self, db, alert_id, recipient, body, kind='agent', transport=None, state='queued', reply_sid=None):
        message_id = uid()
        db.execute('''INSERT INTO messages(id,alert,direction,kind,body,recipient,transport,state,next_attempt,created,reply_sid)
                      VALUES (?,?,'outgoing',?,?,?,?,?,?,?,?)''',
                   (message_id, alert_id, kind, body, recipient, transport or self.settings.transport, state, time.time(), time.time(), reply_sid))
        return message_id

    def ingest(self, event, *, telegram_demo=False):
        if telegram_demo and not (event.source == 'simulation' and self.settings.transport == 'telegram'
                                  and self.settings.telegram_enabled and self.settings.recipient_opted_in):
            raise Conflict('Connect Telegram before sending a demo')
        payload = event.model_dump()
        if telegram_demo:
            payload['telegramDemo'] = True
        raw = json.dumps(payload, sort_keys=True)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT * FROM alerts WHERE event=?', (event.eventId,)).fetchone()
            if existing:
                if telegram_demo and json.loads(existing['payload']).get('telegramDemo'):
                    return self.alert(existing['id'])
                if existing['digest'] != digest:
                    raise Conflict('This event ID already has different content')
                return self.alert(existing['id'])
            if telegram_demo:
                recent = db.execute("SELECT created FROM alerts WHERE event LIKE 'telegram-demo:%' ORDER BY created DESC LIMIT 1").fetchone()
                if recent and time.time()-recent[0] < 30:
                    raise Conflict('Demo already requested. Wait 30 seconds before sending another')
                opted_out = db.execute('SELECT opted_out FROM subscriptions WHERE recipient=?', (self.settings.notification_recipient,)).fetchone()
                if opted_out and opted_out[0]:
                    raise Conflict('Notifications stopped. Send /start to the bot before requesting a demo')
            if event.source == 'live' and (event.identityBasis == 'synthetic' or event.locationBasis == 'synthetic'):
                raise Conflict('Live alerts require registered or human-verified identity and recorded or supplied location')
            if event.evidenceId:
                try:
                    asset(self.settings, event.evidenceId, simulation=event.source == 'simulation')
                except ValueError:
                    raise Conflict('Registered video unavailable or not appropriate for this alert')
            old = time.time()-datetime.fromisoformat(event.observedAt.replace('Z', '+00:00')).timestamp() > self.settings.alert_max_age
            state = 'suppressed' if event.severity != 'high' or old else 'queued'
            alert_id = uid()
            code = 'HC-'+secrets.token_hex(4).upper()
            while db.execute('SELECT 1 FROM alerts WHERE code=?', (code,)).fetchone():
                code = 'HC-'+secrets.token_hex(4).upper()
            # Only the dedicated, labeled Telegram demo action can send a sample.
            transport = 'telegram' if telegram_demo else 'simulator' if event.source == 'simulation' else self.settings.transport
            recipient = 'simulated-rancher' if transport == 'simulator' else self.settings.notification_recipient
            db.execute('INSERT INTO alerts VALUES (?,?,?,?,?,?,?,?)',
                       (alert_id, code, event.eventId, raw, digest, recipient, state, time.time()))
            video = 'unavailable'
            if event.evidenceId:
                token = secrets.token_urlsafe(24)
                db.execute('INSERT INTO video_links VALUES (?,?,?,?)',
                           (hashlib.sha256(token.encode()).hexdigest(), event.evidenceId, int(event.source == 'simulation'), time.time()+86400))
                origin = self.settings.public_url or 'http://127.0.0.1:8870'
                video = f'{origin}/v/{token}'
            reason = event.summary if len(event.summary) <= 140 else event.summary[:137].rsplit(' ', 1)[0]+'…'
            body = f'Cow {event.cowNumber}\nReason: {reason}\nLocation: {event.location}\nVideo: {video}'
            self.outgoing(db, alert_id, recipient, body, kind='alert', transport=transport, state=state)
        return self.alert(alert_id)

    def video(self, token):
        if not re.fullmatch(r'[A-Za-z0-9_-]{32}', token):
            raise KeyError('Video not found')
        with self.connect() as db:
            row = db.execute('SELECT * FROM video_links WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not row:
            raise KeyError('Video not found')
        if row['expires'] <= time.time():
            raise TimeoutError('Video link expired')
        return asset(self.settings, row['asset'], simulation=bool(row['simulation']))

    def alert(self, alert_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone()
            if row is None:
                raise KeyError('Alert not found')
            feedback = [dict(r) for r in db.execute('SELECT verdict,note,method,agent_version,created FROM feedback WHERE alert=? ORDER BY created,rowid', (alert_id,))]
        return {'id': row['id'], 'code': row['code'], **json.loads(row['payload']), 'state': row['state'], 'created': row['created'], 'feedback': feedback}

    def snapshot(self):
        with self.connect() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM alerts ORDER BY created DESC LIMIT 100')]
            messages = [dict(r) for r in db.execute('''SELECT id,alert,direction,kind,body,transport,state,attempts,created,error
                                                       FROM messages ORDER BY created DESC,rowid DESC LIMIT 1000''')][::-1]
        return {'health': self.health(), 'alerts': [self.alert(i) for i in ids], 'messages': messages}

    def receive(self, sid, sender, body, reply_to=None):
        reply_explicit = bool(reply_to)
        if sender not in (self.settings.notification_recipient, 'simulated-rancher'):
            raise PermissionError('Unknown sender')
        if not 1 <= len(body.strip()) <= 1600:
            raise ValueError('Reply must be 1–1600 characters')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT sender,body,reply_to FROM inbox WHERE sid=?', (sid,)).fetchone()
            if existing:
                if existing['sender'] != sender or existing['body'] != body or (reply_to is not None and existing['reply_to'] != reply_to):
                    raise Conflict('Message ID reused with different content')
                return {'received': True, 'duplicate': True}
            reply_alert = None
            if reply_to:
                target = db.execute("SELECT alert FROM messages WHERE id=? AND recipient=? AND direction='outgoing'", (reply_to, sender)).fetchone()
                if not target:
                    raise ValueError('Reply context is not a message in this conversation')
                reply_alert = target['alert']
            else:
                # SMS has one conversation per sender. Snapshot the last message
                # actually sent, rather than the newest queued alert or future sends.
                previous = db.execute("""SELECT id,alert FROM messages WHERE recipient=? AND direction='outgoing'
                    AND alert IS NOT NULL AND state IN ('accepted','sent','delivered','simulated')
                    AND sent_at>? ORDER BY sent_at DESC,rowid DESC LIMIT 1""", (sender, time.time()-1800)).fetchone()
                reply_to = previous['id'] if previous else None
                reply_alert = previous['alert'] if previous else None
            db.execute('INSERT INTO inbox(sid,sender,body,created,reply_to,reply_explicit) VALUES (?,?,?,?,?,?)', (sid, sender, body, time.time(), reply_to, int(reply_explicit)))
            db.execute('''INSERT INTO messages(id,alert,direction,kind,body,recipient,transport,state,provider_sid,next_attempt,created)
                          VALUES (?,?,'incoming','feedback',?,?,?,'received',?,?,?)''',
                       (uid(), reply_alert, body, sender, self.sender_transport(sender), sid, time.time(), time.time()))
        return {'received': True, 'duplicate': False}

    def claim_inbox(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT * FROM inbox WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
            if row:
                db.execute("UPDATE inbox SET state='processing' WHERE sid=?", (row['sid'],))
        return dict(row) if row else None

    def process_inbox(self, incoming, agent):
        sender, body, sid = incoming['sender'], incoming['body'].strip(), incoming['sid']
        control = body.upper()
        if control.startswith('/'):
            control = control.split()[0].split('@')[0][1:]
        controls = ('STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT', 'START')
        if control not in controls:
            from .cow_lookup import answer
            with self.connect() as db:
                lookup_context = db.execute('SELECT cow FROM cow_lookup_context WHERE sender=? AND expires>?', (sender, time.time())).fetchone()
                quoted = db.execute('SELECT alert FROM messages WHERE id=? AND recipient=?', (incoming.get('reply_to'), sender)).fetchone()
                quoted_alert = db.execute('SELECT payload FROM alerts WHERE id=? AND recipient=?', (quoted['alert'], sender)).fetchone() if quoted and quoted['alert'] else None
            context_cow = lookup_context['cow'] if lookup_context else None
            if incoming.get('reply_explicit') and quoted_alert:
                context_cow = None
            response = answer(body, context_cow,
                              json.loads(quoted_alert['payload'])['cowNumber'] if quoted_alert else None)
            if response:
                reply, cow = response
                return self.finish_inbox(incoming, None, reply, lookup_cow=cow)
            if incoming.get('reply_explicit') and quoted and not quoted['alert']:
                return self.finish_inbox(incoming, None,
                    'Ask me for another cow\'s score or location. To review an alert, reply directly to its video or feedback question.')
        # Untrusted text never gets database, network, model-training or sending tools.
        refs = list(dict.fromkeys(re.findall(r'\bHC-[A-F0-9]{8}\b', body.upper())))
        with self.connect() as db:
            rows = db.execute('SELECT * FROM alerts WHERE recipient=? AND state!=? ORDER BY created DESC', (sender, 'suppressed')).fetchall()
            previous = db.execute("SELECT alert FROM messages WHERE id=? AND recipient=? AND direction='outgoing'", (incoming.get('reply_to'), sender)).fetchone()
        preceding = next((r for r in rows if previous and r['id'] == previous['alert']), None)
        row = next((r for r in rows if len(refs) == 1 and r['code'] == refs[0]), None)
        if not refs and len(rows) == 1:
            row = rows[0]
        if not refs and len(rows) > 1 and control not in ('STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT', 'START'):
            named = [r for r in rows if re.search(r'(?<!\w)'+re.escape(json.loads(r['payload'])['cowNumber'])+r'(?!\w)', body, re.I)]
            if len(named) == 1:
                row = named[0]
            elif len(named) > 1:
                if preceding and preceding['id'] in {r['id'] for r in named}:
                    row = preceding
                else:
                    candidates = [{'id': r['id'], **{k: json.loads(r['payload'])[k] for k in ('cowNumber', 'location', 'summary')}} for r in named[:20]]
                    try:
                        chosen = agent.choose_alert(body, candidates)
                        if isinstance(chosen, str):
                            row = next((r for r in named[:20] if r['id'] == chosen), None)
                    except Exception:
                        pass
            elif not named:
                with self.connect() as db:
                    context = db.execute('SELECT * FROM conversation WHERE sender=? AND expires>?', (sender, time.time())).fetchone()
                if preceding:
                    row = preceding
                elif context and not any(r['created'] > context['expires']-1800 for r in rows):
                    row = next((r for r in rows if r['id'] == context['alert']), None)
                if row is None:
                    candidates = [{'id': r['id'], **{k: json.loads(r['payload'])[k] for k in ('cowNumber', 'location', 'summary')}} for r in rows[:20]]
                    try:
                        chosen = agent.choose_alert(body, candidates)
                        if isinstance(chosen, str):
                            row = next((r for r in rows[:20] if r['id'] == chosen), None)
                    except Exception:
                        pass
        # Global opt-out is deterministic and takes precedence over agent interpretation.
        if control in ('STOP', 'STOPALL', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT', 'START'):
            stopped = control != 'START'
            with self.connect() as db:
                db.execute('INSERT OR REPLACE INTO subscriptions VALUES (?,?)', (sender, int(stopped)))
                if stopped:
                    db.execute("UPDATE messages SET state='suppressed' WHERE recipient=? AND state='queued'", (sender,))
                    db.execute("UPDATE alerts SET state='suppressed' WHERE state='queued' AND id IN (SELECT alert FROM messages WHERE recipient=? AND state='suppressed')", (sender,))
                    db.execute('DELETE FROM pending WHERE sender=?', (sender,))
                    db.execute('DELETE FROM conversation WHERE sender=?', (sender,))
                    db.execute('DELETE FROM routing WHERE sender=?', (sender,))
                    db.execute('DELETE FROM cow_lookup_context WHERE sender=?', (sender,))
                db.execute("UPDATE inbox SET state='done' WHERE sid=?", (sid,))
                # Twilio handles STOP/START acknowledgments itself; no duplicate opt-out reply.
                if sender == 'simulated-rancher':
                    self.outgoing(db, None, sender, 'Notifications stopped.' if stopped else 'Notifications resumed.', transport='simulator', state='simulated')
                elif sender.startswith('telegram:'):
                    self.outgoing(db, None, sender, 'Notifications stopped.' if stopped else 'HolyCow connected. Alerts will appear here.', kind='subscription', transport='telegram')
            return
        if not row:
            options = '; '.join(f"cow {json.loads(r['payload'])['cowNumber']} at {json.loads(r['payload'])['location']}" for r in rows[:3])
            with self.connect() as db:
                db.execute('INSERT OR REPLACE INTO routing VALUES (?,?,?)', (sender, body, time.time()+1800))
            return self.finish_inbox(incoming, None,
                f'Which animal do you mean? {options}. You can reply with the cow number or describe the location.' if options else
                'I could not find an alert for you. Tell the ranch manager which animal needs checking.')
        alert = json.loads(row['payload'])
        text = re.sub(r'\bHC-[A-F0-9]{8}\b', '', body, flags=re.I).strip(' :,-')
        with self.connect() as db:
            routing = db.execute('SELECT * FROM routing WHERE sender=? AND expires>?', (sender, time.time())).fetchone()
            history = [dict(r) for r in db.execute('''SELECT direction,body FROM messages WHERE recipient=? AND alert=?
                ORDER BY created DESC,rowid DESC LIMIT 8''', (sender, row['id']))][::-1]
        # A number-only answer to "which cow?" completes the previous feedback.
        if routing and (not text or text.lower() in (alert['cowNumber'].lower(), 'cow '+alert['cowNumber'].lower())):
            text = re.sub(r'\bHC-[A-F0-9]{8}\b', '', routing['body'], flags=re.I).strip(' :,-')
            body = routing['body']+'\nAnimal clarified: '+body
        alert['_history'] = history
        command = re.fullmatch(r'(VALID|FALSE|UNSURE)(?:\s+(.+))?', text, flags=re.I | re.S)
        verdict, note, method, version = None, body, 'command', 'commands-v1'
        draft = None
        if command:
            verdict = {'VALID': 'valid', 'FALSE': 'false_positive', 'UNSURE': 'uncertain'}[command[1].upper()]
            note = command[2] or body
        elif re.sub(r'[^\w\s👍]', '', text.lower().replace('’', "'")).strip() in ('yes', 'yep', 'yeah', 'yup', 'correct', 'right', 'thats right', 'thats correct', 'that is right', 'yes thanks', 'yep thanks', 'yes please', 'sounds right', 'sounds good', 'confirm', '👍'):
            with self.connect() as db:
                pending = db.execute('SELECT * FROM pending WHERE sender=? AND alert=? AND expires>?', (sender, row['id'], time.time())).fetchone()
            if pending:
                verdict, note, method, version = pending['verdict'], pending['note'], 'agent_confirmed', pending['agent_version']
        else:
            try:
                draft = agent.interpret(text, alert)
                if draft.verdict != 'clarify':
                    version = 'feedback-v2/'+self.settings.openai_model if self.settings.uses_llm else 'local-phrases-v1'
            except Exception:
                from .feedback_agent import FeedbackAgent
                draft = FeedbackAgent.local_interpret(text)
                version = 'local-phrases-v1'
        if verdict:
            outcome = {'valid': 'you saw the problem', 'false_positive': 'the alert was a false alarm', 'uncertain': 'you are not sure yet'}[verdict]
            reply = f"Thanks. For cow {alert['cowNumber']}, I recorded that {outcome}. You can text me again if anything changes."
        elif draft and draft.verdict != 'clarify':
            reply = f"For cow {alert['cowNumber']} at {alert['location']}: {draft.explanation} Is that right? Just reply yes, or tell me what I got wrong."
        else:
            question = draft.explanation if draft and draft.verdict == 'clarify' else 'Did you see the problem, was the animal okay, or are you not sure yet?'
            if text.lower().strip(' .!') in ('no', 'nope', 'not quite', 'wrong'):
                question = 'No problem. What did you see instead?'
            reply = f"For cow {alert['cowNumber']}: {question}"
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT state FROM inbox WHERE sid=?', (sid,)).fetchone()[0] == 'done':
                return
            db.execute('UPDATE messages SET alert=? WHERE provider_sid=?', (row['id'], sid))
            db.execute('DELETE FROM routing WHERE sender=?', (sender,))
            if verdict:
                db.execute('INSERT INTO feedback VALUES (?,?,?,?,?,?,?,?)', (uid(), row['id'], sid, verdict, note, method, version, time.time()))
                db.execute('DELETE FROM pending WHERE sender=? AND alert=?', (sender, row['id']))
                db.execute('DELETE FROM conversation WHERE sender=?', (sender,))
            elif draft and draft.verdict != 'clarify':
                db.execute('INSERT OR REPLACE INTO pending VALUES (?,?,?,?,?,?)', (sender, row['id'], draft.verdict, body, version, time.time()+1800))
            else:
                db.execute('DELETE FROM pending WHERE sender=? AND alert=?', (sender, row['id']))
            if not verdict:
                db.execute('INSERT OR REPLACE INTO conversation VALUES (?,?,?)', (sender, row['id'], time.time()+1800))
            self.outgoing(db, row['id'], sender, reply, transport=self.sender_transport(sender))
            db.execute("UPDATE inbox SET state='done' WHERE sid=?", (sid,))

    def finish_inbox(self, incoming, alert_id, reply, lookup_cow=None):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT state FROM inbox WHERE sid=?', (incoming['sid'],)).fetchone()[0] == 'done':
                return
            if lookup_cow is not None:
                db.execute('INSERT OR REPLACE INTO cow_lookup_context VALUES (?,?,?)', (incoming['sender'], lookup_cow, time.time()+1800))
                db.execute("UPDATE messages SET alert=NULL,kind='lookup' WHERE provider_sid=? AND direction='incoming'", (incoming['sid'],))
            self.outgoing(db, alert_id, incoming['sender'], reply, transport=self.sender_transport(incoming['sender']), reply_sid=incoming['sid'])
            db.execute("UPDATE inbox SET state='done' WHERE sid=?", (incoming['sid'],))

    def claim_message(self):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Opt-out applies to all queued messages, including agent replies.
            db.execute("""UPDATE messages SET state='suppressed' WHERE state='queued' AND kind!='subscription' AND recipient IN
                          (SELECT recipient FROM subscriptions WHERE opted_out=1)""")
            db.execute("UPDATE alerts SET state='suppressed' WHERE state='queued' AND id IN (SELECT alert FROM messages WHERE state='suppressed')")
            row = db.execute("SELECT * FROM messages WHERE direction='outgoing' AND state='queued' AND next_attempt<=? ORDER BY CASE WHEN kind='agent' THEN 0 ELSE 1 END,created,rowid LIMIT 1", (time.time(),)).fetchone()
            if row:
                if row['kind'] == 'alert':
                    payload = json.loads(db.execute('SELECT payload FROM alerts WHERE id=?', (row['alert'],)).fetchone()[0])
                    observed = datetime.fromisoformat(payload['observedAt'].replace('Z', '+00:00')).timestamp()
                    if time.time()-observed > self.settings.alert_max_age:
                        db.execute("UPDATE messages SET state='suppressed', error='Observation expired before dispatch' WHERE id=?", (row['id'],))
                        db.execute("UPDATE alerts SET state='suppressed' WHERE id=?", (row['alert'],))
                        return None
                db.execute("UPDATE messages SET state='sending',attempts=attempts+1 WHERE id=?", (row['id'],))
        return dict(row) if row else None

    @staticmethod
    def sender_transport(sender):
        return 'simulator' if sender == 'simulated-rancher' else 'telegram' if sender.startswith('telegram:') else 'twilio'

    def sent(self, message, state, sid=None, error=None, retry=False):
        with self.connect() as db:
            current = db.execute('SELECT state FROM messages WHERE id=?', (message['id'],)).fetchone()
            # A status callback may have arrived before the API response.
            if current and current[0] not in ('delivered', 'failed', 'undelivered'):
                db.execute('UPDATE messages SET state=?,provider_sid=COALESCE(?,provider_sid),error=?,next_attempt=? WHERE id=?',
                           ('queued' if retry else state, sid, error, time.time()+min(300, 2**(message['attempts']+1)), message['id']))
            if state in ('accepted', 'sent', 'delivered', 'simulated') and not retry:
                db.execute('UPDATE messages SET sent_at=COALESCE(sent_at,?) WHERE id=?', (time.time(), message['id']))
            if message['alert'] and message['kind'] == 'alert':
                actual = db.execute('SELECT state FROM messages WHERE id=?', (message['id'],)).fetchone()[0]
                db.execute('UPDATE alerts SET state=? WHERE id=?', (actual, message['alert']))

    def delivery_status(self, message_id, sid, state):
        ranks = {'sending': 0, 'unknown': 0, 'accepted': 1, 'queued': 1, 'sent': 2, 'delivered': 3, 'failed': 3, 'undelivered': 3}
        if state not in ranks or state in ('sending', 'unknown'):
            raise ValueError('Unsupported provider state')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM messages WHERE id=?', (message_id,)).fetchone()
            if not row or row['transport'] != 'twilio' or (row['provider_sid'] and row['provider_sid'] != sid):
                raise KeyError('Provider message not found')
            db.execute('INSERT OR IGNORE INTO delivery_events VALUES (?,?,?)', (sid, state, time.time()))
            if ranks.get(row['state'], -1) < 3 and ranks[state] >= ranks.get(row['state'], -1):
                db.execute('UPDATE messages SET state=?,provider_sid=? WHERE id=?', (state, sid, message_id))
                if state in ('accepted', 'sent', 'delivered'):
                    db.execute('UPDATE messages SET sent_at=COALESCE(sent_at,?) WHERE id=?', (time.time(), message_id))
                if row['kind'] == 'alert':
                    db.execute('UPDATE alerts SET state=? WHERE id=?', (state, row['alert']))

    def training_candidates(self):
        with self.connect() as db:
            rows = db.execute('''SELECT a.payload,a.code,f.verdict,f.note,f.method,f.agent_version,f.created
                                 FROM feedback f JOIN alerts a ON a.id=f.alert ORDER BY f.created,f.rowid''').fetchall()
        return [{**json.loads(r['payload']), 'alertCode': r['code'], 'feedback': r['verdict'], 'reviewerNote': r['note'],
                 'feedbackMethod': r['method'], 'agentVersion': r['agent_version'], 'reviewedAt': r['created'],
                 'eligibleForTraining': False, 'requiresIndependentReview': True} for r in rows]
