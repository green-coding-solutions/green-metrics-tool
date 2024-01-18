import os

#pylint: disable=import-error, invalid-name
from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError

class PsuEnergyAcMcpMachineProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='psu_energy_ac_mcp_machine',
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def check_system(self):
        file_path = "/dev/ttyACM0"
        if not os.path.exists(file_path):
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCould not find device at {file_path}.\n\nAre you running in a VM / cloud / shared hosting? \nIf so please disable the {self._metric_name} provider in the config.yml")
