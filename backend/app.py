"""Private control API plus signed, public Twilio webhooks. One process per volume."""
import hmac
import json
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from urllib.parse import parse_qsl
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from .evidence import asset
from starlette.datastructures import FormData
from twilio.request_validator import RequestValidator
from .config import Settings
from .delivery import Worker
from .models import AlertInput, SimulateReply, TelegramDemo
from .store import Conflict, Store
from .telegram_transport import TelegramReceiver


def create_app(settings=None, start_worker=True):
    settings = settings or Settings.from_env()
    settings.validate()
    store = Store(settings)
    worker = Worker(store)
    receiver = TelegramReceiver(store) if settings.transport == 'telegram' else None

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            worker.start()
            if receiver and settings.telegram_updates == 'polling':
                receiver.start()
        yield
        if start_worker:
            if receiver:
                receiver.stop.set()
            worker.close()
            if receiver and settings.telegram_updates == 'polling':
                receiver.close()

    app = FastAPI(title='HolyCow notification backend', docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)
    app.state.store, app.state.worker = store, worker
    app.state.telegram_receiver = receiver

    @app.exception_handler(RequestValidationError)
    async def invalid_payload(request, error):
        # Pydantic's default includes raw input; do not reflect phone/message text.
        return JSONResponse({'error': {'message': 'Invalid notification request. Check required fields and limits.'}}, status_code=422)

    @app.exception_handler(Conflict)
    async def conflict(request, error):
        return JSONResponse({'error': {'message': str(error)}}, status_code=409)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return JSONResponse({'error': {'message': str(error.detail)}}, status_code=error.status_code)

    @app.middleware('http')
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    def authorized(request: Request):
        provided = request.headers.get('authorization', '')
        if not hmac.compare_digest(provided.encode(), ('Bearer '+settings.api_token).encode()):
            raise HTTPException(401, 'Backend authentication required')

    async def json_body(request, model):
        if not request.headers.get('content-type', '').startswith('application/json'):
            raise HTTPException(415, 'JSON required')
        raw = await limited_body(request)
        try:
            return model.model_validate(json.loads(raw))
        except Exception:
            raise HTTPException(422, 'Invalid request fields or values')

    @app.get('/healthz')
    def health():
        status = store.health()
        return JSONResponse(status, status_code=200 if status['ready'] else 503)

    @app.get('/v/{token}')
    def video(token: str):
        try:
            path = store.video(token)
        except TimeoutError:
            raise HTTPException(410, 'Video link expired. Request a fresh link from the ranch manager.')
        except (KeyError, ValueError):
            raise HTTPException(404, 'Video unavailable')
        return FileResponse(path, media_type='video/mp4', headers={'Content-Disposition': 'inline', 'Referrer-Policy': 'no-referrer'})

    @app.get('/v1/notifications', dependencies=[Depends(authorized)])
    def notifications():
        return {'data': store.snapshot()}

    @app.post('/v1/alerts', dependencies=[Depends(authorized)])
    async def alerts(request: Request):
        event = await json_body(request, AlertInput)
        return {'data': store.ingest(event)}

    @app.post('/v1/sample', dependencies=[Depends(authorized)])
    async def sample(request: Request):
        raw = await limited_body(request)
        if raw != b'{}':
            raise HTTPException(400, 'Sample accepts an empty JSON object')
        evidence_id = None
        try:
            asset(settings, 'demo-scene', simulation=True)
            evidence_id = 'demo-scene'
        except ValueError:
            pass
        event = AlertInput(eventId='simulation-'+uuid4().hex, source='simulation', severity='high',
                           cowNumber='718', identityBasis='synthetic',
                           location='Demo north pasture, Netherlands (illustrative)', locationBasis='synthetic',
                           summary='Movement needs review.',
                           observedAt=datetime.now(timezone.utc).isoformat(), modelVersion='synthetic-alert-demo-v1', evidenceId=evidence_id)
        return {'data': store.ingest(event)}

    @app.post('/v1/simulate-reply', dependencies=[Depends(authorized)])
    async def simulate(request: Request):
        command = await json_body(request, SimulateReply)
        try:
            receipt = store.receive('SIM-IN-'+command.messageId, 'simulated-rancher', command.body, command.replyToMessageId)
        except ValueError:
            raise HTTPException(422, 'Invalid reply context')
        return {'data': receipt}

    @app.post('/v1/telegram-demo', dependencies=[Depends(authorized)])
    async def telegram_demo(request: Request):
        command = await json_body(request, TelegramDemo)
        if settings.transport != 'telegram' or not settings.telegram_enabled or not settings.recipient_opted_in:
            raise HTTPException(409, 'Connect Telegram before sending a demo')
        try:
            asset(settings, 'demo-scene', simulation=True)
        except ValueError:
            raise HTTPException(409, 'Demo video unavailable. Prepare it with python -m backend.prepare_demo_video')
        event = AlertInput(eventId='telegram-demo:'+command.requestId, source='simulation', severity='high',
                           cowNumber='718', identityBasis='synthetic',
                           location='Demo pasture, Netherlands', locationBasis='synthetic',
                           summary='DEMO ONLY: Movement flagged for review.',
                           observedAt=datetime.now(timezone.utc).isoformat(), modelVersion='synthetic-telegram-demo-v1', evidenceId='demo-scene')
        return {'data': store.ingest(event, telegram_demo=True)}

    @app.get('/v1/training-candidates', dependencies=[Depends(authorized)])
    def candidates():
        return {'data': store.training_candidates()}

    @app.post('/webhooks/telegram')
    async def telegram_webhook(request: Request):
        if not receiver or settings.telegram_updates != 'webhook':
            raise HTTPException(503, 'Telegram webhook mode is not enabled')
        provided = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if not hmac.compare_digest(provided.encode(), settings.telegram_webhook_secret.encode()):
            raise HTTPException(403, 'Invalid Telegram webhook secret')
        if not request.headers.get('content-type', '').startswith('application/json'):
            raise HTTPException(415, 'JSON required')
        try:
            update = json.loads(await limited_body(request))
            receiver.accept(update)
            store.telegram_heartbeat()
        except (ValueError, TypeError):
            raise HTTPException(400, 'Invalid Telegram update')
        return {'ok': True}

    async def signed_form(request):
        if settings.transport != 'twilio':
            raise HTTPException(503, 'Twilio transport is not enabled')
        if not request.headers.get('content-type', '').startswith('application/x-www-form-urlencoded'):
            raise HTTPException(415, 'Form payload required')
        raw = await limited_body(request)
        try:
            form = FormData(parse_qsl(raw.decode('utf-8'), keep_blank_values=True, max_num_fields=100))
        except (ValueError, UnicodeError):
            raise HTTPException(400, 'Invalid webhook payload')
        query = ('?'+request.url.query) if request.url.query else ''
        url = settings.public_url+request.url.path+query
        if not RequestValidator(settings.twilio_token).validate(url, form, request.headers.get('X-Twilio-Signature', '')):
            raise HTTPException(403, 'Invalid webhook signature')
        if form.get('AccountSid') != settings.twilio_sid:
            raise HTTPException(403, 'Unknown provider account')
        return form

    @app.post('/webhooks/twilio/inbound')
    async def inbound(request: Request):
        form = await signed_form(request)
        sid = form.get('MessageSid', '')
        if not re.fullmatch(r'SM[a-fA-F0-9]{32}', sid):
            raise HTTPException(400, 'Invalid provider message ID')
        if form.get('To') != settings.twilio_number or form.get('From') != settings.recipient:
            raise HTTPException(403, 'Unknown sender or destination')
        try:
            store.receive(sid, form['From'], form.get('Body', ''))
        except (ValueError, PermissionError):
            raise HTTPException(400, 'Invalid inbound message')
        # Agent replies are queued durably and sent by the worker, not in webhook latency.
        return Response('<Response/>', media_type='application/xml')

    @app.post('/webhooks/twilio/status/{message_id}')
    async def delivery(message_id: str, request: Request):
        form = await signed_form(request)
        if not re.fullmatch(r'[a-f0-9]{32}', message_id) or not re.fullmatch(r'SM[a-fA-F0-9]{32}', form.get('MessageSid', '')):
            raise HTTPException(400, 'Invalid message ID')
        try:
            store.delivery_status(message_id, form['MessageSid'], form.get('MessageStatus', ''))
        except KeyError:
            raise HTTPException(404, 'Message not found')
        except ValueError:
            raise HTTPException(400, 'Invalid delivery status')
        return Response(status_code=204)

    return app


async def limited_body(request):
    result = bytearray()
    async for chunk in request.stream():
        result.extend(chunk)
        if len(result) > 16384:
            raise HTTPException(413, 'Request too large')
    return bytes(result)
