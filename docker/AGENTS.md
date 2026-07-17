# Docker Agent Guide

This directory defines the canonical local deployment and baseline database schema.

## Key files

- `compose.yml`
  - Main development / local runtime stack
- `test-compose.yml`
  - Test stack template used by the test harness
- `structure.sql`
  - One-time database bootstrap only (`CREATE DATABASE` + `\c`). Runs once, ever, on first
    container boot; never re-run after that (`CREATE DATABASE` has no `IF NOT EXISTS`).
- `tables.sql`
  - Canonical schema, extensions, and seed data for fresh installs. Also re-run standalone by
    `tests/test_functions.py::reset_db()` on every test reset, so every statement in it must stay
    idempotent (`IF NOT EXISTS` etc.).
- `nginx/`
  - Frontend and API proxy configuration

## Working rules

- Treat `tables.sql` as the source of truth for schema for fresh installs; `structure.sql` should rarely need touching.
- Any schema change here normally also requires a new migration in `../migrations/`.
- Seeded capabilities and route allowlists for default users live in `tables.sql`; new authenticated routes or settings may require updates there.
- Be careful with port, host, and container-name changes: `tests/setup-test-env.py` rewrites parts of the compose setup for isolated test runs.
- Do not edit vendored TLS or backup files unless the change is explicitly about those artifacts.
