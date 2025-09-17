from contextlib import nullcontext as does_not_raise

import io
import pytest
import re
import os
import platform
import subprocess
import yaml

from contextlib import redirect_stdout, redirect_stderr

from lib.log_types import LogType
from lib.scenario_runner import ScenarioRunner
from lib.global_config import GlobalConfig
from lib.db import DB
from lib import utils
from lib.system_checks import ConfigurationCheckError
from lib import container_compatibility
from tests import test_functions as Tests

GMT_DIR = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../'))

### Tests for the runner options/flags

## --uri URI
#   The URI to get the usage_scenario.yml from. Can be either a local directory starting with
#     / or a remote git repository starting with http(s)://
def test_uri_local_dir():
    run_name = 'test_' + utils.randomword(12)
    filename = 'tests/data/stress-application/usage_scenario.yml'
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--name', run_name, '--uri', GMT_DIR,'--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
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
    runner = ScenarioRunner(uri='/tmp/missing', uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_sleeps=True, dev_cache_build=True, dev_no_save=True)

    with pytest.raises(FileNotFoundError) as e:
        runner.run()


    expected_exception = f"[Errno 2] No such file or directory: '{os.path.realpath('/tmp/missing')}'"

    assert expected_exception == str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

def test_non_git_root_supplied():
    runner = ScenarioRunner(uri=f"{GMT_DIR}/tests/data/usage_scenarios/", uri_type='folder', filename='invalid_image.yml', skip_system_checks=True, dev_cache_build=False, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err), pytest.raises(Exception) as e:
        runner.run()

    assert f"Supplied folder through --uri is not the root of the git repository. Please only supply the root folder and then the target directory through --filename. Real repo root is {GMT_DIR}" == str(e.value)

def test_uri_github_repo_and_using_default_filename():
    uri = 'https://github.com/green-coding-solutions/pytest-dummy-repo'
    default_filename = 'usage_scenario.yml'
    run_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--name', run_name, '--uri', uri ,'--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
        '--skip-system-checks', '--dev-no-sleeps', '--dev-cache-build', '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert ps.returncode == 0
    filename_in_db = utils.get_run_data(run_name)['filename']
    assert filename_in_db == default_filename, Tests.assertion_info(f"filename: {default_filename}", filename_in_db)
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
        ['python3', f'{GMT_DIR}/runner.py', '--name', run_name, '--uri', uri ,
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
        ['python3', f'{GMT_DIR}/runner.py', '--name', run_name, '--uri', GMT_DIR,
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
#    Multiple filenames, wildcards and relative paths are supported

    # basic positive case
def test_different_filename():
    run_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--name', run_name, '--uri', GMT_DIR, '--filename', 'tests/data/usage_scenarios/basic_stress.yml', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
        '--skip-system-checks', '--dev-no-sleeps', '--dev-cache-build', '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    with open(f'{GMT_DIR}/tests/data/usage_scenarios/basic_stress.yml', 'r', encoding='utf-8') as f:
        usage_scenario_contents = yaml.safe_load(f)
    usage_scenario_in_db = utils.get_run_data(run_name)['usage_scenario']
    assert usage_scenario_in_db == usage_scenario_contents, \
        Tests.assertion_info(usage_scenario_contents, usage_scenario_in_db)
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

    # if file does not exist ...
def test_runner_filename_pattern_no_match_error():
    """Test that runner fails gracefully when filename pattern matches no files"""
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--uri', GMT_DIR,
         '--filename', 'tests/data/usage_scenarios/nonexistent_*.yml',
         '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
         '--skip-system-checks', '--dev-cache-build', '--dev-no-sleeps', '--dev-no-save'],
        check=False,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert ps.returncode == 1, "Runner should fail when no files match pattern"
    assert 'No valid files found for --filename pattern' in ps.stdout

    # if file does not exist and ScenarioRunner is called directly
def test_different_filename_missing():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='I_do_not_exist.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_save=True)

    with pytest.raises(FileNotFoundError) as e:
        runner.run()

    # we cannot use == here as file paths will differ throughout systems
    expected_exception = "[Errno 2] No such file or directory"
    assert expected_exception in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception}", str(e.value))

    expected_exception_2 = "I_do_not_exist.yml"
    assert expected_exception_2 in str(e.value),\
        Tests.assertion_info(f"Exception: {expected_exception_2}", str(e.value))

    # Using * wildcard
def test_runner_with_glob_pattern_filename():
    """Test that runner works with glob pattern filenames like folder/*.yml"""
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--uri', GMT_DIR,
         '--filename', 'tests/data/usage_scenarios/runner_filename/basic*.yml',
         '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
         '--skip-system-checks', '--dev-cache-build', '--dev-no-sleeps', '--dev-no-save'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert ps.returncode == 0
    assert 'Running:  tests/data/usage_scenarios/runner_filename/basic_stress_1.yml' in ps.stdout
    assert 'Running:  tests/data/usage_scenarios/runner_filename/basic_stress_2.yml' in ps.stdout
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

    # Using relative path as filename with relative path as URI
def test_runner_filename_relative_to_local_uri():
    """Test that runner works with filename relative to a local URI directory"""
    # Note: The provided folder is not the root of a git repository. Normally that would fail, however we use the `--dev-no-save` flag so this check is skipped.
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--uri', f'{GMT_DIR}/tests/data',
         '--filename', 'usage_scenarios/runner_filename/basic_stress_1.yml',
         '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
         '--skip-system-checks', '--dev-cache-build', '--dev-no-sleeps', '--dev-no-save'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert ps.returncode == 0
    assert 'Running:  usage_scenarios/runner_filename/basic_stress_1.yml' in ps.stdout
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

## --iterations ITERATIONS
#    Optionally specify the number of iterations the files should be executed
def test_runner_with_iterations_and_save_to_database():
    """Test that local URI with iterations works when results are stored to database"""
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--uri', GMT_DIR,
         '--filename', 'tests/data/usage_scenarios/basic_stress.yml',
         '--iterations', '2',
         '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
         '--skip-system-checks', '--dev-cache-build', '--dev-no-sleeps',
         '--dev-no-metrics', '--dev-no-phase-stats', '--dev-no-optimizations'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert ps.returncode == 0
    assert ps.stdout.count('Running:  tests/data/usage_scenarios/basic_stress.yml') == 2
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

def test_runner_with_iterations_and_multiple_files():
    """Test that runner processes files in correct order with --iterations and allows duplicates"""
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--uri', GMT_DIR,
         '--filename', 'tests/data/usage_scenarios/runner_filename/basic_stress_1.yml',
         '--filename', 'tests/data/usage_scenarios/runner_filename/basic_stress_2.yml',
         '--filename', 'tests/data/usage_scenarios/runner_filename/basic_stress_1.yml',
         '--iterations', '2',
         '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
         '--skip-system-checks', '--dev-cache-build', '--dev-no-sleeps', '--dev-no-save'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert ps.returncode == 0
    # Should see basic_stress_1.yml processed 4 times (2 duplicates * 2 iterations)
    # and basic_stress_2.yml processed 2 times (1 instance * 2 iterations)
    assert ps.stdout.count('Running:  tests/data/usage_scenarios/runner_filename/basic_stress_1.yml') == 4
    assert ps.stdout.count('Running:  tests/data/usage_scenarios/runner_filename/basic_stress_2.yml') == 2
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

## --file-cleanup
#   Check that default is to leave the files
def test_no_file_cleanup():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_save=True)
    runner.run()

    assert os.path.exists('/tmp/green-metrics-tool'), \
        Tests.assertion_info('tmp directory exists', os.path.exists('/tmp/green-metrics-tool'))

#   Check that the temp dir is deleted when using --file-cleanup
#   This option exists only in CLI mode
def test_file_cleanup():
    subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--uri', GMT_DIR, '--filename', 'tests/data/usage_scenarios/basic_stress.yml',
         '--file-cleanup', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml", '--skip-system-checks', '--dev-no-sleeps', '--dev-cache-build', '--dev-no-save'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    assert not os.path.exists('/tmp/green-metrics-tool'), \
        Tests.assertion_info('tmp directory exists', not os.path.exists('/tmp/green-metrics-tool'))

## --skip-unsafe and --allow-unsafe
#pylint: disable=unused-variable
def test_skip_and_allow_unsafe_both_true():

    with pytest.raises(ValueError) as e:
        ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_save=True, skip_unsafe=True, allow_unsafe=True)
    expected_exception = 'Cannot specify both --skip-unsafe and --allow-unsafe'
    assert str(e.value) == expected_exception, Tests.assertion_info('', str(e.value))

## --debug
def test_debug(monkeypatch):
    monkeypatch.setattr('sys.stdin', io.StringIO('Enter'))
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--uri', GMT_DIR, '--filename', 'tests/data/usage_scenarios/basic_stress.yml',
         '--debug',
         '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml", '--skip-system-checks',
          '--dev-no-sleeps', '--dev-cache-build', '--dev-no-save'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    expected_output = 'Initial load complete. Waiting to start metric providers'
    assert expected_output in ps.stdout, \
        Tests.assertion_info(expected_output, 'no/different output')

## --skip-systems-check
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
            runner._check_system('start')
    finally:
        GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml") # reset, just in case. although done by fixture

## Variables
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

## Check if metrics provider are already running
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

## Using template
def test_template_website():
    ps = subprocess.run(
        ['bash', os.path.normpath(f"{GMT_DIR}/run-template.sh"), 'website', 'https://www.google.de', '--quick', '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml"],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert ps.returncode == 0
    assert 'MEASUREMENT SUCCESSFULLY COMPLETED' in ps.stdout
    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

## --user-id
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


## Docker pull logic tests
def test_docker_pull_multiarch_image_succeeds():
    """Test successful Docker pull with multi-architecture image"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/docker_pull_multiarch_image.yml',
                          skip_system_checks=True, dev_no_sleeps=True, dev_no_save=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')

    assert runner._usage_scenario['services']['test_service']['image'] == 'alpine:3.22.1'

@pytest.mark.skipif(platform.machine() != 'x86_64', reason="Test requires amd64/x86_64 architecture")
def test_docker_pull_arm64_image_on_amd64_host_fails():
    """Test Docker pull fails when trying to use ARM64 image on AMD64 host"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/docker_pull_arm64_image.yml',
                          skip_system_checks=True, dev_no_sleeps=True, dev_no_save=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "Architecture incompatibility detected" in str(e.value)
    assert "not available for host architecture" in str(e.value)
    assert "amd64" in str(e.value)

@pytest.mark.skipif(platform.machine() != 'aarch64', reason="Test requires arm64/aarch64 architecture")
def test_docker_pull_amd64_image_on_arm64_host_fails():
    """Test Docker pull fails when trying to use AMD64 image on ARM64 host"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/docker_pull_amd64_image.yml',
                          skip_system_checks=True, dev_no_sleeps=True, dev_no_save=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "Architecture incompatibility detected" in str(e.value)
    assert "not available for host architecture" in str(e.value)
    assert "arm64" in str(e.value)

def test_docker_pull_nonexistent_image_non_interactive_fails():
    """Test Docker pull fails due to nonexistent image in non-interactive mode"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/docker_pull_nonexistent.yml',
                          skip_system_checks=True, dev_no_sleeps=True, dev_no_save=True)

    with pytest.raises(OSError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "Docker pull failed. Is your image name correct and are you connected to the internet" in str(e.value)
    assert "NONEXISTENT_IMAGE" in str(e.value)


## Docker run architecture mismatch tests
def can_emulate_amd64_images():
    """Check if this host can run AMD64 Docker images via emulation."""
    return container_compatibility.get_platform_compatibility_status('linux/amd64') == container_compatibility.CompatibilityStatus.EMULATED

def can_emulate_arm64_images():
    """Check if this host can run ARM64 Docker images via emulation."""
    return container_compatibility.get_platform_compatibility_status('linux/arm64') == container_compatibility.CompatibilityStatus.EMULATED

@pytest.mark.skipif(platform.machine() != 'x86_64', reason="Test requires amd64/x86_64 architecture")
@pytest.mark.skipif(can_emulate_arm64_images(), reason="Test is only valid when arm64 can't be emulated")
def test_docker_run_multi_arch_image_with_arm64_digest_on_amd64_host_fails():
    """Test Docker run fails immediately when trying to run ARM64 image on AMD64 host without emulation"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/docker_run_multiarch_image_arm64_digest.yml',
                          skip_system_checks=True, dev_no_sleeps=True, dev_no_save=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    error_msg = str(e.value)
    assert "cannot run due to architecture incompatibility" in error_msg
    assert "arm64" in error_msg and "amd64" in error_msg
    assert "emulation is not available" in error_msg

@pytest.mark.skipif(platform.machine() != 'aarch64', reason="Test requires arm64/aarch64 architecture")
@pytest.mark.skipif(can_emulate_amd64_images(), reason="Test is only valid when amd64 can't be emulated")
def test_docker_run_multi_arch_image_with_amd64_digest_on_arm64_host_fails():
    """Test Docker run fails immediately when trying to run amd64 image on arm64 host without emulation"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/docker_run_multiarch_image_amd64_digest.yml',
                          skip_system_checks=True, dev_no_sleeps=True, dev_no_save=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    error_msg = str(e.value)
    assert "cannot run due to architecture incompatibility" in error_msg
    assert "amd64" in error_msg and "arm64" in error_msg
    assert "emulation is not available" in error_msg

@pytest.mark.skipif(platform.machine() != 'x86_64', reason="Test requires amd64/x86_64 architecture")
@pytest.mark.skipif(not can_emulate_arm64_images(), reason="Test requires Docker with emulation support for arm64 images")
def test_docker_runs_arm64_image_with_emulation_on_amd64_host():
    """Test Docker successfully runs ARM64 images on AMD64 host using emulation and generates warning"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/docker_run_multiarch_image_arm64_digest.yml',
                          skip_system_checks=True, dev_no_sleeps=True, dev_no_save=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        # Test should complete successfully without raising exceptions AND generate emulation warning
        warnings = runner._ScenarioRunner__warnings
        assert any("will run with architecture emulation" in warning for warning in warnings), f"Expected architecture emulation warning not found in: {warnings}"
        emulation_warnings = [w for w in warnings if "emulation" in w.lower()]
        assert len(emulation_warnings) > 0, f"No emulation warnings found in: {warnings}"
        assert any("arm64" in warning and "amd64" in warning for warning in emulation_warnings), f"Warning should mention both architectures: {emulation_warnings}"

@pytest.mark.skipif(platform.machine() != 'aarch64', reason="Test requires arm64/aarch64 architecture")
@pytest.mark.skipif(not can_emulate_amd64_images(), reason="Test requires Docker with emulation support for amd64 images")
def test_docker_runs_amd64_image_with_emulation_on_arm64_host():
    """Test Docker successfully runs AMD64 images on ARM64 host using emulation and generates warning"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/docker_run_multiarch_image_amd64_digest.yml',
                          skip_system_checks=True, dev_no_sleeps=True, dev_no_save=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        # Test should complete successfully without raising exceptions AND generate emulation warning
        warnings = runner._ScenarioRunner__warnings
        assert any("will run with architecture emulation" in warning for warning in warnings), f"Expected architecture emulation warning not found in: {warnings}"
        emulation_warnings = [w for w in warnings if "emulation" in w.lower()]
        assert len(emulation_warnings) > 0, f"No emulation warnings found in: {warnings}"
        assert any("amd64" in warning and "arm64" in warning for warning in emulation_warnings), f"Warning should mention both architectures: {emulation_warnings}"

## Container running verification
def test_container_running_verification_after_boot_phase():
    """Test that container verification catches containers that exit during boot phase"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder',
                          filename='tests/data/usage_scenarios/basic_stress.yml',
                          skip_system_checks=True, dev_no_sleeps=True, dev_cache_build=True, dev_no_save=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            for step in context.run_steps():
                if step == 'setup_services':
                    # Simulate container failure by stopping it manually
                    subprocess.run(['docker', 'stop', 'test-container'], check=False)

    assert "Container 'test-container' failed during boot phase (exit code: 137)" in str(e.value)

def test_container_running_verification_after_runtime_phase():
    """Test that container verification catches containers that exit during runtime phase"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder',
                          filename='tests/data/usage_scenarios/basic_stress.yml',
                          skip_system_checks=True, dev_no_sleeps=True, dev_cache_build=True, dev_no_save=True)

    with pytest.raises(RuntimeError) as e:
        with Tests.RunUntilManager(runner) as context:
            for step in context.run_steps():
                if step == 'runtime_complete':
                    # Simulate container failure by stopping it manually
                    subprocess.run(['docker', 'stop', 'test-container'], check=False)

    assert "Container 'test-container' failed during runtime phase (exit code: 137)" in str(e.value)


    ## rethink this one
def wip_test_verbose_provider_boot():
    run_name = 'test_' + utils.randomword(12)
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--name', run_name, '--uri', GMT_DIR,
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

    # providers are not started at the same time, but with 2 second delay
    # there is a note added when it starts "Booting {metric_provider}"
    # can check for this note in the DB and the notes are about 2s apart
    notes = DB().fetch_all(query, (run_id,'Booting%',))
    metric_providers = utils.get_metric_providers_names(GlobalConfig().config)

    #for each metric provider, assert there is an an entry in notes
    for provider in metric_providers:
        assert any(provider in note for _, note in notes), \
            Tests.assertion_info(f"note: 'Booting {provider}'", f"notes: {notes}")

    #check that each timestamp in notes roughly 10 seconds apart
    for i in range(len(notes)-1):
        diff = (notes[i+1][0] - notes[i][0])/1000000
        assert 9.9 <= diff <= 10.1, \
            Tests.assertion_info('10s apart', f"time difference of notes: {diff}s")

## Logging
def test_logs_structure():
    """Test that logs stored in database are structured in JSON format with proper metadata"""
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/capture_logs.yml',
                          skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True,
                          dev_no_metrics=True, dev_no_phase_stats=True, dev_no_save=False)

    run_id = runner.run()

    logs_result = DB().fetch_one("SELECT logs FROM runs WHERE id = %s", params=(run_id,))
    assert logs_result is not None, "Should have logs stored in database"
    assert logs_result[0] is not None, "Logs field should not be null"

    logs = logs_result[0]

    assert isinstance(logs, dict), "Logs should be in dictionary format"
    assert "test-container" in logs, "Should have logs for test-container"

    container_logs = logs["test-container"]
    assert isinstance(container_logs, list), "Container logs should be a list"
    assert len(container_logs) == 3, f"Should have exactly 3 log entries (container stdout, setup stdout, flow stdout+stderr), found {len(container_logs)}"

    # First check the structure
    for log_entry in container_logs:
        assert isinstance(log_entry, dict), "Each log entry should be a dictionary"
        assert "type" in log_entry, "Log entry should have 'type' field"
        assert "id" in log_entry, "Log entry should have 'id' field"
        assert "cmd" in log_entry, "Log entry should have 'cmd' field"
        assert "phase" in log_entry, "Log entry should have 'phase' field"

        # Check that type is a valid LogType value
        assert log_entry["type"] in [lt.value for lt in LogType], f"Invalid log type: {log_entry['type']}"

        # If it's a flow command, it should have a flow field
        if log_entry["type"] == LogType.FLOW_COMMAND.value:
            assert "flow" in log_entry, "Flow commands should have 'flow' field"

        # Should have either stdout or stderr (or both)
        assert "stdout" in log_entry or "stderr" in log_entry, "Log entry should have stdout or stderr"

        # Should not have both empty - if both are present, at least one should have content
        if "stdout" in log_entry and "stderr" in log_entry:
            assert log_entry["stdout"].strip() or log_entry["stderr"].strip(), "At least one of stdout/stderr should have non-empty content"
        elif "stdout" in log_entry:
            assert log_entry["stdout"].strip(), "stdout should have non-empty content"
        elif "stderr" in log_entry:
            assert log_entry["stderr"].strip(), "stderr should have non-empty content"

    # Now check for specific expected log content
    found_flow_stdout = False
    found_flow_stderr = False
    found_setup_command = False
    found_container_execution = False

    for log_entry in container_logs:
        # Flow command logs
        if "stdout" in log_entry and "Test log message from flow" in log_entry["stdout"]:
            found_flow_stdout = True
            assert log_entry["type"] == LogType.FLOW_COMMAND.value, "Should be a flow command"
            assert log_entry["phase"] == "[RUNTIME]", "Should be in RUNTIME phase"
            assert log_entry["cmd"].startswith("docker exec"), "Flow commands should start with 'docker exec'"
            assert log_entry["flow"] == "Flow Name", "Should have flow name"
        if "stderr" in log_entry and "Test error message from flow" in log_entry["stderr"]:
            found_flow_stderr = True

        # Setup command logs
        if "stdout" in log_entry and "Test log from setup-commands" in log_entry["stdout"]:
            found_setup_command = True
            assert log_entry["type"] == LogType.SETUP_COMMAND.value, "Should be a setup command"
            assert log_entry["phase"] == "[BOOT]", "Should be in BOOT phase"
            assert log_entry["cmd"].startswith("docker exec"), "Setup commands should start with 'docker exec'"

        # Container execution logs
        if "stdout" in log_entry and "Test log from container" in log_entry["stdout"]:
            found_container_execution = True
            assert log_entry["type"] == LogType.CONTAINER_EXECUTION.value, "Should be container execution"
            assert log_entry["phase"] == "[MULTIPLE]", "Container logs should be collected over multiple phases"
            assert log_entry["cmd"].startswith("docker run"), "Container execution should start with 'docker run'"

    assert found_flow_stdout, "Should find the test flow stdout message"
    assert found_flow_stderr, "Should find the test flow stderr message"
    assert found_setup_command, "Should find the setup command log"
    assert found_container_execution, "Should find the container execution log"

def test_all_run_logs_comprehensive():
    """Comprehensive test of _get_all_run_logs() method covering single runs, iterations, and different files"""

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/capture_logs.yml',
                          skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_save=True)

    # Test 1: Single run - basic structure
    runner.run()
    logs = runner._get_all_run_logs()

    assert isinstance(logs, list), "Logs should be a list"
    assert len(logs) == 1, "Should have one run entry after first run"

    run_entry = logs[0]
    assert isinstance(run_entry, dict), "Run entry should be a dictionary"
    assert "iteration" in run_entry, "Run entry should have 'iteration' field"
    assert "filename" in run_entry, "Run entry should have 'filename' field"
    assert "containers" in run_entry, "Run entry should have 'containers' field"

    assert run_entry["iteration"] == 1, "First run should be iteration 1"
    assert run_entry["filename"] == 'tests/data/usage_scenarios/capture_logs.yml', "Filename should match"
    assert isinstance(run_entry["containers"], dict), "Containers should be a dictionary"

    # Test container logs structure
    containers = run_entry["containers"]
    assert "test-container" in containers, "Should have logs for test-container"
    container_logs = containers["test-container"]
    assert isinstance(container_logs, list), "Container logs should be a list"
    assert len(container_logs) > 0, "Should have at least one log entry"

    for log_entry in container_logs:
        assert isinstance(log_entry, dict), "Each log entry should be a dictionary"
        assert "type" in log_entry, "Log entry should have 'type' field"
        assert "stdout" in log_entry or "stderr" in log_entry, "Log entry should have stdout or stderr"

    # Test 2: Multiple iterations of same file
    runner.run()  # Second run of same file
    logs = runner._get_all_run_logs()

    assert len(logs) == 2, "Should have two run entries after second run"

    run1, run2 = logs[0], logs[1]
    assert run1["iteration"] == 1, "First run should be iteration 1"
    assert run2["iteration"] == 2, "Second run should be iteration 2"
    assert run1["filename"] == run2["filename"], "Both runs should have same filename"
    assert "test-container" in run1["containers"], "First run should have container logs"
    assert "test-container" in run2["containers"], "Second run should have container logs"

    # Test 3: Different filename (reset iteration count)
    runner.set_filename('tests/data/usage_scenarios/basic_stress.yml')
    runner.run()  # Third run with different file
    logs = runner._get_all_run_logs()

    assert len(logs) == 3, "Should have three run entries after third run"

    run3 = logs[2]
    assert run3["iteration"] == 1, "First run of different file should be iteration 1"
    assert run3["filename"] == 'tests/data/usage_scenarios/basic_stress.yml', "Third run should have different filename"
    assert isinstance(run3["containers"], dict), "Third run should have containers dict"

def test_print_logs_integration():
    """Integration test for --print-logs CLI flag with iterations"""
    ps = subprocess.run(
        ['python3', f'{GMT_DIR}/runner.py', '--uri', GMT_DIR,
         '--filename', 'tests/data/usage_scenarios/capture_logs.yml',
         '--iterations', '2', '--print-logs',
         '--config-override', f"{os.path.dirname(os.path.realpath(__file__))}/test-config.yml",
         '--skip-system-checks', '--dev-cache-build', '--dev-no-sleeps', '--dev-no-save'],
        check=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )

    assert ps.returncode == 0
    print(ps.stdout)

    assert "Container logs:" in ps.stdout
    container_logs_pos = ps.stdout.find("Container logs:")
    assert container_logs_pos != -1

    container_logs_section = ps.stdout[container_logs_pos:]

    assert "test-container" in container_logs_section

    test_log_count = container_logs_section.count("Test log message from flow")
    test_error_count = container_logs_section.count("Test error message from flow")

    assert test_log_count >= 1, f"Expected at least 1 'Test log message from flow' entry, found {test_log_count}"
    assert test_error_count >= 1, f"Expected at least 1 'Test error message from flow' entry, found {test_error_count}"

    test_log_pos = container_logs_section.find("Test log message from flow")
    test_error_pos = container_logs_section.find("Test error message from flow")

    assert test_log_pos != -1
    assert test_error_pos != -1
    assert test_log_pos < test_error_pos

    assert ps.stderr == '', Tests.assertion_info('no errors', ps.stderr)

## automatic database reconnection
def test_database_reconnection_during_run():
    """Verify GMT runner handles database reconnection during execution
    
    This test simulates a database outage scenario:
    1. A first succesful database query occurs at step 'initialize_run'
    2. After this step, a database restart is triggered to simulate an outage
    3. The next database query occurs at step 'save_image_and_volume_sizes':
       Initially it fails due to the outage, but the retry mechanism should recover it
    """

    out = io.StringIO()
    err = io.StringIO()
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_optimizations=True)

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            for pause_point in context.run_steps(stop_at='save_image_and_volume_sizes'):
                if pause_point == 'initialize_run':
                    # Simulate short db outage
                    result = subprocess.run(['docker', 'restart', '-t', '0', 'test-green-coding-postgres-container'],
                                            check=True, capture_output=True)

    assert ('Database connection error' in out.getvalue() and 'Retrying in' in out.getvalue()), \
        "No database retry messages found - test may not have properly simulated database outage"
