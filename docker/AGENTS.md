# Docker Agent Guide

This directory defines the canonical local deployment and baseline database schema.

## Key files

- `compose.yml`
  - Main development / local runtime stack
- `test-compose.yml`
  - Test stack template used by the test harness
- `00-test-schema.sql`
  - Test-only (mounted via compose.yml.example's `#TEST-ONLY#` volume line). Creates the `gmt_test`
    schema before `structure.sql`/`tables.sql`/`seed-data.sql` run, so their unqualified
    DDL/DML - resolved through the test postgres container's `PGOPTIONS` search_path - lands in
    `gmt_test` instead of silently falling back to `public` (Postgres skips schemas in
    `search_path` that don't exist yet when picking the target for unqualified object creation).
- `structure.sql`
  - One-time database bootstrap only (`CREATE DATABASE` + `\c`). Runs once, ever, on first
    container boot; never re-run after that (`CREATE DATABASE` has no `IF NOT EXISTS`).
- `tables.sql`
  - Canonical schema and extensions for fresh installs. Runs once per database, and in tests once per
    test schema (`tests/test_functions.py::create_test_schema()` skips it when the schema already exists).
    It is never re-run on an existing schema, so its statements do not need `IF NOT EXISTS`.
- `seed-data.sql`
  - Seed data for a freshly created schema. Re-run by `tests/test_functions.py::reset_db()` on every
    test reset, after all tables have been TRUNCATEd. Every statement must therefore work on empty
    tables, but does not need to tolerate already existing rows.
- `nginx/`
  - Frontend and API proxy configuration
- `frontend-image/`
  - Prebuilt frontend image `greencoding/gmt-frontend`, built and pushed by
    `.github/workflows/build-and-push-frontend-image.yml`. Its nginx config is derived from
    `nginx/frontend.conf.example` at build time. `40-gmt-frontend-config.sh` fills
    `frontend/js/helpers/config.js.example` from `GMT_*` env vars at container start, unless a
    `config.js` is mounted. A new placeholder in `config.js.example` must also be added there,
    otherwise the container refuses to start (`test-image.sh` catches this in CI).
- `postgres-image/`
  - Prebuilt database image `greencoding/gmt-postgres`, built by the same workflow. It copies
    `structure.sql`, `tables.sql` and `seed-data.sql` into `/docker-entrypoint-initdb.d` with the
    same file names and server flags as `compose.yml.example`. Keep both in sync when changing init
    files or postgres flags there.

## Working rules

- Treat `tables.sql` as the source of truth for schema for fresh installs; `structure.sql` should rarely need touching.
- Any schema change here normally also requires a new migration in `../migrations/`.
- Seeded capabilities and route allowlists for default users live in `tables.sql`; new authenticated routes or settings may require updates there.
- Be careful with port, host, and container-name changes: `tests/setup-test-env.py` rewrites parts of the compose setup for isolated test runs.
- Do not edit vendored TLS or backup files unless the change is explicitly about those artifacts.
