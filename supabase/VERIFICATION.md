# Supabase verification — November 14, 2026

Target: `holycow-dev` (`enlvqgssvdrigffmlqvh`), an explicitly authorized new development project in `holycow`, US West. This record supersedes the earlier design-only verification for the **Supabase variants**; the original standalone migrations were not applied.

## Passed against the hosted development database

- Inspected the empty database before migration. Confirmed runtime roles: authenticated has no BYPASSRLS, service_role and postgres do.
- Applied seven ordered migrations, including the user-selected backend-isolation configuration. Confirmed PostgreSQL 17.11, PostGIS 3.3.7, 36 cattle tables and 36 tables with RLS plus FORCE RLS.
- Ran the synthetic rollback integration fixture, then expanded it with all website query smoke executions and reran successfully. The final file has 99 SQL statements, including fixture ingestion, assertions, prepared queries and role switches.
- Verified exact upload retry deduplication, separate intentional reruns and conflicting metric outputs, anonymous observations, delayed older location behavior, correction/history/attribution, survey recompute flag and rejected findings.
- Verified an existing foreign-tenant drone cannot be linked to a local flight, immutable output updates fail, and database geography distances use meters with boundary uncertainty contact.
- Under the final `cattle_backend_user` role with simulated reviewer/viewer/nonmember claims: verified self-only memberships, tenant-isolated base reads/invoker views, missing-identity fail-closed behavior, tenant GUC spoofing has no effect, no direct raw writes or membership escalation, role-gated review/correction functions, optimistic-head conflict, and identity-dependent alert invalidation. The initial browser-facing role configuration was superseded by the user's explicit choice to preserve backend/control-layer isolation.
- Verified `authenticated` has no cattle schema USAGE, table SELECT or review-function EXECUTE. Verified backend group is NOBYPASSRLS and has no inherited Supabase authenticated role. A public-key HTTP request independently confirmed cattle is not a Data API schema.
- Verified private bucket state, backend ready-media authorization for own tenant, rejection for other-tenant keys, five restrictive Storage policy guards and anonymous function denial. Browser evidence object access is blocked; a backend evidence endpoint will authorize any future signed links.
- Executed representative bindings for herd locations, unresolved locations, animal trail, open alerts, evidence drilldown, radius, pasture classification, flight summary, historical herd state, model comparison and correction impact. Supabase browser mutations use the new reviewed RPC rather than the standalone raw INSERT example.
- Confirmed rollback left **zero** domain organizations, Auth users, media metadata and evidence objects. No synthetic logins or passwords remain.
- Supabase security advisor initially flagged two mutable search paths. Applied a forward function-hardening migration, then reran advisor: **no findings**.
- Backend-isolation testing caught missing managed Auth schema access. A direct GRANT migration was recorded but the provider schema owner prevented schema USAGE from being granted. Resolved with a cattle-scoped verified-subject helper and reran the full suite successfully; no broad provider-role inheritance was applied. Final security advisor again returned no findings.
- CLI 3.1.0 installed/pinned and `supabase init` succeeded. Local SQL/PLpgSQL syntax, TOML configuration, generation consistency, JSON metadata and whitespace checks passed.

## Pending or not tested

- **Data API exposure is intentionally disabled**, matching the user's backend/control-layer isolation choice. Automatic approval review rejected the earlier schema-list expansion; the pending proposal was removed. It also rejected broad authenticated-role inheritance; that proposal was replaced with a narrowly scoped subject helper. Neither rejected action was applied or bypassed.
- Browser sign-in/JWT verification and real Auth account onboarding. SQL claim simulation exercises DB roles/policies, not GoTrue's token verification or email delivery.
- Actual Storage upload, signed download and blob checksum verification. Tests checked database authorization and policies, without pretending that Storage metadata rows represent uploaded blobs.
- Concurrent ingestion/correction sessions, ingestion service implementation, performance/load tests, object lifecycle jobs and backup/restore drill.
- Local PostgreSQL/Docker execution; no local runtime is available. Hosted execution supplies the database validation previously missing from the design pass.
- CLI account login/link. Connector authorization is confirmed; no CLI token or database password was requested or stored.
- Actual backend server, restricted LOGIN/secret provisioning, token verification, endpoint/controller code and owner membership onboarding. The NOLOGIN permission group exists, but no application framework/server exists in this repository yet.

No production project was altered and no paid upgrade was enabled. The hosted runtime is configured for a separate backend/control layer, with browser cattle access denied. Application endpoints and real owner onboarding are the next implementation work; schema exposure is not required for the chosen architecture.
