import psutil

from optimization_providers.base import Criticality, register_reporter
from lib import error_helpers

REPORTER_NAME = 'utilization'
REPORTER_ICON = 'tachometer alternate'

MIN_MEM_UTIL = 80 #%
MAX_CPU_UTIL = 90 #%
MIN_CPU_UTIL = 50 #%

def memory_to_bytes(memory_str):
    """Convert memory string with units (e.g., '50M', '2G') to bytes."""
    unit_multipliers = {
        'K': 1_000,         # Kilobyte
        'M': 1_000_000,     # Megabyte
        'G': 1_000_000_000, # Gigabyte
        'T': 1_000_000_000, # Terabyte
    }

    if isinstance(memory_str, int) or memory_str[-1].isdigit():
        return int(memory_str)

    num, unit = float(memory_str[:-1]), memory_str[-1].upper()

    if unit in unit_multipliers:
        return int(num * unit_multipliers[unit])

    raise ValueError(f"Unrecognized memory unit: {unit}")

# pylint: disable=unused-argument
@register_reporter('container_memory_utilization', Criticality.INFO, REPORTER_NAME, REPORTER_ICON, req_providers =['MemoryUsedCgroupContainerProvider'])
def container_memory_utilization(self, run, measurements, repo_path, network, notes, phases):

    mem = {}
    for s, d in run.get('usage_scenario').get('services').items():
        if x := d.get('deploy', {}).get('resources', {}).get('limits', {}).get('memory', None):
            mem[s] = memory_to_bytes(x)

    for service, measurement_stats in phases.get('data').get('[RUNTIME]').get('memory_used_cgroup_container').get('data').items():
        if not service in mem:
            self.add_optimization(
                f"You are not using Memory limits definitions on {service}",
                'Even if you want to use all memory you should explicitely specify it'
            )
            continue

        data = measurement_stats.get('data')
        first_item = next(iter(data))
        actual_mem_max = data[first_item].get('max', None)
        if not actual_mem_max:
            error_helpers.log_error('Mem max was not present', data=data, run=run)
            continue

        if (actual_mem_max/mem[service]*100) < MIN_MEM_UTIL:
            self.add_optimization(f"Memory utilization is low in {service}", f'''
                                The service {service} has the memory set to: {mem[service]}bytes but the max
                                usage was {actual_mem_max}bytes. The mean was {data[first_item].get('mean', None)}bytes.
                                Which is a usage of {data[first_item].get('mean', 0)/mem[service]*100}%.
                                Either you should reserve less memory ressources for the container or increase utilization through caching
                                more data in memory and thus in turn reducing cpu calculations or network traffic if possible.
                                ''',)

# pylint: disable=unused-argument
@register_reporter('container_cpu_utilization', Criticality.INFO, REPORTER_NAME, REPORTER_ICON, req_providers =['CpuUtilizationCgroupContainerProvider'])
def container_cpu_utilization(self, run, measurements, repo_path, network, notes, phases):

    cpus = {}
    for s, d in run.get('usage_scenario').get('services').items():
        if x := d.get('deploy', {}).get('resources', {}).get('limits', {}).get('cpus', None):
            cpus[s] = x


    for service, measurement_stats in phases.get('data').get('[RUNTIME]').get('cpu_utilization_cgroup_container').get('data').items():
        if not service in cpus:
            self.add_optimization(
                f"You are not using CPU limits definitions on {service}",
                'Even if you want to use all CPUs you should explicitely specify it'
            )
            continue

        data = measurement_stats.get('data')

        first_item = next(iter(data))
        actual_cpu_mean = data[first_item].get('mean', None)
        if not actual_cpu_mean:
            error_helpers.log_error('Mean utilization was not present', data=data, run_id=run['id'])
            continue

        adjusted_utilization = (actual_cpu_mean/100) * (psutil.cpu_count()/cpus[service])
        if adjusted_utilization < MIN_CPU_UTIL:
            self.add_optimization(f"Cpu utilization is low in {service}", f'''
                                The service {service} has the cpus set to: {cpus[service]}.
                                The system has a total of: {psutil.cpu_count()}.
                                The average utilization in realtion to the whole system was {actual_cpu_mean/100}%.
                                The means that the utilization in the container was {adjusted_utilization}%.
                                You should try for being above {MIN_CPU_UTIL}% on average to best utilize reserved ressources.
                                ''',)
        elif adjusted_utilization > MAX_CPU_UTIL:
            self.add_optimization(f"Cpu utilization is high in {service}", f'''
                                The service {service} has the cpus set to: {cpus[service]}.
                                The system has a total of: {psutil.cpu_count()}.
                                The average utilization was {actual_cpu_mean/100}%.
                                The means that the utilization in the container was {adjusted_utilization}%.
                                You should try for being below {MAX_CPU_UTIL}% on average as CPUs and also the OS tend
                                to be inefficient in these very high utilizations.
                                ''',)
