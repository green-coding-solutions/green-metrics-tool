# Cron Agent Guide

This directory contains worker entrypoints and maintenance scripts intended for cron or systemd-style execution.

## Key files

- `client.py`
  - Long-running cluster worker that continuously pulls work
- `jobs.py`
  - One-off queue processor for job mode
- `watchlist.py`
  - Watchlist-triggered scheduling logic
- `carbondb_compress.py`, `carbondb_copy_over_and_remove_duplicates.py`
  - CarbonDB maintenance tasks
- `backfill_*`
  - Historical data repair or enrichment scripts

## Working rules

- Keep queue ownership in `lib/job/`; cron entrypoints should orchestrate or schedule, not reimplement job state logic.
- Changes to scheduling semantics usually need matching updates in `tests/cron/`.
- These scripts are operational entrypoints, so argument handling, logging, and failure behavior matter more than in ordinary helper modules.
- Prefer forward-compatible changes because these scripts may be deployed as long-running services rather than invoked ad hoc.
