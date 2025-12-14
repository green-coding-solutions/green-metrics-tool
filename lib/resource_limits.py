'''This module takes a list of system configurations to read and puts them in an dict. This file only gets the
things we don't need to be root to get. Please look into the hardware_info_root.py for everything that needs
root.
'''
import os
import subprocess
from functools import cache

from lib.global_config import GlobalConfig

CURRENT_PATH = os.path.dirname(__file__)
GMT_CONFIG = GlobalConfig().config

@cache
def get_assignable_cpus():
    SYSTEM_ASSIGNABLE_CPU_COUNT = int(subprocess.check_output(['docker', 'info', '--format', '{{.NCPU}}'], encoding='UTF-8', errors='replace').strip())
    assignable_cpus = SYSTEM_ASSIGNABLE_CPU_COUNT - int(GMT_CONFIG['machine']['host_reserved_cpus'])
    if assignable_cpus <= 0:
        raise RuntimeError(f"Cannot assign docker containers to any CPU as no more CPUs are available to Docker. System available CPU count for Docker: {SYSTEM_ASSIGNABLE_CPU_COUNT}. Reserved for GMT exclusively: {GMT_CONFIG['machine']['host_reserved_cpus']}")
    return assignable_cpus

def get_assignable_memory():
    SYSTEM_ASSIGNABLE_MEMORY = int(subprocess.check_output(['docker', 'info', '--format', '{{.MemTotal}}'], encoding='UTF-8', errors='replace').strip())
    available_memory = SYSTEM_ASSIGNABLE_MEMORY - int(GMT_CONFIG['machine']['host_reserved_memory'])
    if available_memory <= 0:
        raise RuntimeError(f"Cannot assign docker containers to any memory as no more memory are available to Docker. System available memory for Docker: {SYSTEM_ASSIGNABLE_MEMORY}. Reserved for GMT exclusively: {GMT_CONFIG['machine']['host_reserved_memory']} Bytes")
    return available_memory



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
