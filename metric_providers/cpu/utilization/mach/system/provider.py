import os

from metric_providers.base import BaseMetricProvider

class CpuUtilizationMachSystemProvider(BaseMetricProvider):
    def __init__(self, sampling_rate, skip_check=False):
        super().__init__(
            metric_name='cpu_utilization_mach_system',
            metrics={'time': int, 'value': int},
            sampling_rate=sampling_rate,
            unit='Ratio',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check = skip_check,
        )
