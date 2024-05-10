# https://docs.docker.com/engine/reference/commandline/port/
# List port mappings or a specific mapping for the container
#  docker port CONTAINER [PRIVATE_PORT[/PROTO]]

import io
import os
import re
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from contextlib import redirect_stdout, redirect_stderr
import pytest
import yaml

from lib.db import DB
from lib import utils
from lib.global_config import GlobalConfig
from tests import test_functions as Tests
from runner import Runner

GlobalConfig().override_config(config_name='test-config.yml')
config = GlobalConfig().config

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

# Test allowed characters
def test_env_variable_allowed_characters():

    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/env_vars_stress_allowed.yml', skip_unsafe=False, skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')

        env_var_output = get_env_vars()

        assert 'TESTALLOWED=alpha-num123_' in env_var_output, Tests.assertion_info('TESTALLOWED=alpha-num123_', env_var_output)
        assert 'TEST1_ALLOWED=alpha-key-num123_' in env_var_output, Tests.assertion_info('TEST1_ALLOWED=alpha-key-num123_', env_var_output)
        assert 'TEST2_ALLOWED=http://localhost:8080' in env_var_output, Tests.assertion_info('TEST2_ALLOWED=http://localhost:8080', env_var_output)
        assert 'TEST3_ALLOWED=example.com' in env_var_output, Tests.assertion_info('TEST3_ALLOWED=example.com', env_var_output)

# Test too long values
def test_env_variable_too_long():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/env_vars_stress_forbidden.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert 'TEST_TOO_LONG' in str(e.value), Tests.assertion_info("Env var value is too long", str(e.value))

# Test skip_unsafe=true
def test_env_variable_skip_unsafe_true():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/env_vars_stress_forbidden.yml', skip_unsafe=True, skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        env_var_output = get_env_vars()

    # Only allowed values should be in env vars, forbidden ones should be skipped
    assert 'TEST_ALLOWED' in env_var_output, Tests.assertion_info('TEST_ALLOWED in env vars', env_var_output)
    assert 'TEST_TOO_LONG' not in env_var_output, Tests.assertion_info('TEST_TOO_LONG not in env vars', env_var_output)

# Test allow_unsafe=true
def test_env_variable_allow_unsafe_true():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/env_vars_stress_forbidden.yml', allow_unsafe=True, skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        env_var_output = get_env_vars()

    # Both allowed and forbidden values should be in env vars
    assert 'TEST_ALLOWED' in env_var_output, Tests.assertion_info('TEST_ALLOWED in env vars', env_var_output)
    assert 'TEST_TOO_LONG' in env_var_output, Tests.assertion_info('TEST_TOO_LONG in env vars', env_var_output)

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
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/port_bindings_stress.yml', allow_unsafe=True, skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        port, _ = get_port_bindings()

    assert port.startswith('0.0.0.0:9017'), Tests.assertion_info('0.0.0.0:9017', port)

def test_port_bindings_skip_unsafe_true():
    out = io.StringIO()
    err = io.StringIO()
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/port_bindings_stress.yml', skip_unsafe=True, skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

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
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/port_bindings_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with pytest.raises(Exception) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')
            _, docker_port_err = get_port_bindings()
            expected_container_error = 'Error: No public port \'9018/tcp\' published for test-container\n'
            assert docker_port_err == expected_container_error, \
                Tests.assertion_info(f"Container Error: {expected_container_error}", docker_port_err)
    expected_error = 'Found "ports" but neither --skip-unsafe nor --allow-unsafe is set'
    assert expected_error in str(e.value), \
        Tests.assertion_info(f"Exception: {expected_error}", str(e.value))

def test_compose_include_not_same_dir():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/parentdir_compose_include/subdir/usage_scenario_fail.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    out = io.StringIO()
    err = io.StringIO()


    with redirect_stdout(out), redirect_stderr(err), pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')
    assert str(e.value).startswith('Included compose file "../compose.yml" may only be in the same directory as the usage_scenario file as otherwise relative context_paths and volume_paths cannot be mapped anymore') , \
        Tests.assertion_info('Root directory escape', str(e.value))

def test_context_include():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/subdir_parent_context/subdir/usage_scenario_ok.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')
    # will not throw an exception

def test_context_include_escape():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/subdir_parent_context/subdir/usage_scenario_fail.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    out = io.StringIO()
    err = io.StringIO()


    with redirect_stdout(out), redirect_stderr(err), pytest.raises(ValueError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')
    assert str(e.value).startswith('../../../../ must not be in folder above root repo folder') , \
        Tests.assertion_info('Root directory escape', str(e.value))


# setup-commands: [array] (optional)
# Array of commands to be run before actual load testing.
# uses ps -a to check that sh is process with PID 1
def test_setup_commands_one_command():
    out = io.StringIO()
    err = io.StringIO()
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/setup_commands_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')
    assert 'Running command:  docker exec test-container sh -c ps -a' in out.getvalue(), \
        Tests.assertion_info('stdout message: Running command: docker exec  ps -a', out.getvalue())
    assert '1 root      0:00 /bin/sh' in out.getvalue(), \
        Tests.assertion_info('container stdout showing /bin/sh as process 1', 'different message in container stdout')

def test_setup_commands_multiple_commands():
    out = io.StringIO()
    err = io.StringIO()
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/setup_commands_multiple_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    expected_pattern = re.compile(r'Running command:  docker exec test-container echo hello world.*\
\s*Stdout: hello world.*\
\s*Stderr:.*\
\s*Running command:  docker exec test-container ps -a.*\
\s*Stdout:\s+PID\s+USER\s+TIME\s+COMMAND.*\
\s*1\s+root\s+\d:\d\d\s+/bin/sh.*\
\s*1\d+\s+root\s+\d:\d\d\s+ps -a.*\
\s*Stderr:.*\
\s*Running command:  docker exec test-container echo goodbye world.*\
\s*Stdout: goodbye world.*\
', re.MULTILINE)

    assert re.search(expected_pattern, out.getvalue()), \
        Tests.assertion_info('container stdout showing 3 commands run in sequence',\
         'different messages in container stdout')

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
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/depends_on.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

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
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/depends_on_huge.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

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
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/depends_on_error_not_running.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "Dependent container 'test-container-2' of 'test-container-1' is not running" in str(e.value) , \
        Tests.assertion_info('test-container-2 is not running', str(e.value))

def test_depends_on_error_cyclic_dependency():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/depends_on_error_cycle.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "Cycle found in depends_on definition with service 'test-container-1'" in str(e.value) , \
        Tests.assertion_info('cycle in depends_on with test-container-1', str(e.value))

def test_depends_on_error_unsupported_condition():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/depends_on_error_unsupported_condition.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    message = 'Unsupported condition in healthcheck for service \'test-container-1\':  service_completed_successfully'
    assert message in str(e.value) , \
        Tests.assertion_info(message, str(e.value))

def test_depends_on_long_form():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/depends_on_long_form.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    message = 'State of container'
    assert message in out.getvalue(), \
        Tests.assertion_info(message, out.getvalue())

def test_depends_on_healthcheck():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/healthcheck.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    message = 'Health of container \'test-container-2\': healthy'
    assert message in out.getvalue(), Tests.assertion_info(message, out.getvalue())

def test_depends_on_healthcheck_error_missing():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/healthcheck_error_missing.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with pytest.raises(RuntimeError) as e:
        runner.run()

    expected_exception = "Health check for dependent_container 'test-container-2' was requested, but container has no healthcheck implemented!"
    assert str(e.value).startswith(expected_exception),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))


def test_network_created():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/network_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
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
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/network_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
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

# command: [str] (optional)
#    Command to be executed when container is started.
#    When container does not have a daemon running typically a shell
#    is started here to have the container running like bash or sh
def test_cmd_ran():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/cmd_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
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

### The Tests for the runner options/flags
## --uri URI
#   The URI to get the usage_scenario.yml from. Can be either a local directory starting with
#     / or a remote git repository starting with http(s)://
def test_uri_local_dir():
    run_name = 'test_' + utils.randomword(12)
    uri = f"{CURRENT_DIR}/data/stress-application"
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', uri ,'--config-override', 'test-config.yml',
        '--skip-system-checks', '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    uri_in_db = utils.get_run_data(run_name)['uri']
    assert uri_in_db == uri, Tests.assertion_info(f"uri: {uri}", uri_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

def test_uri_local_dir_missing():
    runner = Runner(uri='/tmp/missing', uri_type='folder', filename='data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with pytest.raises(FileNotFoundError) as e:
        runner.run()
    expected_exception = 'No such file or directory: \'/tmp/missing\''

    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

    # basic positive case
def test_uri_github_repo():
    uri = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    run_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', uri ,'--config-override', 'test-config.yml',
        '--skip-system-checks', '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    uri_in_db = utils.get_run_data(run_name)['uri']
    assert uri_in_db == uri, Tests.assertion_info(f"uri: {uri}", uri_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

## --branch BRANCH
#    Optionally specify the git branch when targeting a git repository
def test_uri_local_branch():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/basic_stress.yml', branch='test-branch', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

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
    uri = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    run_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', uri ,
        '--branch', 'test-branch' , '--filename', 'basic_stress.yml',
        '--config-override', 'test-config.yml', '--skip-system-checks', '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    branch_in_db = utils.get_run_data(run_name)['branch']
    assert branch_in_db == 'test-branch', Tests.assertion_info('branch: test-branch', branch_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

    # should throw error, assert vs error
    # give incorrect branch name
    ## Is the expected_exception OK or should it have a more graceful error?
    ## ATM this is just the default console error of a failed git command
def test_uri_github_repo_branch_missing():
    runner = Runner(uri='https://github.com/green-coding-berlin/pytest-dummy-repo', uri_type='URL', branch='missing-branch', filename='data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    with pytest.raises(subprocess.CalledProcessError) as e:
        runner.run()
    expected_exception = 'returned non-zero exit status 128'
    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

# #   --name NAME
# #    A name which will be stored to the database to discern this run from others
def test_name_is_in_db():
    run_name = 'test_' + utils.randomword(12)
    subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', f"{CURRENT_DIR}/data/stress-application" , '--config-override', 'test-config.yml',
        '--skip-system-checks', '--dev-no-metrics', '--dev-no-optimizations', '--dev-no-sleeps', '--dev-no-build'],
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
        ['python3', '../runner.py', '--name', run_name, '--uri', CURRENT_DIR , '--filename', 'data/usage_scenarios/basic_stress.yml', '--config-override', 'test-config.yml',
        '--skip-system-checks', '--dev-no-metrics', '--dev-no-optimizations', '--dev-no-sleeps', '--dev-no-build'],
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
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='I_do_not_exist.yml', skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True)

    with pytest.raises(FileNotFoundError) as e:
        runner.run()
    expected_exception = 'No such file or directory:'
    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

#   Check that default is to leave the files
def test_no_file_cleanup():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True)
    runner.run()

    assert os.path.exists('/tmp/green-metrics-tool'), \
        Tests.assertion_info('tmp directory exists', os.path.exists('/tmp/green-metrics-tool'))

#   Check that the temp dir is deleted when using --file-cleanup
#   This option exists only in CLI mode
def test_file_cleanup():
    subprocess.run(
        ['python3', '../runner.py', '--uri', CURRENT_DIR , '--filename', 'data/usage_scenarios/basic_stress.yml',
         '--file-cleanup', '--config-override', 'test-config.yml', '--skip-system-checks', '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics', '--dev-no-optimizations'],
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
        Runner(uri=CURRENT_DIR, uri_type='folder', filename='basic_stress.yml', skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True, skip_unsafe=True, allow_unsafe=True)
    expected_exception = 'Cannot specify both --skip-unsafe and --allow-unsafe'
    assert str(e.value) == expected_exception, Tests.assertion_info('', str(e.value))

def test_debug(monkeypatch):
    monkeypatch.setattr('sys.stdin', io.StringIO('Enter'))
    ps = subprocess.run(
        ['python3', '../runner.py', '--uri', CURRENT_DIR , '--filename', 'data/usage_scenarios/basic_stress.yml',
         '--debug',
         '--config-override', 'test-config.yml', '--skip-system-checks',
          '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics', '--dev-no-optimizations'],
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
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/stress_detached_no_exit.yml', skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    assert 'setting to a 1 min, 40 secs run per stressor' in out.getvalue(), \
        Tests.assertion_info('setting to a 1 min, 40 secs run per stressor', out.getvalue())
    assert 'successful run completed' not in out.getvalue(), \
        Tests.assertion_info('NOT successful run completed', out.getvalue())

def test_read_detached_process_after_exit():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/stress_detached_exit.yml', skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    assert 'successful run completed' in out.getvalue(), \
        Tests.assertion_info('successful run completed', out.getvalue())

def test_read_detached_process_failure():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/stress_detached_failure.yml', skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()
    assert '\'g4jiorejf\']\' had bad returncode: 126' in str(e.value), \
        Tests.assertion_info('\'g4jiorejf\']\' had bad returncode: 126', str(e.value))

def test_invalid_container_name():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/invalid_container_name.yml', skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()
    assert 'Invalid container name (highload-api-:cont), only [a-zA-Z0-9][a-zA-Z0-9_.-] are allowed' in str(e.value), \
        Tests.assertion_info('Invalid container name (highload-api-:cont), only [a-zA-Z0-9][a-zA-Z0-9_.-] are allowed', str(e.value))

def test_invalid_container_name_2():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/invalid_container_name_2.yml', skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()
    assert 'Invalid container name (8zhfiuw:-3tjfuehuis), only [a-zA-Z0-9][a-zA-Z0-9_.-] are allowed' in str(e.value), \
        Tests.assertion_info('Invalid container name (8zhfiuw:-3tjfuehuis), only [a-zA-Z0-9][a-zA-Z0-9_.-] are allowed', str(e.value))

def test_duplicate_container_name():
    runner = Runner(uri=CURRENT_DIR, uri_type='folder', filename='data/usage_scenarios/duplicate_container_name.yml', skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()
    assert "Container name 'number-1' was already assigned. Please choose unique container names." in str(e.value), \
        Tests.assertion_info("Container name 'number-1' was already assigned. Please choose unique container names.", str(e.value))



    ## rethink this one
def wip_test_verbose_provider_boot():
    uri = os.path.abspath(os.path.join(CURRENT_DIR, 'stress-application/'))
    run_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', run_name, '--uri', uri ,
         '--verbose-provider-boot', '--config-override', 'test-config.yml',
         '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics', '--dev-no-optimizations'],
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
    metric_providers = utils.get_metric_providers_names(config)

    #for each metric provider, assert there is an an entry in notes
    for provider in metric_providers:
        assert any(provider in note for _, note in notes), \
            Tests.assertion_info(f"note: 'Booting {provider}'", f"notes: {notes}")

    #check that each timestamp in notes roughlly 10 seconds apart
    for i in range(len(notes)-1):
        diff = (notes[i+1][0] - notes[i][0])/1000000
        assert 9.9 <= diff <= 10.1, \
            Tests.assertion_info('10s apart', f"time difference of notes: {diff}s")
