import os

from metric_providers.base import BaseMetricProvider

class DiskIoCgroupContainerProvider(BaseMetricProvider):
    def __init__(self, resolution, rootless=False, skip_check=False):
        super().__init__(
            metric_name='disk_io_cgroup_container',
            metrics={'time': int, 'read_bytes': int, 'written_bytes': int, 'container_id': str},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self._rootless = rootless

    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        df['value'] = df['read_bytes'] + df['written_bytes']


        df['written_bytes_intervals'] = df['written_bytes'].diff()
        df.loc[0, 'written_bytes_intervals'] = df['written_bytes_intervals'].mean()  # approximate first interval

        df['read_bytes_intervals'] = df['read_bytes'].diff()
        df.loc[0, 'read_bytes_intervals'] = df['read_bytes_intervals'].mean()  # approximate first interval

        df['value'] = df['read_bytes_intervals'] + df['written_bytes_intervals']
        df['value'] = df.value.astype(int)
        df = df.drop(columns=['read_bytes','written_bytes', 'written_bytes_intervals', 'read_bytes_intervals'])  # clean up

        return df
