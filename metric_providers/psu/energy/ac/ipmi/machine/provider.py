import os

#pylint: disable=import-error
from metric_providers.base import BaseMetricProvider

class PsuEnergyAcIpmiMachineProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="psu_energy_ac_ipmi_machine",
            metrics={"time": int, "value": int},
            resolution=0.001 * resolution,
            unit="W",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable="ipmi-get-machine-power-stat.sh",
        )
