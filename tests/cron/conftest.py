import os
import pytest

from lib.global_config import GlobalConfig
from tests import test_functions as Tests

# Only test_carbondb_compress.py in this directory talks to the shared gunicorn container over
# HTTP (via API_URL, e.g. POST /v2/carbondb/add) and then asserts on the result with its own
# direct DB() calls - test_client.py/test_jobs.py/test_watchlist.py are plain DB-only tests with
# no relationship to that container, so they're deliberately left out of this treatment below to
# keep their normal per-worker parallelism. That container loaded its GlobalConfig (and therefore
# its DB target) once at process start and is never restarted mid-suite, so it always reads/writes
# the unsuffixed 'gmt_test' schema (get_test_schema() falls back to it whenever PYTEST_XDIST_WORKER
# is unset). Under pytest-xdist, test_carbondb_compress.py's tests must therefore:
#   1. run on the same worker as every other test that shares the shared container (tests/api/,
#      tests/frontend/), one at a time (xdist_group, shared with their conftest.py files), and
#   2. target that same unsuffixed 'gmt_test' schema itself, regardless of which physical worker
#      it lands on - otherwise a direct DB().fetch_one() here would read from this worker's own
#      gmt_test_gwN schema while the HTTP POST landed in the container's unsuffixed 'gmt_test'
#      schema, and never find the row it just inserted.

CARBONDB_TEST_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'test_carbondb_compress.py')

def pytest_collection_modifyitems(items):
    # pytest_collection_modifyitems is called once per session with the *complete* list of
    # collected items, regardless of which conftest.py defines it - so this must filter down to
    # only the items actually collected from this one file.
    for item in items:
        if str(item.fspath) == CARBONDB_TEST_FILE:
            item.add_marker(pytest.mark.xdist_group(name="gunicorn"))

@pytest.fixture(autouse=True)
def setup_and_cleanup_test(request, monkeypatch):
    if str(request.node.fspath) == CARBONDB_TEST_FILE:
        monkeypatch.delenv('PYTEST_XDIST_WORKER', raising=False)
    GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.dirname(os.path.realpath(__file__)))}/test-config.yml")
    yield
    Tests.reset_db()
