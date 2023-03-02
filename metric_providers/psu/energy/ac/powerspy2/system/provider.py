import os

#pylint: disable=import-error
from metric_providers.base import BaseMetricProvider

class PsuEnergyAcPowerspy2SystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="psu_energy_ac_powerspy2_system",
            metrics={"time": int, "value": int},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable="metric-provider.py",
        )
        self._extra_switches = ['-u','mJ']
