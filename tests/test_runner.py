from contextlib import nullcontext as does_not_raise

import io
import pytest
import re
import os
import platform
import subprocess

from contextlib import redirect_stdout, redirect_stderr

from lib.scenario_runner import ScenarioRunner
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
    runner = ScenarioRunner(uri="not_relevant", uri_type="folder", skip_system_checks=skip_system_checks)

    try:
        with expectation:
            runner.check_system()
    finally:
        GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml") # reset, just in case. although done by fixture

def test_check_broken_variable_format():

    with pytest.raises(ValueError) as e:
        ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, usage_scenario_variables={'Wrong': "1"})

    assert str(e.value) == 'Usage Scenario variable (Wrong) has invalid name. Format must be __GMT_VAR_[\\w]+__ - Example: __GMT_VAR_EXAMPLE__'

def test_check_variable_no_replacement_found():

    with pytest.raises(ValueError) as e:
        runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, usage_scenario_variables={'__GMT_VAR_VALID__': "1"})
        runner.run()

    assert str(e.value) == "Usage Scenario Variable '__GMT_VAR_VALID__' does not exist in usage scenario. Did you forget to add it?"

def test_usage_scenario_variable_leftover():

    with pytest.raises(RuntimeError) as e:
        runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress_with_variables.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True)
        runner.run()

    assert str(e.value) == "Unreplaced leftover variables are still in usage_scenario: ['__GMT_VAR_COMMAND__']. Please add variables when submitting run."

def test_usage_scenario_variable_replacement_done_correctly():

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress_with_variables.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, usage_scenario_variables={'__GMT_VAR_COMMAND__': "stress-ng"})

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')

    assert runner._usage_scenario['flow'][0]['commands'][0]['command'] == 'stress-ng -c 1 -t 1 -q'

def test_reporters_still_running():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=False, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=False)
    runner2 = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=False, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=False)


    with Tests.RunUntilManager(runner) as context:

        context.run_until('setup_services')

        with Tests.RunUntilManager(runner2) as context2:

            with pytest.raises(Exception) as e:
                context2.run_until('import_metric_providers')

            expected_error = r'Another instance of the \w+ metrics provider is already running on the system!\nPlease close it before running the Green Metrics Tool.'
            assert re.match(expected_error, str(e.value)), Tests.assertion_info(expected_error, str(e.value))

def test_template_website():
    ps = subprocess.run(
        ['bash', '../run-template.sh', 'website', 'https://www.google.de', '--quick', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml"],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert ps.returncode == 0
    assert 'MEASUREMENT SUCCESSFULLY COMPLETED' in ps.stdout
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)


def test_runner_can_use_different_user():
    USER_ID = 758932
    Tests.insert_user(USER_ID, "My bad password")
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, user_id=USER_ID)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')

    assert runner._user_id == USER_ID

@pytest.fixture
def delete_and_create_temp_file():
    file_path = f"{GMT_DIR}/THIS_IS_A_TEST_FILE_FROM_A_UNIT_TESTS_DELETE_ME"

    with open(file_path, "w", encoding='utf-8') as f:
        f.write("Hello, world!")

    yield

    os.unlink(file_path)

def test_runner_dirty_dir(delete_and_create_temp_file): #pylint: disable=unused-argument, redefined-outer-name

    out = io.StringIO()
    err = io.StringIO()

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=False, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True)

    with redirect_stdout(out), redirect_stderr(err), Tests.RunUntilManager(runner) as context:
        context.run_until('import_metric_providers')

    assert 'The GMT directory contains untracked or changed files - These changes will not be stored and it will be hard to understand possible changes when comparing the measurements later. We recommend only running on a clean dir.' in out.getvalue()

def test_runner_run_invalidated():

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True)

    run_id = runner.run()

    query = """
            SELECT message
            FROM warnings
            WHERE run_id = %s
            ORDER BY created_at DESC
            """
    data = DB().fetch_all(query, (run_id,))

    messages = [d[0] for d in data]

    if platform.system() == 'Darwin':
        assert 'Measurements are not reliable as they are done on a Mac in a virtualized docker environment with high overhead and low reproducability.\n' in messages
        assert any('Development switches or skip_system_checks were active for this run.' in msg for msg in messages)
    else:
        assert 'Development switches or skip_system_checks were active for this run. This will likely produce skewed measurement data.\n' in messages
