import os
from metric_providers.base import BaseMetricProvider

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
