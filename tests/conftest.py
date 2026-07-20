import subprocess
import pytest
import os
from pathlib import Path

from tests import test_functions as Tests

## VERY IMPORTANT to override the config file here
## otherwise it will automatically connect to non-test DB and delete all your real data
from lib.global_config import GlobalConfig
GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml")

# no proxies for internal requests to the dashboard and API
os.environ['NO_PROXY'] = f"{os.environ.get('NO_PROXY','')},api.green-coding.internal,metrics.green-coding.internal"
os.environ['no_proxy'] = f"{os.environ.get('no_proxy','')},api.green-coding.internal,metrics.green-coding.internal"

def pytest_collection_modifyitems(items):
    for item in items:
        if item.fspath.basename == 'test_functions.py':
            item.add_marker(pytest.mark.skip(reason='Skipping this file'))


# Note: This fixture runs always
# Pytest collects all fixtures before running any tests
# no matter which order they are loaded in
@pytest.fixture(autouse=True)
def setup_and_cleanup_test():
    GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml") # we want to do this globally for all tests
    yield
    Tests.reset_db()


### If you wish to turn off the above auto-cleanup per test, include the following in your
### test module:
# from conftest import cleanup_after_test
# @pytest.fixture(autouse=False)  # Set autouse to False to override the fixture
# def setup_and_cleanup_test():
#     pass


TEST_CONTAINERS = (
    'test-green-coding-gunicorn-container',
#    'test-green-coding-postgres-container', # not for now - too verbose
#    'test-green-coding-redis-container', # not for now - too verbose
)

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # pylint: disable=unused-argument
    outcome = yield
    report = outcome.get_result()
    if report.when == 'call' and report.failed:
        for container in TEST_CONTAINERS:
            try:
                logs = subprocess.check_output(
                    ['docker', 'logs', container, '--tail', '50'],
                    stderr=subprocess.STDOUT,
                    encoding='UTF-8',
                )
                report.sections.append((f'Docker logs ({container})', logs))
            except subprocess.CalledProcessError:
                pass


def pytest_sessionstart(session):  # pylint: disable=unused-argument
    tests_dir = Path(__file__).parent.resolve()
    cwd = Path.cwd().resolve()

    if cwd != tests_dir:
        pytest.exit(
            f"Tests must be run from {tests_dir}, but current dir is {cwd}"
        )
