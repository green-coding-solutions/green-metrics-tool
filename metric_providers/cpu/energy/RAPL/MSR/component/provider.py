import os
import subprocess

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError

class CpuEnergyRaplMsrComponentProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name='cpu_energy_rapl_msr_component',
            metrics={'time': int, 'value': int, 'package_id': str},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )

    def check_system(self):
        ps = subprocess.run(['./metric-provider-binary', '-c'], capture_output=True, text=True, check=False)
        if ps.returncode != 0:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nError: {ps.stderr}\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml")
