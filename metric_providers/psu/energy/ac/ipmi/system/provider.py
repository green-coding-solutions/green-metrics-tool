import os

#pylint: disable=import-error
from metric_providers.base import BaseMetricProvider

class PsuEnergyAcIpmiSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="psu_energy_ac_ipmi_system",
            metrics={"time": int, "value": int},
            resolution=0.001 * resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable="ipmi-get-system-power-stat.sh",
        )

    def read_metrics(self, project_id, containers):
        df = super().read_metrics(project_id, containers)

        # Conversion to Joules
        intervals = df["time"].diff()
        intervals[0] = intervals.mean()  # approximate first interval
        df["interval"] = intervals  # in microseconds
        df["value"] = df.apply(lambda x: x["value"] * x["interval"] / 1_000, axis=1)
        df = df.drop(columns="interval")  # clean up

        return df
