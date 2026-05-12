# Green Metrics Tool - Agent Guide

This repository benchmarks the energy usage of other software, primarily through containerized measurement runs.
Use this file as the top-level map, and when you need to touch files in a subdirectory
read nearest `AGENTS.md` before making localized changes. Instructions in these files can override instructions from
this file.

## System Overview

Green Metrics Tool is itself a multi-service application with these main runtime pieces:

- PostgreSQL database
- NGINX webserver serving the frontend and reverse-proxying the API
- Gunicorn-hosted FastAPI application
- ScenarioRunner CLI entrypoint in `runner.py`
- Cron / helper scripts

The canonical local stack definition is `docker/compose.yml`.

## Read-Next Map

- `api/AGENTS.md`
  - FastAPI routers, request models, auth, and response-shape constraints
- `lib/AGENTS.md`
  - ScenarioRunner, job state machine, shared orchestration, and core helpers
- `cron/AGENTS.md`
  - Queue workers and operational maintenance scripts
- `frontend/AGENTS.md`
  - Static pages, vanilla JS wiring, and API/UI coupling
- `docker/AGENTS.md`
  - Compose stack, canonical schema, and seeded capabilities
- `metric_providers/AGENTS.md`
  - Provider contracts, parsing, and platform-specific sensor behavior
- `tests/AGENTS.md`
  - Test harness rules, setup scripts, and containerized test workflow

## Important Concepts

- Usage scenario syntax is enforced in `lib/schema_checker.py`.
- The system distinguishes Git / URL measurements from local folder measurements via `uri_type`.
- Many frontend tables consume positional SQL result arrays, so changing backend `SELECT` column order can silently break the UI.

## Cross-Directory Flows

### Measurement request lifecycle

1. Request enters through `api/`.
2. Validated input flows into `lib/job/` or directly into `lib/scenario_runner.py`.
3. ScenarioRunner executes workloads, metric collection, persistence, and post-processing.
4. `cron/` workers can execute queued jobs.
5. Results are consumed by `frontend/` pages and covered by `tests/`.

### Schema changes

1. Update `docker/structure.sql` first.
2. Add a forward-only migration in `migrations/` for existing deployments.
3. Check whether seeded user capabilities or route allowlists in `docker/structure.sql` also need updates.
4. Run or update tests that rely on `tests/setup-test-env.py`, which copies schema state into `tests/structure.sql`.

### User-facing request field changes

If a new field is visible to users, it often has to move through multiple layers:

1. `api/object_specifications.py`
2. relevant router in `api/`
3. `lib/job/` and/or `lib/scenario_runner.py`
4. `runner.py` if CLI support is required
5. `frontend/`
6. `tests/`

## Quick Commands

- Run a quick CLI measurement to check if the runner code is working:
  - first `cd docker && docker compose up -d`
  - then `python3 runner.py --uri /home/node/green-metrics-tool --filename tests/data/usage_scenarios/basic_stress.yml --dev-no-sleeps --dev-cache-build --skip-download-dependencies --skip-optimizations`
- Compile-check a Python file:
  - `python3 -m py_compile path/to/file.py`
