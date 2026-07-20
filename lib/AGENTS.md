# Lib Agent Guide

`lib/` contains the core orchestration and shared implementation used by the CLI, API, cron workers, and tests.

## Key files

- `scenario_runner.py`
  - Main measurement lifecycle, repository checkout, workload execution, provider startup, persistence, cleanup, and post-processing
- `job/base.py`
  - Queue selection, state transitions, DB persistence, and job object construction
- `job/run.py`
  - Run-job execution wrapper around ScenarioRunner
- `schema_checker.py`
  - Validation rules for `usage_scenario.yml`
- `metric_importer.py`
  - Imports provider output into DB structures
- `phase_stats.py`
  - Computes phase-level summaries after a run
- `db.py`, `global_config.py`, `user.py`
  - Shared infrastructure used almost everywhere

## Working rules

- Treat `ScenarioRunner` as the canonical measurement pipeline. Avoid duplicating its logic in API or cron code.
- Do not casually reorder or remove cleanup / post-processing steps in `ScenarioRunner`; those steps guard persistence and cleanup after partial failures.
- When adding arguments to `ScenarioRunner` beware that if they contain sensitive information they must be pruned from `self._arguments` at the end of the `__init__()``
- When adding fields that must survive from API submission to execution, update `job/base.py`, `job/run.py`, and `runner.py` together.
- Tests override config through `tests/conftest.py`; avoid hard-coding production config assumptions.
- `lib/c/` and `lib/sgx-software-enable/` contain native build artifacts and helpers. Only touch them if the change actually affects native behavior or installation.

## Common pitfalls

- Job state changes are part of a queue state machine; preserve the `WAITING -> RUNNING -> FINISHED/FAILED` semantics unless you are intentionally changing workflow behavior.
- Many helpers are imported widely. Small signature changes here can create broad regressions, so verify impact with targeted tests.
