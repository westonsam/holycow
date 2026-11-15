# Supabase development setup

Project: **holycow-dev**, organization **holycow**, region **US West (`us-west-1`)**.

- [Project dashboard](https://supabase.com/dashboard/project/enlvqgssvdrigffmlqvh)
- API URL: `https://enlvqgssvdrigffmlqvh.supabase.co`
- Database schema: `cattle`; PostgreSQL 17.11 / PostGIS 3.3.7.
- Private Storage bucket: `cattle-evidence` (50 MiB/object, JPEG/PNG/WebP/MP4).
- Browser configuration is in the ignored root `.env.local`, using the **publishable** key only.
- Project metadata is in `project.json`; it is not a CLI login or secret.

The user selected the organization/region and approved the quoted **$0/month project creation cost**. Future usage, plan changes, storage/egress and processing costs are separate. No paid upgrades were enabled.

## What is live

Seven migrations are applied, and their filenames match Supabase's recorded migration versions:

1. `20261114193116_core.sql`: 36 tables, PostGIS in `extensions`, composite tenant constraints, spatial and temporal indexes.
2. `20261114193129_history_views.sql`: append-only history guards, run publication rules and invoker-security current views.
3. `20261114193142_auth_storage.sql`: Supabase Auth membership, JWT-based RLS, private Storage, reviewed mutation RPCs.
4. `20261114193432_function_hardening.sql`: fixed search paths for two trigger functions.
5. `20261114194703_backend_isolation.sql`: backend-only role/policies; removes browser cattle grants and direct evidence downloads.
6. `20261114194736_backend_auth_context.sql`: attempted narrow managed Auth permissions; hosted schema ownership prevented the schema grant. The following migration supplies the working scoped alternative.
7. `20261114195422_backend_subject_context.sql`: cattle-scoped verified subject helper; no broad Supabase role inheritance.

All 36 tables have RLS and FORCE RLS. The security advisor returned no findings after hardening. Auth exists but no real users/organization memberships have been onboarded. No production data was loaded. Database rollback tests left zero auth users, domain organizations, media rows and evidence objects.

**Chosen architecture: frontend → backend/control layer → Supabase database and private Storage.** The user explicitly chose backend/control-layer isolation. The cattle schema is absent from both the hosted and local Data API schema lists. Browser `anon`/`authenticated` roles have no cattle schema, table or function permissions. Even an accidental future API schema-list change would not grant browser access. Supabase Auth can still handle browser sign-in; the frontend sends its access token to the application backend for verification. No cattle API expansion was applied.

## Auth and authorization

Provider-specific difference from the standalone design: `cattle.membership` uses `(org_id,user_id)` with `user_id REFERENCES auth.users(id)`, replacing external issuer/subject columns. Passwords remain entirely in Supabase Auth. Through the backend, users can read their own membership rows; other tenant data uses membership checks bound to the verified request subject. Setting `app.org_id` has no effect on this authorization.

The NOLOGIN, NOINHERIT, NOBYPASSRLS group `cattle_backend_user` gets tenant-scoped SELECT and two narrow database mutation functions:

- `cattle.review_finding`: owner/admin/reviewer only, with expected review head, valid decision, mandatory reason, server-assigned actor and audit event.
- `cattle.correct_track_identity`: owner/admin/reviewer only, expected identity head, mandatory reason, same-flight succeeded output evidence, tenant-constrained animal reference, immutable decision/evidence/audit writes.

Both functions validate permissions internally, use a fixed empty search path and allow no arbitrary SQL. Expected-head mismatches require reloading (`40001`); concurrent successor uniqueness may yield `23505`. Do not silently overwrite another review. The backend must cryptographically verify each access token (issuer, audience, signature and expiry) before supplying its subject in transaction-local `request.jwt.claims`. `cattle.request_user_id()` reads that verified subject; it does not verify tokens itself. Backend database credentials remain trusted: a holder can set session claims and must never be a browser/drone client. The group has no inherited broad provider roles and no auth.users/credential read access. All other mutations currently require the trusted processing/administration service; no browser membership creation, upload, raw model edits or bulk table mutation grant exists. An operator editing UI/server API is not implemented yet.

`service_role` is for trusted server processing and bypasses RLS. Its secret must never appear in browser code, screenshots, committed files or logs. It must verify end-user roles for user-initiated operations and always filter tenant UUIDs. It may insert pipeline data and update limited operational state; history triggers remain active. Retention deletes and DDL are not granted by these migrations. Supabase's admin `postgres` owns the migrations and bypasses RLS; this is why the application must not connect as that role.

For Storage, object keys must start with the canonical organization UUID, for example:

`<org_uuid>/<flight_uuid>/<clip_uuid>/000200.jpg`

The backend checks organization membership and a matching **ready** `media_asset` row before authorizing evidence. Browser object listing/download/upload/update/deletion are blocked; restrictive policies prevent broad policies for other buckets from opening this bucket. A trusted service can stream an authorized object or issue a short-lived signed link after the backend's access check. A signed link is a bounded evidence capability, not database access. A trusted ingestion service uploads and verifies objects before marking ready. A worker-scoped upload endpoint/credential and actual image upload test are still to be implemented. Mask keys need matching media metadata or an explicitly authorized evidence endpoint.

## Owner onboarding

Once the website's sign-in flow is connected, sign in through Supabase Auth. An administrator must then create the first domain organization and owner membership for that user's Auth UUID. Supabase platform organization `holycow` is distinct from the domain `cattle.organization` tenant. Do not create a new tenant automatically for every frame or every login.

Use this reviewed template in the Supabase SQL editor after replacing the user UUID with the actual Auth user ID. The FK rejects an unknown user. This is **not** an applied migration or an automatic seed:

```sql
BEGIN;
WITH new_org AS (
 INSERT INTO cattle.organization(name) VALUES ('Your ranching organization') RETURNING id
)
INSERT INTO cattle.membership(org_id,user_id,role)
SELECT id, 'REPLACE_WITH_REAL_AUTH_USER_UUID'::uuid, 'owner' FROM new_org
RETURNING org_id,user_id,role;
COMMIT;
```

Configure the actual website URL and exact redirect allowlist in hosted Auth settings when the website address is known. Local config uses `http://127.0.0.1:3000` and `http://localhost:3000`; those are development placeholders, not a deployed website. Authentication email delivery, password recovery and real user sign-in have not been tested. No invitation emails were sent.

## Backend integration contract

Frontend requests go to application endpoints such as `GET /api/herds/:id/locations` and `POST /api/findings/:id/review`; the browser does not query `cattle` through Supabase JS. The backend verifies the Supabase access token, checks endpoint permissions, then uses a restricted database login assigned `cattle_backend_user`. Provision that LOGIN and its password in the chosen backend's secret store after the backend host is selected; no password or login was invented here.

```sql
-- Driver-bound parameters; claims JSON is built by the backend from the VERIFIED token.
BEGIN;
SET LOCAL ROLE cattle_backend_user;
SELECT set_config('request.jwt.claims', $1, true);
SELECT * FROM cattle.latest_animal_location WHERE org_id=$2;
-- A separate review endpoint can call cattle.review_finding(...) with bound arguments.
COMMIT;
```

Always roll back on errors before returning the pooled connection; do not keep claims at session scope. Membership-less users get no tenant data. Keep tenant filters even with RLS. The UI still needs to join current herd membership and expose last observation age/unknown states. See the full SQL website queries for those semantics. There is no frontend/backend framework or app to wire up in the repository yet; this setup does not invent one. The backend/control endpoints and worker implementation are the next application task.

## CLI, migrations and tests

Supabase CLI **3.1.0** is pinned in root package.json/package-lock.json as a dev dependency. Node 20+ is available. Standard CLI init succeeded. `.env.local`, CLI temp state and credentials are ignored. The connector authorization is independent of CLI login; it does not put a CLI access token or database password in the repository.

```powershell
Set-Location C:\SchoolProjects\holycow\holycow_git
npm ci
npx supabase login
npx supabase link --project-ref enlvqgssvdrigffmlqvh
# Inspect migration state before applying any NEW future migrations:
npx supabase migration list --linked
npx supabase db push --dry-run
```

Do not reapply the standalone `database/migrations` to this project; they use a different authentication model. The first two Supabase migration files are derived by `database/tools/build_supabase.py`; the source-to-generated check preserves their current contents. Now that they have been applied, future changes must be new forward migrations, not baseline regeneration from edited SQL. No destructive down/reset command is part of normal hosted setup.

For local runtime testing, the standard `supabase start` requires a supported local runtime (Docker is absent on this machine). No Docker or local database was provisioned. Local seeding is disabled to prevent accidental sample users/data. `fixtures/synthetic.sql` is a disposable-only fixture that commits; prefer `tests/integration.sql`, which is self-contained and rolls back its data, including synthetic Auth users.

The hosted integration test ran successfully through the authorized Supabase connection using the final `cattle_backend_user` role, then rolled back. It includes all website query smoke executions and asserts browser cattle grants are absent. See [VERIFICATION.md](VERIFICATION.md) for boundaries: database role claims were simulated inside SQL, not real browser tokens; object download/upload, concurrent sessions, recovery drills and benchmarks remain untested. `node --env-file=.env.local supabase/tests/anonymous-access.mjs` independently confirmed the cattle API schema is not exposed.

References: [Supabase PostGIS](https://supabase.com/docs/guides/database/extensions/postgis), [Auth and RLS](https://supabase.com/docs/guides/database/postgres/row-level-security), [Storage access](https://supabase.com/docs/guides/storage/security/access-control), [custom API schemas](https://supabase.com/docs/guides/api/using-custom-schemas).
