"""
Benchmark for the async/threading fix in api/*.py (routes converted from blocking
`async def` to plain `def` so Starlette dispatches them through its AnyIO thread pool
instead of running them inline on the event loop).

Not part of the normal test suite: this file is deliberately NOT named `test_*.py`, so
plain `pytest` runs (tests/run-tests.sh, CI's default `gmt-pytest` action) never collect
it. Run it explicitly, on request, from the `tests/` directory with the test containers up:

    pytest api/benchmark_api_concurrency.py -v -s

`-s` is required to see the printed report; pytest captures stdout otherwise.

What it measures: a batch of GET requests against a real, DB-backed endpoint, once fired
serially and once fired concurrently from a thread pool. If routes block the event loop
(the bug this benchmark guards against), concurrent wall time collapses to roughly the
serial wall time - one request has to finish before the next one on that worker can even
start. If routes are properly offloaded, concurrent wall time drops well below serial,
bounded only by the DB connection pool (lib/db.py) and worker count (docker/startup_gunicorn.sh).
"""
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from lib.global_config import GlobalConfig

API_URL = GlobalConfig().config['cluster']['api_url']  # will be pre-loaded with test-config.yml due to conftest.py

# DB-backed, side-effect-free, cheap to call repeatedly.
BENCHMARK_ENDPOINT = '/v1/machines'
HEADERS = {'X-Authentication': 'DEFAULT'}

REQUEST_COUNT = int(os.environ.get('BENCHMARK_REQUEST_COUNT', 40))
WARMUP_REQUESTS = 5

# Loose on purpose: real parallelism is capped by the DB pool (max_size=2 per worker,
# lib/db.py) and worker count (8, docker/startup_gunicorn.sh), so we're not expecting a
# clean N-times speedup - just a speedup clearly above 1.0, which is what a fully
# serialized (blocked event loop) API would produce.
MIN_EXPECTED_SPEEDUP = 1.5


def _timed_get():
    start = time.monotonic()
    response = requests.get(f"{API_URL}{BENCHMARK_ENDPOINT}", timeout=30, headers=HEADERS)
    elapsed = time.monotonic() - start
    assert response.status_code == 200, response.text
    return elapsed


def _run_serial(count):
    start = time.monotonic()
    latencies = [_timed_get() for _ in range(count)]
    total = time.monotonic() - start
    return total, latencies


def _run_concurrent(count):
    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=count) as executor:
        latencies = list(executor.map(lambda _: _timed_get(), range(count)))
    total = time.monotonic() - start
    return total, latencies


def _report(label, total, latencies):
    print(f"\n{label}")
    print(f"  requests:      {len(latencies)}")
    print(f"  total time:    {total:.3f}s")
    print(f"  mean latency:  {statistics.mean(latencies) * 1000:.1f}ms")
    print(f"  median latency:{statistics.median(latencies) * 1000:.1f}ms")
    print(f"  max latency:   {max(latencies) * 1000:.1f}ms")


def test_concurrent_requests_are_faster_than_serial():
    # Warm up connections/pools so the first-connection cost doesn't skew either phase.
    for _ in range(WARMUP_REQUESTS):
        _timed_get()

    serial_total, serial_latencies = _run_serial(REQUEST_COUNT)
    concurrent_total, concurrent_latencies = _run_concurrent(REQUEST_COUNT)

    speedup = serial_total / concurrent_total

    _report('Serial', serial_total, serial_latencies)
    _report('Concurrent', concurrent_total, concurrent_latencies)
    print(f"\nSpeedup (serial / concurrent): {speedup:.2f}x")
    print(f"Endpoint: {BENCHMARK_ENDPOINT}, requests per phase: {REQUEST_COUNT}\n")

    assert speedup >= MIN_EXPECTED_SPEEDUP, (
        f"Concurrent requests were only {speedup:.2f}x faster than serial "
        f"(expected >= {MIN_EXPECTED_SPEEDUP}x). This is the signature of an API route "
        f"blocking the event loop again - check for `async def` routes in api/ that call "
        f"blocking code (e.g. DB()) directly instead of being plain `def`."
    )
