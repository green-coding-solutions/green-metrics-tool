from contextlib import nullcontext as does_not_raise

import pytest
import re
import os
import platform

from runner import Runner
from lib.global_config import GlobalConfig
from lib.db import DB
from lib.system_checks import ConfigurationCheckError
from tests import test_functions as Tests

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')

test_data = [
   (True, f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml", does_not_raise()),
   (False, f"{os.path.dirname(os.path.realpath(__file__))}/test-config-extra-network-and-duplicate-psu-providers.yml", pytest.raises(ConfigurationCheckError)),
]

@pytest.mark.parametrize("skip_system_checks,config_file,expectation", test_data)
def test_check_system(skip_system_checks, config_file, expectation):

    GlobalConfig().override_config(config_location=config_file)
    runner = Runner(uri="not_relevant", uri_type="folder", skip_system_checks=skip_system_checks)

    try:
        with expectation:
            runner.check_system()
    finally:
        GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml") # reset, just in case. although done by fixture

def test_reporters_still_running():
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=False, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=False)
    runner2 = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=False, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=False)


    with Tests.RunUntilManager(runner) as context:

        context.run_until('setup_services')

        with Tests.RunUntilManager(runner2) as context2:

            with pytest.raises(Exception) as e:
                context2.run_until('import_metric_providers')

            expected_error = r'Another instance of the \w+ metrics provider is already running on the system!\nPlease close it before running the Green Metrics Tool.'
            assert re.match(expected_error, str(e.value)), Tests.assertion_info(expected_error, str(e.value))


def test_runner_can_use_different_user():
    USER_ID = 758932
    Tests.insert_user(USER_ID, "My bad password")
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, user_id=USER_ID)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')

    assert runner._user_id == USER_ID

def test_runner_run_invalidated():

    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True)

    run_id = runner.run()

    query = """
            SELECT id, invalid_run
            FROM runs
            WHERE id = %s
            """
    data = DB().fetch_one(query, (run_id,))

    assert data[0] == run_id

    if platform.system() == 'Darwin':
        assert data[1] == 'Measurements are not reliable as they are done on a Mac in a virtualized docker environment with high overhead and low reproducability.\nDevelopment switches or skip_system_checks were active for this run. This will likely produce skewed measurement data.\n'
    else:
        assert data[1] == 'Development switches or skip_system_checks were active for this run. This will likely produce skewed measurement data.\n'
