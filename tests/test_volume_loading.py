import os
import subprocess
import io

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')

from contextlib import redirect_stdout, redirect_stderr
import pytest

from tests import test_functions as Tests

from lib.global_config import GlobalConfig
from runner import Runner

GlobalConfig().override_config(config_name='test-config.yml')

def test_volume_load_no_escape():
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/volume_load_etc_hosts.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    try:
        with pytest.raises(ValueError) as e:
            with Tests.RunUntilManager(runner) as context:
                context.run_until('setup_services')
    finally:
        container_running = Tests.check_if_container_running('test-container')

    expected_error = '/etc/hosts must not be in folder above root repo folder'
    assert str(e.value).startswith(expected_error), Tests.assertion_info(expected_error, str(e.value))
    assert container_running is False, Tests.assertion_info('test-container stopped', 'test-container was still running!')

def test_volume_load_escape_ok_with_allow_unsafe():
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/volume_load_etc_hosts.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False, allow_unsafe=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
        # check that the volume was loaded
        ps = subprocess.run(
            ['docker', 'exec', 'test-container', '/bin/sh',
            '-c', 'test -f /tmp/hosts && echo "File mounted"'],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding='UTF-8',
            check=False,
        )
        out = ps.stdout
        err = ps.stderr

    assert "File mounted" in out, Tests.assertion_info('File mounted', f"out: {out} | err: {err}")

def test_load_files_from_within_gmt():
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/volume_load_within_proj.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
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

    assert "File mounted" in out, Tests.assertion_info('File mounted', f"out: {out} | err: {err}")


def test_symlinks_should_fail():
    symlink_file = os.path.join(f"{GMT_DIR}/tests/data/tmp/", 'symlink')

    os.symlink('/etc/hosts', symlink_file)

    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/volume_load_symlinks_negative.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    try:
        with pytest.raises(ValueError) as e:
            with Tests.RunUntilManager(runner) as context:
                context.run_until('setup_services')
    finally:
        container_running = Tests.check_if_container_running('test-container')
        os.remove(symlink_file)

    expected_error = '../tmp/symlink must not be in folder above root repo folder'
    assert str(e.value).startswith(expected_error), Tests.assertion_info(expected_error, str(e.value))
    assert container_running is False, Tests.assertion_info('test-container stopped', 'test-container was still running!')

def test_non_bind_mounts_should_fail():
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/volume_load_non_bind_mounts.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    try:
        with pytest.raises(RuntimeError) as e:
            with Tests.RunUntilManager(runner) as context:
                context.run_until('setup_services')
    finally:
        container_running = Tests.check_if_container_running('test-container')

    expected_error = 'The volume test-volume could not be loaded or found at the specified path.'
    assert expected_error in str(e.value), Tests.assertion_info(expected_error, str(e.value))
    assert container_running is False, Tests.assertion_info('test-container stopped', 'test-container was still running!')

def test_load_volume_references():
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/volume_load_references.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')
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

    assert "File mounted" in out, Tests.assertion_info('File mounted', f"out: {out} | err: {err}")

def test_volume_loading_subdirectories_root():
    runner = Runner(uri=GMT_DIR, filename='tests/data/usage_scenarios/subdir_volume_loading/usage_scenario.yml', uri_type='folder', skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

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
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename="tests/data/usage_scenarios/subdir_volume_loading/subdir/usage_scenario_subdir.yml", skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

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
    runner = Runner(uri=GMT_DIR, uri_type='folder', filename="tests/data/usage_scenarios/subdir_volume_loading/subdir/subdir2/usage_scenario_subdir2.yml", skip_system_checks=True, dev_no_metrics=True, dev_no_sleeps=True, dev_no_build=False)

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
