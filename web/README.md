# HolyCow dashboard

A working frontend based on `webapp.png`, with a separate HTTP control layer and a demo repository. The existing Supabase database and its backend-only access rules are unchanged.

## Run locally

From the parent repository:

```powershell
npm --prefix web ci
npm run dev
```

Open the Local URL printed by the server, normally `http://127.0.0.1:5173/`. A project-local Node 22.23.5 dev dependency supplies the runtime without changing the machine's default Node installation. Dependencies are pinned through the lockfile. The supplied Sites/Vinext starter provides React, TypeScript, server route handlers and a Worker build; no frontend framework existed previously.

```powershell
npm run check:web
npm run test:web   # with the local dev server running
npm run build:web
```

## What works

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
