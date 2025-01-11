import os

from lib import utils
from metric_providers.cpu.utilization.cgroup.container.provider import CpuUtilizationCgroupContainerProvider

class CpuUtilizationCgroupSystemProvider(CpuUtilizationCgroupContainerProvider):
    def __init__(self, resolution, skip_check=False, cgroups: dict = None):
        super(CpuUtilizationCgroupContainerProvider, self).__init__( # this will call BaseMetricProvider
            metric_name='cpu_utilization_cgroup_system',
            metrics={'time': int, 'value': int, 'container_id': str},
            resolution=resolution,
            unit='Ratio',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

        self._cgroups = cgroups.copy() if cgroups else {} # because it is a frozen dict, we need to copy
        self._cgroups[utils.find_own_cgroup_name()] = {'name': 'GMT Overhead'} # we also find the cgroup that the GMT process belongs to. It will be a user session

    def start_profiling(self, containers=None):
        super().start_profiling(self._cgroups) # we hook here into the mechanism that can supply container names to the parent function

    def read_metrics(self, run_id, containers=None):
        return super().read_metrics(run_id, self._cgroups) # this will call CpuUtilizationCgroupContainerProvider
