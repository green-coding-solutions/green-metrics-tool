import os
from functools import lru_cache

from metric_providers.base import BaseMetricProvider
from metric_providers.disk.io.disk_io_parse import DiskIoParseMixin

class DiskIoProcfsSystemProvider(BaseMetricProvider, DiskIoParseMixin):
    def __init__(self, sampling_rate, skip_check=False):
        super().__init__(
            metric_name='disk_io_procfs_system',
            metrics={'time': int, 'read_sectors': int, 'written_sectors': int, 'device': str},
            sampling_rate=sampling_rate,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

        self._sub_metrics_name = ['disk_io_read_procfs_system', 'disk_io_write_procfs_system']

    def _parse_metrics(self, df):
        df = super()._parse_metrics(df)

        df['blocksize'] = df['device'].apply(self.get_blocksize)
        df['read_bytes'] = df['read_sectors']*df['blocksize']
        df['written_bytes'] = df['written_sectors']*df['blocksize']
        df['detail_name'] = df['device']

        return self._parse_metrics_splitup_helper(df)

    @lru_cache(maxsize=100)
    def get_blocksize(self, device_name):
        device_path = f"/sys/block/{device_name}/queue/hw_sector_size"
        with open(device_path, "r", encoding='utf-8') as fd:
            sector_size = int(fd.read().strip())

        return sector_size
