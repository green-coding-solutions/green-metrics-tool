from optimization_providers.base import Criticality, register_reporter
from lib import error_helpers
from lib import resource_limits

REPORTER_NAME = 'utilization'
REPORTER_ICON = 'tachometer alternate'

MIN_MEM_UTIL = 80 #%
MAX_CPU_UTIL = 90 #%
MIN_CPU_UTIL = 50 #%

# pylint: disable=unused-argument
@register_reporter('container_memory_utilization', Criticality.INFO, REPORTER_NAME, REPORTER_ICON, req_providers =['MemoryUsedCgroupContainerProvider'])
def container_memory_utilization(self, run, measurements, repo_path, network, notes, phases):

    mem = {}
    for s, d in run.get('containers').items():
        mem[s] = resource_limits.docker_memory_to_bytes(d['mem_limit']) # will always be there bc populated by scenario_runner

    for service, measurement_stats in phases['data']['[RUNTIME]']['data']['memory_used_cgroup_container']['data'].items():
        if not service in mem:
            self.add_optimization(
                f"You are not using Memory limits definitions on {service}",
                'Even if you want to use all memory you should explicitely specify it'
            )
            continue

        data = measurement_stats.get('data')
        first_item = next(iter(data))
        mem_service_max = data[first_item].get('max', None)
        if mem_service_max is None:
            error_helpers.log_error('Mem max was not present', data=data, run=run)
            continue

        mem_service_max_MB = round(mem_service_max/1_000_000,2)
        mem_service_reserved_MB = round(mem[service]/1_000_000,2)
        mem_service_mean_MB = round(data[first_item]['mean']/1_000_000, 2)
        mem_service_usage = round((mem_service_max_MB/mem_service_reserved_MB)*100,2)

        if (mem_service_usage) < MIN_MEM_UTIL:
            self.add_optimization(f"Memory utilization is low in {service}", f'''
                                The service {service} has the memory reservation set to: {mem_service_reserved_MB} MB but the max
                                usage was {mem_service_max_MB} MB. The mean was {mem_service_mean_MB} MB.
                                Which is a usage of {mem_service_usage}%.
                                Either you should reserve less memory ressources for the container or increase utilization through caching
                                more data in memory and thus in turn reducing cpu calculations or network traffic if possible.
                                ''',
                                criticality=Criticality.LOW)
        else:
            self.add_optimization(f"Memory utilization is good in {service}", f'''
                    The service {service} has the memory reservation set to: {mem_service_reserved_MB} MB and the max
                    usage was {mem_service_max_MB} MB. The mean was {mem_service_mean_MB} MB.
                    Which is a usage of {mem_service_usage}%, which is in an optimal range.
                    ''',
                    criticality=Criticality.GOOD)

# pylint: disable=unused-argument
@register_reporter('container_cpu_utilization', Criticality.INFO, REPORTER_NAME, REPORTER_ICON, req_providers =['CpuUtilizationCgroupContainerProvider'])
def container_cpu_utilization(self, run, measurements, repo_path, network, notes, phases):

    cpus = {}
    for s, d in run.get('containers').items():
        cpus[s]  = float(d['cpus']) # will always be there bc populated by scenario_runner

    for service, measurement_stats in phases['data']['[RUNTIME]']['data']['cpu_utilization_cgroup_container']['data'].items():
        if not service in cpus:
            self.add_optimization(
                f"You are not using CPU limits definitions on {service}",
                'Even if you want to use all CPUs you should explicitely specify it'
            )
            continue

        data = measurement_stats.get('data')

        first_item = next(iter(data))
        actual_cpu_mean = data[first_item].get('mean', None)
        if actual_cpu_mean is None:
            error_helpers.log_error('Mean utilization was not present', data=data, run_id=run['id'])
            continue

        adjusted_utilization = round( (actual_cpu_mean/100) * (resource_limits.get_docker_available_cpus()/cpus[service]) ,2)

        if adjusted_utilization < MIN_CPU_UTIL:
            self.add_optimization(f"Cpu utilization is low in {service}", f'''
                                The service {service} has the cpus set to: {cpus[service]}.
                                This means that the utilization in the container was {adjusted_utilization}%.
                                You should try for being above {MIN_CPU_UTIL}% on average to best utilize reserved ressources.
                                ''',
                                criticality=Criticality.LOW)
        elif adjusted_utilization > MAX_CPU_UTIL:
            self.add_optimization(f"Cpu utilization is high in {service}", f'''
                                The service {service} has the cpus set to: {cpus[service]}.
                                This means that the utilization in the container was {adjusted_utilization}%.
                                You should try for being below {MAX_CPU_UTIL}% on average as CPUs and also the OS tend
                                to be inefficient in these very high utilizations.
                                ''',
                                criticality=Criticality.HIGH)
        else:
            self.add_optimization(f"Cpu utilization is good in {service}", f'''
                    The service {service} has the cpus set to: {cpus[service]}.
                    This means that the utilization in the container was {adjusted_utilization}% which is in an optimal range.
                    ''',
                    criticality=Criticality.GOOD)
