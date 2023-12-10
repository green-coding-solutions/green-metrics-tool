import os
from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError

class PsuEnergyAcPowerspy2MachineProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="psu_energy_ac_powerspy2_machine",
            metrics={"time": int, "value": int},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable="metric-provider.py",
        )
        self._extra_switches = ['-u','mJ']

    def check_system(self):
        file_path = "/dev/rfcomm0"
        if not os.path.exists(file_path):
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCould not find device at {file_path}.\n\nAre you running in a VM / cloud / shared hosting? \nIf so please disable the {self._metric_name} provider in the config.yml")
