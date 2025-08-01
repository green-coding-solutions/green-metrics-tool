from contextlib import nullcontext as does_not_raise

import pytest
import re
import os
import platform
import subprocess

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

def test_runner_run_invalidated():

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True)

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

def test_runner_with_glob_pattern_filename():
    """Test that runner works with glob pattern filenames like basic_*.yml"""
    # Test runner.py with glob pattern that matches multiple files, providing required variable
    ps = subprocess.run(
        ['python3', 'runner.py', '--uri', GMT_DIR, '--filename', 'tests/data/usage_scenarios/basic_*.yml',
         '--variables', '__GMT_VAR_COMMAND__=stress-ng',
         '--skip-system-checks', '--dev-cache-build', '--dev-no-sleeps', '--dev-no-metrics', '--dev-no-optimizations'],
        cwd=GMT_DIR,
        capture_output=True,
        text=True,
        check=False
    )

    assert ps.returncode == 0, f"Runner failed with stderr: {ps.stderr}"
    # Should see both files being processed
    assert 'tests/data/usage_scenarios/basic_stress.yml' in ps.stdout
    assert 'tests/data/usage_scenarios/basic_stress_with_variables.yml' in ps.stdout

def test_runner_with_multiple_filename_args():
    """Test that runner works with multiple --filename arguments"""
    # Test runner.py with multiple --filename arguments
    ps = subprocess.run(
        ['python3', 'runner.py', '--uri', GMT_DIR,
         '--filename', 'tests/data/usage_scenarios/basic_stress.yml',
         '--filename', 'tests/data/usage_scenarios/setup_commands_stress.yml',
         '--skip-system-checks', '--dev-cache-build', '--dev-no-sleeps', '--dev-no-metrics', '--dev-no-optimizations'],
        cwd=GMT_DIR,
        capture_output=True,
        text=True,
        check=False
    )

    assert ps.returncode == 0, f"Runner failed with stderr: {ps.stderr}"
    # Should see both files being processed
    assert 'tests/data/usage_scenarios/basic_stress.yml' in ps.stdout
    assert 'tests/data/usage_scenarios/setup_commands_stress.yml' in ps.stdout

def test_runner_with_iterations_and_multiple_files():
    """Test that runner processes files in correct order with --iterations"""
    # Test runner.py with multiple files and iterations=2
    ps = subprocess.run(
        ['python3', 'runner.py', '--uri', GMT_DIR,
         '--filename', 'tests/data/usage_scenarios/basic_stress.yml',
         '--filename', 'tests/data/usage_scenarios/setup_commands_stress.yml',
         '--iterations', '2',
         '--skip-system-checks', '--dev-cache-build', '--dev-no-sleeps', '--dev-no-metrics', '--dev-no-optimizations'],
        cwd=GMT_DIR,
        capture_output=True,
        text=True,
        check=False
    )

    assert ps.returncode == 0, f"Runner failed with stderr: {ps.stderr}"
    # Should see each file processed twice (2 iterations)
    assert ps.stdout.count('tests/data/usage_scenarios/basic_stress.yml') == 2
    assert ps.stdout.count('tests/data/usage_scenarios/setup_commands_stress.yml') == 2

def test_runner_filename_pattern_no_match_error():
    """Test that runner fails gracefully when filename pattern matches no files"""
    # Test runner.py with pattern that matches no files
    ps = subprocess.run(
        ['python3', 'runner.py', '--uri', GMT_DIR,
         '--filename', 'tests/data/usage_scenarios/nonexistent_*.yml',
         '--skip-system-checks'],
        cwd=GMT_DIR,
        capture_output=True,
        text=True,
        check=False
    )

    assert ps.returncode == 1, "Runner should fail when no files match pattern"
    assert 'No valid files found for --filename pattern' in ps.stdout
