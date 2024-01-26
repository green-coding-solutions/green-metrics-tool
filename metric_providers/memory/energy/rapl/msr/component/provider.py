import os
import subprocess

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError

class MemoryEnergyRaplMsrComponentProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='memory_energy_rapl_msr_component',
            metrics={'time': int, 'value': int, 'package_id': str},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self._extra_switches = ['-d']

    def check_system(self):
        call_string = self._metric_provider_executable

        if self._metric_provider_executable[0] != '/':
            call_string = f"{self._current_dir}/{call_string}"

        ps = subprocess.run([f"{call_string}", '-c', '-d'], capture_output=True, encoding='UTF-8', check=False)
        if ps.returncode != 0:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nError: {ps.stderr}\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml")

        self.check_parallel_provider_running()
