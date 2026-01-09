# https://docs.docker.com/engine/reference/commandline/port/
# List port mappings or a specific mapping for the container
#  docker port CONTAINER [PRIVATE_PORT[/PROTO]]

import io
import os
import subprocess
import math

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')

from contextlib import redirect_stdout, redirect_stderr
import yaml
import pytest

from lib import utils
from lib.global_config import GlobalConfig
from tests import test_functions as Tests
from lib.scenario_runner import ScenarioRunner
from lib.schema_checker import SchemaError
from lib import resource_limits

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

    run_name = 'test_' + utils.randomword(12)
    runner = ScenarioRunner(name=run_name, uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/resource_limits_good.yml', skip_unsafe=False, skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    with Tests.RunUntilManager(runner) as context:
        context.run_until('check_process_returncodes')

    with open(f'{GMT_DIR}/tests/data/usage_scenarios/resource_limits_good.yml', 'r', encoding='utf-8') as f:
        usage_scenario_contents = yaml.safe_load(f)
    container_dict = utils.get_run_data(run_name)['containers']

    assert 'deploy' not in container_dict['test-container-only-cpu'] # not used
    assert container_dict['test-container-only-cpu']['mem_limit'] > 0 # auto-fill
    assert container_dict['test-container-only-cpu']['cpus'] == usage_scenario_contents['services']['test-container-only-cpu']['deploy']['resources']['limits']['cpus'] # copy over

    assert 'deploy' not in container_dict['test-container-only-memory'] # not used
    assert container_dict['test-container-only-memory']['cpus'] > 0 # auto-fill
    assert container_dict['test-container-only-memory']['mem_limit'] == 104857600 # copy over but transformed from 100 MB. We use static value for test

    assert 'deploy' not in container_dict['test-container-both'] # not used
    assert container_dict['test-container-both']['mem_limit'] == 10485760 # copy over but transformed from 100 MB. We use static value for test
    assert container_dict['test-container-both']['cpus'] == usage_scenario_contents['services']['test-container-both']['deploy']['resources']['limits']['cpus'] # copy over

    assert 'deploy' not in container_dict['test-container-cpu-and-memory-in-both'] # not used
    assert container_dict['test-container-cpu-and-memory-in-both']['mem_limit'] == 10485760 # copy over but transformed from 100 MB. We use static value for test
    assert container_dict['test-container-cpu-and-memory-in-both']['cpus'] == usage_scenario_contents['services']['test-container-cpu-and-memory-in-both']['deploy']['resources']['limits']['cpus'] # copy over

    MEMORY_DEFINED_IN_USAGE_SCENARIO = 199286402 # ~ 190.05 MB
    MEM_AVAILABLE = resource_limits.get_assignable_memory()
    MEM_ASSIGNABLE = MEM_AVAILABLE - MEMORY_DEFINED_IN_USAGE_SCENARIO
    MEM_PER_CONTAINER = math.floor(MEM_ASSIGNABLE/3)

    CPUS_ASSIGNABLE = resource_limits.get_assignable_cpus()

    # these are the only three containers that get auto assigned. Thus their values we can check
    assert 'deploy' not in container_dict['test-container-limits-partial'] # no fill of deploy key
    assert container_dict['test-container-limits-partial']['mem_limit'] == MEM_PER_CONTAINER # auto-fill
    assert container_dict['test-container-limits-partial']['cpus'] == CPUS_ASSIGNABLE # auto-fill

    assert 'deploy' not in container_dict['test-container-limits-none'] # no creation of deploy key
    assert container_dict['test-container-limits-none']['mem_limit'] == MEM_PER_CONTAINER # auto-fill
    assert container_dict['test-container-limits-none']['cpus'] == CPUS_ASSIGNABLE # auto-fill

    assert container_dict['test-container-only-cpu']['mem_limit'] == MEM_PER_CONTAINER # auto-fill




def test_resource_limits_too_high():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/resource_limits_too_high.yml', skip_unsafe=False, skip_system_checks=True, dev_cache_build=True, dev_no_sleeps=True, dev_no_metrics=True, dev_no_phase_stats=True)

    with pytest.raises(ValueError) as e:
        with Tests.RunUntilManager(runner) as context:
            context.run_until('initialize_run')

    assert str(e.value).startswith('You are trying to assign more cpus to service test-container than is available host system. Requested CPUs: 400.')


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

def test_resource_limits_cpuset():
    out = io.StringIO()
    err = io.StringIO()

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with redirect_stdout(out), redirect_stderr(err), Tests.RunUntilManager(runner) as context:
        context.run_until('setup_services')

    docker_cpus = resource_limits.get_docker_available_cpus()
    exp_string = ','.join(map(str, range(1,docker_cpus)))
    assert f"--cpuset-cpus {exp_string} --" in out.getvalue() # we extend the check to -- to make sure nothing after 1,2,XXX is cut off and thus match the start of the next element

@pytest.mark.skipif(resource_limits.get_docker_available_cpus() < 4, reason="Test requires 4 cores available to docker")
def test_resource_limits_alternate_cpuset():
    out = io.StringIO()
    err = io.StringIO()

    try:
        GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/test-config-alternate-host-reserved-cpus.yml")
        resource_limits.get_docker_available_cpus.cache_clear()
        resource_limits.get_assignable_memory.cache_clear()
        resource_limits.get_assignable_cpus.cache_clear()

        runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/basic_stress.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

        with redirect_stdout(out), redirect_stderr(err), Tests.RunUntilManager(runner) as context:
            context.run_until('setup_services')

        docker_cpus = resource_limits.get_docker_available_cpus()
        exp_string = ','.join(map(str, range(1,docker_cpus-2))) # we remove 1 CPU here as the file contains two more reserved CPUs
        assert f"--cpuset-cpus {exp_string} --" in out.getvalue() # we extend the check to -- to make sure nothing after 1,2,XXX is cut off and thus match the start of the next element
    finally:
        resource_limits.get_docker_available_cpus.cache_clear()
        resource_limits.get_docker_available_cpus.cache_clear()
        resource_limits.get_assignable_memory.cache_clear()
        resource_limits.get_assignable_cpus.cache_clear()


def test_resource_limits_shm_good():
    out = io.StringIO()
    err = io.StringIO()

    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/resource_limits_shm_good.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with redirect_stdout(out), redirect_stderr(err):
        runner.run()

    assert 'SHM size is: Filesystem' in out.getvalue()
    assert "30.0M   0% /dev/shm" in out.getvalue()
    assert "15.0M   0% /dev/shm" in out.getvalue()

def test_resource_limits_oom_setup():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/oom_setup.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(MemoryError) as e:
        runner.run()

    assert str(e.value) == "Your process ['docker', 'exec', 'test-container', 'dd', 'if=/dev/zero', 'of=/dev/shm/test100mb', 'bs=1M', 'count=100'] failed due to an Out-of-Memory error (Code: 137). Please check if you can instruct the process to use less memory or higher resource limits on the container. The set memory for the container is exposed in the ENV var: GMT_CONTAINER_MEMORY_LIMIT.\n\n========== Stdout ==========\n\n\n========== Stderr ==========\n"

def test_resource_limits_oom_launch():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/oom_launch.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(MemoryError) as e:
        runner.run()

    assert str(e.value) == "Container 'test-container' failed during [BOOT] due to an Out-of-Memory error (Code: 137). Please check if you can instruct the startup process to use less memory or higher resource limits on the container. The set memory for the container is exposed in the ENV var: GMT_CONTAINER_MEMORY_LIMIT\nContainer logs:\n\n========== Stdout ==========\n\n\n========== Stderr ==========\n"

def test_resource_limits_oom_exec():
    runner = ScenarioRunner(uri=GMT_DIR, uri_type='folder', filename='tests/data/usage_scenarios/oom_exec.yml', skip_system_checks=True, dev_no_metrics=True, dev_no_phase_stats=True, dev_no_sleeps=True, dev_cache_build=True)

    with pytest.raises(MemoryError) as e:
        runner.run()

    assert str(e.value) == "Your process ['docker', 'exec', 'test-container', 'dd', 'if=/dev/zero', 'of=/dev/shm/test100mb', 'bs=1M', 'count=100'] failed due to an Out-of-Memory error (Code: 137). Please check if you can instruct the process to use less memory or higher resource limits on the container. The set memory for the container is exposed in the ENV var: GMT_CONTAINER_MEMORY_LIMIT.\n\nDetached process: False\n\n========== Stderr ==========\n"
