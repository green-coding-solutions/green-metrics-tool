import os
from functools import lru_cache

from metric_providers.base import BaseMetricProvider

class DiskIoProcfsSystemProvider(BaseMetricProvider):
    def __init__(self, resolution, rootless=False, skip_check=False):
        super().__init__(
            metric_name='disk_io_procfs_system',
            metrics={'time': int, 'read_sectors': int, 'written_sectors': int, 'interface': str},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self._rootless = rootless


    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        df['written_sectors_intervals'] = df['written_sectors'].diff()
        df.loc[0, 'written_sectors_intervals'] = df['written_sectors_intervals'].mean()  # approximate first interval

        df['read_sectors_intervals'] = df['read_sectors'].diff()
        df.loc[0, 'read_sectors_intervals'] = df['read_sectors_intervals'].mean()  # approximate first interval

        df['blocksize'] = df['interface'].apply(self.get_blocksize)
        df['value'] = (df['read_sectors_intervals'] + df['written_sectors_intervals'])*df['blocksize']
        df['value'] = df.value.astype(int)
        df['detail_name'] = df['interface']
        df = df.drop(columns=['read_sectors','written_sectors', 'written_sectors_intervals', 'read_sectors_intervals', 'interface', 'blocksize'])  # clean up

        return df

    @lru_cache(maxsize=100)
    def get_blocksize(self, device_name):
        device_path = f"/sys/block/{device_name}/queue/hw_sector_size"

        with open(device_path, "r", encoding='utf-8') as fd:
            sector_size = int(fd.read().strip())

        return sector_size

# Test code
#if __name__ == '__main__':
#    obj = DiskIoProcfsSystemProvider(100)
#    obj._filename = 'test.log'
#    df = obj.read_metrics('asd')
#    print(df)
