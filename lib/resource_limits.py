'''This module takes a list of system configurations to read and puts them in an dict. This file only gets the
things we don't need to be root to get. Please look into the hardware_info_root.py for everything that needs
root.
'''
import os
import subprocess
from functools import cache

from lib.global_config import GlobalConfig
from lib.utils import get_test_worker_count

CURRENT_PATH = os.path.dirname(__file__)

@cache
def get_docker_available_cpus():
    return int(subprocess.check_output(['docker', 'info', '--format', '{{.NCPU}}'], encoding='UTF-8', errors='replace').strip())

@cache
def get_assignable_cpus():
    GMT_CONFIG = GlobalConfig().config
    SYSTEM_ASSIGNABLE_CPU_COUNT = get_docker_available_cpus()
    host_reserved_cpus = int(GMT_CONFIG['machine']['host_reserved_cpus'])
    if host_reserved_cpus < 1:
        raise ValueError(f"host_reserved_cpus in the config.yml must be at min. 1. Configured value: {host_reserved_cpus}. Please increase the value.")
    assignable_cpus = SYSTEM_ASSIGNABLE_CPU_COUNT - host_reserved_cpus
    if assignable_cpus <= 0:
        raise RuntimeError(f"Cannot assign docker containers to any CPU as no more CPUs are available to Docker. System available CPU count for Docker: {SYSTEM_ASSIGNABLE_CPU_COUNT}. Reserved for GMT exclusively: {GMT_CONFIG['machine']['host_reserved_cpus']}")
    # Deliberately *not* divided by get_test_worker_count() the way get_assignable_memory() below is.
    # CPU oversubscription between parallel pytest-xdist workers degrades gracefully - the scheduler
    # time-slices the shared cores and everything just runs slower - whereas splitting the cpuset
    # would pin each worker's containers to a single core on a typical CI runner and make the
    # measurement workloads slower still, which is the opposite of what we want. Memory has no such
    # graceful degradation, hence the asymmetry.
    return assignable_cpus

@cache
def get_assignable_memory():
    GMT_CONFIG = GlobalConfig().config
    SYSTEM_ASSIGNABLE_MEMORY = int(subprocess.check_output(['docker', 'info', '--format', '{{.MemTotal}}'], encoding='UTF-8', errors='replace').strip())
    available_memory = SYSTEM_ASSIGNABLE_MEMORY - int(GMT_CONFIG['machine']['host_reserved_memory'])
    if available_memory <= 0:
        raise RuntimeError(f"Cannot assign docker containers to any memory as no more memory are available to Docker. System available memory for Docker: {SYSTEM_ASSIGNABLE_MEMORY}. Reserved for GMT exclusively: {GMT_CONFIG['machine']['host_reserved_memory']} Bytes")

    # Under pytest-xdist every worker is a separate process running its own ScenarioRunner against the
    # same host, and each one would otherwise hand the *entire* remaining host memory to its own
    # containers - on an 8 vCPU / 31 GiB CI runner with 6 workers that is ~174 GiB of limits promised
    # against 31 GiB of RAM, with swap explicitly turned off by the CI job. These are caps rather than
    # reservations, so it does not fail on the spot, but it voids the guarantee host_reserved_memory
    # exists to give: nothing then stops the workers' containers from collectively exhausting the host
    # and taking unrelated processes (dockerd, the test postgres, pytest itself) down with them.
    # Splitting the pool evenly restores the invariant that the sum of all limits handed out across
    # concurrently running workers stays within what the host actually has. Outside a parallel test
    # session get_test_worker_count() is 1 and this changes nothing.
    return available_memory // get_test_worker_count()



def docker_memory_to_bytes(memory_value):
    """Convert memory string with units (e.g., '50M', '2G') to bytes."""
    """Although GMT internally works with MiB this function is for converting for docker syntax"""
    unit_multipliers = {
        'B': 1,        # Byte
        'K': 1_024,    # Kilobyte
        'M': 1_024**2, # Megabyte
        'G': 1_024**3, # Gigabyte
        'T': 1_024**4, # Terabyte
    }

    if isinstance(memory_value, (float, int)) or memory_value[-1].isdigit():
        # in case of float this will round down. but since float would be pure bytes anyway
        # we must floor the value in any case as no less than a byte can be accounted
        return int(memory_value)

    # although not specified in the docker specification values like 10m and also 10MB are allowed.
    # so if we see an additional B we remove it at the end
    if memory_value[-1] == 'b' or memory_value[-1] == 'B':
        memory_value = memory_value[:-1]

    if memory_value[-1].isdigit():
        unit = 'B'
        num = memory_value
    else:
        num, unit = float(memory_value[:-1]), memory_value[-1].upper()

    if unit in unit_multipliers:
        return int(num * unit_multipliers[unit])

    raise ValueError(f"Unrecognized memory unit: {unit}")
