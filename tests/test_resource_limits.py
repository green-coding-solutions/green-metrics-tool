# https://docs.docker.com/engine/reference/commandline/port/
# List port mappings or a specific mapping for the container
#  docker port CONTAINER [PRIVATE_PORT[/PROTO]]

import io
import os
import subprocess

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')

from contextlib import redirect_stdout, redirect_stderr
import pytest

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

def test_resource_limits_good():

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/resource_limits_good.yml', skip_unsafe=False, skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    out = io.StringIO()
    err = io.StringIO()

    with redirect_stdout(out), redirect_stderr(err):
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert err.getvalue() == ''
    assert 'Applying CPU Limit from deploy' in out.getvalue()
    assert 'Applying CPU Limit from services' in out.getvalue()
    assert 'Applying Memory Limit from deploy' in out.getvalue()
    assert 'Applying Memory Limit from services' in out.getvalue()

def test_resource_limits_memory_none():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/resource_limits_memory_none.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with pytest.raises(SchemaError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "None should be instance of 'str'" in str(e.value)

def test_resource_limits_cpu_none():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/resource_limits_cpu_none.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with pytest.raises(SchemaError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "None should be instance of 'str'" in str(e.value)


def test_resource_limits_disalign_cpu():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/resource_limits_disalign_cpu.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with pytest.raises(SchemaError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "cpus service top level key and deploy.resources.limits.cpus must be identical" in str(e.value)

def test_resource_limits_disalign_memory():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/resource_limits_disalign_memory.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)
    with pytest.raises(SchemaError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

    assert "mem_limit service top level key and deploy.resources.limits.memory must be identical" in str(e.value)


def test_resource_limits_shm_good():
    out = io.StringIO()
    err = io.StringIO()

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/resource_limits_shm_good.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        runner.run()

    assert 'SHM size is: Filesystem' in out.getvalue()
    assert "30.0M   0% /dev/shm" in out.getvalue()
    assert "15.0M   0% /dev/shm" in out.getvalue()
