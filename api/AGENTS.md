# API Agent Guide

This directory contains the FastAPI application and the product-specific routers.

## Entry points

- `main.py`
  - Creates the FastAPI app
  - Registers exception middleware and CORS
  - Includes routers conditionally based on config feature flags
- `scenario_runner.py`
  - Main user-facing ScenarioRunner routes such as jobs, runs, software submission, timeline, compare, artifacts
- `eco_ci.py`, `power_hog.py`, `carbondb.py`
  - Product-specific APIs
- `object_specifications.py`
  - Pydantic request and response models
- `api_helpers.py`
  - Shared response helpers, auth helpers, comparison helpers, and route utilities

## Working rules

- Prefer adding or updating typed request models in `object_specifications.py` instead of parsing raw bodies inline.
- Most authenticated routes use `Depends(authenticate)` and must filter data by visible users unless the route is intentionally public.
- Keep response shapes stable. Several frontend pages consume positional arrays directly from SQL-backed responses.
- If you add a new authenticated route, check whether the seeded route allowlist in `docker/structure.sql` also needs to include it.
- If a new API field affects queued measurements, trace it through `api/ -> lib/job/ -> lib/scenario_runner.py -> frontend/`.

## Validation and error handling

- Global request validation and exception logging are centralized in `main.py`.
- Reuse `HTTPException` for user-correctable API errors and reserve generic exceptions for real server failures.
- Be careful with request logging and authentication tokens; existing middleware already obfuscates auth headers before logging.
