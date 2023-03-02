import os

#pylint: disable=import-error
from metric_providers.base import BaseMetricProvider

class CpuUtilizationProcfsSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="cpu_utilization_procfs_system",
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit="Ratio",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )
