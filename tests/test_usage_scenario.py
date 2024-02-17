# https://docs.docker.com/engine/reference/commandline/port/
# List port mappings or a specific mapping for the container
#  docker port CONTAINER [PRIVATE_PORT[/PROTO]]

import io
import os
import re
import shutil
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
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

# This should be done once per module
@pytest.fixture(autouse=True, scope="module", name="build_image")
def build_image_fixture():
    uri = os.path.abspath(os.path.join(CURRENT_DIR, 'stress-application/'))
    subprocess.run(['docker', 'compose', '-f', uri+'/compose.yml', 'build'], check=True)
    GlobalConfig().override_config(config_name='test-config.yml')

# cleanup test/tmp directory after every test run
@pytest.fixture(autouse=True, name="cleanup_tmp_directories")
def cleanup_tmp_directories_fixture():
    yield
    tmp_dir = os.path.join(CURRENT_DIR, 'tmp/')
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    if os.path.exists('/tmp/gmt-test-data'):
        shutil.rmtree('/tmp/gmt-test-data')

# This function runs the runner up to and *including* the specified step
#pylint: disable=redefined-argument-from-local
### The Tests for usage_scenario configurations

# environment: [object] (optional)
# Key-Value pairs for ENV variables inside the container

def get_env_vars(runner):
    try:
        Tests.run_until(runner, 'setup_services')

        ps = subprocess.run(
            ['docker', 'exec', 'test-container', '/bin/sh',
            '-c', 'env'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        env_var_output = ps.stdout
    finally:
        Tests.cleanup(runner)
    return env_var_output

# Test allowed characters
def test_env_variable_allowed_characters():
    runner = Tests.setup_runner(usage_scenario='env_vars_stress_allowed.yml', skip_unsafe=False, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    env_var_output = get_env_vars(runner)

    assert 'TESTALLOWED=alpha-num123_' in env_var_output, Tests.assertion_info('TESTALLOWED=alpha-num123_', env_var_output)
    assert 'TEST1_ALLOWED=alpha-key-num123_' in env_var_output, Tests.assertion_info('TEST1_ALLOWED=alpha-key-num123_', env_var_output)
    assert 'TEST2_ALLOWED=http://localhost:8080' in env_var_output, Tests.assertion_info('TEST2_ALLOWED=http://localhost:8080', env_var_output)
    assert 'TEST3_ALLOWED=example.com' in env_var_output, Tests.assertion_info('TEST3_ALLOWED=example.com', env_var_output)

# Test too long values
def test_env_variable_too_long():
    runner = Tests.setup_runner(usage_scenario='env_vars_stress_forbidden.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    with pytest.raises(RuntimeError) as e:
        get_env_vars(runner)

    assert 'TEST_TOO_LONG' in str(e.value), Tests.assertion_info("Env var value is too long", str(e.value))

# Test skip_unsafe=true
def test_env_variable_skip_unsafe_true():
    runner = Tests.setup_runner(usage_scenario='env_vars_stress_forbidden.yml', skip_unsafe=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    env_var_output = get_env_vars(runner)

    # Only allowed values should be in env vars, forbidden ones should be skipped
    assert 'TEST_ALLOWED' in env_var_output, Tests.assertion_info('TEST_ALLOWED in env vars', env_var_output)
    assert 'TEST_TOO_LONG' not in env_var_output, Tests.assertion_info('TEST_TOO_LONG not in env vars', env_var_output)

# Test allow_unsafe=true
def test_env_variable_allow_unsafe_true():
    runner = Tests.setup_runner(usage_scenario='env_vars_stress_forbidden.yml', allow_unsafe=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    env_var_output = get_env_vars(runner)

    # Both allowed and forbidden values should be in env vars
    assert 'TEST_ALLOWED' in env_var_output, Tests.assertion_info('TEST_ALLOWED in env vars', env_var_output)
    assert 'TEST_TOO_LONG' in env_var_output, Tests.assertion_info('TEST_TOO_LONG in env vars', env_var_output)

# ports: [int:int] (optional)
# Docker container portmapping on host OS to be used with --allow-unsafe flag.

def get_port_bindings(runner):
    try:
        Tests.run_until(runner, 'setup_services')
        ps = subprocess.run(
                ['docker', 'port', 'test-container', '9018'],
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='UTF-8'
            )
        port = ps.stdout
        err = ps.stderr
    finally:
        Tests.cleanup(runner)
    return port, err

def test_port_bindings_allow_unsafe_true():
    runner = Tests.setup_runner(usage_scenario='port_bindings_stress.yml', allow_unsafe=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    port, _ = get_port_bindings(runner)
    assert port.startswith('0.0.0.0:9017'), Tests.assertion_info('0.0.0.0:9017', port)

def test_port_bindings_skip_unsafe_true():
    out = io.StringIO()
    err = io.StringIO()
    runner = Tests.setup_runner(usage_scenario='port_bindings_stress.yml', skip_unsafe=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    # need to catch exception here as otherwise the subprocess returning an error will
    # fail the test
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception):
        _, docker_port_err = get_port_bindings(runner)
        expected_container_error = 'Error: No public port \'9018/tcp\' published for test-container\n'
        assert docker_port_err == expected_container_error, \
            Tests.assertion_info(f"Container Error: {expected_container_error}", docker_port_err)
    expected_warning = 'Found ports entry but not running in unsafe mode. Skipping'
    assert expected_warning in out.getvalue(), \
        Tests.assertion_info(f"Warning: {expected_warning}", 'no/different warning')

def test_port_bindings_no_skip_or_allow():
    runner = Tests.setup_runner(usage_scenario='port_bindings_stress.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    with pytest.raises(Exception) as e:
        _, docker_port_err = get_port_bindings(runner)
        expected_container_error = 'Error: No public port \'9018/tcp\' published for test-container\n'
        assert docker_port_err == expected_container_error, \
            Tests.assertion_info(f"Container Error: {expected_container_error}", docker_port_err)
    expected_error = 'Found "ports" but neither --skip-unsafe nor --allow-unsafe is set'
    assert expected_error in str(e.value), \
        Tests.assertion_info(f"Exception: {expected_error}", str(e.value))

# setup-commands: [array] (optional)
# Array of commands to be run before actual load testing.
# uses ps -a to check that sh is process with PID 1
def test_setup_commands_one_command():
    out = io.StringIO()
    err = io.StringIO()
    runner = Tests.setup_runner(usage_scenario='setup_commands_stress.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        try:
            Tests.run_until(runner, 'setup_services')
        finally:
            runner.cleanup()
    assert 'Running command:  docker exec test-container sh -c ps -a' in out.getvalue(), \
        Tests.assertion_info('stdout message: Running command: docker exec  ps -a', out.getvalue())
    assert '1 root      0:00 /bin/sh' in out.getvalue(), \
        Tests.assertion_info('container stdout showing /bin/sh as process 1', 'different message in container stdout')

def test_setup_commands_multiple_commands():
    out = io.StringIO()
    err = io.StringIO()
    runner = Tests.setup_runner(usage_scenario='setup_commands_multiple_stress.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        try:
            Tests.run_until(runner, 'setup_services')
        finally:
            runner.cleanup()

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

def create_test_file(path):
    if not os.path.exists(path):
        os.mkdir(path)
    Path(f"{path}/test-file").touch()

def get_contents_of_bound_volume(runner):
    try:
        Tests.run_until(runner, 'setup_services')
        ps = subprocess.run(
                ['docker', 'exec', 'test-container', 'ls', '/tmp/test-data'],
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='UTF-8'
            )
        ls = ps.stdout
    finally:
        Tests.cleanup(runner)
    return ls

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
    runner = Tests.setup_runner(usage_scenario='depends_on.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        try:
            Tests.run_until(runner, 'setup_services')
        finally:
            runner.cleanup()

    # Expected order: test-container-2, test-container-4, test-container-3, test-container-1
    assert_order(out.getvalue(), 'test-container-2', 'test-container-4')
    assert_order(out.getvalue(), 'test-container-4', 'test-container-3')
    assert_order(out.getvalue(), 'test-container-3', 'test-container-1')


def test_depends_on_huge():
    out = io.StringIO()
    err = io.StringIO()
    runner = Tests.setup_runner(usage_scenario='depends_on_huge.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        try:
            Tests.run_until(runner, 'setup_services')
        finally:
            runner.cleanup()

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
    runner = Tests.setup_runner(usage_scenario='depends_on_error_not_running.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    try:
        with pytest.raises(RuntimeError) as e:
            Tests.run_until(runner, 'setup_services')
    finally:
        runner.cleanup()

    assert "Dependent container 'test-container-2' of 'test-container-1' is not running" in str(e.value) , \
        Tests.assertion_info('test-container-2 is not running', str(e.value))

def test_depends_on_error_cyclic_dependency():
    runner = Tests.setup_runner(usage_scenario='depends_on_error_cycle.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    try:
        with pytest.raises(RuntimeError) as e:
            Tests.run_until(runner, 'setup_services')
    finally:
        runner.cleanup()

    assert "Cycle found in depends_on definition with service 'test-container-1'" in str(e.value) , \
        Tests.assertion_info('cycle in depends_on with test-container-1', str(e.value))

def test_depends_on_error_unsupported_condition():
    runner = Tests.setup_runner(usage_scenario='depends_on_error_unsupported_condition.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    try:
        with pytest.raises(RuntimeError) as e:
            Tests.run_until(runner, 'setup_services')
    finally:
        runner.cleanup()

    message = 'Unsupported condition in healthcheck for service \'test-container-1\':  service_completed_successfully'
    assert message in str(e.value) , \
        Tests.assertion_info(message, str(e.value))

def test_depends_on_long_form():
    runner = Tests.setup_runner(usage_scenario='depends_on_long_form.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    out = io.StringIO()
    err = io.StringIO()

    try:
        with redirect_stdout(out), redirect_stderr(err):
            runner.run()
        message = 'State of container'
        assert message in out.getvalue(), \
            Tests.assertion_info(message, out.getvalue())
    finally:
        runner.cleanup()

def test_depends_on_healthcheck():
    runner = Tests.setup_runner(usage_scenario='healthcheck.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    out = io.StringIO()
    err = io.StringIO()

    try:
        with redirect_stdout(out), redirect_stderr(err):
            runner.run()
        message = 'Health of container \'test-container-2\': starting'
        assert message in out.getvalue(), Tests.assertion_info(message, out.getvalue())
        message2 = 'Health of container \'test-container-2\': healthy'
        assert message2 in out.getvalue(), Tests.assertion_info(message, out.getvalue())

    finally:
        runner.cleanup()

def test_depends_on_healthcheck_error_missing():
    runner = Tests.setup_runner(usage_scenario='healthcheck_error_missing.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    try:
        with pytest.raises(RuntimeError) as e:
            runner.run()
    finally:
        runner.cleanup()

    expected_exception = "Health check for dependent_container 'test-container-2' was requested, but container has no healthcheck implemented!"
    assert str(e.value).startswith(expected_exception),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

#volumes: [array] (optional)
#Array of volumes to be mapped. Only read of runner.py is executed with --allow-unsafe flag
def test_volume_bindings_allow_unsafe_true():
    create_test_file('/tmp/gmt-test-data')
    runner = Tests.setup_runner(usage_scenario='volume_bindings_stress.yml', allow_unsafe=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    ls = get_contents_of_bound_volume(runner)
    assert 'test-file' in ls, Tests.assertion_info('test-file', ls)

def test_volumes_bindings_skip_unsafe_true():
    create_test_file('/tmp/gmt-test-data')
    out = io.StringIO()
    err = io.StringIO()
    runner = Tests.setup_runner(usage_scenario='volume_bindings_stress.yml', skip_unsafe=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception):
        ls = get_contents_of_bound_volume(runner)
        assert ls == '', Tests.assertion_info('empty list', ls)
    expected_warning = '' # expecting no warning for safe volumes
    assert expected_warning in out.getvalue(), \
        Tests.assertion_info(f"Warning: {expected_warning}", 'no/different warning')

def test_volumes_bindings_no_skip_or_allow():
    create_test_file('/tmp/gmt-test-data')
    runner = Tests.setup_runner(usage_scenario='volume_bindings_stress.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    with pytest.raises(RuntimeError) as e:
        ls = get_contents_of_bound_volume(runner)
        assert ls == '', Tests.assertion_info('empty list', ls)
    expected_exception = '' # Expecting no error for safe volumes
    assert expected_exception in str(e.value) ,\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

def test_network_created():
    runner = Tests.setup_runner(usage_scenario='network_stress.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    try:
        Tests.run_until(runner, 'setup_networks')
        ps = subprocess.run(
            ['docker', 'network', 'ls'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        ls = ps.stdout
    finally:
        Tests.cleanup(runner)
    assert 'gmt-test-network' in ls, Tests.assertion_info('gmt-test-network', ls)

def test_container_is_in_network():
    runner = Tests.setup_runner(usage_scenario='network_stress.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    try:
        Tests.run_until(runner, 'setup_services')
        ps = subprocess.run(
            ['docker', 'network', 'inspect', 'gmt-test-network'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        inspect = ps.stdout
    finally:
        Tests.cleanup(runner)
    assert 'test-container' in inspect, Tests.assertion_info('test-container', inspect)

# command: [str] (optional)
#    Command to be executed when container is started.
#    When container does not have a daemon running typically a shell
#    is started here to have the container running like bash or sh
def test_cmd_ran():
    runner = Tests.setup_runner(usage_scenario='cmd_stress.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    try:
        Tests.run_until(runner, 'setup_services')
        ps = subprocess.run(
            ['docker', 'exec', 'test-container', 'ps', '-a'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        docker_ps_out = ps.stdout
    finally:
        Tests.cleanup(runner)
    assert '1 root      0:00 sh' in docker_ps_out, Tests.assertion_info('1 root      0:00 sh', docker_ps_out)

### The Tests for the runner options/flags
## --uri URI
#   The URI to get the usage_scenario.yml from. Can be either a local directory starting with
#     / or a remote git repository starting with http(s)://
def test_uri_local_dir():
    uri = os.path.abspath(os.path.join(CURRENT_DIR, 'stress-application/'))
    RUN_NAME = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', RUN_NAME, '--uri', uri ,'--config-override', 'test-config.yml',
        '--skip-system-checks', '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    uri_in_db = utils.get_run_data(RUN_NAME)['uri']
    assert uri_in_db == uri, Tests.assertion_info(f"uri: {uri}", uri_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

def test_uri_local_dir_missing():
    runner = Tests.setup_runner(usage_scenario='basic_stress.yml', uri='/tmp/missing', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    try:
        with pytest.raises(FileNotFoundError) as e:
            runner.run()
        expected_exception = 'No such file or directory: \'/tmp/missing\''
    finally:
        runner.cleanup()
    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

    # basic positive case
def test_uri_github_repo():
    uri = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    RUN_NAME = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', RUN_NAME, '--uri', uri ,'--config-override', 'test-config.yml',
        '--skip-system-checks', '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    uri_in_db = utils.get_run_data(RUN_NAME)['uri']
    assert uri_in_db == uri, Tests.assertion_info(f"uri: {uri}", uri_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

## --branch BRANCH
#    Optionally specify the git branch when targeting a git repository
def test_uri_local_branch():
    runner = Tests.setup_runner(usage_scenario='basic_stress.yml', branch='test-branch', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
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
    RUN_NAME = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', RUN_NAME, '--uri', uri ,
        '--branch', 'test-branch' , '--filename', 'basic_stress.yml',
        '--config-override', 'test-config.yml', '--skip-system-checks', '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    branch_in_db = utils.get_run_data(RUN_NAME)['branch']
    assert branch_in_db == 'test-branch', Tests.assertion_info('branch: test-branch', branch_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

    # should throw error, assert vs error
    # give incorrect branch name
    ## Is the expected_exception OK or should it have a more graceful error?
    ## ATM this is just the default console error of a failed git command
def test_uri_github_repo_branch_missing():
    runner = Tests.setup_runner(usage_scenario='basic_stress.yml',
        uri='https://github.com/green-coding-berlin/pytest-dummy-repo',
        uri_type='URL',
        branch='missing-branch',
        dev_no_sleeps=True,
        dev_no_build=True,
        dev_no_metrics=True,
    )
    with pytest.raises(subprocess.CalledProcessError) as e:
        runner.run()
    expected_exception = 'returned non-zero exit status 128'
    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

# #   --name NAME
# #    A name which will be stored to the database to discern this run from others
def test_name_is_in_db():
    uri = os.path.abspath(os.path.join(CURRENT_DIR, 'stress-application/'))
    RUN_NAME = 'test_' + utils.randomword(12)
    subprocess.run(
        ['python3', '../runner.py', '--name', RUN_NAME, '--uri', uri ,'--config-override', 'test-config.yml',
        '--skip-system-checks', '--dev-no-metrics', '--dev-no-sleeps', '--dev-no-build'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    name_in_db = utils.get_run_data(RUN_NAME)['name']
    assert name_in_db == RUN_NAME, Tests.assertion_info(f"name: {RUN_NAME}", name_in_db)

# --filename FILENAME
#    An optional alternative filename if you do not want to use "usage_scenario.yml"
    # basic positive case
def test_different_filename():
    usage_scenario_path = os.path.join(CURRENT_DIR, 'data/usage_scenarios/', 'basic_stress.yml')
    dir_name = utils.randomword(12)
    compose_path = os.path.abspath(os.path.join(CURRENT_DIR, 'stress-application/compose.yml'))
    Tests.make_proj_dir(dir_name=dir_name, usage_scenario_path=usage_scenario_path, docker_compose_path=compose_path)
    uri = os.path.join(CURRENT_DIR, 'tmp/', dir_name)
    RUN_NAME = 'test_' + utils.randomword(12)

    ps = subprocess.run(
        ['python3', '../runner.py', '--name', RUN_NAME, '--uri', uri ,
         '--filename', 'basic_stress.yml', '--config-override', 'test-config.yml',
         '--skip-system-checks', '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    with open(usage_scenario_path, 'r', encoding='utf-8') as f:
        usage_scenario_contents = yaml.safe_load(f)
    usage_scenario_in_db = utils.get_run_data(RUN_NAME)['usage_scenario']
    assert usage_scenario_in_db == usage_scenario_contents,\
        Tests.assertion_info(usage_scenario_contents, usage_scenario_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

# if that filename is missing...
def test_different_filename_missing():
    uri = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'stress-application/'))
    RUN_NAME = 'test_' + utils.randomword(12)

    runner = Runner(name=RUN_NAME, uri=uri, uri_type='folder', filename='basic_stress.yml', skip_system_checks=True, dev_no_build=True, dev_no_sleeps=True, dev_no_metrics=True)

    with pytest.raises(FileNotFoundError) as e:
        runner.run()
    expected_exception = 'No such file or directory:'
    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

#   --no-file-cleanup
#    Do not delete files in /tmp/green-metrics-tool
def test_no_file_cleanup():
    uri = os.path.abspath(os.path.join(CURRENT_DIR, 'stress-application/'))
    RUN_NAME = 'test_' + utils.randomword(12)
    subprocess.run(
        ['python3', '../runner.py', '--name', RUN_NAME, '--uri', uri ,
         '--no-file-cleanup', '--config-override', 'test-config.yml', '--skip-system-checks', '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    assert os.path.exists('/tmp/green-metrics-tool'), \
        Tests.assertion_info('tmp directory exists', os.path.exists('/tmp/green-metrics-tool'))

#pylint: disable=unused-variable
def test_skip_and_allow_unsafe_both_true():
    with pytest.raises(RuntimeError) as e:
        runner = Tests.setup_runner(usage_scenario='basic_stress.yml', skip_unsafe=True, allow_unsafe=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    expected_exception = 'Cannot specify both --skip-unsafe and --allow-unsafe'
    assert str(e.value) == expected_exception, Tests.assertion_info('', str(e.value))

def test_debug(monkeypatch):
    monkeypatch.setattr('sys.stdin', io.StringIO('Enter'))
    uri = os.path.abspath(os.path.join(CURRENT_DIR, 'stress-application/'))
    RUN_NAME = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', RUN_NAME, '--uri', uri ,
         '--debug', '--config-override', 'test-config.yml', '--skip-system-checks',
          '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics'],
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
    runner = Tests.setup_runner(usage_scenario='stress_detached_no_exit.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            runner.run()
        finally:
            runner.cleanup()
    assert 'setting to a 1 min, 40 secs run per stressor' in out.getvalue(), \
        Tests.assertion_info('setting to a 1 min, 40 secs run per stressor', out.getvalue())
    assert 'successful run completed' not in out.getvalue(), \
        Tests.assertion_info('NOT successful run completed', out.getvalue())

def test_read_detached_process_after_exit():
    runner = Tests.setup_runner(usage_scenario='stress_detached_exit.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            runner.run()
        finally:
            runner.cleanup()
    assert 'successful run completed' in out.getvalue(), \
        Tests.assertion_info('successful run completed', out.getvalue())

def test_read_detached_process_failure():
    runner = Tests.setup_runner(usage_scenario='stress_detached_failure.yml', dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        try:
            runner.run()
        finally:
            runner.cleanup()
    assert '\'g4jiorejf\']\' had bad returncode: 126' in str(e.value), \
        Tests.assertion_info('\'g4jiorejf\']\' had bad returncode: 126', str(e.value))


    ## rethink this one
def wip_test_verbose_provider_boot():
    uri = os.path.abspath(os.path.join(CURRENT_DIR, 'stress-application/'))
    RUN_NAME = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', RUN_NAME, '--uri', uri ,
         '--verbose-provider-boot', '--config-override', 'test-config.yml',
         '--dev-no-sleeps', '--dev-no-build', '--dev-no-metrics'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    run_id = utils.get_run_data(RUN_NAME)['id']
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
