# Cattle monitoring database design

**Provider selected: Supabase.** The deployed provider-specific migrations, Auth/Storage integration and runtime verification are in [supabase/README.md](../supabase/README.md). The standalone files below remain the original design reference; do not apply both migration sets to the same database.

Recommend PostgreSQL 16+ with PostGIS 3.x, private object storage, and asynchronous ingestion. This is a standalone database proposal, not an application implementation. No existing stack is replaced. Migrations have **not** been applied to a database; see [verification](VERIFICATION.md) for the exact checks performed.

Start with [design and assumptions](DESIGN.md), [ER diagram](ERD.md), [data dictionary](DATA_DICTIONARY.md), [operations](OPERATIONS.md), [sample payloads](examples/ingestion.json), and [website queries](queries/website.sql).

The user requested inspection, assumptions, design and migration artifacts. The supplied context document was used as a design brief: its working assumptions are not promoted to confirmed facts. The mockup is visual guidance, not evidence that the models support its health categories or that the example counts, battery values, or coverage percentages exist.

## Repository inspection

Inspected `holycow_git`, its README, ignore rules, tracked/untracked file inventory, surrounding workspace, `databases.txt`, and the supplied context and screenshot. No applicable AGENTS.md was found. The repository contained only `README.md` (`# holycow`) and a generic Visual Studio `.gitignore`. No application, provider, auth integration, ORM, migrations, dependencies, or tests exist. The ignore file alone does not establish a .NET/SQL Server stack. Git status was read using a command-scoped safe-directory exception; global Git settings were not changed.

No PostgreSQL client/server, PostgreSQL service, Docker, or Podman was found in PATH or the conventional install locations inspected. No remote service was contacted for migration, resource creation, or deployment.

## Artifacts and order

1. `migrations/001_core.sql`: extensions, core tables, constraints, indexes.
2. `migrations/002_policy_views.sql`: deployment role groups, RLS, append-only guards, publication checks, current views.
3. `tests/fixture.sql`: sparse, synthetic data; disposable databases only.
4. `tests/verify.sql`: assertions under the proposed application role groups and prepared-query smoke checks, then rollback.
5. `tests/concurrency.py`: two competing sessions for retry uniqueness and identity edit serialization; fixture-only cleanup.

For an explicitly chosen **disposable local** database, provision PostGIS-enabled PostgreSQL and use the migration administrator connection. The administrator needs extension installation, role creation, schema creation, and the ability to SET ROLE. Fixture setup needs BYPASSRLS/superuser to seed both tenants. Runtime logins must have neither privilege. Names `cattle_*` must be unused or deliberately mapped before migration; roles are cluster-wide.

```powershell
# Set this yourself to a disposable local DB. Scripts have no default DSN.
$env:CATTLE_TEST_DSN = 'postgresql://local-test-admin@localhost/cattle_design_test'
psql $env:CATTLE_TEST_DSN -X -v ON_ERROR_STOP=1 -f database/migrations/001_core.sql
psql $env:CATTLE_TEST_DSN -X -v ON_ERROR_STOP=1 -f database/migrations/002_policy_views.sql
psql $env:CATTLE_TEST_DSN -X -v ON_ERROR_STOP=1 -f database/tests/fixture.sql
psql $env:CATTLE_TEST_DSN -X -v ON_ERROR_STOP=1 -f database/tests/verify.sql
# Install psycopg 3 in an isolated test environment, then:
python database/tests/concurrency.py
```

Run from the repository root. Check each process exit code before continuing. Do not paste DSNs containing credentials into logs or shell history. This design includes no destructive down migration. Versioned forward repair or verified restore is the recovery path.

To repeat the static parse checks, install `pglast` in a separate validation environment and run `python database/tools/check_artifacts.py`. This checks syntax and structural consistency, not PostgreSQL execution or performance.
