# HolyCow dashboard

A working frontend based on `webapp.png`, with a separate HTTP control layer and a demo repository. The existing Supabase database and its backend-only access rules are unchanged.

## Run locally

From the parent repository:

```powershell
npm --prefix web ci
npm run dev
```

Open the Local URL printed by the server, normally `http://127.0.0.1:5173/`. Use system Node 22.13 or newer for installation; a project-local Node 22.23.5 dev dependency supplies the npm-script runtime. Dependencies are pinned through the lockfile. The supplied Sites/Vinext starter provides React, TypeScript, server route handlers and a Worker build; no frontend framework existed previously.

On the current Windows machine, clean-install development startup fails inside the Workers runtime with `ERR_RUNTIME_FAILURE`. The built app was verified to serve successfully. From `web/`, use `npm run build`, then `npm start -- --port 8787`, and open `http://127.0.0.1:8787`. Stop running HolyCow servers before `npm ci` to avoid Windows dependency-file locks. See the [repository setup guide](../README.md) for details.

```powershell
npm run check:web
npm run test:web   # with the local dev server running
npm run build:web
```

## What works

The **Notifications** sidebar opens a local operator console for the independent messaging backend. **Send demo to Telegram** queues a clearly labeled sample video to the configured private chat. All conversation happens in Telegram; the page shows notification delivery and durable feedback history, without an internal chat. Demo events remain synthetic and ineligible for training. See [Telegram bot setup and demo walkthrough](../backend/TELEGRAM.md) and [backend/README.md](../backend/README.md) for Docker supervision, optional OpenAI interpretation and deployment limits. Ordinary simulator ingestion remains local-only.

Flight log includes a separate **Process demo flight** workflow with a local Python HTTP service, background jobs, actual saved pipeline results, timestamped video boxes and SQLite review history. Read [DEMO.md](../DEMO.md) for setup, server-side configuration, verification and the three-minute walkthrough. Existing fictional alert reviews still use their original nonpersistent receipt contract. Flight evidence uses temporary video track IDs and is never associated with the fictional registered cattle described below.

- Overview: clickable alerts, herd charts, drone readings, refresh, search and data-source explanation.
- Map: clickable cattle/pasture labels, herd/status filters, zoom, reset, drag/keyboard pan, layers and expanded view.
- Register: search, herd/assessment filtering, sorting, pagination, row selection, CSV export, details and adding an unobserved cow.
- Reviews: note validation, acknowledgement, accept/reject, lifecycle changes and attributed local history.
- Flights: history, details, processing summary, pasture navigation and local flight planning.
- Workspace: mobile navigation, settings, freshness count, profile, demo reset, dialog focus trap, Escape handling, reduced-motion support, loading/error states.
- Spotlight: star/unstar cows, persistent favorites, circular preview cards, open-alert badges, cow details, and a last-available recording viewer. Attach a local video to generate a thumbnail and play it with native controls; recordings persist in IndexedDB and are never uploaded by this feature.
- Non-cow observations: separate purple diamond markers, legend filter and a detail view. They never contribute to cattle counts or health alerts.

## Demo and live boundaries

All sample observations are fictional and clearly marked. The snapshot is November 14, 2026, 8:42 AM Pacific; freshness uses the fixed demo reference time of 8:54 AM, not a simulated live clock. The roster has 90 animals, 82 observed and 8 unobserved. Herd charts separately account for unable-to-assess and unobserved cattle. They do not classify missing evidence as healthy.

Reviews pass through a server handler and service validation, then return an explicit `persisted: false` receipt. The browser stores demo receipts, added animals, plans and preferences under a versioned local-storage key. Refresh restores them; profile → Reset demo changes restores the original fixture. No real drone is dispatched, no diagnosis is recorded and no Supabase record is changed.

The aerial background is generated and not georeferenced. All map coordinates are normalized illustrative viewport positions, never fabricated ground GPS. Actual source-frame evidence is not connected; the detail view states the demo model/scale/confidence rather than pretending to show a real captured image.

See [control-layer architecture](docs/CONTROL_LAYER.md), [verification](docs/VERIFICATION.md) and [asset provenance](docs/ASSETS.md) before extending the application.

See [Spotlight behavior and recording integration](docs/SPOTLIGHT.md) for favorites, browser-local clips, capture-time semantics and non-cow detections. Real source footage remains unconnected; no sample clip is represented as a real cow recording.

## Private preview

The Site identity is tracked in `.openai/hosting.json`. The preview is owner-only and contains no live ranch data or database secrets. Supabase configuration remains in the parent repository; it is not copied into the frontend bundle. A separate publication staging directory is used so publishing does not create an embedded Git repository inside `web/`.
