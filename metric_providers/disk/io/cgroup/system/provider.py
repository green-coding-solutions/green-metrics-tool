import os

from metric_providers.cgroup import CgroupMetricProvider
from metric_providers.disk.io.disk_io_parse import DiskIoParseMixin

class DiskIoCgroupSystemProvider(DiskIoParseMixin, CgroupMetricProvider):
    def __init__(self, sampling_rate, folder, skip_check=False, cgroups: dict = None):
        super().__init__(
            metric_name='disk_io_cgroup_system',
            metrics={'time': int, 'read_bytes': int, 'written_bytes': int, 'cgroup_str': str},
            sampling_rate=sampling_rate,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
            cgroups=cgroups,
        )

        self._sub_metrics_name = ['disk_io_read_cgroup_system', 'disk_io_write_cgroup_system']

    def _parse_metrics(self, df):
        df = super()._parse_metrics(df)
        return self._parse_metrics_splitup_helper(df)
