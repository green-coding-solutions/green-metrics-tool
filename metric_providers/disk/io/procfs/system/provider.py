import os

from metric_providers.base import BaseMetricProvider
from metric_providers.disk.io.disk_io_parse import DiskIoParseMixin

# /proc/diskstats always reports sectors in 512-byte units, regardless of the
# device's hw_sector_size / logical_block_size.
# See https://www.kernel.org/doc/Documentation/admin-guide/iostats.rst
DISKSTATS_SECTOR_SIZE = 512

class DiskIoProcfsSystemProvider(BaseMetricProvider, DiskIoParseMixin):
    def __init__(self, sampling_rate, folder, skip_check=False):
        super().__init__(
            metric_name='disk_io_procfs_system',
            metrics={'time': int, 'read_sectors': int, 'written_sectors': int, 'device': str},
            sampling_rate=sampling_rate,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )

        self._sub_metrics_name = ['disk_io_read_procfs_system', 'disk_io_write_procfs_system']

    def _parse_metrics(self, df):
        df = super()._parse_metrics(df)

        df['read_bytes'] = df['read_sectors']*DISKSTATS_SECTOR_SIZE
        df['written_bytes'] = df['written_sectors']*DISKSTATS_SECTOR_SIZE
        df['detail_name'] = df['device']

        return self._parse_metrics_splitup_helper(df)
