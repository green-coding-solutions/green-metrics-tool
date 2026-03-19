import pytest
import os
from pathlib import Path

from tests import test_functions as Tests

PARALLEL_SAFE_FILES = {
    'api/test_api_helpers.py',
    'lib/test_diff.py',
    'lib/test_email_helpers.py',
    'lib/test_save_notes.py',
    'lib/test_schema_checker.py',
    'metric_providers/test_metric_provider_functions.py',
    'test_internal_sanity.py',
    'test_yml_parsing.py',
}

PARALLEL_SAFE_NODEID_PREFIXES = (
    'lib/test_container_compatibility.py::TestArchitectureCompatibility::TestUnitTests::',
    'lib/test_container_compatibility.py::TestNativeCompatibility::',
    'lib/test_container_compatibility.py::TestPlatformCompatibilityStatus::TestUnitTests::',
    'lib/test_db.py::TestWithDbRetryDecorator::',
)

## VERY IMPORTANT to override the config file here
## otherwise it will automatically connect to non-test DB and delete all your real data
from lib.global_config import GlobalConfig
GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml")

# no proxies for internal requests to the dashboard and API
os.environ['NO_PROXY'] = f"{os.environ.get('NO_PROXY','')},api.green-coding.internal,metrics.green-coding.internal"
os.environ['no_proxy'] = f"{os.environ.get('no_proxy','')},api.green-coding.internal,metrics.green-coding.internal"

def pytest_configure(config):
    config.addinivalue_line('markers', 'parallel_safe: test does not touch shared DB/Docker/browser state')
    config.addinivalue_line('markers', 'serial: test touches shared state and must stay on one worker')

def _is_parallel_safe(item):
    if item.get_closest_marker('serial'):
        return False

    if item.get_closest_marker('parallel_safe'):
        return True

    if item.nodeid.startswith(PARALLEL_SAFE_NODEID_PREFIXES):
        return True

    return item.nodeid.split('::', 1)[0] in PARALLEL_SAFE_FILES

def pytest_collection_modifyitems(items):
    for item in items:
        if item.fspath.basename == 'test_functions.py':
            item.add_marker(pytest.mark.skip(reason='Skipping this file'))
            continue

        if _is_parallel_safe(item):
            item.add_marker(pytest.mark.parallel_safe)
            continue

        item.add_marker(pytest.mark.serial)
        item.add_marker(pytest.mark.xdist_group(name='shared_state'))


# Note: This fixture runs always
# Pytest collects all fixtures before running any tests
# no matter which order they are loaded in
@pytest.fixture(autouse=True)
def setup_and_cleanup_test(request):
    GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml") # we want to do this globally for all tests
    yield
    if request.node.get_closest_marker('parallel_safe'):
        return
    Tests.reset_db()


### If you wish to turn off the above auto-cleanup per test, include the following in your
### test module:
# from conftest import cleanup_after_test
# @pytest.fixture(autouse=False)  # Set autouse to False to override the fixture
# def setup_and_cleanup_test():
#     pass


def pytest_sessionstart(session):  # pylint: disable=unused-argument
    tests_dir = Path(__file__).parent.resolve()
    cwd = Path.cwd().resolve()

    if cwd != tests_dir:
        pytest.exit(
            f"Tests must be run from {tests_dir}, but current dir is {cwd}"
        )
