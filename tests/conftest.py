import subprocess
import pytest
import os
import logging
from pathlib import Path

from tests import test_functions as Tests
from lib.utils import get_test_worker_id

# lib/db.py's ConnectionPool is opened eagerly (open=True) the first time DB() is instantiated in
# each worker process, and psycopg_pool retries a failed connection attempt internally on its own
# (this is expected, self-healing behavior, not a real failure) - but it also logs every individual
# failed attempt via logging.getLogger("psycopg.pool") ("error connecting in 'pool-N': ...")
# regardless of whether the pool as a whole goes on to succeed a moment later. If that first
# DB()/pool creation in a worker lands while Postgres is still finishing its own boot/recovery (the
# same transient window tests/test_functions.py::reset_db() already retries around for its own
# subprocess psql calls), this log line goes to stderr and gets picked up by any test capturing
# output with redirect_stderr, failing an unrelated "no errors" assertion over a condition that
# already resolved itself. Since with_db_retry (lib/db.py) is this codebase's own retry/backoff
# layer and already prints its own actionable messages on genuine failures, psycopg_pool's internal
# per-attempt noise isn't needed here.
logging.getLogger('psycopg.pool').setLevel(logging.CRITICAL)

## VERY IMPORTANT to override the config file here
## otherwise it will automatically connect to non-test DB and delete all your real data
from lib.global_config import GlobalConfig
GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml")

# no proxies for internal requests to the dashboard and API
os.environ['NO_PROXY'] = f"{os.environ.get('NO_PROXY','')},api.green-coding.internal,metrics.green-coding.internal"
os.environ['no_proxy'] = f"{os.environ.get('no_proxy','')},api.green-coding.internal,metrics.green-coding.internal"

@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items):
    for item in items:
        if item.fspath.basename == 'test_functions.py':
            item.add_marker(pytest.mark.skip(reason='Skipping this file'))

    # Every test carrying the 'real-metric-providers' xdist_group is forced onto a single worker
    # (see the comment on pytestmark in tests/smoke_test.py) and, combined, they're one of the
    # longest-running chunks in the whole suite. pytest-xdist's loadgroup scheduler dispatches work
    # in roughly collection order, so if this group's tests are scattered late in that order, the
    # worker they land on doesn't start on them until well into the run - and since every other
    # worker finishes its own (shorter, ungrouped) tests long before that one worker gets through
    # its serialized group, that worker becomes the straggler the whole session waits on at the
    # end. Sorting the group to the very front means that worker starts on it immediately and runs
    # for the same duration everyone else does, instead of after. Stable sort preserves the
    # relative order within the group and among everything else.
    # trylast=True so this runs after tests/api/, tests/frontend/, tests/cron/'s own
    # pytest_collection_modifyitems hooks have already attached their own xdist_group markers.
    items.sort(key=lambda item: 0 if any(
        marker.name == 'xdist_group' and marker.kwargs.get('name') == 'real-metric-providers'
        for marker in item.iter_markers()
    ) else 1)


# Scenario-runner test containers are suffixed with this worker's xdist id (see
# lib/utils.py::container_name()), precisely so concurrent workers never collide on a name - but
# that same determinism means a container left running by an earlier crashed/interrupted run on
# this exact worker id (gw6, say) will collide with a brand new, unrelated run that happens to
# land on worker gw6 again: lib/scenario_runner.py::_check_running_containers_before_start()
# then refuses to proceed with "... is already running on system". Force-removing anything still
# running under this worker's suffix before the session's first test runs means every session
# starts from a clean slate regardless of how the previous one on this worker id ended.
@pytest.fixture(scope='session', autouse=True)
def _initial_container_cleanup():
    worker_id = get_test_worker_id()
    if not worker_id:
        return

    suffix = f'-{worker_id}'
    result = subprocess.run(
        ['docker', 'ps', '-a', '--format', '{{.Names}}'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, encoding='UTF-8',
    )
    for name in result.stdout.splitlines():
        if name.endswith(suffix):
            subprocess.run(['docker', 'rm', '-f', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


# Under pytest-xdist each worker gets its own private schema (gmt_test_gw001, gmt_test_gw002, ...)
# that doesn't exist at all until something creates it - only the boot-time default ('gmt_test',
# with no worker suffix) is populated with tables at container start. Without this, a worker's
# first test would run before setup_and_cleanup_test's own reset_db() ever fires (that one only
# runs at teardown), hitting a schema that doesn't exist yet and failing with
# 'relation "users" does not exist'; every test after the first would then pass, since teardown
# had created and populated it by then. session scope + autouse makes this run exactly once per
# worker, before that worker's first test.
@pytest.fixture(scope='session', autouse=True)
def _initial_db_reset():
    Tests.reset_db()


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
