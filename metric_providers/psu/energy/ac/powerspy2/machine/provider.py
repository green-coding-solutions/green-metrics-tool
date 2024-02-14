import os
from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError

class PsuEnergyAcPowerspy2MachineProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name="psu_energy_ac_powerspy2_machine",
            metrics={"time": int, "value": int},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable="metric-provider.py",
            skip_check=skip_check,
        )
        self._extra_switches = ['-u','mJ']

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        super().check_system(check_command=None)

        file_path = "/dev/rfcomm0"
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    file.read()
            except PermissionError as exc:
                raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCannot read device at {file_path}.\n\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml") from exc
        else:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCould not find device at {file_path}.\n\nAre you running in a VM / cloud / shared hosting? \nIf so please disable the {self._metric_name} provider in the config.yml")
