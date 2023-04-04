import os

#pylint: disable=import-error
from metric_providers.base import BaseMetricProvider

class CpuEnergyRaplMsrSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="cpu_energy_rapl_msr_component",
            metrics={"time": int, "value": int, "package_id": str},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )
