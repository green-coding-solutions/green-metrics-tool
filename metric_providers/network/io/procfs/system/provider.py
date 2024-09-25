import os

from metric_providers.base import BaseMetricProvider

class NetworkIoProcfsSystemProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='network_io_procfs_system',
            metrics={'time': int, 'received_bytes': int, 'transmitted_bytes': int},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        df['transmitted_bytes_intervals'] = df['transmitted_bytes'].diff()
        df.loc[0, 'transmitted_bytes_intervals'] = df['transmitted_bytes_intervals'].mean()  # approximate first interval

        df['received_bytes_intervals'] = df['received_bytes'].diff()
        df.loc[0, 'received_bytes_intervals'] = df['received_bytes_intervals'].mean()  # approximate first interval

        df['value'] = df['received_bytes_intervals'] + df['transmitted_bytes_intervals']
        df['value'] = df.value.astype(int)

        df = df.drop(columns=['received_bytes','transmitted_bytes', 'transmitted_bytes_intervals', 'received_bytes_intervals'])  # clean up

        return df
