import os
import subprocess

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError


class MemoryEnergyRaplMsrComponentProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name='memory_energy_rapl_msr_component',
            metrics={'time': int, 'value': int, 'package_id': str},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )
        self._extra_switches = ['-d']

    # TODO: we get a permissions error here. is this expected?
    def check_system_with_permissions(self):
        file_path = "/dev/cpu/0/msr"
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    file.read()
            except PermissionError as exc:
                raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCannot read the RAPL MSR at {file_path}.\n\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml") from exc
        else:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCould not find the path for the RAPL MSR at {file_path}.\n\nAre you running in a VM / cloud / shared hosting? \nIf so please disable the {self._metric_name} provider in the config.yml")

    def check_system(self):
        ps = subprocess.run(['./metric-provider-binary', '-c'], capture_output=True, text=True, check=False)
        if ps.returncode != 0:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nError: {ps.stderr}\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml")
