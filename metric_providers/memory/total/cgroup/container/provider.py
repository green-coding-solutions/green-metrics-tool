import os

from metric_providers.base import BaseMetricProvider

class MemoryTotalCgroupContainerProvider(BaseMetricProvider):
    def __init__(self, resolution, rootless=False, skip_check=False):
        super().__init__(
            metric_name='memory_total_cgroup_container',
            metrics={'time': int, 'value': int, 'container_id': str},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self._rootless = rootless
