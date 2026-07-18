import os
import pytest

from lib.global_config import GlobalConfig
from tests import test_functions as Tests

# The frontend (Playwright) tests here drive the one shared gunicorn+nginx container. That
# container loaded its GlobalConfig (and therefore its DB target) once at process start and is
# never restarted mid-suite, so it always reads/writes the 'public' schema. Under pytest-xdist
# every test in this directory must therefore:
#   1. run on the same worker as every other test here (and tests/api/), one at a time
#      (xdist_group, shared with tests/api/conftest.py), and
#   2. target the 'public' schema itself, regardless of which physical worker it lands on.
# This overrides tests/conftest.py's fixture of the same name for everything under this directory.

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))

def pytest_collection_modifyitems(items):
    # pytest_collection_modifyitems is called once per session with the *complete* list of
    # collected items, regardless of which conftest.py defines it - so this must filter down to
    # only the items actually collected from this directory.
    for item in items:
        if str(item.fspath).startswith(CURRENT_DIR + os.sep):
            item.add_marker(pytest.mark.xdist_group(name="gunicorn"))

@pytest.fixture(autouse=True)
def setup_and_cleanup_test(monkeypatch):
    monkeypatch.delenv('PYTEST_XDIST_WORKER', raising=False)
    GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.dirname(os.path.realpath(__file__)))}/test-config.yml")
    yield
    Tests.reset_db()
