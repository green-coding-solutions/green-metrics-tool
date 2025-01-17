import os

from metric_providers.container import ContainerMetricProvider

class CpuTimeCgroupContainerProvider(ContainerMetricProvider):
    def __init__(self, resolution, skip_check=False, containers: dict = None):
        super().__init__(
            metric_name='cpu_time_cgroup_container',
            metrics={'time': int, 'value': int, 'container_id': str},
            resolution=resolution,
            unit='us',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            containers=containers,
        )
