import os

from metric_providers.base import BaseMetricProvider

class CpuEnergyRaplMsrComponentProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='cpu_energy_rapl_msr_component',
            metrics={'time': int, 'value': int, 'package_id': str},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
