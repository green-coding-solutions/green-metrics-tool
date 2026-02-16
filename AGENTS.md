# Green Metrics Tool - Agent Guide

This file is a quick map for contributors and coding agents working in this repository.

## What This Software Does

Green Metrics Tool is a software suite that benchmarks energy usage of other containerized software.

It itself a fully containerzied software consisting out of five basic components
- A Postgresql database
- An NGINX webserver to serve a dashboard
- A gunicorn application server that hosts a FastAPI API to be served via the NGINX webserver as reverse proxy
- A CLI where the product *ScenarioRunner* can be excuted (via runner.py)
- Helper tools and scripts

All containers are defined in the `docker/compose.yml`

The suite encapsulates multiple products that have API endpoints and also CLI/Desktop App counterparts:

- ScenarioRunner
    - Is the benchmark runner to capture energy and machine metrics. Data can then be viewed and compared in the frontend
    - API defined in `api/scenario_runner.py`
    - CLI tool to be executed via `runner.py`
- Power HOG
    - API defined in `api/power_hog.py`
    - macOS Desktop app in different repository. Out of scope for now. Please ignore
- Eco CI
    - API defined in `api/eco_ci.py`
    - GitHub Action in different repository. Out of scope for now. Please ignore
- CarbonDB
    - API defined in `api/carbondb.py`
    - No direct CLI or Desktop App. All data comes from the API directly or via import from ScenarioRunner, Power HOG or Eco CI
    - Compression and COpy functions are in `cron/carbondb_*`

### Metric Providers

Metric providers which generate the metrics ingested by the Green Metrics Tool are in `metric_providers`.

They always consist out of three basic components:
- A source file (typically a C source file. But can also be a bash script if no need for a custom binary is present)
    - After compiling this file typically metric-provider-binary exists (if no bash script, as an alternative, exists)
- A Makefile (building the source if a source exists)
- `provider.py` file that specifies how metrics from the `metric-provider-binary` are ingested via Python into the database

All metrics the provider generate (if any) are always stored in `/tmp/green-metrics-tool/metrics/X` whereas X 
is the name if the provider. For Instance `cpu_frequency_sysfs_core.txt`. The name of the file is specified via the `metric_name`
variable in the `provider.py`

Furthermore a lot of shared functionality is handled by the base class in `metric_providers/base.py`

## Main Benchmarking flow for ScenarioRunner CLI

1. CLI `runner.py` is executed
2. `ScenarioRunner` checks out repositories, loads `usage_scenario.yml`, builds/runs workloads, records metrics.
3. Metric Provider files are ingested and stored in DB. Furthermore meta info from the run like machine info, free memory etc. is recored in DB
4. Phase Stats (`lib/phase_stats.py`) are generated
4. Optimizations run (`optimization_providers`)
5. View results in frontend dashboards.

## Main flow for adding jobs ScenarioRunner via API

1. Request enters via API:
   - `POST /v1/software/add` in `api/scenario_runner.py`
   - Validated by `Software` model in `api/object_specifications.py`
2. Job is created:
   - `Job.insert('run', ...)` in `lib/job/base.py`
3. Job processing:
   - `RunJob` in `lib/job/run.py`
   - instantiates `ScenarioRunner` in `lib/scenario_runner.py`
4. Measurement execution:
   - repository + relations checkout
   - scenario parsing and execution
   - metric collection/import
   - run + logs + stats persistence

## Main Benchmarking flow for ScenarioRunner jobs

1. Receiving a measurement request via API (see before)
2. Either executing job via `cron/client.py` which is called "cluster mode" or via `tools/jobs.py` which is called "job mode"
3. A waiting job is picked up by the jobs queue (code in `lib/job/run.py` with base class in `lib/job/base.py`)
4. A `ScenarioRunner` class is created and run with additions like Phase Stats (`lib/phase_stats.py`) and Optimizations (`optimization_providers`)
5. Results are stored in DB.
6. An optional email is sent to the user.
   

## Main API Flow for Eco CI

1. Request enters via API:
   - `POST /v3/ci/measurement/add` or `POST /v2/ci/measurement/add` in `api/eco_ci.py`
   - Validated by `CI_MeasurementBase` model in `api/object_specifications.py`
2. Entry in `ci_measurements` is created via SQL directly:
   - in `api/eco_ci.py` in the function `_insert_ci_measurement`

## Key Files and Folders

### Core Measurement Logic

- `lib/scenario_runner.py`
  - Main orchestration and measurement lifecycle.
  - Repository checkout (`_checkout_repository`) and relations checkout (`_checkout_relations`).
  - Run persistence and post-processing.
- `runner.py`
  - CLI entrypoint for local/manual runs.

### Jobs and Scheduling

- `lib/job/base.py`
  - Base job model, job selection, DB insert/get logic.
- `lib/job/run.py`
  - Processing logic for `run` jobs.
- `cron/`
  - Cluster-side loops/schedulers (including watchlist-triggered runs).

### API Layer

- `api/scenario_runner.py`
  - Main user-facing endpoints (jobs, runs, software add, timeline, etc.).
- `api/object_specifications.py`
  - Pydantic request/response input models.

### Frontend

- `frontend/runs.html`
    - Shows overview all of all stored ScenarioRunner runs in DB
- `frontend/stats.html`
    - Details page for a run showing all the metrics, machine information for a run, metric charts etc
- `frontend/compare.html`
    - Compate page to compare one or more runs
- `frontend/request.html`
    - Submit software form.
- `frontend/js/`
    - Respective JS codes for pages

### Database

- `docker/structure.sql`
  - Canonical schema used in docker/dev setup.
- `migrations/`
  - Incremental schema migrations for existing deployments.

### Tests

- `tests/cron/`
  - Job/cron/watchlist behavior tests.
- `tests/`
  - API and functional coverage.

### Helper Scripts
- All helper scripts lie in the `tools` folder. They are thought to be one-off and executed by a human user


## Common Change Paths

### Add a New Request Field (API -> Job -> Runner)

1. Add field to model in `api/object_specifications.py`.
2. Accept + sanitize field in endpoint (typically `api/scenario_runner.py`).
3. Persist in jobs table if needed:
   - Update `docker/structure.sql`
   - Add migration in `migrations/`
   - Update `lib/job/base.py` insert/select/object construction.
4. Pass into `ScenarioRunner` via `lib/job/run.py` (and optionally `runner.py` for CLI).
5. Add frontend form/input wiring in `frontend/request.html` + `frontend/js/request.js`.


## Operational Notes

- The system differentiates URL repositories (`uri_type='URL'`) from local folder runs (`uri_type='folder'`).
- Many job/run listings are consumed as positional arrays in frontend DataTables; changing SQL select column order can break UI.
- When modifying schema:
  - Update `docker/structure.sql`
  - Add a migration to `migration` folder

## Quick Commands

- Run CLI measurement:
  - `python3 runner.py --uri <repo-url-or-folder> --branch main`
- Compile check a Python file:
  - `python3 -m py_compile path/to/file.py`
- Run tests (if pytest available):
  - `pytest -q`
