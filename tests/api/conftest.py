import os
import pytest

from lib.global_config import GlobalConfig
from tests import test_functions as Tests

# The API tests here talk to the one shared gunicorn container over HTTP. That container
# loaded its GlobalConfig (and therefore its DB target) once at process start and is never
# restarted mid-suite, so it always reads/writes the unsuffixed 'gmt_test' schema (get_test_schema()
# falls back to it whenever PYTEST_XDIST_WORKER is unset). Under pytest-xdist every test in this
# directory must therefore:
#   1. run on the same worker as every other test here, one at a time (xdist_group), and
#   2. target that same unsuffixed 'gmt_test' schema itself, regardless of which physical worker
#      it lands on.
# This overrides tests/conftest.py's fixture of the same name for everything under this directory.

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))

def pytest_collection_modifyitems(items):
    # pytest_collection_modifyitems is called once per session with the *complete* list of
    # collected items, regardless of which conftest.py defines it - so this must filter down to
    # only the items actually collected from this directory.
    for item in items:
        if str(item.fspath).startswith(CURRENT_DIR + os.sep):
            item.add_marker(pytest.mark.xdist_group(name="gunicorn"))

# tests/conftest.py::_initial_db_reset already creates a schema once per worker process - but it
# does so using *this* worker's real PYTEST_XDIST_WORKER id, before the monkeypatch below ever gets
# a chance to run. Whichever worker this xdist_group happens to land on, its _initial_db_reset call
# therefore creates and populates that worker's own suffixed schema (e.g. 'gmt_test_gw3'), not the
# unsuffixed 'gmt_test' one gunicorn actually reads/writes - so without this, the first test here
# would TRUNCATE-and-reseed a 'gmt_test' schema that was never created, silently falling through
# search_path into 'public' instead (already seeded at container boot) and colliding with its
# existing id=1 user. create_test_schema() is idempotent, so this is safe to call regardless of
# whether 'gmt_test' happens to already exist (e.g. a non-parallel run with no worker id at all).
@pytest.fixture(scope='session', autouse=True)
def _initial_gunicorn_schema_setup():
    # monkeypatch is function-scoped and can't be used from a session-scoped fixture, so this
    # saves/restores the env var by hand instead.
    saved_worker_id = os.environ.pop('PYTEST_XDIST_WORKER', None)
    try:
        Tests.create_test_schema()
    finally:
        if saved_worker_id is not None:
            os.environ['PYTEST_XDIST_WORKER'] = saved_worker_id

@pytest.fixture(autouse=True)
def setup_and_cleanup_test(monkeypatch):
    monkeypatch.delenv('PYTEST_XDIST_WORKER', raising=False)
    GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.dirname(os.path.realpath(__file__)))}/test-config.yml")
    yield
    Tests.reset_db()
