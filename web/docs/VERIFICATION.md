# Frontend verification — November 14, 2026

## Direct Telegram integration

Demo-send follow-up: Notifications now has **Send demo to Telegram**, delivery history and saved reviews, with no browser chat transcript or reply composer. The new authenticated, fixed-payload demo endpoint keeps synthetic provenance, permits only the prepared clip and configured chat, and adds durable request deduplication, a 30-second cooldown and opt-out checks. All 41 backend tests pass, including mocked native video upload, quoted Telegram feedback, confirmation and SQLite restoration, invalid requests, unavailable video, opt-out, duplicate requests and failed provider sends. Web typecheck and production build passed. Browser inspection of the built page verified the enabled button, Netherlands/sample explanation and zero chat bubbles/composers. No live demo message was sent during verification. Screenshot: ignored `web/outputs/telegram-send-demo.jpg`. Restart an existing backend process to load the new endpoint.

- Web typecheck and production Worker build passed. All 38 Python notification/Telegram tests passed (25 existing backend checks plus 13 Telegram checks). Four notification HTTP tests and six existing control-layer HTTP tests passed against the built Worker.
- Mocked Telegram checks cover compact text and native video captions, private recipient allowlists, native replies to older alerts, duplicate updates, durable polling offsets, bot namespaces, storage-failure recovery, start/stop, webhook secrets, sanitized failures, rate limits and the credential setup wizard. No live Telegram API calls were made.
- Browser verification exercised the Telegram message preview through the existing web control layer: “She's fine, just resting.” produced a cow-specific confirmation; “yep” saved false-positive feedback with the original wording. Internal HC codes were absent from the rancher view. Screenshot: ignored `web/outputs/telegram-preview.jpg`.
- No bot token or recipient was configured during implementation. The running demo remains explicitly simulated. Live Telegram/device delivery, hosted webhooks and Docker runtime remain unverified; one private rancher chat and text feedback are supported. See [Telegram setup](../../backend/TELEGRAM.md).

## Independent notification backend

Preceding-message follow-up: replies now retain exact rancher wording, with an optional validated reply-to message reference stored separately in SQLite. SMS context is captured from the last successful send at receipt time, so queued/future alerts cannot redirect it. The simulator no longer prepends HC codes; cards, legacy messages and notes hide those codes in the rancher view. Tests cover multi-cow context, selecting older threads, invalid references, and ensuring a newly sent cow's alert cannot confirm an older draft.

Compact-text follow-up: alert bodies now have exactly four lines (cow tag, reason, location and video). Reasons are shortened to 140 characters while the complete original event stays in SQLite. Twenty-two backend tests cover compact payloads, metadata retention and registered-video access, expiry, persistence and byte ranges. Browser verification opened the five-second simulator clip through the existing web control layer. New simulator clips are marked as simulation-only in the evidence registry; unavailable video is explicit. Existing message history is preserved as an audit trail.

Conversational follow-up: twenty backend tests pass, including everyday replies plus yep/emoji confirmation, clarification by cow number without retyping the original feedback, context across restart, negation, acknowledgments, correction, new-alert ambiguity, bounded LLM location routing and unknown-ID rejection. The simulator now supplies selected-alert context and uses plain-language guidance. Model-backed routing/interpretation is configured through auto mode; the local demo labels its limited fallback explicitly. Real model calls remain unverified without API credentials.

- Typecheck and production Worker build passed with the new Notifications sidebar and allowlisted HTTP control route. Two notification integration tests passed through the built Worker. The six existing fixture/control tests and two flight-demo integration tests also passed.
- Fifteen backend tests passed, covering authenticated/validated ingestion, severity and expiry gates, idempotency, saved feedback and training quarantine, signature/account/sender validation, callback ordering, opt-out, ambiguous send recovery, and agent confirmation/fallback. Twilio sending and OpenAI interpretation were mocked; no external SMS or model calls were made.
- The autonomous-worker test exercised the real background thread with no browser and no status-poll trigger: a queued alert and a queued reply both processed independently. Real local Uvicorn process restarts preserved the browser-created message, false-positive reply, assistant acknowledgment and review history.
- Browser checks verified the Notifications screen, visible simulator/backend status, contextual cow/location/reason message, submitting a reply, saved feedback, reload/reopen and restart persistence. Confirmed alert-specific threads do not mix other alerts' processed feedback. Screenshot saved under ignored `web/outputs/notifications-feedback.jpg`.
- Dockerfile/Compose provide one supervised process, persistent SQLite volume, non-root execution and health checks. Docker Engine is absent here, so container build/runtime were not executed. Hosting is deferred by user choice. Live carrier delivery, public HTTPS webhook routing and real model-assisted interpretation require configuration and remain unverified.
- The scene model remains segmentation-only. New sample alerts are explicitly synthetic and simulator-only; no registered cow identity, precise location or health severity is inferred from the stock video. The existing dashboard fixtures and demo evidence remain separate. See [backend guide](../../backend/README.md).

## Local flight evidence demo

- Web typecheck and production Worker build passed. Six existing control-layer tests and two new demo HTTP integration tests passed against the built Worker at port 8790. Six Python tests passed using temporary SQLite databases (intentional failure cases print tracebacks).
- Ran the full actual scene pipeline through `POST /api/demo-flight/jobs`: returned queued, reported running with actual processed/818 frame progress, then completed all 818 frames in about 187 seconds. The output contains 131 distinct geometric tracks over time; this is not a cattle census.
- Stopped and restarted the local Python service with the original source deliberately unavailable. Prepared mode still completed without inference. A real inference request failed explicitly, and the Flights UI showed the failure with the prepared-results fallback explanation. Durable jobs and review history survived the process restart.
- Browser checks in Edge verified Process demo flight, explicit prepared-mode labeling, selectable boxes and detection buttons, flag plus note, resolve plus second note, ordered SQLite history, refresh restoration and service-restart restoration. HTTP tests additionally verify rejection and stale-save conflicts.
- Selected video track 100 from its first-sighting menu: the actual video paused and sought to 22.88s / source frame 572. Playback was verified with paused=false and readyState=4. Visually checked boxes at the initial frame and the later selected frame; video and SVG had identical displayed rectangles (891.2×501.3), video intrinsic size 1280×720, SVG source viewBox 3840×2160. The viewer scales uncropped evidence consistently. Screenshot: local ignored `web/outputs/demo-evidence.jpg`.
- Reset through the built Worker removed all test-created jobs/reviews. SHA-256 checks confirmed source footage, playback, prepared results and scene weights were unchanged. Existing dashboard fixture counts and its six HTTP checks remained unchanged.
- Startup, configuration, asset provenance, API lifecycle, limitations and a repeatable three-minute prepared-mode walkthrough are in [DEMO.md](../../DEMO.md). This is a loopback-only, single-service-process demo, not a production authenticated backend. Nothing was published.

## Spotlight follow-up

- Six control-layer HTTP tests passed, including latest-recording unavailable/404 behavior and non-cow/cattle separation; TypeScript checks passed.
- Browser checks verified starring a new cow, reload persistence, circular-card recording access, explicit no-recording state, local video attachment, real poster extraction, actual native video playback (`paused=false`, readyState=4), IndexedDB restoration after reload, rejection of an undecodable replacement without losing the saved clip, and removal of the temporary attached copy.
- Verified the non-cow legend filter shows zero cow markers and two non-cow markers, with a separate unidentified-object dialog. Roster counts remain unchanged.
- Checked Spotlight at 390×844 with no horizontal page overflow; restored the normal viewport afterward. The temporary favorite and decoder-test clip were removed through the UI.
- Live ranch recordings, automatic RFID/video matching, remote uploads and cross-device favorite synchronization remain unconnected. The placeholder photograph is illustrative; an attached recording supplies its actual frame.

## Original frontend checks

Executed:

- `npm run typecheck`: passed with no TypeScript errors.
- Production Sites/Vinext build: passed, producing `/`, `/api/overview` and `/api/alerts/:id/review` plus Worker/client assets.
- `node --test tests/control-layer.test.mjs`: all 5 tests passed. Checks fixture roster/identity/missingness invariants; required review reason; missing/invalid commands and malformed input; cross-origin rejection; explicit nonpersistent receipt and immutable source fixture.
- Ran the same 5 checks against the built production Worker on port 8787: all passed with the current stable local runner. Wrangler 4.92's proxy previously returned a misleading restart 503 after a foreign-origin request. Updated to Wrangler 4.162.0 with matching Worker types, normalized the obsolete adapter-emitted legacy_env setting, and verified the unchanged adversarial/valid request sequence passes. No POST auto-retry was introduced. [Related upstream proxy report](https://github.com/cloudflare/workers-sdk/issues/14641).
- Browser checks through the real local UI: alert details, rejected empty review note, rejection with a note, lifecycle/list count and history update, cattle search, CSV download, adding an unobserved cow, local flight plan, refresh persistence, mobile overview/map, herd filtering, zoom/reset, marker layer toggle and resetting demo changes.
- Verified the CSV download completed as `holycow-demo-cattle.csv`.
- Responsive check at 390 × 844, then restored the browser's default viewport. Checked the normal desktop overview visually against the supplied PNG.
- Verified the demo HTTP endpoint returned 200 with 90 animals, two herds and explicit demo mode.

Browser test changes were reset through the UI, leaving the clean original demo. The private preview uses synthetic observations and generated illustrative terrain. No live Supabase table, policy, API exposure, Auth user or Storage object was changed by this frontend task.

Not verified: real Supabase sign-in, actual source-media evidence, durable/shared reviews, database-backed registration/planning, drone control, real geospatial accuracy, production load, full assistive-technology/WCAG audit or a live database adapter. These are intentionally outside this frontend/control-skeleton implementation. HTTP tests ran on both dev and locally built production servers; hosted publication is verified separately through the Sites deployment result.
