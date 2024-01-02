import os

#pylint: disable=import-error, invalid-name
from metric_providers.base import BaseMetricProvider

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
