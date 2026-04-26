# Docker Agent Guide

This directory defines the canonical local deployment and baseline database schema.

## Key files

- `compose.yml`
  - Main development / local runtime stack
- `test-compose.yml`
  - Test stack template used by the test harness
- `structure.sql`
  - Canonical schema and seed data for fresh installs
- `nginx/`
  - Frontend and API proxy configuration

## Working rules

- Treat `structure.sql` as the source of truth for fresh installs.
- Any schema change here normally also requires a new migration in `../migrations/`.
- Seeded capabilities and route allowlists for default users live in `structure.sql`; new authenticated routes or settings may require updates there.
- Be careful with port, host, and container-name changes: `tests/setup-test-env.py` rewrites parts of the compose setup for isolated test runs.
- Do not edit vendored TLS or backup files unless the change is explicitly about those artifacts.
