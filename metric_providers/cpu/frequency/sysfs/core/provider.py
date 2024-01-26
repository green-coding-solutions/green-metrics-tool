import os

from metric_providers.base import BaseMetricProvider

class CpuFrequencySysfsCoreProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='cpu_frequency_sysfs_core',
            metrics={'time': int, 'value': int, 'core_id': int},
            resolution=0.001*resolution,
            unit='Hz',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable='get-scaling-cur-freq.sh',
            skip_check=skip_check,
        )
