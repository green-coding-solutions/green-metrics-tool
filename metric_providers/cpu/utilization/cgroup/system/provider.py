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
        self._cgroups = cgroups

    def start_profiling(self, containers=None):
        # we hook here into the mechanism that can supply container names to the parent function
        super().start_profiling(self._cgroups)

    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, self._cgroups)

        if df.empty:
            return df

        df['detail_name'] = df.container_id
        for container_id in containers:
            df.loc[df.detail_name == container_id, 'detail_name'] = containers[container_id]['name']
        df = df.drop('container_id', axis=1)

        return df
