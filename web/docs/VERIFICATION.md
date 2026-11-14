# Frontend verification — November 14, 2026

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
