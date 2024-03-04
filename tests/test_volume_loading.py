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

GlobalConfig().override_config(config_name='test-config.yml')

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
    parallel_id = utils.randomword(12)

    usage_scenario_file="basic_stress_w_import.yml"
    usage_scenario_path = os.path.join(CURRENT_DIR, 'data/usage_scenarios/', usage_scenario_file)
    docker_compose_file="volume_load_etc_passwords.yml"
    docker_compose_path=os.path.join(CURRENT_DIR, 'data/docker-compose-files/', docker_compose_file)

    Tests.make_proj_dir(dir_name=parallel_id, usage_scenario_path=usage_scenario_path, docker_compose_path=docker_compose_path)

    tmp_usage_scenario = os.path.join(CURRENT_DIR, 'tmp', parallel_id, usage_scenario_file)
    Tests.replace_include_in_usage_scenario(tmp_usage_scenario, 'volume_load_etc_passwords.yml')

    runner = Tests.setup_runner( usage_scenario=usage_scenario_file, docker_compose=docker_compose_file,
                parallel_id=parallel_id, create_tmp_directory=False)

    try:
        with pytest.raises(RuntimeError) as e:
            Tests.run_until(runner, 'setup_services')
    finally:
        container_running = check_if_container_running(f"test-container-{parallel_id}")
        runner.cleanup()

    container_name = f'test-container-{parallel_id}'
    expected_error = f'Service \'{container_name}\' volume path (/etc/passwd) is outside allowed folder:'
    assert str(e.value).startswith(expected_error), Tests.assertion_info(expected_error, str(e.value))
    assert container_running is False, Tests.assertion_info(f'{container_name} stopped', f'{container_name} was still running!')

def edit_compose_file(compose_file, tmp_dir):
    tmp_compose_file = os.path.join(tmp_dir, compose_file)

    #regex replace CURRENT_DIR in docker-compose.yml with temp proj directory where test-file exists
    with open(tmp_compose_file, 'r', encoding='utf-8') as file:
        data = file.read()
        data = re.sub(r'CURRENT_DIR', tmp_dir, data)
    with open(tmp_compose_file, 'w', encoding='utf-8') as file:
        file.write(data)

def test_load_files_from_within_gmt():
    parallel_id = utils.randomword(12)

    usage_scenario_file="basic_stress_w_import.yml"
    usage_scenario_path = os.path.join(CURRENT_DIR, 'data/usage_scenarios/', usage_scenario_file)
    docker_compose_file="volume_load_within_proj.yml"
    docker_compose_path=os.path.join(CURRENT_DIR, 'data/docker-compose-files/', docker_compose_file)

    dir_path = Tests.make_proj_dir(dir_name=parallel_id, usage_scenario_path=usage_scenario_path, docker_compose_path=docker_compose_path)
    tmp_usage_scenario = os.path.join(CURRENT_DIR, 'tmp', parallel_id, usage_scenario_file)
    Tests.replace_include_in_usage_scenario(tmp_usage_scenario, docker_compose_file)
    edit_compose_file(docker_compose_file, dir_path)
    Tests.create_test_file(dir_path)

    runner = Tests.setup_runner(usage_scenario=usage_scenario_file, docker_compose=docker_compose_file,
                parallel_id=parallel_id, create_tmp_directory=False)

    try:
        Tests.run_until(runner, 'setup_services')
        # check that the volume was loaded
        ps = subprocess.run(
            ['docker', 'exec', f"test-container-{parallel_id}", '/bin/sh',
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
    parallel_id = utils.randomword(12)

    usage_scenario_file="basic_stress_w_import.yml"
    usage_scenario_path = os.path.join(CURRENT_DIR, 'data/usage_scenarios/', usage_scenario_file)
    docker_compose_file="volume_load_symlinks_negative.yml"
    docker_compose_path=os.path.join(CURRENT_DIR, 'data/docker-compose-files/', docker_compose_file)

    dir_path = Tests.make_proj_dir(dir_name=parallel_id, usage_scenario_path=usage_scenario_path, docker_compose_path=docker_compose_path)
    tmp_usage_scenario = os.path.join(CURRENT_DIR, 'tmp', parallel_id, usage_scenario_file)
    Tests.replace_include_in_usage_scenario(tmp_usage_scenario, docker_compose_file)
    edit_compose_file(docker_compose_file, dir_path)

    # make a symlink to /etc/passwords in tmp_dir
    symlink = os.path.join(dir_path, 'symlink')
    os.symlink('/etc/passwd', os.path.join(dir_path, 'symlink'))

    runner = Tests.setup_runner( usage_scenario=usage_scenario_file, docker_compose=docker_compose_file,
                parallel_id=parallel_id, create_tmp_directory=False)

    container_name = f'test-container-{parallel_id}'
    try:
        with pytest.raises(RuntimeError) as e:
            Tests.run_until(runner, 'setup_services')
    finally:
        container_running = check_if_container_running(container_name)
        runner.cleanup()

    expected_error = f"Service '{container_name}' volume path ({symlink}) is outside allowed folder:"
    assert str(e.value).startswith(expected_error), Tests.assertion_info(expected_error, str(e.value))
    assert container_running is False, Tests.assertion_info(f"{container_name} stopped", f"{container_name} was still running!")

def test_non_bind_mounts_should_fail():
    parallel_id = utils.randomword(12)

    usage_scenario_file="basic_stress_w_import.yml"
    usage_scenario_path = os.path.join(CURRENT_DIR, 'data/usage_scenarios/', usage_scenario_file)
    docker_compose_file="volume_load_non_bind_mounts.yml"
    docker_compose_path=os.path.join(CURRENT_DIR, 'data/docker-compose-files/', docker_compose_file)

    Tests.make_proj_dir(dir_name=parallel_id, usage_scenario_path=usage_scenario_path, docker_compose_path=docker_compose_path)
    tmp_usage_scenario = os.path.join(CURRENT_DIR, 'tmp', parallel_id, usage_scenario_file)
    Tests.replace_include_in_usage_scenario(tmp_usage_scenario, docker_compose_file)

    runner = Tests.setup_runner(usage_scenario=usage_scenario_file, docker_compose=docker_compose_file,
                parallel_id=parallel_id, create_tmp_directory=False)

    container_name=f'test-container-{parallel_id}'
    try:
        with pytest.raises(RuntimeError) as e:
            Tests.run_until(runner, 'setup_services')
    finally:
        container_running = check_if_container_running(container_name)
        runner.cleanup()

    expected_error = 'volume path does not exist'
    assert expected_error in str(e.value), Tests.assertion_info(expected_error, str(e.value))
    assert container_running is False, Tests.assertion_info(f"{container_name} stopped", f"{container_name} was still running!")

def test_load_volume_references():
    parallel_id = utils.randomword(12)

    usage_scenario_file="basic_stress_w_import.yml"
    usage_scenario_path = os.path.join(CURRENT_DIR, 'data/usage_scenarios/', usage_scenario_file)
    docker_compose_file="volume_load_references.yml"
    docker_compose_path=os.path.join(CURRENT_DIR, 'data/docker-compose-files/', docker_compose_file)

    dir_path = Tests.make_proj_dir(dir_name=parallel_id, usage_scenario_path=usage_scenario_path, docker_compose_path=docker_compose_path)
    tmp_usage_scenario = os.path.join(CURRENT_DIR, 'tmp', parallel_id, usage_scenario_file)
    Tests.replace_include_in_usage_scenario(tmp_usage_scenario, docker_compose_file)
    edit_compose_file(docker_compose_file, dir_path)

    Tests.create_test_file(dir_path)
    runner = Tests.setup_runner(
                usage_scenario=usage_scenario_file, docker_compose=docker_compose_file, dir_name=parallel_id,
                parallel_id=parallel_id, create_tmp_directory=False)

    try:
        Tests.run_until(runner, 'setup_services')
        # check that the volume was loaded
        ps = subprocess.run(
            ['docker', 'exec', f"test-container-2-{parallel_id}", '/bin/sh',
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

def prepare_subdir_tmp_directory(parallel_id):
    test_case_path=os.path.join(CURRENT_DIR, 'data/test_cases/subdir_volume_loading')
    tmp_dir_path=os.path.join(CURRENT_DIR, 'tmp', parallel_id)
    shutil.copytree(test_case_path, tmp_dir_path)

    usage_scenario_path=os.path.join(tmp_dir_path, 'usage_scenario.yml')
    compose_yaml_path=os.path.join(tmp_dir_path, 'compose.yaml')
    subdir_usage_scenario_path=os.path.join(tmp_dir_path, 'subdir/', 'usage_scenario_subdir.yml')
    subdir2_usage_scenario_path=os.path.join(tmp_dir_path, 'subdir/subdir2', 'usage_scenario_subdir2.yml')

    Tests.edit_yml_with_id(usage_scenario_path, parallel_id)
    Tests.edit_yml_with_id(compose_yaml_path, parallel_id)
    Tests.edit_yml_with_id(subdir_usage_scenario_path, parallel_id)
    Tests.edit_yml_with_id(subdir2_usage_scenario_path, parallel_id)

    return tmp_dir_path

@pytest.mark.serial
def test_volume_loading_subdirectories_root():
    parallel_id = utils.randomword(12)
    prepare_subdir_tmp_directory(parallel_id)
    runner = Tests.setup_runner(do_parallelize_files=False, parallel_id=parallel_id, create_tmp_directory=False)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    run_stderr = err.getvalue()
    run_stdout = out.getvalue()
    assert run_stderr == '', Tests.assertion_info('stderr empty', f"stderr: {run_stderr}")

    expect_content_testfile_root = f"stdout from process: ['docker', 'exec', 'test-container-root-{parallel_id}', 'grep', 'testfile-root-content', '/tmp/testfile-root'] testfile-root-content"
    assert expect_content_testfile_root in run_stdout, Tests.assertion_info(expect_content_testfile_root, f"expected output not in {run_stdout}")

    expect_extra_testfile_root = f"stdout from process: ['docker', 'exec', 'test-container-root-{parallel_id}', 'grep', 'testfile-root-content', '/tmp/testfile-root-extra-copied'] testfile-root-content"
    assert expect_extra_testfile_root in run_stdout, Tests.assertion_info(expect_extra_testfile_root, f"expected output not in {run_stdout}")

    expect_mounted_testfile = f"stdout from process: ['docker', 'exec', 'test-container-{parallel_id}', 'grep', 'testfile-content', '/tmp/testfile-correctly-mounted'] testfile-content"
    assert expect_mounted_testfile in run_stdout, Tests.assertion_info(expect_mounted_testfile, f"expected output not in {run_stdout}")

    expect_mounted_testfile_2 = f"stdout from process: ['docker', 'exec', 'test-container-{parallel_id}', 'grep', 'testfile2-content', '/tmp/testfile2-correctly-mounted'] testfile2-content"
    assert expect_mounted_testfile_2 in run_stdout, Tests.assertion_info(expect_mounted_testfile_2, f"expected output not in {run_stdout}")

    expect_mounted_testfile_3 = f"stdout from process: ['docker', 'exec', 'test-container-root-{parallel_id}', 'grep', 'testfile3-content', '/tmp/testfile3-correctly-copied'] testfile3-content"
    assert expect_mounted_testfile_3 in run_stdout, Tests.assertion_info(expect_mounted_testfile_3, f"expected output not in {run_stdout}")

def test_volume_loading_subdirectories_subdir():
    parallel_id = utils.randomword(12)
    prepare_subdir_tmp_directory(parallel_id)
    runner = Tests.setup_runner(usage_scenario='subdir/usage_scenario_subdir.yml',
                do_parallelize_files=False, parallel_id=parallel_id, create_tmp_directory=False)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    run_stderr = err.getvalue()
    run_stdout = out.getvalue()
    assert run_stderr == '', Tests.assertion_info('stderr empty', f"stderr: {run_stderr}")

    expect_mounted_testfile_2 = f"stdout from process: ['docker', 'exec', 'test-container-{parallel_id}', 'grep', 'testfile2-content', '/tmp/testfile2-correctly-mounted'] testfile2-content"
    assert expect_mounted_testfile_2 in run_stdout, Tests.assertion_info(expect_mounted_testfile_2, f"expected output not in {run_stdout}")

    expect_mounted_testfile_3 = f"stdout from process: ['docker', 'exec', 'test-container-{parallel_id}', 'grep', 'testfile3-content', '/tmp/testfile3-correctly-mounted'] testfile3-content"
    assert expect_mounted_testfile_3 in run_stdout, Tests.assertion_info(expect_mounted_testfile_3, f"expected output not in {run_stdout}")

def test_volume_loading_subdirectories_subdir2():
    parallel_id = utils.randomword(12)
    prepare_subdir_tmp_directory(parallel_id)
    runner = Tests.setup_runner(usage_scenario='subdir/subdir2/usage_scenario_subdir2.yml',
                do_parallelize_files=False, parallel_id=parallel_id, create_tmp_directory=False)

    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        runner.run()
    run_stderr = err.getvalue()
    run_stdout = out.getvalue()
    assert run_stderr == '', Tests.assertion_info('stderr empty', f"stderr: {run_stderr}")

    expect_mounted_testfile_2 = f"stdout from process: ['docker', 'exec', 'test-container-{parallel_id}', 'grep', 'testfile2-content', '/tmp/testfile2-correctly-mounted'] testfile2-content"
    assert expect_mounted_testfile_2 in run_stdout, Tests.assertion_info(expect_mounted_testfile_2, "expected output not in {run_stdout}")

    expect_copied_testfile_2 = f"stdout from process: ['docker', 'exec', 'test-container-{parallel_id}', 'grep', 'testfile2-content', '/tmp/testfile2-correctly-copied'] testfile2-content"
    assert expect_copied_testfile_2 in run_stdout, Tests.assertion_info(expect_copied_testfile_2, f"expected output not in {run_stdout}")

    expect_copied_testfile_3 = f"stdout from process: ['docker', 'exec', 'test-container-{parallel_id}', 'grep', 'testfile3-content', '/tmp/testfile3-correctly-copied'] testfile3-content"
    assert expect_copied_testfile_3 in run_stdout, Tests.assertion_info(expect_copied_testfile_3, f"expected output not in {run_stdout}")

    expect_copied_testfile_4 = f"stdout from process: ['docker', 'exec', 'test-container-{parallel_id}', 'grep', 'testfile4-content', '/tmp/testfile4-correctly-copied'] testfile4-content"
    assert expect_copied_testfile_4 in run_stdout, Tests.assertion_info(expect_copied_testfile_4, f"expected output not in {run_stdout}")
