import os

from metric_providers.base import BaseMetricProvider

class CpuTimeCgroupContainerProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='cpu_time_cgroup_container',
            metrics={'time': int, 'value': int, 'container_id': str},
            resolution=resolution,
            unit='us',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        if df.empty:
            return df

        df['detail_name'] = df.container_id
        for container_id in containers:
            df.loc[df.detail_name == container_id, 'detail_name'] = containers[container_id]['name']
        df = df.drop('container_id', axis=1)

        return df
