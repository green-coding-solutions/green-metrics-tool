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

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../tools")
sys.path.append(f"{current_dir}/../lib")

from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from db import DB
import pytest
import utils
from runner import Runner
from global_config import GlobalConfig

config = GlobalConfig(config_name='test-config.yml').config

## Note:
# Always do asserts after try:finally: blocks
# otherwise failing tests will not run the runner.cleanup() properly

# This should be done once per module
@pytest.fixture(autouse=True, scope="module")
def build_image():
    uri = os.path.abspath(os.path.join(
            current_dir, 'stress-application/'))
    subprocess.run(['docker', 'compose', '-f', uri+'/compose.yml', 'build'], check=True)

# cleanup test/tmp directory after every test run
@pytest.fixture(autouse=True)
def cleanup_tmp_directories():
    yield
    tmp_dir = os.path.join(current_dir, 'tmp/')
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    if os.path.exists('/tmp/gmt-test-data'):
        shutil.rmtree('/tmp/gmt-test-data')

#create test/tmp directory with specified usage_scenario to be passed as uri to runner
def make_proj_dir(dir_name, usage_scenario_path):
    if not os.path.exists('tmp'):
        os.mkdir('tmp')
    os.mkdir('tmp/' + dir_name)
    shutil.copy2(usage_scenario_path, os.path.join(current_dir, 'tmp' ,dir_name))

def insert_project(uri):
    project_name = 'test_' + utils.randomword(12)
    pid = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at") \
                    VALUES \
                    (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(project_name, uri))[0]
    return pid

def assertion_info(expected, actual):
    return f"Expected: {expected}, Actual: {actual}"

#pylint: disable=too-many-arguments
def setup_runner(usage_scenario, uri='default', uri_type='folder', branch=None,
        debug_mode=False, allow_unsafe=False, no_file_cleanup=False,
        skip_unsafe=False, verbose_provider_boot=False):
    usage_scenario_path = os.path.join(current_dir, 'data/usage_scenarios/', usage_scenario)
    if uri == 'default':
        dir_name = utils.randomword(12)
        make_proj_dir(dir_name=dir_name, usage_scenario_path=usage_scenario_path)
        uri = os.path.join(current_dir, 'tmp/', dir_name)
    pid = insert_project(uri)
    return Runner(uri=uri, uri_type=uri_type, pid=pid, filename=usage_scenario, branch=branch,
        debug_mode=debug_mode, allow_unsafe=allow_unsafe, no_file_cleanup=no_file_cleanup,
        skip_unsafe=skip_unsafe, verbose_provider_boot=verbose_provider_boot)

RUNNER_STEPS = ['prepare_filesystem_location',
                'checkout_repository',
                'initial_parse',
                'update_and_insert_specs',
                'import_metric_providers',
                'setup_networks',
                'setup_services',
                'start_metric_providers',
                'pre_idle_containers',
                'start_measurement',
                'run_flows',
                'update_start_and_end_times',
                ]
# This function runs the runner up to and *including* the specified step
#pylint: disable=redefined-argument-from-local
def run_until(runner, step):
    for step in RUNNER_STEPS:
        getattr(runner, step)()

### The tests for usage_scenario configurations

# environment: [object] (optional)
# Key-Value pairs for ENV variables inside the container

def get_env_vars(runner):
    try:
        run_until(runner, 'setup_services')

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
    runner = setup_runner(usage_scenario='env_vars_stress.yml')
    with pytest.raises(RuntimeError) as e:
        get_env_vars(runner)
    expected_exception = 'Docker container setup environment var value had wrong format.'
    assert expected_exception in str(e.value), \
        assertion_info(f"Exception: {expected_exception}", str(e.value))

def test_env_variable_skip_unsafe_true():
    runner = setup_runner(usage_scenario='env_vars_stress.yml', skip_unsafe=True)
    allowed, backtick, dollar, parenthesis = get_env_vars(runner)
    assert allowed == 'alpha-num123_\n', assertion_info('alpha-num123_', allowed)
    assert backtick == '\n', assertion_info('empty string', backtick)
    assert dollar == '\n', assertion_info('empty string', dollar)
    assert parenthesis == '\n', assertion_info('empty string', parenthesis)

def test_env_variable_allow_unsafe_true():
    runner = setup_runner(usage_scenario='env_vars_stress.yml', allow_unsafe=True)
    allowed, backtick, dollar, parenthesis = get_env_vars(runner)
    assert allowed == 'alpha-num123_\n', assertion_info('alpha-num123_', allowed)
    assert backtick == '`\n', assertion_info('`', backtick)
    assert dollar == '$\n', assertion_info('$', dollar)
    assert parenthesis == '()\n', assertion_info('()', parenthesis)

# ports: [int:int] (optional)
# Docker container portmapping on host OS to be used with --allow-unsafe flag.

def get_port_bindings(runner):
    try:
        run_until(runner, 'setup_services')
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
    runner = setup_runner(usage_scenario='port_bindings_stress.yml', allow_unsafe=True)
    port, _ = get_port_bindings(runner)
    assert port == '0.0.0.0:9017\n:::9017\n', assertion_info('0.0.0.0:9017:::9017', port)

def test_port_bindings_skip_unsafe_true():
    out = io.StringIO()
    err = io.StringIO()
    runner = setup_runner(usage_scenario='port_bindings_stress.yml', skip_unsafe=True)

    # need to catch exception here as otherwise the subprocess returning an error will
    # fail the test
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception):
        _, docker_port_err = get_port_bindings(runner)
        expected_container_error = 'Error: No public port \'9018/tcp\' published for test-container\n'
        assert docker_port_err == expected_container_error, \
            assertion_info(f"Container Error: {expected_container_error}", docker_port_err)
    expected_warning = 'Found ports entry but not running in unsafe mode. Skipping'
    assert expected_warning in out.getvalue(), \
        assertion_info(f"Warning: {expected_warning}", 'no/different warning')

def test_port_bindings_no_skip_or_allow():
    runner = setup_runner(usage_scenario='port_bindings_stress.yml')
    with pytest.raises(Exception) as e:
        _, docker_port_err = get_port_bindings(runner)
        expected_container_error = 'Error: No public port \'9018/tcp\' published for test-container\n'
        assert docker_port_err == expected_container_error, \
            assertion_info(f"Container Error: {expected_container_error}", docker_port_err)
    expected_error = 'Found "ports" but neither --skip-unsafe nor --allow-unsafe is set'
    assert expected_error in str(e.value), \
        assertion_info(f"Exception: {expected_error}", str(e.value))

# setup-commands: [array] (optional)
# Array of commands to be run before actual load testing.
# uses ps -a to check that sh is process with PID 1
def test_setup_commands_one_command():
    out = io.StringIO()
    err = io.StringIO()
    runner = setup_runner(usage_scenario='setup_commands_stress.yml')

    with redirect_stdout(out), redirect_stderr(err):
        try:
            run_until(runner, 'setup_services')
        finally:
            runner.cleanup()
    assert 'Running command: docker exec  ps -a' in out.getvalue(), \
        assertion_info('stdout message: Running command: <command>', 'no/different stdout message')
    assert '1 root      0:00 /bin/sh' in out.getvalue(), \
        assertion_info('container stdout showing /bin/sh as process 1', 'different message in container stdout')

def test_setup_commands_multiple_commands():
    out = io.StringIO()
    err = io.StringIO()
    runner = setup_runner(usage_scenario='setup_commands_multiple_stress.yml')

    with redirect_stdout(out), redirect_stderr(err):
        try:
            run_until(runner, 'setup_services')
        finally:
            runner.cleanup()

    expected_pattern = re.compile(r'Running command: docker exec  echo hello world.*\
\s*Stdout: hello world.*\
\s*Running command: docker exec  ps -a.*\
\s*Stdout: PID   USER     TIME  COMMAND.*\
\s*1 root\s+\d:\d\d /bin/sh.*\
\s*1\d+ root\s+\d:\d\d ps -a.*\
\s*Running command: docker exec  echo goodbye world.*\
\s*Stdout: goodbye world.*\
', re.MULTILINE)

    assert re.search(expected_pattern, out.getvalue()), \
        assertion_info('container stdout showing 3 commands run in sequence', 'different messages in container stdout')

def create_test_file(path):
    if not os.path.exists(path):
        os.mkdir(path)
    Path(f"{path}/test-file").touch()

def get_contents_of_bound_volume(runner):
    try:
        run_until(runner, 'setup_services')
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
    runner = setup_runner(usage_scenario='volume_bindings_stress.yml', allow_unsafe=True)
    ls = get_contents_of_bound_volume(runner)
    assert 'test-file' in ls, assertion_info('test-file', ls)

def test_volumes_bindings_skip_unsafe_true():
    create_test_file('/tmp/gmt-test-data')
    out = io.StringIO()
    err = io.StringIO()
    runner = setup_runner(usage_scenario='volume_bindings_stress.yml', skip_unsafe=True)

    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception):
        ls = get_contents_of_bound_volume(runner)
        assert ls == '', assertion_info('empty list', ls)
    expected_warning = 'Found volumes entry but not running in unsafe mode. Skipping'
    assert expected_warning in out.getvalue(), \
        assertion_info(f"Warning: {expected_warning}", 'no/different warning')

def test_volumes_bindings_no_skip_or_allow():
    create_test_file('/tmp/gmt-test-data')
    runner = setup_runner(usage_scenario='volume_bindings_stress.yml')
    with pytest.raises(RuntimeError) as e:
        ls = get_contents_of_bound_volume(runner)
        assert ls == '', assertion_info('empty list', ls)
    expected_exception = 'Found "volumes" but neither --skip-unsafe nor --allow-unsafe is set'
    assert expected_exception in str(e.value) ,\
        assertion_info(f"Exception: {expected_exception}", str(e.value))

def test_network_created():
    runner = setup_runner(usage_scenario='network_stress.yml')
    try:
        run_until(runner, 'setup_networks')
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
    assert 'gmt-test-network' in ls, assertion_info('gmt-test-network', ls)

def test_container_is_in_network():
    runner = setup_runner(usage_scenario='network_stress.yml')
    try:
        run_until(runner, 'setup_networks')
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
    assert 'test-container' in inspect, assertion_info('test-container', inspect)

# cmd: [str] (optional)
#    Command to be executed when container is started.
#    When container does not have a daemon running typically a shell
#    is started here to have the container running like bash or sh
def test_cmd_ran():
    runner = setup_runner(usage_scenario='cmd_stress.yml')
    try:
        run_until(runner, 'setup_services')
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
    assert '1 root      0:00 sh' in docker_ps_out, assertion_info('1 root      0:00 sh', docker_ps_out)

### The tests for the runner options/flags
## --uri URI
#   The URI to get the usage_scenario.yml from. Can be either a local directory starting with
#     / or a remote git repository starting with http(s)://
def test_uri_local_dir():
    runner = setup_runner(usage_scenario='basic_stress.yml')
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    assert err.getvalue() == '', assertion_info('no errors', err.getvalue())

def test_uri_local_dir_missing():
    runner = setup_runner(usage_scenario='basic_stress.yml', uri='/tmp/missing')
    with pytest.raises(FileNotFoundError) as e:
        runner.run()
    expected_exception = 'No such file or directory: \'/tmp/missing/basic_stress.yml\''
    assert expected_exception in str(e.value),\
        assertion_info(f"Exception: {expected_exception}", str(e.value))

    # basic positive case
def test_uri_github_repo():
    runner = setup_runner(usage_scenario='usage_scenario.yml',
        uri='https://github.com/green-coding-berlin/pytest-dummy-repo',
        uri_type='URL')
    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    assert err.getvalue() == '', assertion_info('no errors', err.getvalue())

## --branch BRANCH
#    Optionally specify the git branch when targeting a git repository
def test_uri_local_branch():
    runner = setup_runner(usage_scenario='basic_stress.yml', branch='test-branch')
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(RuntimeError) as e:
        runner.run()
    expected_exception = 'Specified --branch but using local URI. Did you mean to specify a github url?'
    assert str(e.value) == expected_exception, \
        assertion_info(f"Exception: {expected_exception}", str(e.value))

    # basic positive case, branch prepped ahead of time
    # this branch has a different usage_scenario file name - basic_stress
    # that makes sure that it really is pulling a different branch
def test_uri_github_repo_branch():
    runner = setup_runner(usage_scenario='basic_stress.yml',
        uri='https://github.com/green-coding-berlin/pytest-dummy-repo',
        uri_type='URL',
        branch='test-branch')
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    assert err.getvalue() == '', assertion_info('no errors', err.getvalue())

    # should throw error, assert vs error
    # give incorrect branch name
    ## Is the expected_exception OK or should it have a more graceful error?
    ## ATM this is just the default console error of a failed git command
def test_uri_github_repo_branch_missing():
    runner = setup_runner(usage_scenario='basic_stress.yml',
        uri='https://github.com/green-coding-berlin/pytest-dummy-repo',
        uri_type='URL',
        branch='missing-branch')
    with pytest.raises(subprocess.CalledProcessError) as e:
        runner.run()
    expected_exception = 'returned non-zero exit status 128'
    assert expected_exception in str(e.value),\
        assertion_info(f"Exception: {expected_exception}", str(e.value))



# check if there is a project with this name in the db
def check_name_in_db(name):
    return DB().fetch_one('SELECT id FROM "projects" WHERE name=%s', params=(name,))


# #   --name NAME
# #    A name which will be stored to the database to discern this run from others
#     # test if name is in the database
# Name is only put into DB during initial argument parsing, so must call with subprocess
# This is an issue because it does not use the correct test-config.yml file
# and therefore does not connect to the test db.
# Not currently stest_env_variable_forbidden_chars_not_allowedure how to proceed here yet.
#pylint: disable=unused-variable
def wip_test_name_is_in_db():
    name = utils.randomword(12)
    stress_dir = os.path.join(current_dir, 'stress-application')
    ps = subprocess.run(
            ['python3', '../tools/runner.py', '--name', name, '--uri', stress_dir],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
    retval = check_name_in_db(name)
    print(f"retval: {retval}")
    assert False


# --filename FILENAME
#    An optional alternative filename if you do not want to use "usage_scenario.yml"
    # basic positive case
## Skipping as 99% of the above tests use different filenames...
# def test_different_filename():

# if that filename is missing...
def test_different_filename_missing():
    uri = os.path.abspath(os.path.join(current_dir, '..', 'stress-application/'))
    pid = insert_project(uri)
    runner = Runner(uri=uri, uri_type='folder', pid=pid, filename='basic_stress.yml')

    with pytest.raises(FileNotFoundError) as e:
        runner.run()
    expected_exception = 'No such file or directory:'
    assert expected_exception in str(e.value),\
        assertion_info(f"Exception: {expected_exception}", str(e.value))

#   --no-file-cleanup
#    Do not delete files in /tmp/green-metrics-tool
def test_no_file_cleanup():
    runner = setup_runner(usage_scenario='basic_stress.yml', no_file_cleanup=True)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    assert os.path.exists('/tmp/green-metrics-tool'), \
        assertion_info('tmp directory exists', os.path.exists('/tmp/green-metrics-tool'))

#pylint: disable=unused-variable
def test_skip_and_allow_unsafe_both_true():
    with pytest.raises(RuntimeError) as e:
        runner = setup_runner(usage_scenario='basic_stress.yml', skip_unsafe=True, allow_unsafe=True)
    expected_exception = 'Cannot specify both --skip-unsafe and --allow-unsafe'
    assert str(e.value) == expected_exception, assertion_info('', str(e.value))

def test_debug(monkeypatch):
    monkeypatch.setattr('sys.stdin', io.StringIO('Enter'))
    runner = setup_runner(usage_scenario='basic_stress.yml', debug_mode=True)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    expected_output = 'Initial load complete. Waiting to start network setup'
    assert expected_output in out.getvalue(), \
        assertion_info(expected_output, 'no/different output')

    # providers are not started at the same time, but with 2 second delay
    # there is a note added when it starts "Booting {metric_provider}"
    # can check for this note in the DB and the notes are about 2s apart
def test_verbose_provider_boot():
    # not using setup_runner just to have the PID for later, potentially refactor
    dir_name = utils.randomword(12)
    usage_scenario_path = os.path.join(current_dir, 'data/usage_scenarios/basic_stress.yml')
    make_proj_dir(dir_name=dir_name, usage_scenario_path=usage_scenario_path)
    uri = os.path.join(current_dir, 'tmp/', dir_name)
    pid = insert_project(uri)
    runner = Runner(uri=uri,uri_type='folder', pid=pid, filename='basic_stress.yml', verbose_provider_boot=True)

    runner.run()

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
    metric_providers = utils.get_metric_providers(config)

    #for each metric provider, assert there is an an entry in notes
    for provider in metric_providers:
        assert any(provider in note for _, note in notes), \
            assertion_info(f"Booting {provider}", f"notes: {notes}")

    #check that each timestamp in notes is no longer than 2 seconds apart
    for i in range(len(notes)-1):
        diff = notes[i+1][0] - notes[i][0]
        assert 9900000 <= diff <= 10100000, \
            assertion_info('2s apart', f"time difference of notes: {diff}")
