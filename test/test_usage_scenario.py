# https://docs.docker.com/engine/reference/commandline/port/
# List port mappings or a specific mapping for the container
#  docker port CONTAINER [PRIVATE_PORT[/PROTO]]


#pylint: disable=fixme,import-error,wrong-import-position, global-statement, unused-argument, invalid-name, redefined-outer-name
# unused-argument because its not happy with 'module', which is unfortunately necessary for pytest
# also disabled invalid-name because its not happy with single word for d in data , for example

import io
import os
import re
import shutil
import sys
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/..")
sys.path.append(f"{CURRENT_DIR}/../lib")

from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from db import DB
import pytest
import utils
import yaml
from global_config import GlobalConfig
import test_functions as Tests
from runner import Runner

config = GlobalConfig(config_name='test-config.yml').config

## Note:
# Always do asserts after try:finally: blocks
# otherwise failing Tests will not run the runner.cleanup() properly

# This should be done once per module
@pytest.fixture(autouse=True, scope="module")
def build_image():
    uri = os.path.abspath(os.path.join(
            CURRENT_DIR, 'stress-application/'))
    subprocess.run(['docker', 'compose', '-f', uri+'/compose.yml', 'build'], check=True)

# cleanup test/tmp directory after every test run
@pytest.fixture(autouse=True)
def cleanup_tmp_directories():
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
            '-c', 'echo $TESTALLOWED'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        allowed = ps.stdout

        ps = subprocess.run(
            ['docker', 'exec', 'test-container', '/bin/sh',
            '-c', 'echo $TESTBACKTICK'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        backtick = ps.stdout

        ps = subprocess.run(
            ['docker', 'exec', 'test-container', '/bin/sh',
            '-c', 'echo $TESTDOLLAR'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        dollar = ps.stdout

        ps = subprocess.run(
            ['docker', 'exec', 'test-container', '/bin/sh',
            '-c', 'echo $TESTPARENTHESIS'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        parenthesis= ps.stdout
    finally:
        runner.cleanup()

    return allowed, backtick, dollar, parenthesis

def test_env_variable_no_skip_or_allow():
    runner = Tests.setup_runner(usage_scenario='env_vars_stress.yml')
    with pytest.raises(RuntimeError) as e:
        get_env_vars(runner)
    expected_exception = 'Docker container setup environment var value had wrong format.'
    assert expected_exception in str(e.value), \
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

def test_env_variable_skip_unsafe_true():
    runner = Tests.setup_runner(usage_scenario='env_vars_stress.yml', skip_unsafe=True)
    allowed, backtick, dollar, parenthesis = get_env_vars(runner)
    assert allowed == 'alpha-num123_\n', Tests.assertion_info('alpha-num123_', allowed)
    assert backtick == '\n', Tests.assertion_info('empty string', backtick)
    assert dollar == '\n', Tests.assertion_info('empty string', dollar)
    assert parenthesis == '\n', Tests.assertion_info('empty string', parenthesis)

def test_env_variable_allow_unsafe_true():
    runner = Tests.setup_runner(usage_scenario='env_vars_stress.yml', allow_unsafe=True)
    allowed, backtick, dollar, parenthesis = get_env_vars(runner)
    assert allowed == 'alpha-num123_\n', Tests.assertion_info('alpha-num123_', allowed)
    assert backtick == '`\n', Tests.assertion_info('`', backtick)
    assert dollar == '$\n', Tests.assertion_info('$', dollar)
    assert parenthesis == '()\n', Tests.assertion_info('()', parenthesis)

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
        runner.cleanup()
    return port, err

def test_port_bindings_allow_unsafe_true():
    runner = Tests.setup_runner(usage_scenario='port_bindings_stress.yml', allow_unsafe=True)
    port, _ = get_port_bindings(runner)
    assert port.startswith('0.0.0.0:9017'), Tests.assertion_info('0.0.0.0:9017', port)

def test_port_bindings_skip_unsafe_true():
    out = io.StringIO()
    err = io.StringIO()
    runner = Tests.setup_runner(usage_scenario='port_bindings_stress.yml', skip_unsafe=True)

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
    runner = Tests.setup_runner(usage_scenario='port_bindings_stress.yml')
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
    runner = Tests.setup_runner(usage_scenario='setup_commands_stress.yml')

    with redirect_stdout(out), redirect_stderr(err):
        try:
            Tests.run_until(runner, 'setup_services')
        finally:
            runner.cleanup()
    assert 'Running command:  docker exec test-container sh -c ps -a' in out.getvalue(), \
        Tests.assertion_info('stdout message: Running command: <command>', 'no/different stdout message')
    assert '1 root      0:00 /bin/sh' in out.getvalue(), \
        Tests.assertion_info('container stdout showing /bin/sh as process 1', 'different message in container stdout')

def test_setup_commands_multiple_commands():
    out = io.StringIO()
    err = io.StringIO()
    runner = Tests.setup_runner(usage_scenario='setup_commands_multiple_stress.yml')

    with redirect_stdout(out), redirect_stderr(err):
        try:
            Tests.run_until(runner, 'setup_services')
        finally:
            runner.cleanup()

    expected_pattern = re.compile(r'Running command:  docker exec test-container sh -c echo hello world.*\
\s*Stdout: hello world.*\
\s*Running command:  docker exec test-container sh -c ps -a.*\
\s*Stdout: PID   USER     TIME  COMMAND.*\
\s*1 root\s+\d:\d\d /bin/sh.*\
\s*1\d+ root\s+\d:\d\d ps -a.*\
\s*Running command:  docker exec test-container sh -c echo goodbye world.*\
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
        runner.cleanup()
    return ls

#volumes: [array] (optional)
#Array of volumes to be mapped. Only read of runner.py is executed with --allow-unsafe flag
def test_volume_bindings_allow_unsafe_true():
    create_test_file('/tmp/gmt-test-data')
    runner = Tests.setup_runner(usage_scenario='volume_bindings_stress.yml', allow_unsafe=True)
    ls = get_contents_of_bound_volume(runner)
    assert 'test-file' in ls, Tests.assertion_info('test-file', ls)

def test_volumes_bindings_skip_unsafe_true():
    create_test_file('/tmp/gmt-test-data')
    out = io.StringIO()
    err = io.StringIO()
    runner = Tests.setup_runner(usage_scenario='volume_bindings_stress.yml', skip_unsafe=True)

    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception):
        ls = get_contents_of_bound_volume(runner)
        assert ls == '', Tests.assertion_info('empty list', ls)
    expected_warning = '' # expecting no warning for safe volumes
    assert expected_warning in out.getvalue(), \
        Tests.assertion_info(f"Warning: {expected_warning}", 'no/different warning')

def test_volumes_bindings_no_skip_or_allow():
    create_test_file('/tmp/gmt-test-data')
    runner = Tests.setup_runner(usage_scenario='volume_bindings_stress.yml')
    with pytest.raises(RuntimeError) as e:
        ls = get_contents_of_bound_volume(runner)
        assert ls == '', Tests.assertion_info('empty list', ls)
    expected_exception = '' # Expecting no error for safe volumes
    assert expected_exception in str(e.value) ,\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

def test_network_created():
    runner = Tests.setup_runner(usage_scenario='network_stress.yml')
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
        runner.cleanup()
    assert 'gmt-test-network' in ls, Tests.assertion_info('gmt-test-network', ls)

def test_container_is_in_network():
    runner = Tests.setup_runner(usage_scenario='network_stress.yml')
    try:
        Tests.run_until(runner, 'setup_networks')
        ps = subprocess.run(
            ['docker', 'network', 'inspect', 'gmt-test-network'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        inspect = ps.stdout
    finally:
        runner.cleanup()
    assert 'test-container' in inspect, Tests.assertion_info('test-container', inspect)

# cmd: [str] (optional)
#    Command to be executed when container is started.
#    When container does not have a daemon running typically a shell
#    is started here to have the container running like bash or sh
def test_cmd_ran():
    runner = Tests.setup_runner(usage_scenario='cmd_stress.yml')
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
        runner.cleanup()
    assert '1 root      0:00 sh' in docker_ps_out, Tests.assertion_info('1 root      0:00 sh', docker_ps_out)

### The Tests for the runner options/flags
## --uri URI
#   The URI to get the usage_scenario.yml from. Can be either a local directory starting with
#     / or a remote git repository starting with http(s)://
def test_uri_local_dir():
    uri = os.path.abspath(os.path.join(
            CURRENT_DIR, 'stress-application/'))
    project_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', project_name, '--uri', uri ,'--config-override', 'test-config.yml'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    uri_in_db = utils.get_project_data(project_name)['uri']
    assert uri_in_db == uri, Tests.assertion_info(f"uri: {uri}", uri_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

def test_uri_local_dir_missing():
    runner = Tests.setup_runner(usage_scenario='basic_stress.yml', uri='/tmp/missing')
    with pytest.raises(FileNotFoundError) as e:
        runner.run()
    expected_exception = 'No such file or directory: \'/tmp/missing/basic_stress.yml\''
    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

    # basic positive case
def test_uri_github_repo():
    uri = 'https://github.com/green-coding-berlin/pytest-dummy-repo'
    project_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', project_name, '--uri', uri ,'--config-override', 'test-config.yml'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    uri_in_db = utils.get_project_data(project_name)['uri']
    assert uri_in_db == uri, Tests.assertion_info(f"uri: {uri}", uri_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

## --branch BRANCH
#    Optionally specify the git branch when targeting a git repository
def test_uri_local_branch():
    runner = Tests.setup_runner(usage_scenario='basic_stress.yml', branch='test-branch')
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
    project_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', project_name, '--uri', uri ,
        '--branch', 'test-branch' , '--filename', 'basic_stress.yml',
        '--config-override', 'test-config.yml'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    branch_in_db = utils.get_project_data(project_name)['branch']
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
        branch='missing-branch')
    with pytest.raises(subprocess.CalledProcessError) as e:
        runner.run()
    expected_exception = 'returned non-zero exit status 128'
    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

# #   --name NAME
# #    A name which will be stored to the database to discern this run from others
def test_name_is_in_db():
    uri = os.path.abspath(os.path.join(
            CURRENT_DIR, 'stress-application/'))
    project_name = 'test_' + utils.randomword(12)
    subprocess.run(
        ['python3', '../runner.py', '--name', project_name, '--uri', uri ,'--config-override', 'test-config.yml'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    name_in_db = utils.get_project_data(project_name)['name']
    assert name_in_db == project_name, Tests.assertion_info(f"name: {project_name}", name_in_db)

# --filename FILENAME
#    An optional alternative filename if you do not want to use "usage_scenario.yml"
    # basic positive case
def test_different_filename():
    usage_scenario_path = os.path.join(CURRENT_DIR, 'data/usage_scenarios/', 'basic_stress.yml')
    dir_name = utils.randomword(12)
    Tests.make_proj_dir(dir_name=dir_name, usage_scenario_path=usage_scenario_path)
    uri = os.path.join(CURRENT_DIR, 'tmp/', dir_name)
    project_name = 'test_' + utils.randomword(12)

    ps = subprocess.run(
        ['python3', '../runner.py', '--name', project_name, '--uri', uri ,
         '--filename', 'basic_stress.yml', '--config-override', 'test-config.yml'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    with open(usage_scenario_path, 'r', encoding='utf-8') as f:
        usage_scenario_contents = yaml.safe_load(f)
    usage_scenario_in_db = utils.get_project_data(project_name)['usage_scenario']
    assert usage_scenario_in_db == usage_scenario_contents,\
        Tests.assertion_info(usage_scenario_contents, usage_scenario_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

# if that filename is missing...
def test_different_filename_missing():
    uri = os.path.abspath(os.path.join(CURRENT_DIR, '..', 'stress-application/'))
    pid = Tests.insert_project(uri)
    runner = Runner(uri=uri, uri_type='folder', pid=pid, filename='basic_stress.yml')

    with pytest.raises(FileNotFoundError) as e:
        runner.run()
    expected_exception = 'No such file or directory:'
    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

#   --no-file-cleanup
#    Do not delete files in /tmp/green-metrics-tool
def test_no_file_cleanup():
    uri = os.path.abspath(os.path.join(
            CURRENT_DIR, 'stress-application/'))
    project_name = 'test_' + utils.randomword(12)
    subprocess.run(
        ['python3', '../runner.py', '--name', project_name, '--uri', uri ,
         '--no-file-cleanup', '--config-override', 'test-config.yml'],
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
        runner = Tests.setup_runner(usage_scenario='basic_stress.yml', skip_unsafe=True, allow_unsafe=True)
    expected_exception = 'Cannot specify both --skip-unsafe and --allow-unsafe'
    assert str(e.value) == expected_exception, Tests.assertion_info('', str(e.value))

def test_debug(monkeypatch):
    monkeypatch.setattr('sys.stdin', io.StringIO('Enter'))
    uri = os.path.abspath(os.path.join(
            CURRENT_DIR, 'stress-application/'))
    project_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', project_name, '--uri', uri ,
         '--debug', '--config-override', 'test-config.yml'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    expected_output = 'Initial load complete. Waiting to start network setup'
    assert expected_output in ps.stdout, \
        Tests.assertion_info(expected_output, 'no/different output')

    # providers are not started at the same time, but with 2 second delay
    # there is a note added when it starts "Booting {metric_provider}"
    # can check for this note in the DB and the notes are about 2s apart
def test_verbose_provider_boot():
    uri = os.path.abspath(os.path.join(
            CURRENT_DIR, 'stress-application/'))
    project_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', '../runner.py', '--name', project_name, '--uri', uri ,
         '--verbose-provider-boot', '--config-override', 'test-config.yml'],
         # '--config-override', 'test-config.yml'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    pid = utils.get_project_data(project_name)['id']
    query = """
            SELECT
                time, note
            FROM
                notes
            WHERE
                project_id = %s
                AND note LIKE %s
            ORDER BY
                time
            """

    notes = DB().fetch_all(query, (pid,'Booting%',))
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
