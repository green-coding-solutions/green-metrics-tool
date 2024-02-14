import os

from metric_providers.base import BaseMetricProvider

class CpuTimeProcfsSystemProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='cpu_time_procfs_system',
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit='us',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check = skip_check
        )
