import os

from metric_providers.base import BaseMetricProvider

class CpuUtilizationCgroupSystemProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False, cgroups: dict = None):
        super().__init__(
            metric_name='cpu_utilization_cgroup_system',
            metrics={'time': int, 'value': int, 'container_id': str},
            resolution=resolution,
            unit='Ratio',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check = skip_check,
        )
        if cgroups:
            self._cgroups = cgroups.copy() # because it is a frozen dict, we need to copy
        else:
            self._cgroups = {}

        # we also find the cgroup that the GMT process belongs to. It will be a user session
        current_pid = os.getpid()
        with open(f"/proc/{current_pid}/cgroup", 'r', encoding='utf-8') as file:
            lines = file.readlines()
            if found_cgroups := len(lines) != 1:
                raise RuntimeError(f"Could not find GMT\'s own cgroup or found too many. Amount: {found_cgroups}")
            cgroup_name = lines[0].split('/')[-1].strip()
            self._cgroups[cgroup_name] = 'GMT Overhead'

    def start_profiling(self, containers=None):
        # we hook here into the mechanism that can supply container names to the parent function
        super().start_profiling(self._cgroups)

    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, self._cgroups)

        if df.empty:
            return df

        df['detail_name'] = df.container_id
        for container_id in self._cgroups:
            df.loc[df.detail_name == container_id, 'detail_name'] = self._cgroups[container_id]
        df = df.drop('container_id', axis=1)

        return df
