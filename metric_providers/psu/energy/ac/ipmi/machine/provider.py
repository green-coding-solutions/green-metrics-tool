import os

#pylint: disable=import-error, invalid-name
from metric_providers.base import BaseMetricProvider

class PsuEnergyAcIpmiMachineProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name='psu_energy_ac_ipmi_machine',
            metrics={'time': int, 'value': int},
            resolution=0.001 * resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable='ipmi-get-machine-energy-stat.sh',
        )

    def read_metrics(self, run_id, containers):
        df = super().read_metrics(run_id, containers)

        # Conversion to Joules
        intervals = df['time'].diff()
        intervals[0] = intervals.mean()  # approximate first interval
        df['interval'] = intervals  # in microseconds
        df['value'] = df.apply(lambda x: x['value'] * x['interval'] / 1_000, axis=1)
        df['value'] = df.value.fillna(0) # maybe not needed
        df['value'] = df.value.astype(int)

        df = df.drop(columns='interval')  # clean up

        return df
