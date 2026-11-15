# HolyCow alert delivery and rancher feedback

For the public presentation dashboard with an on-demand laptop backend, see
[HOSTING.md](../HOSTING.md). Its authenticated gateway enables only the shared
demo controls while the launcher is running. The direct backend and ingestion
API remain private; this does not add production rancher authentication.

**Use Telegram for live messaging:** [connect a Telegram bot](TELEGRAM.md). The
backend supports direct video uploads, native replies, durable long polling and
optional authenticated webhooks. No Twilio account or Codex connector is needed.
The existing Twilio section below documents the optional legacy SMS adapter.

This service is independent of the dashboard and the scene inference process.
It owns a SQLite outbox, inbox, immutable alert snapshots, delivery events,
conversation drafts and confirmed feedback. A background worker drains its
queues even with no browser connected. Docker supplies process supervision and
a persistent volume. Hosting is intentionally deferred; running this on a laptop
does **not** keep it available when that laptop is off.

## What is connected

- **Notifications** in the existing dashboard is a local operator console. It
  shows backend health, alert context/status, a Telegram demo-send action, saved
  feedback and a training-review export.
- Authenticated ingestion accepts high/medium/low severity events. Only fresh
  **high** severity observations queue notifications. The default freshness
  window is one hour, checked at ingestion and again at dispatch. Older and
  lower-severity events remain visible as suppressed. Reusing an event ID with
  identical content returns the existing alert; different content returns 409.
- Alert texts contain only **cow tag, reason, location and video link**. Reasons
  are limited to 140 characters in text; the full summary stays in SQLite.
  Observation times, alert codes, model versions, severity, confidence and
  delivery metadata stay in the backend. No extra instructions or diagnostic
  boilerplate are appended to the alert text. Videos open through an opaque,
  expiring link; MMS attachments are not implemented.
- Ordinary simulator messages never leave this service. Even with Twilio enabled,
  `source: simulation` is forced to the simulator and labeled in the operator UI,
  outside the text body. The dedicated Telegram demo action is an explicitly
  labeled exception, with fixed sample fields, duplicate protection and a 30-second
  cooldown. Its original events and feedback remain synthetic. The dashboard
  has no internal chat; ranchers reply in Telegram. See [TELEGRAM.md](TELEGRAM.md).
  Samples do not identify cows in the Netherlands stock clip or turn its
  geometric tracks into registered animal identities.
- The bundled model does not produce health severity, verified cattle identity
  or georeferenced locations. A future trusted detector/ingestion adapter must
  supply those fields; live events reject synthetic identity/location provenance.
  The service records provenance assertions from that trusted producer; it does
  not itself verify registry membership or GPS accuracy.
- Existing fictional alerts and the flight demo SQLite database are unchanged.
  Their reset controls do not clear messaging history.

## Local setup

From `holycow_git`, Python 3.11+:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.lock
Copy-Item backend/.env.example backend/.env
backend/.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the generated random secret in `HOLYCOW_NOTIFICATIONS_TOKEN` inside
`backend/.env`. Keep `HOLYCOW_MESSAGING_TRANSPORT=simulator` and
`HOLYCOW_FEEDBACK_AGENT=auto` for an offline demo with a limited phrase fallback. A configured local
environment file already exists in this workspace and is ignored by Git.
Never paste provider credentials into browser fields or commit environment files.

Terminal 1, repository root:

```powershell
backend/.venv/Scripts/python.exe -m backend.run
```

Terminal 2, repository root (stop any old web server before rebuilding):

```powershell
npm --prefix web run build
backend/.venv/Scripts/python.exe -m backend.configure_web
cd web
npm start -- --port 8790
```

Open [HolyCow](http://127.0.0.1:8790) → **Notifications** → Create simulated
high-severity alert. The backend binds to loopback port 8870. `configure_web`
copies only the server-side backend URL/token and existing flight-demo URL into
ignored `web/dist/server/.dev.vars`; rerun it after each build. It never copies
Twilio or OpenAI credentials to the Worker. The flight service is still started
separately using [DEMO.md](../DEMO.md).

## Docker deployment package

With Docker Engine and Compose installed, from the repository root:

```sh
docker compose -f backend/compose.yaml build
docker compose -f backend/compose.yaml up -d
docker compose -f backend/compose.yaml ps
docker compose -f backend/compose.yaml logs --tail 50 notifications
```

Create `backend/.env` first as above. The image runs as UID 10001, drops Linux
capabilities, uses a read-only root filesystem and stores all durable state in
the named `notification-data` volume at `/data`. `restart: unless-stopped`
restarts the service after process/host restarts when Docker starts. The worker
heartbeat and `/healthz` support external monitoring. Compose health checks
report unhealthy status; they do not by themselves restart unhealthy containers.

Run **one service replica and one Uvicorn worker per volume**. Keep the host
port bound to loopback. When choosing hosting, use a persistent-volume host that
does not sleep and put a TLS reverse proxy in front of it. Give it a stable HTTPS
origin for Twilio callbacks. Do not use ephemeral or horizontally replicated
SQLite deployments. This package is not yet deployed to an internet host.

Back up SQLite with the SQLite backup API or a consistent volume snapshot;
copying only the main database while WAL writes are active is not a valid backup.
`docker compose down` preserves the volume; `down -v` destroys its history.

## Legacy optional Twilio SMS

Set server-side values in `backend/.env`:

```dotenv
HOLYCOW_MESSAGING_TRANSPORT=twilio
HOLYCOW_LIVE_SMS_ENABLED=true
HOLYCOW_RECIPIENT_OPTED_IN=true
HOLYCOW_RANCHER_PHONE=+15555550101
HOLYCOW_PUBLIC_BACKEND_URL=https://notifications.your-domain.example
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_FROM_NUMBER=your-two-way-sms-number
```

The example phone numbers are placeholders. Configure a real, opted-in recipient
and a two-way SMS-capable Twilio number. Complete the provider's sender setup and
any applicable registration before enabling live sends. No real texts were sent
while implementing this feature.

Configure the Twilio number's inbound webhook as an HTTP POST to:

```text
https://notifications.your-domain.example/webhooks/twilio/inbound
```

Delivery callbacks are set automatically on each outgoing message. Webhooks use
the official Twilio SDK to validate `X-Twilio-Signature` against the configured
public HTTPS URL and every submitted form parameter. Account SID, inbound From,
To and provider message IDs are checked. Forward the exact public path and query
through the reverse proxy. Unauthenticated, unsigned or foreign-sender requests
cannot create feedback. [Twilio webhook security](https://www.twilio.com/docs/usage/security).

The service explicitly distinguishes queued, sending, accepted, sent, delivered,
failed, undelivered, suppressed, simulated and unknown. A delivered receipt is
**not** an acknowledgment or evidence the alert was valid. Callbacks are deduped
and cannot regress a terminal state. The Twilio queue validity period is five
minutes. [Message API and callbacks](https://www.twilio.com/docs/messaging/api/message-resource).

Definite rate-limit rejections retry with bounded backoff (up to five total
attempts). Definite 4xx rejections fail. Timeouts, unexpected transport failures
and interrupted sends become **unknown**, because the provider might already
have accepted them. Inspect the Twilio console and reconcile the record before
any manual resend; there is intentionally no blind retry button or exactly-once
delivery claim. Pending unsent work survives restart. Inbound STOP/START commands
update local opt-out state; Twilio supplies its own opt-out acknowledgments.

## Video evidence

Register evidence in `backend/evidence/manifest.json` (ignored by Git):

```json
{
  "flight42-cow718": {"file": "flight42-cow718.mp4"},
  "demo-scene": {"file": "demo-scene.mp4", "simulationOnly": true}
}
```

Files must be MP4 videos under that evidence directory. Supply the known key as
`evidenceId` during ingestion. Unknown IDs, files outside the directory and using
simulator-only clips in live alerts are rejected. The trusted producer is
responsible for associating the correct cow and event with the clip.

Texts look like:

```text
Cow 718
Reason: Movement needs review.
Location: North pasture
Video: https://your-backend.example/v/<opaque-token>
```

The `/v/` link is a bearer capability to one registered video, valid for 24 hours.
The lookup table stores its hash, asset mapping and expiration; the delivery
history retains the sent message URL. No cow ID or timestamp is encoded into
the URL. Links survive restart and support byte ranges
for playback/seeking. Expired links return 410; invalid links return 404. Treat
the link as private and share it only with the intended recipient. Live links
use `HOLYCOW_PUBLIC_BACKEND_URL`, which must be reachable by the phone. Local
simulator links use port 8870 and work only on this computer until hosting exists.
If an alert has no attached video, its fourth line explicitly says `Video: unavailable`.

For a repeatable local sample, after preparing flight playback, run this with
the ML virtual environment (which includes imageio-ffmpeg):

```powershell
ml/.venv/Scripts/python.exe -m backend.prepare_demo_video
```

To replace only the Telegram/demo-message clip, preserving the full custom clip:

```powershell
../.cow-vision-venv/Scripts/python.exe -m backend.prepare_demo_video --source C:/Users/fbook/Downloads/cow_message.mp4
```

This workspace now uses that portrait cow clip, encoded at 720×1280 and 30 fps.
The backend reads the registered file for each send, so replacement needs no restart.
It is simulator-only illustrative footage, not proof of the synthetic movement flag or cattle
identity. The sample alert uses it only when available. It never runs inference
again or overwrites the original source clip. Docker mounts `backend/evidence`
read-only at `/evidence`; media is excluded from the image and Git. Set
`HOLYCOW_EVIDENCE_DIRECTORY` for a different operator-owned evidence directory.

## Feedback assistant

Everyday language is the main interface. Ranch hands do not need special codes,
capital letters or a command vocabulary. For example:

```text
Ranch hand: She's fine, just resting.
HolyCow: For cow 718 at the north pasture: the animal was okay and the alert
        was a false alarm. Is that right? Just reply yes, or tell me what I got wrong.
Ranch hand: yep
HolyCow: Thanks. For cow 718, I recorded that the alert was a false alarm.
```

The assistant accepts short confirmations such as yep, yeah, that's right and 👍.
It remembers clarification context for 30 minutes, including across service
restarts. With multiple alerts, it can route a reply by cow number, or use the
LLM to match a location or description to an existing candidate. When unsure it
asks which animal; a number-only answer completes the earlier feedback without
requiring the ranch hand to retype it. Replies are attached to the preceding
outgoing message, not the newest queued alert. If a newly sent alert changes
the conversation to another cow, a bare yes cannot confirm the older cow's draft.

The simulator sends the selected preceding message as separate reply metadata;
it never inserts an internal code into the rancher's text. The backend snapshots
the most recent successfully sent message for real SMS (within 30 minutes),
preserving that context even if other messages are queued or sent while the reply
waits for processing. Explicit cow numbers and locations can switch subjects.
Reply metadata and exact raw wording survive restart. The rancher-facing view
hides internal codes, including codes in legacy messages and saved notes; the
original records stay intact in SQLite. Existing advanced commands remain supported:

```text
HC-1234ABCD VALID I saw the same abnormal movement.
HC-1234ABCD FALSE The animal was resting.
HC-1234ABCD UNSURE Need another camera angle.
```

Ambiguous references prompt a follow-up. Unknown senders, unknown codes and
replies naming multiple codes cannot label an observation.
Duplicate inbound MessageSids are acknowledged without duplicate processing.
Corrections append to history instead of rewriting earlier feedback.

For full LLM language understanding, set:

```dotenv
HOLYCOW_FEEDBACK_AGENT=auto
OPENAI_API_KEY=your-server-side-key
HOLYCOW_FEEDBACK_MODEL=your-structured-output-capable-model
```

The implementation follows the OpenAI [Responses quickstart](https://developers.openai.com/api/docs/quickstart)
and [structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs).
For deeper integration assistance, the OpenAI Developers plugin is also available.
Auto mode uses OpenAI when both key and model are configured; otherwise health
reports `local fallback`. The local fallback only understands a small set of
common phrases and is not a modern language model. `openai` mode requires both
settings at startup. Legacy `commands` mode retains the limited local fallback.
The configured API receives bounded candidate alert details for routing and the
chosen alert's cow number, location, summary, recent thread and reply text for
interpretation. It receives no phone number and has no tools, browsing, arbitrary
SQL, sending authority or model-training authority. API storage is disabled for
the response. Provider data-retention policies still apply.

The agent proposes valid/false-positive/uncertain and a short explanation.
The rancher can reply naturally (for example, `yep`) to commit an interpretation.
Drafts expire after 30 minutes; ambiguous replies and API failures do not save
labels. Acknowledgments such as `ok thanks` and plans to check do not imply
validity feedback. Negation, uncertainty, contradictions and corrections are
handled explicitly in the model prompt, and all proposed labels require confirmation.
Explicit VALID/FALSE/UNSURE commands and common local phrases continue to work if the model API is
unavailable. The conversational state machine is exercised locally; actual model calls require
credentials and were not exercised in this implementation.

## API and model-review export

All `/v1/*` routes require `Authorization: Bearer <HOLYCOW_NOTIFICATIONS_TOKEN>`.
The token is a service credential, not a substitute for future rancher identity,
tenant authorization or role-based access. This initial deployment supports one
configured rancher. The current unauthenticated dashboard's operator proxy is
restricted to local app URLs; integrate verified user/tenant authentication
before enabling that console on a hosted dashboard.

| Route | Purpose |
| --- | --- |
| `GET /healthz` | Public readiness and worker heartbeat, no secrets |
| `POST /v1/alerts` | Trusted producer ingests an immutable observation |
| `GET /v1/notifications` | Latest 100 alerts and up to 1,000 messages |
| `POST /v1/sample` | Empty JSON object creates a synthetic simulator alert |
| `POST /v1/simulate-reply` | Authenticated test reply, never sent to a phone |
| `GET /v1/training-candidates` | Confirmed feedback with model/observation lineage |

Example authenticated ingestion body (use a current timestamp):

```json
{
  "eventId": "flight-42:observation-17",
  "source": "live",
  "severity": "high",
  "cowNumber": "718",
  "identityBasis": "human_verified",
  "location": "North pasture, west gate",
  "locationBasis": "human_supplied",
  "summary": "Repeated movement deviation in three observations; please inspect the animal.",
  "observedAt": "2026-11-14T17:00:00-08:00",
  "modelVersion": "your-validated-alert-model-version"
}
```

Required provenance fields distinguish registered/human-verified/synthetic
identity and recorded/human-supplied/synthetic location. Text fields are bounded,
plain text; embedded URLs, unknown fields, invalid times and unsupported values
are rejected. No filename or arbitrary media URL is accepted.

The review export includes original event/model version, cow/location/summary,
optional evidence ID, each confirmed verdict, reviewer note, interpretation
method, agent version and review time. Every row has `eligibleForTraining:false`
and `requiresIndependentReview:true`. Reviewers must deidentify notes, reconcile
contradictory feedback, exclude synthetic samples, independently verify labels,
and split evaluation by flight/herd before retraining. A rancher's feedback is
an assessment, not ground truth or a diagnosis. No automatic model/threshold
updates are implemented.

## Verification

```powershell
backend/.venv/Scripts/python.exe -m unittest backend.test_notifications -v
npm --prefix web run typecheck
npm --prefix web run build
# Configure/start backend and built Worker as above before HTTP tests.
$env:TEST_ORIGIN = 'http://127.0.0.1:8790'
npm --prefix web run test:control
npm --prefix web run test:notifications
```

Backend tests cover durable/idempotent alerts, severity/expiry gates, identity
provenance, correlated replies, ambiguous/expired interpretations, confirmation,
opt-out, send uncertainty/restarts, bounded retries, signed inbound/delivery
webhooks, callback ordering, API validation and quarantined training exports.
Twilio and OpenAI calls are mocked: no credentials or external messages needed.

Browser walkthrough: create sample → inspect cow/location/reason → send a FALSE
reply with a note → see assistant acknowledgment and saved feedback → refresh
and reopen Notifications → inspect the same history. Stop/restart the service
to verify durability. Close the browser and submit an authenticated event from a
producer to verify the worker does not depend on page polling.

Docker Engine is not installed in the current environment, so the container
build/runtime must be checked on the selected Docker host. The same backend code
and worker are exercised locally under Uvicorn. Real carrier delivery, public
TLS/webhooks and real OpenAI interpretation remain configuration-dependent.
