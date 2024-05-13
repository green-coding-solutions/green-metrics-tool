import os
import re
import shutil
import subprocess
import io

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from contextlib import redirect_stdout, redirect_stderr
import pytest

from tests import test_functions as Tests

from lib import utils
from lib.global_config import GlobalConfig
from runner import Runner

GlobalConfig().override_config(config_name='test-config.yml')

@pytest.fixture(autouse=True, name="cleanup_tmp_directories")
def cleanup_tmp_directories_fixture():
    yield
    tmp_dir = os.path.join(CURRENT_DIR, 'tmp/')
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)

def check_if_container_running(container_name):
    ps = subprocess.run(
            ['docker', 'container', 'inspect', '-f', '{{.State.Running}}', container_name],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8',
            check=False,
        )
    if ps.returncode != 0:
        return False
    return True

def test_volume_load_no_escape():
    tmp_dir_name = utils.randomword(12)
    tmp_dir = os.path.join(CURRENT_DIR, 'tmp', tmp_dir_name, 'basic_stress_w_import.yml')
    runner = Tests.setup_runner(usage_scenario='basic_stress_w_import.yml', docker_compose='volume_load_etc_passwords.yml', dir_name=tmp_dir_name, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)
    Tests.replace_include_in_usage_scenario(tmp_dir, 'volume_load_etc_passwords.yml')

    try:
        with pytest.raises(RuntimeError) as e:
            Tests.run_until(runner, 'setup_services')
    finally:
        container_running = check_if_container_running('test-container')
        runner.cleanup()

    expected_error = 'Service \'test-container\' volume path (/etc/passwd) is outside allowed folder:'
    assert str(e.value).startswith(expected_error), Tests.assertion_info(expected_error, str(e.value))
    assert container_running is False, Tests.assertion_info('test-container stopped', 'test-container was still running!')

def create_tmp_dir():
    tmp_dir_name = utils.randomword(12)
    if not os.path.exists(os.path.join(CURRENT_DIR, 'tmp/')):
        os.mkdir(os.path.join(CURRENT_DIR, 'tmp/'))
    os.mkdir('tmp/' + tmp_dir_name)
    tmp_dir = os.path.join(CURRENT_DIR, f'tmp/{tmp_dir_name}')
    return tmp_dir, tmp_dir_name

def copy_compose_and_edit_directory(compose_file, tmp_dir):
    tmp_compose_file = os.path.join(tmp_dir, 'docker-compose.yml')
    shutil.copyfile(
        os.path.join(CURRENT_DIR, f'data/docker-compose-files/{compose_file}'),
        tmp_compose_file)

    #regex replace CURRENT_DIR in docker-compose.yml with temp proj directory where test-file exists
    with open(tmp_compose_file, 'r', encoding='utf-8') as file:
        data = file.read()
        data = re.sub(r'CURRENT_DIR', tmp_dir, data)
    with open(tmp_compose_file, 'w', encoding='utf-8') as file:
        file.write(data)

def test_load_files_from_within_gmt():
    tmp_dir, tmp_dir_name = create_tmp_dir()
    Tests.create_test_file(tmp_dir)

    # copy compose file over so that we can edit it safely
    copy_compose_and_edit_directory('volume_load_within_proj.yml', tmp_dir)

    # setup runner and run test
    runner = Tests.setup_runner(usage_scenario='basic_stress_w_import.yml', dir_name=tmp_dir_name, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)
    Tests.replace_include_in_usage_scenario(os.path.join(tmp_dir, 'basic_stress_w_import.yml'), 'docker-compose.yml')

    try:
        Tests.run_until(runner, 'setup_services')
        # check that the volume was loaded
        ps = subprocess.run(
            ['docker', 'exec', 'test-container', '/bin/sh',
            '-c', 'test -f /tmp/test-file && echo "File mounted"'],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8',
            check=False,
        )
        out = ps.stdout
        err = ps.stderr
    finally:
        Tests.cleanup(runner)
    assert "File mounted" in out, Tests.assertion_info('/tmp/test-file mounted', f"out: {out} | err: {err}")

def test_symlinks_should_fail():
    tmp_dir, tmp_dir_name = create_tmp_dir()
    # make a symlink to /etc/passwords in tmp_dir
    symlink = os.path.join(tmp_dir, 'symlink')
    os.symlink('/etc/passwd', os.path.join(tmp_dir, 'symlink'))

    copy_compose_and_edit_directory('volume_load_symlinks_negative.yml', tmp_dir)

    runner = Tests.setup_runner(usage_scenario='basic_stress_w_import.yml', dir_name=tmp_dir_name, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)
    Tests.replace_include_in_usage_scenario(os.path.join(tmp_dir, 'basic_stress_w_import.yml'), 'docker-compose.yml')

    try:
        with pytest.raises(RuntimeError) as e:
            Tests.run_until(runner, 'setup_services')
    finally:
        container_running = check_if_container_running('test-container')
        runner.cleanup()

    expected_error = f"Service 'test-container' volume path ({symlink}) is outside allowed folder:"
    assert str(e.value).startswith(expected_error), Tests.assertion_info(expected_error, str(e.value))
    assert container_running is False, Tests.assertion_info('test-container stopped', 'test-container was still running!')

def test_non_bind_mounts_should_fail():
    tmp_dir_name = create_tmp_dir()[1]
    tmp_dir_usage = os.path.join(CURRENT_DIR, 'tmp', tmp_dir_name, 'basic_stress_w_import.yml')
    runner = Tests.setup_runner(usage_scenario='basic_stress_w_import.yml', docker_compose='volume_load_non_bind_mounts.yml', dir_name=tmp_dir_name, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)
    Tests.replace_include_in_usage_scenario(tmp_dir_usage, 'volume_load_non_bind_mounts.yml')

    try:
        with pytest.raises(RuntimeError) as e:
            Tests.run_until(runner, 'setup_services')
    finally:
        container_running = check_if_container_running('test-container')
        runner.cleanup()

    expected_error = 'volume path does not exist'
    assert expected_error in str(e.value), Tests.assertion_info(expected_error, str(e.value))
    assert container_running is False, Tests.assertion_info('test-container stopped', 'test-container was still running!')

def test_load_volume_references():
    tmp_dir, tmp_dir_name = create_tmp_dir()
    Tests.create_test_file(tmp_dir)

    copy_compose_and_edit_directory('volume_load_references.yml', tmp_dir)

    runner = Tests.setup_runner(usage_scenario='basic_stress_w_import.yml', dir_name=tmp_dir_name, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)
    Tests.replace_include_in_usage_scenario(os.path.join(tmp_dir, 'basic_stress_w_import.yml'), 'docker-compose.yml')

    try:
        Tests.run_until(runner, 'setup_services')
        # check that the volume was loaded
        ps = subprocess.run(
            ['docker', 'exec', 'test-container-2', '/bin/sh',
            '-c', 'test -f /tmp/test-file && echo "File mounted"'],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8',
            check=False,
        )
        out = ps.stdout
        err = ps.stderr
    finally:
        Tests.cleanup(runner)
    assert "File mounted" in out, Tests.assertion_info('/tmp/test-file mounted', f"out: {out} | err: {err}")

def test_volume_loading_subdirectories_root():
    uri = os.path.join(CURRENT_DIR, 'data/test_cases/subdir_volume_loading')
    RUN_NAME = 'test_' + utils.randomword(12)
    runner = Runner(name=RUN_NAME, uri=uri, uri_type='folder', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    run_stderr = err.getvalue()
    run_stdout = out.getvalue()
    assert run_stderr == '', Tests.assertion_info('stderr empty', f"stderr: {run_stderr}")

    expect_content_testfile_root = "stdout from process: ['docker', 'exec', 'test-container-root', 'grep', 'testfile-root-content', '/tmp/testfile-root'] testfile-root-content"
    assert expect_content_testfile_root in run_stdout, Tests.assertion_info(expect_content_testfile_root, f"expected output not in {run_stdout}")

    expect_extra_testfile_root = "stdout from process: ['docker', 'exec', 'test-container-root', 'grep', 'testfile-root-content', '/tmp/testfile-root-extra-copied'] testfile-root-content"
    assert expect_extra_testfile_root in run_stdout, Tests.assertion_info(expect_extra_testfile_root, f"expected output not in {run_stdout}")

    expect_mounted_testfile = "stdout from process: ['docker', 'exec', 'test-container', 'grep', 'testfile-content', '/tmp/testfile-correctly-mounted'] testfile-content"
    assert expect_mounted_testfile in run_stdout, Tests.assertion_info(expect_mounted_testfile, f"expected output not in {run_stdout}")

    expect_mounted_testfile_2 = "stdout from process: ['docker', 'exec', 'test-container', 'grep', 'testfile2-content', '/tmp/testfile2-correctly-mounted'] testfile2-content"
    assert expect_mounted_testfile_2 in run_stdout, Tests.assertion_info(expect_mounted_testfile_2, f"expected output not in {run_stdout}")

    expect_mounted_testfile_3 = "stdout from process: ['docker', 'exec', 'test-container-root', 'grep', 'testfile3-content', '/tmp/testfile3-correctly-copied'] testfile3-content"
    assert expect_mounted_testfile_3 in run_stdout, Tests.assertion_info(expect_mounted_testfile_3, f"expected output not in {run_stdout}")

def test_volume_loading_subdirectories_subdir():
    uri = os.path.join(CURRENT_DIR, 'data/test_cases/subdir_volume_loading')
    RUN_NAME = 'test_' + utils.randomword(12)
    runner = Runner(name=RUN_NAME, uri=uri, uri_type='folder', filename="subdir/usage_scenario_subdir.yml", skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    run_stderr = err.getvalue()
    run_stdout = out.getvalue()
    assert run_stderr == '', Tests.assertion_info('stderr empty', f"stderr: {run_stderr}")

    expect_mounted_testfile_2 = "stdout from process: ['docker', 'exec', 'test-container', 'grep', 'testfile2-content', '/tmp/testfile2-correctly-mounted'] testfile2-content"
    assert expect_mounted_testfile_2 in run_stdout, Tests.assertion_info(expect_mounted_testfile_2, f"expected output not in {run_stdout}")

    expect_mounted_testfile_3 = "stdout from process: ['docker', 'exec', 'test-container', 'grep', 'testfile3-content', '/tmp/testfile3-correctly-mounted'] testfile3-content"
    assert expect_mounted_testfile_3 in run_stdout, Tests.assertion_info(expect_mounted_testfile_3, f"expected output not in {run_stdout}")

def test_volume_loading_subdirectories_subdir2():
    uri = os.path.join(CURRENT_DIR, 'data/test_cases/subdir_volume_loading')
    RUN_NAME = 'test_' + utils.randomword(12)
    runner = Runner(name=RUN_NAME, uri=uri, uri_type='folder', filename="subdir/subdir2/usage_scenario_subdir2.yml", skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    run_stderr = err.getvalue()
    run_stdout = out.getvalue()
    assert run_stderr == '', Tests.assertion_info('stderr empty', f"stderr: {run_stderr}")

    expect_mounted_testfile_2 = "stdout from process: ['docker', 'exec', 'test-container', 'grep', 'testfile2-content', '/tmp/testfile2-correctly-mounted'] testfile2-content"
    assert expect_mounted_testfile_2 in run_stdout, Tests.assertion_info(expect_mounted_testfile_2, "expected output not in {run_stdout}")

    expect_copied_testfile_2 = "stdout from process: ['docker', 'exec', 'test-container', 'grep', 'testfile2-content', '/tmp/testfile2-correctly-copied'] testfile2-content"
    assert expect_copied_testfile_2 in run_stdout, Tests.assertion_info(expect_copied_testfile_2, f"expected output not in {run_stdout}")

    expect_copied_testfile_3 = "stdout from process: ['docker', 'exec', 'test-container', 'grep', 'testfile3-content', '/tmp/testfile3-correctly-copied'] testfile3-content"
    assert expect_copied_testfile_3 in run_stdout, Tests.assertion_info(expect_copied_testfile_3, f"expected output not in {run_stdout}")

    expect_copied_testfile_4 = "stdout from process: ['docker', 'exec', 'test-container', 'grep', 'testfile4-content', '/tmp/testfile4-correctly-copied'] testfile4-content"
    assert expect_copied_testfile_4 in run_stdout, Tests.assertion_info(expect_copied_testfile_4, f"expected output not in {run_stdout}")
