# https://docs.docker.com/engine/reference/commandline/port/
# List port mappings or a specific mapping for the container
#  docker port CONTAINER [PRIVATE_PORT[/PROTO]]

import io
import os
import re
import subprocess
import json

GMT_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../'))

from contextlib import redirect_stdout, redirect_stderr
import pytest
import yaml

from lib.db import DB
from lib import utils
from lib.global_config import GlobalConfig
from tests import test_functions as Tests
from lib.scenario_runner import ScenarioRunner
from lib.schema_checker import SchemaError

## Note:
# Always do asserts after try:finally: blocks
# otherwise failing Tests will not run the runner.cleanup() properly


# This function runs the runner up to and *including* the specified step
#pylint: disable=redefined-argument-from-local
### The Tests for usage_scenario configurations

# environment: [object] (optional)
# Key-Value pairs for ENV variables inside the container

def get_env_vars():
    ps = subprocess.run(
        ['docker', 'exec', 'test-container', '/bin/sh',
        '-c', 'env'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    env_var_output = ps.stdout
    return env_var_output

def test_env_variable_allowed_characters():

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/env_vars_stress_allowed.yml', skip_unsafe=False, skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')

        env_var_output = get_env_vars()

        assert 'TESTALLOWED=alpha-num123_' in env_var_output, Tests.assertion_info('TESTALLOWED=alpha-num123_', env_var_output)
        assert 'TEST1_ALLOWED=alpha-key-num123_' in env_var_output, Tests.assertion_info('TEST1_ALLOWED=alpha-key-num123_', env_var_output)
        assert 'TEST2_ALLOWED=http://localhost:8080' in env_var_output, Tests.assertion_info('TEST2_ALLOWED=http://localhost:8080', env_var_output)
        assert 'TEST3_ALLOWED=example.com' in env_var_output, Tests.assertion_info('TEST3_ALLOWED=example.com', env_var_output)

# Test too long values
def test_env_variable_too_long():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/env_vars_stress_forbidden.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "- value of environment var 'TEST_TOO_LONG' is too long 1025 (max allowed length is 1024) - Maybe consider using --allow-unsafe or --skip-unsafe" == str(e.value), Tests.assertion_info("Env var value is too long", str(e.value))

# Test skip_unsafe=true
def test_env_variable_skip_unsafe_true():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/env_vars_stress_forbidden.yml', skip_unsafe=True, skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        env_var_output = get_env_vars()

    # Only allowed values should be in env vars, forbidden ones should be skipped
    assert 'TEST_ALLOWED' in env_var_output, Tests.assertion_info('TEST_ALLOWED in env vars', env_var_output)
    assert 'TEST_TOO_LONG' not in env_var_output, Tests.assertion_info('TEST_TOO_LONG not in env vars', env_var_output)

# Test allow_unsafe=true
def test_env_variable_allow_unsafe_true():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/env_vars_stress_forbidden.yml', allow_unsafe=True, skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        env_var_output = get_env_vars()

    # Both allowed and forbidden values should be in env vars
    assert 'TEST_ALLOWED' in env_var_output, Tests.assertion_info('TEST_ALLOWED in env vars', env_var_output)
    assert 'TEST_TOO_LONG' in env_var_output, Tests.assertion_info('TEST_TOO_LONG in env vars', env_var_output)

# labels: [object] (optional)
# Key-Value pairs for labels on the container

def get_labels():
    ps = subprocess.run(
        ['docker', 'inspect', 'test-container'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8',
    )
    labels = json.loads(ps.stdout)[0].get('Config', {}).get('Labels', {})
    return labels

def test_labels_allowed_characters():

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/labels_stress_allowed.yml', skip_unsafe=False, skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        labels = get_labels()

        assert labels.get('TESTALLOWED') == 'alpha-num123_', Tests.assertion_info('TESTALLOWED label', labels)
        assert labels.get('test.label') == 'example.com', Tests.assertion_info('test.label label', labels)
        assert labels.get('OTHER_LABEL') == 'http://localhost:8080', Tests.assertion_info('OTHER_LABEL label', labels)

def test_labels_too_long():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/labels_stress_forbidden.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "- value of label 'LABEL_TOO_LONG' is too long 1075 (max allowed length is 1024) - Maybe consider using --allow-unsafe or --skip-unsafe" == str(e.value), Tests.assertion_info('Label value is too long', str(e.value))

def test_labels_skip_unsafe_true():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/labels_stress_forbidden.yml', skip_unsafe=True, skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        labels = get_labels()

    assert 'LABEL_ALLOWED' in labels, Tests.assertion_info('LABEL_ALLOWED in labels', labels)
    assert 'LABEL_TOO_LONG' not in labels, Tests.assertion_info('LABEL_TOO_LONG not in labels', labels)

def test_labels_allow_unsafe_true():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/labels_stress_forbidden.yml', allow_unsafe=True, skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        labels = get_labels()

    assert 'LABEL_ALLOWED' in labels, Tests.assertion_info('LABEL_ALLOWED in labels', labels)
    assert 'LABEL_TOO_LONG' in labels, Tests.assertion_info('LABEL_TOO_LONG in labels', labels)

# ports: [int:int] (optional)
# Docker container portmapping on host OS to be used with --allow-unsafe flag.

def get_port_bindings():
    ps = subprocess.run(
            ['docker', 'port', 'test-container', '9018'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
    port = ps.stdout
    err = ps.stderr
    return port, err

def test_port_bindings_allow_unsafe_true():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/port_bindings_stress.yml', allow_unsafe=True, skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        port, _ = get_port_bindings()

    assert port.startswith('0.0.0.0:9017'), Tests.assertion_info('0.0.0.0:9017', port)

def test_port_bindings_skip_unsafe_true():
    out = io.StringIO()
    err = io.StringIO()
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/port_bindings_stress.yml', skip_unsafe=True, skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    # need to catch exception here as otherwise the subprocess returning an error will
    # fail the test
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')
            _, docker_port_err = get_port_bindings()

            expected_container_error = 'Error: No public port \'9018/tcp\' published for test-container\n'
            assert docker_port_err == expected_container_error, \
                Tests.assertion_info(f"Container Error: {expected_container_error}", docker_port_err)
    expected_warning = 'Found ports entry but not running in unsafe mode. Skipping'
    assert expected_warning in out.getvalue(), \
        Tests.assertion_info(f"Warning: {expected_warning}", 'no/different warning')

def test_port_bindings_no_skip_or_allow():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/port_bindings_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(Exception) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')
            _, docker_port_err = get_port_bindings()
            expected_container_error = 'Error: No public port \'9018/tcp\' published for test-container\n'
            assert docker_port_err == expected_container_error, \
                Tests.assertion_info(f"Container Error: {expected_container_error}", docker_port_err)
    expected_error = 'Found "ports" but neither --skip-unsafe nor --allow-unsafe is set'
    assert expected_error == str(e.value), \
        Tests.assertion_info(f"Exception: {expected_error}", str(e.value))

def test_compose_include_not_same_dir():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/parentdir_compose_include/subdir/usage_scenario_fail.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=False)

    out = io.StringIO()
    err = io.StringIO()


    with redirect_stdout(out), redirect_stderr(err), pytest.raises(ValueError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('import_metric_providers')
    assert str(e.value).startswith('Included compose file "../compose.yml" may only be in the same directory as the usage_scenario file as otherwise relative context_paths and volume_paths cannot be mapped anymore') , \
        Tests.assertion_info('Root directory escape', str(e.value))

def test_context_include():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/subdir_parent_context/subdir/usage_scenario_ok.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=False)

    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('import_metric_providers')
    # will not throw an exception

def test_context_include_escape():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/subdir_parent_context/subdir/usage_scenario_fail.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=False)

    out = io.StringIO()
    err = io.StringIO()


    with redirect_stdout(out), redirect_stderr(err), pytest.raises(ValueError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')
    assert str(e.value).startswith('../../../../../../ must not be in folder above root repo folder') , \
        Tests.assertion_info('Root directory escape', str(e.value))

def test_include_overwrites_string_values():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/overwrite_string_from_include.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=False)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('import_metric_providers')

    assert runner._usage_scenario['name'] == 'Name overwritten'
    assert runner._usage_scenario['author'] == 'Author overwritten'
    assert runner._usage_scenario['description'] == 'Description as is'

def test_include_overwrites_string_values_even_if_top_include():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/overwrite_string_from_include_even_if_top.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=False)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('import_metric_providers')

    assert runner._usage_scenario['name'] == 'Name overwritten'
    assert runner._usage_scenario['author'] == 'Author overwritten'
    assert runner._usage_scenario['description'] == 'Description as is'


def test_unsupported_compose():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/unsupported_compose.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=False)

    with pytest.raises(SchemaError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('import_metric_providers')
    assert str(e.value) == 'Your compose file does contain a key that GMT does not support - Please check if the container will still run as intended. If you want to ignore this error you can add the attribute `ignore-unsupported-compose: true` to your usage_scenario.yml\nError: ["Wrong key \'blkio_config\' in {\'image\': \'alpine\', \'blkio_config\': {\'weight\': 300}}"]'

def test_skip_unsupported_compose():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/skip_unsupported_compose.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=False)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('import_metric_providers')

# setup-commands: [array] (optional)
# Array of commands to be run before actual load testing.
# uses ps -a to check that sh is process with PID 1
def test_setup_commands_one_command():
    out = io.StringIO()
    err = io.StringIO()
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/setup_commands_noop.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    assert 'Running command:  docker exec test-container sh -c ps -a' in out.getvalue(), \
        Tests.assertion_info('stdout message: Running command: docker exec  ps -a', out.getvalue())
    assert '1 root      0:00 /bin/sh' in out.getvalue(), \
        Tests.assertion_info('container stdout showing /bin/sh as process 1', 'different message in container stdout')

def test_setup_commands_multiple_commands():
    out = io.StringIO()
    err = io.StringIO()
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/setup_commands_multiple_noop.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        runner.run()

    assert 'Running command:  docker exec test-container ps -a' in out.getvalue()
    assert 'hello world' in out.getvalue()
    assert 'goodbye world' in out.getvalue()

def assert_order(text, first, second):
    index1 = text.find(first)
    index2 = text.find(second)

    assert index1 != -1 and index2 != -1, \
        Tests.assertion_info(f"stdout contain the container names '{first}' and '{second}'.", \
                             f"stdout doesn't contain '{first}' and/or '{second}'.")

    assert index1 < index2, Tests.assertion_info(f'{first} should start first, \
                             because it is a dependency of {second}.', f'{second} started first')

# depends_on: [array] (optional)
# Array of container names to express dependencies
def test_depends_on_order():
    out = io.StringIO()
    err = io.StringIO()
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/depends_on.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    # Expected order: test-container-2, test-container-4, test-container-3, test-container-1
    assert_order(out.getvalue(), 'test-container-2', 'test-container-4')
    assert_order(out.getvalue(), 'test-container-4', 'test-container-3')
    assert_order(out.getvalue(), 'test-container-3', 'test-container-1')


def test_depends_on_huge():
    out = io.StringIO()
    err = io.StringIO()
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/depends_on_huge.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    # For test-container-20
    assert_order(out.getvalue(), 'test-container-16', 'test-container-20')
    assert_order(out.getvalue(), 'test-container-15', 'test-container-20')

    # For test-container-19
    assert_order(out.getvalue(), 'test-container-14', 'test-container-19')
    assert_order(out.getvalue(), 'test-container-13', 'test-container-19')

    # For test-container-18
    assert_order(out.getvalue(), 'test-container-12', 'test-container-18')
    assert_order(out.getvalue(), 'test-container-11', 'test-container-18')

    # For test-container-17
    assert_order(out.getvalue(), 'test-container-10', 'test-container-17')
    assert_order(out.getvalue(), 'test-container-9', 'test-container-17')

    # For test-container-16
    assert_order(out.getvalue(), 'test-container-8', 'test-container-16')
    assert_order(out.getvalue(), 'test-container-7', 'test-container-16')

    # For test-container-15
    assert_order(out.getvalue(), 'test-container-6', 'test-container-15')
    assert_order(out.getvalue(), 'test-container-5', 'test-container-15')

    # For test-container-14
    assert_order(out.getvalue(), 'test-container-4', 'test-container-14')

    # For test-container-13
    assert_order(out.getvalue(), 'test-container-3', 'test-container-13')

    # For test-container-12
    assert_order(out.getvalue(), 'test-container-2', 'test-container-12')

    # For test-container-11
    assert_order(out.getvalue(), 'test-container-1', 'test-container-11')

    # For test-container-10
    assert_order(out.getvalue(), 'test-container-4', 'test-container-10')

    # For test-container-9
    assert_order(out.getvalue(), 'test-container-3', 'test-container-9')

    # For test-container-8
    assert_order(out.getvalue(), 'test-container-2', 'test-container-8')

    # For test-container-7
    assert_order(out.getvalue(), 'test-container-1', 'test-container-7')

    # For test-container-6
    assert_order(out.getvalue(), 'test-container-4', 'test-container-6')

    # For test-container-5
    assert_order(out.getvalue(), 'test-container-3', 'test-container-5')

    # For test-container-4
    assert_order(out.getvalue(), 'test-container-2', 'test-container-4')

    # For test-container-3
    assert_order(out.getvalue(), 'test-container-1', 'test-container-3')

    # For test-container-2
    assert_order(out.getvalue(), 'test-container-1', 'test-container-2')

def test_depends_on_error_not_running():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/depends_on_error_not_running.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "State check of dependent services of 'test-container-1' failed! Container 'test-container-2' is not running but 'exited' after waiting for 10 sec! Consider checking your service configuration, the entrypoint of the container or the logs of the container." == str(e.value) , \
        Tests.assertion_info("State check of dependent services of 'test-container-1' failed! Container 'test-container-2' is not running but 'exited' after waiting for 10 sec! Consider checking your service configuration, the entrypoint of the container or the logs of the container.", str(e.value))

def test_depends_on_error_cyclic_dependency():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/depends_on_error_cycle.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "Cycle found in depends_on definition with service 'test-container-1'!" == str(e.value) , \
        Tests.assertion_info("Cycle found in depends_on definition with service 'test-container-1'!", str(e.value))

def test_depends_on_error_unsupported_condition():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/depends_on_error_unsupported_condition.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    message = 'Unsupported condition in healthcheck for service \'test-container-1\': service_completed_successfully'
    assert message == str(e.value) , \
        Tests.assertion_info(message, str(e.value))

def test_depends_on_long_form():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/depends_on_long_form.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    message = 'Container state of dependent service'
    assert message in out.getvalue(), \
        Tests.assertion_info(message, out.getvalue())

def test_depends_on_with_custom_container_name():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/depends_on_custom_container_name.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    message = 'Container state of dependent service \'test-service-2\': running'
    assert message in out.getvalue(), Tests.assertion_info(message, out.getvalue())

def test_depends_on_healthcheck_using_interval():
    # Test setup: Container has a startup time of 3 seconds, interval is set to 1s, retries is set to a number bigger than 3.
    # Container should become healthy after 3 seconds.
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/healthcheck_using_interval.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    message = 'Container health of dependent service \'test-container-2\': healthy'
    assert message in out.getvalue(), Tests.assertion_info(message, out.getvalue())

def test_depends_on_healthcheck_using_start_interval():
    # Using start_interval is preferable (available since Docker Engine version 25)
    # Test setup: Container has a startup time of 3 seconds, start_interval is set to 1s, start_period to 5s
    # Container should become healthy after 3 seconds.
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/healthcheck_using_start_interval.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    message = """
Container state of dependent service 'test-container-2': running
Container health of dependent service 'test-container-2': starting
Container health of dependent service 'test-container-2': starting
"""
    assert message in out.getvalue(), Tests.assertion_info(message, out.getvalue())

    message = """
Container health of dependent service 'test-container-2': healthy
"""
    assert message in out.getvalue(), Tests.assertion_info(message, out.getvalue())

def test_depends_on_healthcheck_missing_start_period():
    # Test setup: Container would be healthy after 3 seconds, however, no start_period is set (default 0s), therefore start_interval is not used.
    # Because max waiting time is configured to be 5s (test_config.yml), exception is raised after 5s.
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/healthcheck_missing_start_period.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    expected_exception = "Health check of dependent services of 'test-container-1' failed! Container 'test-container-2' is not healthy but 'starting' after waiting for 10 sec"
    assert str(e.value).startswith(expected_exception),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

def test_depends_on_healthcheck_error_missing():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/healthcheck_error_missing.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(RuntimeError) as e:
        runner.run()

    expected_exception = "Health check for service 'test-container-2' was requested by 'test-container-1', but service has no healthcheck implemented!"
    assert str(e.value).startswith(expected_exception),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

def test_depends_on_healthcheck_error_container_unhealthy():
    # Test setup: Healthcheck test will never be successful, interval is set to 1s and retries to 3.
    # Container should become unhealthy after 3-4 seconds.
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/healthcheck_error_container_unhealthy.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    expected_exception = 'Health check of container "test-container-2" failed terminally with status "unhealthy" after'

    assert str(e.value).startswith(expected_exception) or str(e.value).startswith(expected_exception),\
        Tests.assertion_info(f"Exception: {expected_exception} or {expected_exception}", str(e.value))

def test_depends_on_healthcheck_error_max_waiting_time():
    # Test setup: Container would be healthy after 7 seconds, however, interval is set to 100s and there is no start interval.
    # Because max waiting time is configured to be 10s (test_config.yml), the healthcheck at 10s will never be executed.
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/healthcheck_error_max_waiting_time.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    expected_exception = "Health check of dependent services of 'test-container-1' failed! Container 'test-container-2' is not healthy but 'starting' after waiting for 10 sec"
    assert str(e.value).startswith(expected_exception),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

def test_network_created():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/network_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_networks')
        ps = subprocess.run(
            ['docker', 'network', 'ls'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        ls = ps.stdout
    assert 'gmt-test-network' in ls, Tests.assertion_info('gmt-test-network', ls)

def test_container_is_in_network():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/network_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        ps = subprocess.run(
            ['docker', 'network', 'inspect', 'gmt-test-network'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        inspect = ps.stdout
    assert 'test-container' in inspect, Tests.assertion_info('test-container', inspect)

def test_network_alias_added():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/network_alias.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert 'Adding network alias test-alias for network gmt-test-network in service test-container' in out.getvalue()
    docker_run_command = re.search(r"docker run with: (.*)", out.getvalue()).group(1)
    assert '--network-alias test-alias' in docker_run_command



def test_cmd_entrypoint():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/test_docker_compose_entrypoint.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()

    o = out.getvalue()
    assert '--entrypoint echo alpine_gmt_run_tmp A $0 echo B $0' in o
    assert '--entrypoint env alpine_gmt_run_tmp env' in o
    assert '--entrypoint env alpine_gmt_run_tmp -h' in o
    assert '--entrypoint echo alpine_gmt_run_tmp A $0 echo B $0' in o
    assert 'alpine_gmt_run_tmp ash -c env' in o
    assert 'alpine_gmt_run_tmp env' in o
    assert 'alpine_gmt_run_tmp echo $0' in o
    assert 'alpine_gmt_run_tmp echo $$0' in o
    assert '--entrypoint echo alpine_gmt_run_tmp $0' in o
    assert '--entrypoint echo alpine_gmt_run_tmp A $0' in o
    assert 'alpine_gmt_run_tmp echo $0' in o

    assert err.getvalue() == '', Tests.assertion_info('stderr should be empty', err.getvalue())

# command: [str] (optional)
#    Command to be executed when container is started.
#    When container does not have a daemon running typically a shell
#    is started here to have the container running like bash or sh
def test_cmd_ran():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/cmd_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        ps = subprocess.run(
            ['docker', 'exec', 'test-container', 'ps', '-a'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        docker_ps_out = ps.stdout
    assert '1 root      0:00 sh' in docker_ps_out, Tests.assertion_info('1 root      0:00 sh', docker_ps_out)

# entrypoint: [str] (optional)
#    entrypoint declares the default entrypoint for the service container.
#    This overrides the ENTRYPOINT instruction from the service's Dockerfile.
#    If the entrypoint is empty, the ENTRYPOINT instruction is ignored.
def test_entrypoint_ran_with_script():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/entrypoint_script.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        ps = subprocess.run(
            ['docker', 'exec', 'test-container', 'ps', '-a'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        docker_ps_out = ps.stdout
    assert 'stress-ng' not in docker_ps_out, Tests.assertion_info('`stress-ng` should not be in ps output, as it should have been overwritten', docker_ps_out)
    assert 'entrypoint-overwrite.sh' in docker_ps_out, Tests.assertion_info('entrypoint `entrypoint-overwrite.sh` in ps output', docker_ps_out)
    assert 'tail -f /dev/null' in docker_ps_out, Tests.assertion_info('entrypoint `tail -f /dev/null` in ps output', docker_ps_out)

def test_entrypoint_ran_in_conjunction_with_command():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/entrypoint_with_command.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        ps = subprocess.run(
            ['docker', 'exec', 'test-container', 'ps', '-a'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        docker_ps_out = ps.stdout
    assert 'stress-ng' not in docker_ps_out, Tests.assertion_info('`stress-ng` should not be in ps output, as it should have been overwritten', docker_ps_out)
    assert 'tail -f /dev/null' in docker_ps_out, Tests.assertion_info('`tail -f /dev/null` in ps output', docker_ps_out)

def test_entrypoint_empty():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/entrypoint_empty.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')
            ps = subprocess.run(
                ['docker', 'exec', 'test-container', 'ps', '-a'],
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='UTF-8'
        )
        docker_ps_out = ps.stdout
    docker_run_command = re.search(r"docker run with: (.*)", str(out.getvalue())).group(1)
    assert '--entrypoint= ' in docker_run_command, f"--entrypoint= not found in docker run command: {docker_run_command}"
    assert 'stress-ng' not in docker_ps_out, Tests.assertion_info('`stress-ng` should not be in ps output, as it should have been ignored', docker_ps_out)
    assert 'tail -f /dev/null' in docker_ps_out, Tests.assertion_info('command `tail -f /dev/null` in ps output', docker_ps_out)


### The Tests for the runner options/flags
## --uri URI
#   The URI to get the usage_scenario.yml from. Can be either a local directory starting with
#     / or a remote git repository starting with http(s)://
def test_uri_local_dir():
    run_name = 'test_' + utils.randomword(12)
    filename = 'tests/data/stress-application/usage_scenario.yml'
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', GMT_DIR ,'--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
        '--filename', filename,
        '--skip-system-checks', '--dev-no-sleeps', '--dev-cache-build', '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    filename_in_db = utils.get_run_data(run_name)['filename']
    assert filename_in_db == filename, Tests.assertion_info(f"filename: {filename}", filename_in_db)
    uri_in_db = utils.get_run_data(run_name)['uri']
    assert uri_in_db == GMT_DIR, Tests.assertion_info(f"uri: {GMT_DIR}", uri_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

def test_uri_local_dir_missing():
    runner = ScenarioRunner(uri='/tmp/missing', uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(FileNotFoundError) as e:
        runner.run()


    expected_exception = f"[Errno 2] No such file or directory: '{os.path.realpath('/tmp/missing')}'"

    assert expected_exception == str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

    # basic positive case
def test_uri_github_repo():
    uri = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    filename = 'usage_scenario.yml'
    run_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', uri ,'--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
        '--skip-system-checks', '--dev-no-sleeps', '--dev-cache-build', '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    filename_in_db = utils.get_run_data(run_name)['filename']
    assert filename_in_db == filename, Tests.assertion_info(f"filename: {filename}", filename_in_db)
    uri_in_db = utils.get_run_data(run_name)['uri']
    assert uri_in_db == uri, Tests.assertion_info(f"uri: {uri}", uri_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

## --branch BRANCH
#    Optionally specify the git branch when targeting a git repository
def test_uri_local_branch():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', branch='test-branch', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(RuntimeError) as e:
        runner.run()
    expected_exception = 'Specified --branch but using local URI. Did you mean to specify a github url?'
    assert str(e.value) == expected_exception, \
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

    # basic positive case, branch prepped ahead of time
    # this branch has a different usage_scenario file name - basic_stress
    # that makes sure that it really is pulling a different branch
def test_uri_github_repo_branch():
    uri = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    run_name = 'test_' + utils.randomword(12)
    branch = 'test-branch'
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', uri ,
        '--branch', branch , '--filename', 'basic_stress.yml',
        '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml", '--skip-system-checks', '--dev-no-sleeps', '--dev-cache-build', '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    branch_in_db = utils.get_run_data(run_name)['branch']
    assert branch_in_db == 'test-branch', Tests.assertion_info(f"branch: {branch}", branch_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

    # should throw error, assert vs error
    # give incorrect branch name
    ## Is the expected_exception OK or should it have a more graceful error?
    ## ATM this is just the default console error of a failed git command
def test_uri_github_repo_branch_missing():
    runner = ScenarioRunner(uri='https://github.com/green-coding-solutions/pytest-dummy-repo', uri_type='URL', branch='missing-branch', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with pytest.raises(subprocess.CalledProcessError) as e:
        runner.run()
    expected_exception = f"Command '['git', 'clone', '--depth', '1', '-b', 'missing-branch', '--single-branch', '--recurse-submodules', '--shallow-submodules', 'https://github.com/green-coding-solutions/pytest-dummy-repo', '{os.path.realpath('/tmp/green-metrics-tool/repo')}']' returned non-zero exit status 128."
    assert expected_exception == str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

# #   --name NAME
# #    A name which will be stored to the database to discern this run from others
def test_name_is_in_db():
    run_name = 'test_' + utils.randomword(12)
    subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', GMT_DIR ,
        '--filename', 'tests/data/stress-application/usage_scenario.yml',
        '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
        '--skip-system-checks', '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations', '--dev-no-sleeps', '--dev-cache-build'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    name_in_db = utils.get_run_data(run_name)['name']
    assert name_in_db == run_name, Tests.assertion_info(f"name: {run_name}", name_in_db)

# --filename FILENAME
#    An optional alternative filename if you do not want to use "usage_scenario.yml"
    # basic positive case
def test_different_filename():
    run_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', GMT_DIR , '--filename', 'tests/data/usage_scenarios/basic_stress.yml', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
        '--skip-system-checks', '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations', '--dev-no-sleeps', '--dev-cache-build'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    with open('data/usage_scenarios/basic_stress.yml', 'r', encoding='utf-8') as f:
        usage_scenario_contents = yaml.safe_load(f)
    usage_scenario_in_db = utils.get_run_data(run_name)['usage_scenario']
    assert usage_scenario_in_db == usage_scenario_contents,\
        Tests.assertion_info(usage_scenario_contents, usage_scenario_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

# if that filename is missing...
def test_different_filename_missing():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='I_do_not_exist.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    with pytest.raises(FileNotFoundError) as e:
        runner.run()

    # we cannot use == here as file paths will differ throughout systems
    expected_exception = "[Errno 2] No such file or directory"
    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

    expected_exception_2 = "I_do_not_exist.yml"
    assert expected_exception_2 in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception_2}", str(e.value))


#   Check that default is to leave the files
def test_no_file_cleanup():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)
    runner.run()

    assert os.path.exists('/tmp/green-metrics-tool'), \
        Tests.assertion_info('tmp directory exists', os.path.exists('/tmp/green-metrics-tool'))

#   Check that the temp dir is deleted when using --file-cleanup
#   This option exists only in CLI mode
def test_file_cleanup():
    subprocess.run(
        ['python3', '../runner.py', '--uri', GMT_DIR , '--filename', 'tests/data/usage_scenarios/basic_stress.yml',
         '--file-cleanup', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml", '--skip-system-checks', '--dev-no-sleeps', '--dev-cache-build', '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    assert not os.path.exists('/tmp/green-metrics-tool'), \
        Tests.assertion_info('tmp directory exists', not os.path.exists('/tmp/green-metrics-tool'))

#pylint: disable=unused-variable
def test_skip_and_allow_unsafe_both_true():

    with pytest.raises(RuntimeError) as e:
        ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True, skip_unsafe=True, allow_unsafe=True)
    expected_exception = 'Cannot specify both --skip-unsafe and --allow-unsafe'
    assert str(e.value) == expected_exception, Tests.assertion_info('', str(e.value))

def test_debug(monkeypatch):
    monkeypatch.setattr('sys.stdin', io.StringIO('Enter'))
    ps = subprocess.run(
        ['python3', '../runner.py', '--uri', GMT_DIR , '--filename', 'tests/data/usage_scenarios/basic_stress.yml',
         '--debug',
         '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml", '--skip-system-checks',
          '--dev-no-sleeps', '--dev-cache-build', '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    expected_output = 'Initial load complete. Waiting to start metric providers'
    assert expected_output in ps.stdout, \
        Tests.assertion_info(expected_output, 'no/different output')

    # providers are not started at the same time, but with 2 second delay
    # there is a note added when it starts "Booting {metric_provider}"
    # can check for this note in the DB and the notes are about 2s apart

def test_read_detached_process_no_exit():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/stress_detached_no_exit.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    assert 'setting to a 1 min, 40 secs run per stressor' in out.getvalue(), \
        Tests.assertion_info('setting to a 1 min, 40 secs run per stressor', out.getvalue())
    assert 'successful run completed' not in out.getvalue(), \
        Tests.assertion_info('NOT successful run completed', out.getvalue())

def test_read_detached_process_after_exit():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/stress_detached_exit.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    assert 'successful run completed' in out.getvalue(), \
        Tests.assertion_info('successful run completed', out.getvalue())

def test_read_detached_process_failure():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/stress_detached_failure.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()
    # TODO: Move this again to "Process '['docker', 'exec', 'test-container', 'g4jiorejf']' had bad returncode: 127. Stderr: ; Detached process: True. Please also check the stdout in the logs and / or enable stdout logging to debug further." once GitHub Actions has updated docker. See https://github.com/green-coding-solutions/green-metrics-tool/issues/1128
    assert "Process '['docker', 'exec', 'test-container', 'g4jiorejf']' had bad returncode: 12" in str(e.value), \
        Tests.assertion_info("Process '['docker', 'exec', 'test-container', 'g4jiorejf']' had bad returncode: 12", str(e.value))

def test_invalid_container_name():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/invalid_container_name.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(OSError) as e:
        runner.run()

    expected_exception = "Docker run failed\nStderr: docker: Error response from daemon: Invalid container name (highload-api-:cont), only [a-zA-Z0-9][a-zA-Z0-9_.-] are allowed"
    assert expected_exception in str(e.value), \
        Tests.assertion_info(expected_exception, str(e.value))

def test_invalid_container_name_2():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/invalid_container_name_2.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(OSError) as e:
        runner.run()

    expected_exception = "Docker run failed\nStderr: docker: Error response from daemon: Invalid container name (8zhfiuw:-3tjfuehuis), only [a-zA-Z0-9][a-zA-Z0-9_.-] are allowed"
    assert expected_exception in str(e.value), \
        Tests.assertion_info(expected_exception, str(e.value))

def test_duplicate_container_name():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/duplicate_container_name.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(SchemaError) as e:
        runner.run()
    assert "Container name 'number-1' was already used. Please choose unique container names." == str(e.value), \
        Tests.assertion_info("Container name 'number-1' was already used. Please choose unique container names.", str(e.value))

def test_empty_container_name():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/empty_container_name.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(SchemaError) as e:
        runner.run()
    assert "Key 'container_name' error:\nNone should be instance of 'str'" == str(e.value), \
        Tests.assertion_info("Key 'container_name' error:\nNone should be instance of 'str'", str(e.value))


def test_none_container_name():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/none_container_name.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(SchemaError) as e:
        runner.run()
    assert "Key 'container_name' error:\nNone should be instance of 'str'" == str(e.value), \
        Tests.assertion_info("Key 'container_name' error:\nNone should be instance of 'str'", str(e.value))

def test_empty_phase_name():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/empty_phase_name.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(SchemaError) as e:
        runner.run()
    assert "Key 'name' error:\nValue cannot be empty" == str(e.value), \
        Tests.assertion_info("Key 'name' error:\nValue cannot be empty", str(e.value))


def test_invalid_phase_name():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/invalid_phase_name.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(SchemaError) as e:
        runner.run()
    assert "Key 'name' error:\n'This phase is / not ok!' does not match '^[\\\\.\\\\s0-9a-zA-Z_\\\\(\\\\)-]+$'" == str(e.value), \
        Tests.assertion_info("Key 'name' error:\n'This phase is / not ok!' does not match '^[\\\\.\\\\s0-9a-zA-Z_\\\\(\\\\)-]+$'", str(e.value))

def test_invalid_phase_name_runtime():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/invalid_phase_name_runtime.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(SchemaError) as e:
        runner.run()

    assert "Key 'name' error:\n'[RUNTIME]' does not match '^[\\\\.\\\\s0-9a-zA-Z_\\\\(\\\\)-]+$'" == str(e.value), \
        Tests.assertion_info("Key 'name' error:\n'[RUNTIME]' does not match '^[\\\\.\\\\s0-9a-zA-Z_\\\\(\\\\)-]+$'", str(e.value))

def test_duplicate_phase_name():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/duplicate_phase_name.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()
    assert "The 'name' field in 'flow' must be unique. 'This phase is ok' was already used." == str(e.value), \
        Tests.assertion_info("The 'name' field in 'flow' must be unique. 'This phase is ok' was already used.", str(e.value))


def test_failed_pull_does_not_trigger_cli():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/invalid_image.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()

    assert 'Docker pull failed. Is your image name correct and are you connected to the internet: 1j98t3gh4hih8723ztgifuwheksh87t34gt' == str(e.value), \
        Tests.assertion_info('Docker pull failed. Is your image name correct and are you connected to the internet: 1j98t3gh4hih8723ztgifuwheksh87t34gt', str(e.value))

def test_failed_pull_does_not_trigger_cli_with_build_on():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/invalid_image.yml', skip_system_checks=True, dev_cache_build=False, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()

    assert 'Docker pull failed. Is your image name correct and are you connected to the internet: 1j98t3gh4hih8723ztgifuwheksh87t34gt' == str(e.value), \
        Tests.assertion_info('Docker pull failed. Is your image name correct and are you connected to the internet: 1j98t3gh4hih8723ztgifuwheksh87t34gt', str(e.value))

def test_non_git_root_supplied():
    runner = ScenarioRunner(uri=f"{GMT_DIR}/tests/data/usage_scenarios/", uri_type='folder', filename='invalid_image.yml', skip_system_checks=True, dev_cache_build=False, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()

    assert f"Supplied folder through --uri is not the root of the git repository. Please only supply the root folder and then the target directory through --filename. Real repo root is {GMT_DIR}" == str(e.value)

def test_internal_network():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/internal_network.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(RuntimeError) as e:
        runner.run()

    assert str(e.value) == "Process '['docker', 'exec', 'test-container', 'curl', '-s', '--fail', 'https://www.google.de']' had bad returncode: 6. Stderr: ; Detached process: False. Please also check the stdout in the logs and / or enable stdout logging to debug further."

    ## rethink this one
def wip_test_verbose_provider_boot():
    run_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', GMT_DIR ,
         '--verbose-provider-boot', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
         '--filename', 'tests/data/stress-application/usage_scenario.yml',
         '--dev-no-sleeps', '--dev-cache-build', '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    run_id = utils.get_run_data(run_name)['id']
    query = """
            SELECT
                time, note
            FROM
                notes
            WHERE
                run_id = %s
                AND note LIKE %s
            ORDER BY
                time
            """

    notes = DB().fetch_all(query, (run_id,'Booting%',))
    metric_providers = utils.get_metric_providers_names(GlobalConfig().config)

    #for each metric provider, assert there is an an entry in notes
    for provider in metric_providers:
        assert any(provider in note for _, note in notes), \
            Tests.assertion_info(f"note: 'Booting {provider}'", f"notes: {notes}")

    #check that each timestamp in notes roughlly 10 seconds apart
    for i in range(len(notes)-1):
        diff = (notes[i+1][0] - notes[i][0])/1000000
        assert 9.9 <= diff <= 10.1, \
            Tests.assertion_info('10s apart', f"time difference of notes: {diff}s")


def test_bad_arg():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/docker_arg_bad.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err), pytest.raises(RuntimeError) as e:
        runner.run()

    assert "Argument '-P' is not allowed in the docker-run-args list. Please check the capabilities of the user or if running locally consider --allow-unsafe" in str(e.value)

def test_good_arg():

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/docker_arg_good.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True, user_id=1, allowed_run_args=[r'--label\s+([\w.-]+)=([\w.-]+)'])

    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        runner.run()

    assert re.search(r"docker run -it -d .* --label test=true", str(out.getvalue())), f"--label test=true not found in docker run command: {out.getvalue()}"

def test_restart_no_error():

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/compose_restart_key.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')


def test_outside_symlink_not_allowed():
    runner = ScenarioRunner(uri='https://github.com/green-coding-solutions/symlink-repo', uri_type='URL', filename='usage_scenario.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    with pytest.raises(RuntimeError) as exc:

        with Tests.RunUntilManager(runner) as context:
            context.run_until('import_metric_providers')

    assert 'Repository contained outside symlink' in str(exc)
    assert '/passwd' in str(exc)


def test_outside_symlink_not_allowed_deep():
    runner = ScenarioRunner(uri='https://github.com/green-coding-solutions/symlink-repo', uri_type='URL', branch="deep", filename='usage_scenario_deep.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    with pytest.raises(RuntimeError) as exc:

        with Tests.RunUntilManager(runner) as context:
            context.run_until('import_metric_providers')

    assert 'Repository contained outside symlink' in str(exc)
    assert '/passwd' in str(exc)

def test_outside_symlink_not_allowed_missing_outside():
    runner = ScenarioRunner(uri='https://github.com/green-coding-solutions/symlink-repo', uri_type='URL', branch="missing-outside", filename='usage_scenario.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    with pytest.raises(RuntimeError) as exc:

        with Tests.RunUntilManager(runner) as context:
            context.run_until('import_metric_providers')

    assert 'Repository contained outside symlink' in str(exc)
    assert '/h4huhguihui3ghguirue' in str(exc)

# plain symlinks, even if missing, as long as they are inside the repository we want to allow at the moment
def test_outside_symlink_not_allowed_missing_inside():
    runner = ScenarioRunner(uri='https://github.com/green-coding-solutions/symlink-repo', uri_type='URL', branch="missing-inside", filename='usage_scenario.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('import_metric_providers')
