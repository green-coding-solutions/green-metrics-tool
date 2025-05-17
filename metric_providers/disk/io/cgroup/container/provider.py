import os

from metric_providers.container import ContainerMetricProvider
from metric_providers.disk.io.disk_io_parse import DiskIoParseMixin

class DiskIoCgroupContainerProvider(DiskIoParseMixin, ContainerMetricProvider):
    def __init__(self, resolution, skip_check=False, containers: dict = None):
        super().__init__(
            metric_name='disk_io_cgroup_container',
            metrics={'time': int, 'read_bytes': int, 'written_bytes': int, 'container_id': str},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            containers=containers,
        )
        self._sub_metrics_name = ['disk_io_read_cgroup_container', 'disk_io_write_cgroup_container']
