import os

from metric_providers.container import ContainerMetricProvider

class MemoryUsedCgroupContainerProvider(ContainerMetricProvider):
    def __init__(self, sampling_rate, skip_check=False, containers: dict = None):
        super().__init__(
            metric_name='memory_used_cgroup_container',
            metrics={'time': int, 'value': int, 'container_id': str},
            sampling_rate=sampling_rate,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            containers=containers,
        )
