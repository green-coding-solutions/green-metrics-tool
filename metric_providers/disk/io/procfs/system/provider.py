import os
from functools import lru_cache

from lib import utils
from metric_providers.base import BaseMetricProvider

class DiskIoProcfsSystemProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='disk_io_procfs_system',
            metrics={'time': int, 'read_sectors': int, 'written_sectors': int, 'device': str},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        if df.empty:
            return df

        df = df.sort_values(by=['device', 'time'], ascending=True)

        df['read_sectors_intervals'] = df.groupby(['device'])['read_sectors'].diff()
        df['read_sectors_intervals'] = df.groupby('device')['read_sectors_intervals'].transform(utils.df_fill_mean) # fill first NaN value resulted from diff()

        df['written_sectors_intervals'] = df.groupby(['device'])['written_sectors'].diff()
        df['written_sectors_intervals'] = df.groupby('device')['written_sectors_intervals'].transform(utils.df_fill_mean) # fill first NaN value resulted from diff()

        # we checked at ingest if it contains NA values. So NA can only occur if group diff resulted in only one value.
        # Since one value is useless for us we drop the row
        df.dropna(inplace=True)

        if (df['written_sectors_intervals'] < 0).any():
            raise ValueError('DiskIoProcfsSystemProvider data column written_sectors_intervals had negative values.')

        if (df['read_sectors_intervals'] < 0).any():
            raise ValueError('DiskIoProcfsSystemProvider data column read_sectors_intervals had negative values.')

        df['blocksize'] = df['device'].apply(self.get_blocksize)
        df['value'] = (df['read_sectors_intervals'] + df['written_sectors_intervals'])*df['blocksize']
        df['value'] = df.value.astype(int)
        df['detail_name'] = df['device']
        df = df.drop(columns=['read_sectors','written_sectors', 'written_sectors_intervals', 'read_sectors_intervals', 'device', 'blocksize'])  # clean up

        return df

    @lru_cache(maxsize=100)
    def get_blocksize(self, device_name):
        device_path = f"/sys/block/{device_name}/queue/hw_sector_size"
        with open(device_path, "r", encoding='utf-8') as fd:
            sector_size = int(fd.read().strip())

        return sector_size
