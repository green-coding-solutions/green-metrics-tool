import os

from lib import utils
from metric_providers.base import BaseMetricProvider

class DiskIoCgroupContainerProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='disk_io_cgroup_container',
            metrics={'time': int, 'read_bytes': int, 'written_bytes': int, 'container_id': str},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        if df.empty:
            return df

        df = df.sort_values(by=['container_id', 'time'], ascending=True)

        df['written_bytes_intervals'] = df.groupby(['container_id'])['written_bytes'].diff()
        df['written_bytes_intervals'] = df.groupby('container_id')['written_bytes_intervals'].transform(utils.df_fill_mean) # fill first NaN value resulted from diff()

        df['read_bytes_intervals'] = df.groupby(['container_id'])['read_bytes'].diff()
        df['read_bytes_intervals'] = df.groupby('container_id')['read_bytes_intervals'].transform(utils.df_fill_mean) # fill first NaN value resulted from diff()

        # we checked at ingest if it contains NA values. So NA can only occur if group diff resulted in only one value.
        # Since one value is useless for us we drop the row
        df.dropna(inplace=True)

        if (df['read_bytes_intervals'] < 0).any():
            raise ValueError('DiskIoCgroupContainerProvider data column read_bytes_intervals had negative values.')

        if (df['written_bytes_intervals'] < 0).any():
            raise ValueError('DiskIoCgroupContainerProvider data column written_bytes_intervals had negative values.')

        df['value'] = df['read_bytes_intervals'] + df['written_bytes_intervals']
        df['value'] = df.value.astype(int)
        df = df.drop(columns=['read_bytes','written_bytes', 'written_bytes_intervals', 'read_bytes_intervals'])  # clean up

        return df
