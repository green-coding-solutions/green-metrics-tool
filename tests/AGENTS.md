# Tests Agent Guide

This directory contains the integration and unit-style test harness for the repository.

## Important behavior

- Run pytest from `tests/`, not the repository root. `tests/conftest.py` exits the session if the working directory is wrong.
- `setup-test-env.py` prepares `test-config.yml`, `test-compose.yml`, and the frontend test config. `test-compose.yml` mounts `docker/00-test-schema.sql` first, followed by `docker/structure.sql`/`docker/tables.sql`/`docker/seed-data.sql`, directly into the test postgres container - there is no `tests/`-local copy to regenerate.
- `conftest.py` overrides `GlobalConfig` to the test config and resets the DB between tests.

## Useful commands

- First-time setup:
  - `cd tests && python3 setup-test-env.py`
- Start test containers:
  - `cd tests && ./start-test-containers.sh -d`
- Run a smoke test:
  - `cd tests && pytest -q smoke_test.py`
- Never run the full test suite, but always run targeted tests or files:
  - e.g. for single test `cd tests && pytest test_usage_scenario.py::test_labels_allow_unsafe_true`
  - e.g. for full test `cd tests && pytest test_usage_scenario.py`

## Working rules

- Schema changes in `docker/tables.sql` are only applied when a test schema is created (no copy step). `create_test_schema()` in `test_functions.py` skips a schema that already exists, and `reset_db()` only TRUNCATEs the tables and re-runs `docker/seed-data.sql`. So drop the existing test schemas (or recreate the test postgres container) to pick up schema changes. Seeded-capability changes in `docker/seed-data.sql` are picked up on every reset.
- Cron behavior belongs in `tests/cron/`; API behavior belongs in `tests/api/`; provider parsing belongs in `tests/metric_providers/`.
- Many tests assume the dockerized test environment is already running. If a test interacts with the API, DB, or runner end-to-end, verify the container prerequisite first.
