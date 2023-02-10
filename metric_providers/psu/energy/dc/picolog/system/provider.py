import os

#pylint: disable=import-error
from metric_providers.base import BaseMetricProvider

class PsuEnergyDcPicologSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="psu_energy_dc_picolog_system",
            metrics={"time": int, "value": int},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )
