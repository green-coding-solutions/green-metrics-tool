# Metric Providers Agent Guide

This directory contains measurement providers that collect raw metrics for ScenarioRunner.

## Layout

Most providers follow this pattern:

- a source file or script that captures raw metrics
- a `Makefile` if compilation is required
- a `provider.py` that subclasses `BaseMetricProvider` or a specialized provider base

Representative shared files:

- `base.py`
  - Provider lifecycle, health checks, process control, CSV loading, sampling-rate validation, and dataframe validation
- `container.py`, `cgroup.py`
  - Specialized provider bases for container and cgroup providers

## Working rules

- Keep provider contracts compatible with `BaseMetricProvider`: timestamps must be monotonic, values must parse cleanly, and per-series timestamps must be unique.
- `provider.py` is the ingestion boundary. Raw scripts or binaries should emit predictable output that the provider can validate.
- If you add a provider, also check config wiring in `config.yml.example` and any tests or fixtures that enumerate providers.
- Many providers are platform-specific. Preserve existing Linux vs macOS assumptions and skip checks unless you are intentionally broadening support.
- Avoid touching large embedded model or data assets in the XGBoost PSU subtree unless the task is specifically about that model.
