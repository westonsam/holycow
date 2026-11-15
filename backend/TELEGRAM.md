# Telegram alerts and feedback

Telegram is HolyCow's preferred live messaging transport. It calls the official
[Telegram Bot API](https://core.telegram.org/bots/api) directly; Twilio and a
Codex connector are not required. The existing durable outbox, feedback assistant,
SQLite history, evidence registry and background worker remain in use.

## Connect a bot

1. In Telegram, open [@BotFather](https://t.me/BotFather), send `/newbot`, and
   create a dedicated HolyCow bot. Keep the token private.
2. Stop the notification backend, then run from `holycow_git`:

   ```powershell
   backend/.venv/Scripts/python.exe -m backend.telegram_setup
   ```

   The setup prompts for the token without echoing it. It verifies the bot,
   gives you its Telegram link, waits for the rancher to tap **Start**, and lets
   you choose the private chat explicitly. Enable alerts when prompted. Settings
   are written to ignored `backend/.env`; provider tokens never reach the browser.
   Use a private terminal, not a chat message, to enter credentials.
3. Restart the backend:

   ```powershell
   backend/.venv/Scripts/python.exe -m backend.run
   ```

   The bot processes the pending `/start` and sends “HolyCow connected. Alerts
   will appear here.” This verifies reception and sending without a fake cattle
   alert. Telegram requires the user to start a bot conversation first.
   [Bot setup and initiation](https://core.telegram.org/bots).
4. Check **Notifications** in the dashboard. It reports transport `telegram`
   and polling health. Optional read-only CLI check:

   ```powershell
   backend/.venv/Scripts/python.exe -m backend.telegram_setup --action check
   ```

Live Telegram delivery requires this setup; implementation checks use mocked
provider calls and do not establish delivery to a phone.

## Send a demo to your phone

With the backend and web app running, open **Notifications → Send demo to Telegram**.
This sends the registered five-second sample MP4 to the configured private chat.
The caption includes cow 718, a **DEMO ONLY** reason and an illustrative Netherlands
location. The cow tag and observation are fictional; the footage is from a farm
in the Netherlands and does not establish that cow's identity or health.

Use Telegram's **Reply** on the video and write “she's fine, just resting.”
Confirm the assistant's interpretation with “yep”. Select the alert in the web
history to inspect delivery status and saved feedback. All conversation takes
place in Telegram; the dashboard has no chat simulator or message composer.

The button queues a background job, not a delivery receipt. Status **sent** means
accepted by Telegram, not read on the device. A request ID prevents duplicate
queueing after uncertain browser responses, and a 30-second cooldown limits
accidental repeat sends. Missing footage, disconnected Telegram and `/stop`
subscriptions fail explicitly. Send `/start` to resume after stopping.
Demo messages and reviews stay marked synthetic and ineligible for training.

## Environment

Setup writes these backend-only values:

```dotenv
HOLYCOW_MESSAGING_TRANSPORT=telegram
HOLYCOW_LIVE_TELEGRAM_ENABLED=true
HOLYCOW_RECIPIENT_OPTED_IN=true
TELEGRAM_BOT_TOKEN=<secret from BotFather>
TELEGRAM_CHAT_ID=<selected rancher private chat ID>
TELEGRAM_UPDATES_MODE=polling
```

Manual configuration is also supported. Use a positive private-chat ID; groups,
channels and arbitrary senders are excluded in this first version. One service
instance receives updates for one dedicated bot and rancher. The service checks
both chat ID and sender ID. Do not run another polling program against that bot
while HolyCow is running. Token rotation for the same bot retains its cursor;
changing to a different bot starts a separate cursor namespace.

## Messages and video

A high-severity live event enters the existing authenticated `POST /v1/alerts`
producer endpoint. The message caption contains only:

```text
Cow 718
Reason: Movement needs review.
Location: North pasture
```

If the event has registered `evidenceId`, its MP4 is uploaded as a native Telegram
video with that caption. Only registered, readable videos inside the evidence
directory are accepted; simulator-only clips cannot be sent as live evidence.
Uploads are capped at 49 MB. No local filesystem path, private localhost link,
internal alert code, timestamp or model metadata is transmitted in the caption.
The original complete event and four-field message representation remain in SQLite.
If no video is attached, a text message explicitly says `Video: unavailable`.

API success is recorded as **sent**, not delivered or read. No delivery/read
receipt is fabricated. Network timeouts or interrupted sends remain **unknown**
and are not automatically retried; definite rate-limit rejections use Telegram's
`retry_after` with the existing bounded retry policy. Error bodies and token-bearing
request URLs are never logged or returned in user-facing errors. Text and videos
use Telegram's protected-content option. Uploaded evidence is shared with Telegram
and the configured recipient; it is no longer only a local file.

Ordinary simulation ingestion remains simulator-only, even with a connected bot.
The dedicated authenticated `POST /v1/telegram-demo` action is the sole exception:
it accepts only a 32-character hexadecimal `requestId`, fixes all sample fields
server-side, and marks the stored event `source: simulation` and `telegramDemo: true`.
It cannot choose a recipient, file path, reason or cow. Real alerting still requires
a trusted producer supplying actual cow identity, location and severity; the
stock-video segmentation model does not provide those facts.

## Replies

- Ranchers can reply naturally: “she's fine, just resting”, then “yep”. Original
  wording is retained, interpretations require confirmation and no model changes
  are made automatically. Full free-text understanding uses the configured LLM;
  otherwise the limited local phrase fallback is labeled in the dashboard.
- Telegram's native **Reply** to an alert or video resolves the exact preceding
  message. A reply to an older cow's video cannot silently label a newer cow.
  Unknown or external quoted messages are ignored instead of guessed.
- Without an explicit quote, the backend uses its existing last-sent-message
  context, captured when the incoming update is durably stored. Cow tags or
  locations can change the subject. Internal IDs never need to be typed.
- Assistant responses use Telegram's native reply reference to the rancher's
  incoming message. Backend provider IDs include bot, chat and message IDs, so
  correlation and deduplication survive restarts and bot changes.
- `/stop` or `STOP` suppresses unsent alerts and agent replies. One opt-out
  acknowledgment is allowed. `/start` resumes future alerts and acknowledges
  connection. Suppressed historical alerts are not automatically resent.
- Text replies are supported. Voice notes, edited messages, groups and other
  media feedback are not yet transcribed or classified.

## Polling, hosting and webhooks

Long polling is the default. The receiver is a separate thread from sending and
feedback processing; it works with the browser closed and needs no inbound public
endpoint. The update offset is checkpointed in SQLite only after each incoming
message is durably committed (or safely ignored). Replayed updates do not duplicate
feedback, and storage failures do not advance the cursor. The service continues
to need an always-on host for unattended operation; the existing Docker package
provides a persistent volume and process restart policy.

Telegram polling and webhooks are mutually exclusive. Setup preserves an existing
webhook rather than silently taking over another application. To intentionally
switch an existing dedicated bot to polling:

```powershell
backend/.venv/Scripts/python.exe -m backend.telegram_setup --action polling
```

That command asks before removing an existing webhook and preserves pending updates.
Stop the backend while changing delivery mode.

For an HTTPS-hosted backend, optional webhook mode uses:

```dotenv
HOLYCOW_PUBLIC_BACKEND_URL=https://notifications.your-domain.example
TELEGRAM_WEBHOOK_SECRET=<random 32+ character URL-safe secret>
```

Register it with:

```powershell
backend/.venv/Scripts/python.exe -m backend.telegram_setup --action webhook
```

The setup helper registers `/webhooks/telegram`, saves webhook mode and preserves
pending updates. Restart the backend afterward. Requests must supply the configured
`X-Telegram-Bot-Api-Secret-Token` header and still pass sender/chat validation.
No LLM calls or outgoing sends occur inside webhook latency; the existing worker
handles the committed inbox. [Telegram update delivery](https://core.telegram.org/bots/api#getupdates),
[webhook authentication](https://core.telegram.org/bots/api#setwebhook).

## Checks

```powershell
backend/.venv/Scripts/python.exe -m unittest backend.test_notifications backend.test_telegram -v
npm --prefix web run typecheck
npm --prefix web run build
```

Telegram HTTP tests use mocks and check direct text/video payloads, compact
captions, native reply correlation, allowlists, duplicate updates, cursor durability,
bot namespaces, cursor behavior on storage failure, opt-out/resume, webhook secrets,
sanitized failures and rate-limit handling. Carrier/device delivery and real bot
calls require configured credentials and are not claimed as verified by mocks.
