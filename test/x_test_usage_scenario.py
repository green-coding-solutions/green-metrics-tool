# https://docs.docker.com/engine/reference/commandline/port/
# List port mappings or a specific mapping for the container
#  docker port CONTAINER [PRIVATE_PORT[/PROTO]]


#pylint: disable=fixme,import-error,wrong-import-position, global-statement, unused-argument, invalid-name
# unused-argument because its not happy with 'module', which is unfortunately necessary for pytest
# also disabled invalid-name because its not happy with single word for d in data , for example

#pytestmark = pytest.mark.skip("all tests still WIP")

import io
import os
import pytest
import shutil
import sys
import subprocess
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../tools")
sys.path.append(f"{current_dir}/../lib")

from contextlib import redirect_stdout, redirect_stderr
from db import DB
from pathlib import Path
import utils
from runner import Runner
from global_config import GlobalConfig

config = GlobalConfig(config_name='test-config.yml').config
run_stderr = ''
run_stdout = ''

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
def run_until(runner, step):
    for step in RUNNER_STEPS:
        getattr(runner, step)()

### The tests for usage_scenario configurations

# environment: [object] (optional)
# Key-Value pairs for ENV variables inside the container

def test_env_variable_allow_unsafe_true():
    runner = setup_runner(usage_scenario='env_vars_stress.yml', allow_unsafe=True)
    echo_out = None
    try:
        run_until(runner, 'setup_services')
        ps = subprocess.run(
                ['docker', 'exec', 'test-container', '/bin/sh', 
                '-c', 'echo $TEST'],
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='UTF-8'
            )
        echo_out = ps.stdout
    finally:
        runner.cleanup()
    assert echo_out == 'hello world\n'

def test_env_variable_skip_unsafe_true():
    runner = setup_runner(usage_scenario='env_vars_stress.yml', skip_unsafe=True)
    echo_out = None
    try:
        run_until(runner, 'setup_services')
        ps = subprocess.run(
                ['docker', 'exec', 'test-container', '/bin/sh', 
                '-c', 'echo $TEST'],
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='UTF-8'
            )
        echo_out = ps.stdout
    finally:
        runner.cleanup()
    assert echo_out == '\n'

def test_env_variable_no_skip_or_allow():
    runner = setup_runner(usage_scenario='env_vars_stress.yml')
    with pytest.raises(Exception) as e:
        try:
            run_until(runner, 'setup_services')
            ps = subprocess.run(
                ['docker', 'exec', 'test-container', '/bin/sh', 
                '-c', 'echo $TEST'],
                check=True,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE,
                encoding='UTF-8'
            )
            echo_out = ps.stdout
        finally:
            runner.cleanup()
        assert echo_out == ''
    assert 'Maybe consider using --allow-unsafe --skip-unsafe' in str(e.value)


## THINK ABOUT THIS ONE
# problem - i could check $PATH
# but $PATH still returns something, and I think
# in a container its identical to a GH VM so its a false postivie

# one way to do it -
# set a host path variable (remember to cleanup!)
# then check for that host path variable afterwards
@pytest.fixture
def setup_env_variable():
    os.environ["GMTTEST"] = "wakkawakka"
    yield
    del os.environ["GMTTEST"]

# Why doens't this work?
# Is there a better way to do this test?
def wip_test_env_variable_host_vars_not_readable(setup_env_variable):   
    runner = setup_runner(usage_scenario='env_vars_stress.yml', allow_unsafe=True)
    ps = subprocess.run(
            ['echo', '$GMTTEST'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
    print(ps.stdout)
    try:
        run_until(runner, 'setup_services')
        ps = subprocess.run(
            ['docker', 'exec', 'test-container', '/bin/sh', 
            '-c', 'echo $GMTTEST'],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8'
        )
        echo_out = ps.stdout
    finally:
        runner.cleanup()
    assert echo_out == '\nasdf'

# ports: [int:int] (optional)
# Docker container portmapping on host OS to be used with --allow-unsafe flag.

def test_port_bindings_allow_unsafe_true():
    runner = setup_runner(usage_scenario='port_bindings_stress.yml', allow_unsafe=True)
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
    finally:
        runner.cleanup()
    assert port == '0.0.0.0:9017\n:::9017\n'

def test_port_bindings_skip_unsafe_true():
    out = io.StringIO()
    err = io.StringIO()
    runner = setup_runner(usage_scenario='port_bindings_stress.yml', skip_unsafe=True)

    # need to catch exception here as otherwise the subprocess returning an error will
    # fail the test
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        try:
            run_until(runner, 'setup_services')
            ps = subprocess.run(
                    ['docker', 'port', 'test-container', '9018'],
                    check=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    encoding='UTF-8'
                )
            docker_port_err = ps.stderr
        finally:
            runner.cleanup()
        assert docker_port_err == 'Error: No public port \'9018/tcp\' published for test-container\n'
    assert 'Found ports entry but not running in unsafe mode. Skipping' in out.getvalue()

def test_port_bindings_no_skip_or_allow():
    runner = setup_runner(usage_scenario='port_bindings_stress.yml')
    with pytest.raises(Exception) as e:
        try:
            run_until(runner, 'setup_services')
            ps = subprocess.run(
                    ['docker', 'port', 'test-container', '9018'],
                    check=True,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    encoding='UTF-8'
                )
            docker_port_err = ps.stderr
        finally:
            runner.cleanup()
        assert docker_port_err == 'Error: No public port \'9018/tcp\' published for test-container\n'
    assert 'Found "ports" but neither --skip-unsafe nor --allow-unsafe is set' in str(e.value)

# setup-commands: [array] (optional)
# Array of commands to be run before actual load testing. 
# uses ps -a to check that sh is process with PID 1
# q: in a VM, still true?
def test_setup_commands_one_command():
    out = io.StringIO()
    err = io.StringIO()
    runner = setup_runner(usage_scenario='setup_commands_stress.yml')

    with redirect_stdout(out), redirect_stderr(err):
        try:
            run_until(runner, 'setup_services')
        finally:
            runner.cleanup()
    assert 'Running command: docker exec  ps -a' in out.getvalue()
    assert '1 root      0:00 /bin/sh' in out.getvalue()

## Why does this test fail when run in full, but not on its own??
def test_setup_commands_multiple_commands():
    out = io.StringIO()
    err = io.StringIO()
    runner = setup_runner(usage_scenario='setup_commands_multiple_stress.yml')

    with redirect_stdout(out), redirect_stderr(err):
        try:
            run_until(runner, 'setup_services')
        finally:
            runner.cleanup()
    print(out.getvalue())
    expected = 'Running command: docker exec  echo hello world\n\
Stdout: hello world\n\n\
Running command: docker exec  ps -a\n\
Stdout: PID   USER     TIME  COMMAND\n\
    1 root      0:00 /bin/sh\n\
   13 root      0:00 ps -a\n\n\
Running command: docker exec  echo goodbye world\n\
Stdout: goodbye world\n'
    print(out.getvalue()) # debug
    assert expected in out.getvalue()

def create_test_file(path):
    if not os.path.exists(path):
        os.mkdir(path)
    Path(f"{path}/test-file").touch()

#volumes: [array] (optional)
#Array of volumes to be mapped. Only read of runner.py is executed with --allow-unsafe flag
def test_volume_bindings_allow_unsafe_true():
    create_test_file('/tmp/gmt-test-data')
    runner = setup_runner(usage_scenario='volume_bindings_stress.yml', allow_unsafe=True)
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
    assert 'test-file' in ls

def test_volumes_bindings_skip_unsafe_true():
    create_test_file('/tmp/gmt-test-data')
    out = io.StringIO()
    err = io.StringIO()
    runner = setup_runner(usage_scenario='volume_bindings_stress.yml', skip_unsafe=True)

    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
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
        assert ls == ''
    assert 'Found volumes entry but not running in unsafe mode. Skipping' in out.getvalue()

def test_volumes_bindings_no_skip_or_allow():
    create_test_file('/tmp/gmt-test-data')
    runner = setup_runner(usage_scenario='volume_bindings_stress.yml')
    with pytest.raises(Exception) as e:
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
        assert ls == ''
    assert 'Found "volumes" but neither --skip-unsafe nor --allow-unsafe is set' in str(e)

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
    assert 'gmt-test-network' in ls

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
    assert 'test-container' in inspect

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
    print(docker_ps_out)
    assert '1 root      0:00 sh' in docker_ps_out

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
    assert err.getvalue() == ''

def test_uri_local_dir_missing():
    runner = setup_runner(usage_scenario='basic_stress.yml', uri='/tmp/missing')
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()
    assert 'No such file or directory: \'/tmp/missing/basic_stress.yml\'' in str(e.value)

# def test_uri_github_repo():
#     # setup a test repo on github
#     # https://github.com/green-coding-berlin/simple-example-application
#     # basic positive case

# ## --branch BRANCH       
# #    Optionally specify the git branch when targeting a git repository
# def test_uri_local_branch():
#     # should throw error
#     # assert aginst error

# def test_uri_github_repo_branch():
#     # basic positive case, branch prepped ahead of time

# def test_uri_github_repo_branch_missing():
#     # give incorrect branch name
#     # should throw error, assert vs error

# #   --name NAME           
# #    A name which will be stored to the database to discern this run from others
# def test_name_is_in_db():
#     # as implied, test if name is in DB
#     # Open Question: is there a way to "stop" the run early? just to save on time

# --filename FILENAME   
#    An optional alternative filename if you do not want to use "usage_scenario.yml"
# def test_different_filename():
    # rename usage_scenario
    # basic positive case

# def test_different_filename_missing():
#     # does it default to usage_scenario?
#     # if:y, check with/without usage_scenario backup

# #   --no-file-cleanup     
# #    Do not delete files in /tmp/green-metrics-tool
# def test_no_file_cleanup():
#     # What files should be written there?
#     #    its the repo from GH at least
#     #    '/tmp/green-metrics-tool/repo'
#     #        what if its localdir? is anything written there?
#     #
#     ## test that these files exist -> /tmp/green-metrics-tool
#     # no need to go further than this

# def test_skip_and_allow_unsafe_both_true():
#     # what *should* happen here?
#     # honestly probably should be an error
#     # should fail, implement if it doesn't exist
#        # this can be done in the constructor

# def test_verbose_provider_boot():
#     # providers are not started at the same time, but with 2 second delay
#     # there is a note added when it starts "Booting {metric_provider}"
#     # can check for this note in the DB
#     # and the notes are about 2s apart

# def test_debug():
# ## it stops the execution
# # safe to check for first inital laod complete message


# ## Do this as a seperate task/file
# # just notes for now
# ### Test Flow
# # flow: [array] (Array of flows to interact with containers)
# #     name: [str] An arbitrary name, that helps you distinguish later on where the load happend in the chart
# #     container: [a-zA-Z0-9_] The name of the container specified on setup which you want the run the flow
# #     commands: [array]
# #         type: [console] (Only console currently supported)
# #                 console will execute a shell command inside the container
# #         command: [str]
# #                 The command to be executed. 
# #                 If type is console then piping or moving to background is not supported.
# #         detach: [bool] (optional. default false)
# #                 When the command is detached it will get sent to the background.
# #                  This allows to run commands in parallel if needed, for instance if you want to stress the DB in parallel with a web request
# #         note:   [str] (optional)
# #                 A string that will appear as note attached to the datapoint of measurement (optional)
# #         read-notes-stdout: [bool] (optional)
# #                 Read notes from the STDOUT of the command. This is helpful if you have a long running command that does multiple steps and you want to log every step.


