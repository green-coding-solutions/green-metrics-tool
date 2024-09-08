import pytest

from tests import test_functions as Tests

## VERY IMPORTANT to override the config file here
## otherwise it will automatically connect to non-test DB and delete all your real data
from lib.global_config import GlobalConfig
GlobalConfig().override_config(config_name='test-config.yml')

def pytest_collection_modifyitems(items):
    for item in items:
        if item.fspath.basename == 'test_functions.py':
            item.add_marker(pytest.mark.skip(reason='Skipping this file'))


# Note: This fixture runs always
# Pytest collects all fixtures before running any tests
# no matter which order they are loaded in
@pytest.fixture(autouse=True)
def cleanup_after_test():
    yield
    Tests.reset_db()


### If you wish to turn off the above auto-cleanup per test, include the following in your
### test module:
# from conftest import cleanup_after_test
# @pytest.fixture(autouse=False)  # Set autouse to False to override the fixture
# def cleanup_after_test():
#     pass
