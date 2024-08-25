import pytest
import subprocess

from lib.db import DB

## VERY IMPORTANT to override the config file here
## otherwise it will automatically connect to non-test DB and delete all your real data
from lib.global_config import GlobalConfig
GlobalConfig().override_config(config_name='test-config.yml')

def pytest_collection_modifyitems(items):
    for item in items:
        if item.fspath.basename == 'test_functions.py':
            item.add_marker(pytest.mark.skip(reason='Skipping this file'))

# should we hardcode test-db here?
@pytest.fixture(autouse=True)
def cleanup_after_test():
    yield
    DB().query('DROP schema "public" CASCADE')
    subprocess.run(
        ['docker', 'exec', '--user', 'postgres', 'test-green-coding-postgres-container', 'bash', '-c', 'psql --port 9573 < ./docker-entrypoint-initdb.d/structure.sql'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )


### If you wish to turn off the above auto-cleanup per test, include the following in your
### test module:
# from conftest import cleanup_after_test
# @pytest.fixture(autouse=False)  # Set autouse to False to override the fixture
# def cleanup_after_test():
#     pass
