# Verification record

This is the original design-pass record. The later authorized Supabase setup applied provider-specific migrations and ran hosted database tests; see [Supabase verification](../supabase/VERIFICATION.md) for the current runtime status.

Date: November 14, 2026 (user's America/Los_Angeles date).

## Executed here

- Inspected repository/workspace files, README, ignore rules, Git status, context and attached mockup. Found no application/provider/auth/ORM implementation or applicable AGENTS.md.
- Checked PATH for psql, pg_ctl, Docker and Podman, conventional PostgreSQL/Docker install directories, and PostgreSQL/Docker Windows services. No usable local database runtime found. WSL launcher exists; no Linux database was provisioned or assumed available.
- Installed `pglast 8.8` into the workspace-local scratch directory `C:/SchoolProjects/holycow/.validation-libs`, outside the repository. This is a validation-only dependency, not an application stack dependency.
- Ran `database/tools/check_artifacts.py --write-dictionary` with that directory on PYTHONPATH. Final result: **239 SQL statements parsed; 18 function/DO bodies parsed; 36 tables checked; 61 FK declarations checked against declared target unique/primary keys and tenant scope; example JSON and Python concurrency-test syntax passed**. Parser also verified all declared output kinds have examples and sample clip fps/duration/count are consistent.
- Regenerated the data dictionary and Mermaid FK graph from the final core schema. Field descriptions cover every table/column. Inspected generated output and file inventory.
- Ran `git diff --check` for tracked edits and a separate whitespace scan over all new database files. No whitespace errors found. Git status shows the intended README edit and new database directory; no unrelated tracked edits.

SQL parsing is not execution. PL/pgSQL parsing does not resolve live table types, grants, PostGIS signatures, triggers or query plans. FK static checks do not execute constraints. No latency or capacity benchmark ran.

## Supplied, but NOT executed here

| Verification | Artifact | Status |
|---|---|---|
| Extension install, DDL, role creation, triggers and views | migrations/001_core.sql, migrations/002_policy_views.sql | Requires disposable PostgreSQL/PostGIS |
| Sparse synthetic fixture including repeated upload, late event, anonymous track, conflict, correction and rejected finding | tests/fixture.sql | Not loaded into DB |
| Cross-tenant composite FK rejection and RLS reads/inserts, including invoker view and missing tenant | tests/verify.sql | Not executed |
| Immutable output privileges, terminal run transition, membership overlap and valid subject checks | tests/verify.sql | Not executed |
| Retry dedupe, distinct reruns, event-time ordering, correction projections, history, survey staleness, review rejection, identity-bound alert invalidation | tests/verify.sql | Not executed |
| Geography distances in meters and boundary uncertainty contact | tests/verify.sql | Not executed |
| Prepare/execute representative bindings for all eight website questions and supporting drilldowns | tests/verify.sql + queries/website.sql | Parsed only |
| Concurrent retry and identity-successor lock serialization; observer confirms blocking | tests/concurrency.py | Python parsed only; requires psycopg 3 and local DB |
| Actual deployed application LOGIN, auth claims, pooled connections and private storage policy | Deployment integration gate in OPERATIONS.md | No implementation exists yet |
| Backup/PITR plus object evidence restore drill; performance/retention load test | OPERATIONS.md | Not executed |

The SQL role tests use the proposed runtime groups through SET ROLE, not a fictional existing application login. Re-run with the actual least-privilege LOGIN before deployment and inspect its memberships, ownership and BYPASSRLS flag. Tests intentionally use a migration administrator as the session user for fixture setup and role switching; that is not the production application connection model.

Concurrency tests require a disposable database administrator DSN and ability to inspect `pg_stat_activity`; a temporary fixture drone is committed to exercise ON CONFLICT then removed in `finally`. Identity test changes roll back. Do not point fixture or concurrency tests at a production database.

No remote migrations, deployment, paid resource provisioning, backup, restore or production data mutation occurred. Use the run sequence in README to perform the pending database validation before treating this proposal as deployment-ready.
