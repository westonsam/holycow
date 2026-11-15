# HolyCow

HolyCow is a cattle monitoring dashboard for reviewing drone observations, finding cattle that need attention, and following important animals over time. It includes a React/TypeScript web app, a backend/control-layer skeleton, and PostgreSQL/PostGIS migrations for Supabase.

The dashboard currently uses **synthetic demo data**. Flight log also has a separate local evidence demo using actual output from the scene-specific Python pipeline, with durable SQLite reviews. See [startup and the three-minute walkthrough](DEMO.md). The Supabase development database is configured separately; real authentication and ranch ingestion remain unconnected.

## Features

- **Herd overview:** observation summaries, alert review, herd charts, and drone status.
- **Pasture map:** last-known observations, herd/status filters, pan, zoom, and separate non-cow detections.
- **Cattle register:** search, filtering, sorting, pagination, CSV export, and animal details.
- **Spotlight:** favorite cows displayed as bubble cards with cow numbers, alert badges, and recording previews.
- **Recordings:** attach a local clip, extract its thumbnail, and play it with native controls. Clips remain in this browser and are not uploaded.
- **Flight log:** sample history and local planning, plus Process demo flight → background inference or labeled precomputed results → video evidence → durable observation reviews.
- **Notifications:** independent alert backend, durable outbox/inbox, direct Telegram text/video delivery, a labeled phone demo, contextual Telegram replies and saved feedback for future model review. See [Telegram bot setup](backend/TELEGRAM.md) and [Docker deployment](backend/README.md). Hosting and live bot configuration remain separate setup steps.

## Repository layout

```text
holycow_git/
├── web/                   Web app and HTTP control-layer skeleton
│   ├── app/               Pages, layout, and API routes
│   ├── components/cattle/ Dashboard, map, Spotlight, and dialogs
│   ├── lib/cattle/        Contracts, API client, and local recording storage
│   ├── server/            Business services and repository interfaces
│   ├── public/assets/     Dashboard imagery
│   ├── tests/             HTTP control-layer tests
│   └── docs/              Architecture, verification, and asset notes
├── supabase/              Provider-specific migrations and setup
├── database/              Original database design and standalone SQL reference
└── package.json           Root development and database command shortcuts
```

The application source is in `web/`. Sibling workspace folders named `holycow-site-preview*` are publication working copies, not the application source.

## Local setup

Use **Node.js 22.13 or newer**. The project pins Node 22.23.5 as a development dependency; using a compatible system Node version also avoids installation engine warnings.

If you use NVM for Windows:

```powershell
nvm install 22.23.5
nvm use 22.23.5
node --version
```

Install web dependencies from the repository root:

```powershell
cd C:\SchoolProjects\holycow\holycow_git
npm --prefix web ci
```

Stop existing HolyCow servers with `Ctrl+C` before reinstalling dependencies. On Windows, a running server can lock native files and cause `EPERM` or `EBUSY`. An interrupted install can then cause missing-module errors. Stop the server and rerun the install.

### Development server

```powershell
cd web
npm run dev
```

Open the address printed in the terminal, normally **http://127.0.0.1:5173**. From the repository root, `npm run dev` invokes the same command.

**Known local issue:** after a clean dependency install on the current Windows machine, development startup fails inside the Cloudflare Workers runtime with `ERR_RUNTIME_FAILURE`. Development startup remains unresolved. The built application has been verified to run locally using the following path.

### Build and run locally

From `web/`:

```powershell
npm run build
npm start -- --port 8787
```

Open **http://127.0.0.1:8787**. `npm start` requires an existing successful build; rebuild after source changes. These commands run locally and do not publish the site.

## Checks

From `web/`:

```powershell
npm run typecheck
npm run build
```

The HTTP tests require a running application. For a server on port 8787, run in another PowerShell terminal:

```powershell
cd C:\SchoolProjects\holycow\holycow_git\web
$env:TEST_ORIGIN = 'http://127.0.0.1:8787'
npm run test:control
```

Without `TEST_ORIGIN`, tests target port 5173. The six control-layer tests cover fixture consistency, recording availability, review validation, origin rejection, and nonpersistent demo receipts. They do not verify live Supabase integration.

## Architecture

```text
Browser UI → HTTP route → Monitoring service → Repository interface
                                                 ├── Demo repository (current)
                                                 └── Supabase/private storage adapter (future)
```

The chosen access model keeps cattle operations behind the backend/control layer. The browser does not query the cattle database directly. The `cattle` schema is not exposed through Supabase's Data API, and browser roles have no cattle permissions.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/overview` | Synthetic cattle, herd, flight, and map observations |
| `POST /api/alerts/:id/review` | Validate a review and return an explicitly nonpersistent receipt |
| `GET /api/cattle/:id/recording` | Look up the latest recording; currently reports no connected footage |

Live integration still needs verified authentication and tenant context, a server-side repository adapter, durable review/audit handling, and authorized private evidence access. The hosted Worker requires a suitable HTTPS backend gateway for database access. See the [control-layer guide](web/docs/CONTROL_LAYER.md).

## Data and media boundaries

- Sample cattle, alerts, flights, and locations are fictional. The map background is illustrative and not georeferenced.
- Assessments are model observations for review, not veterinary diagnoses. Missing evidence is not classified as healthy.
- Favorites and demo edits persist in browser local storage. Attached recordings persist separately in IndexedDB and can be removed through the recording viewer.
- Generic cow previews are labeled illustrative. A thumbnail from an attached clip is labeled as a recorded frame.
- The app does not dispatch a drone or modify the Supabase database. The separate local flight demo consumes actual scene-model output through an HTTP service; it does not associate video tracks with registered cattle.
- Keep database credentials and privileged keys on the backend. Local environment files, dependencies, runtime state, test output, and generated builds are ignored by Git.

## Database

Provider-specific migrations and backend isolation configuration are in [supabase/README.md](supabase/README.md). The original design, assumptions, ER diagram, data dictionary, example ingestion, and standalone SQL are in [database/README.md](database/README.md).

Use the Supabase migration set for the configured development project. **Do not apply both migration sets to the same database.** Running the demo frontend does not require a Supabase connection or a local PostgreSQL server.

## More documentation

- [Web app guide](web/README.md)
- [Spotlight and recording integration](web/docs/SPOTLIGHT.md)
- [Frontend verification notes](web/docs/VERIFICATION.md)
- [Asset provenance](web/docs/ASSETS.md)

The public dashboard is [HolyCow Herd Monitor](https://holycow-herd-monitor.freebream261.chatgpt.site). Judges can open it without signing in. See [public demo hosting](HOSTING.md) to connect video processing and Telegram from the laptop on demand.
