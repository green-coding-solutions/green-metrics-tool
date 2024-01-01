import os

from metric_providers.base import BaseMetricProvider

class PsuEnergyAcIpmiMachineProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='psu_energy_ac_ipmi_machine',
            metrics={'time': int, 'value': int},
            resolution=0.001 * resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable='ipmi-get-machine-energy-stat.sh',
            skip_check=skip_check,
        )


    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        '''
        Conversion to Joules

        If ever in need to convert the database from Joules back to a power format:

        WITH times as (
                    SELECT id, value, detail_name, time, (time - LAG(time) OVER (ORDER BY detail_name ASC, time ASC)) AS diff, unit
                    FROM measurements
                    WHERE run_id = RUN_ID AND metric = 'psu_energy_ac_ipmi_machine'

                    ORDER BY detail_name ASC, time ASC)
                    SELECT *, value / (diff / 1000) as power FROM times;

        One can see that the value only changes once per second
        '''

        intervals = df['time'].diff()
        intervals[0] = intervals.mean()  # approximate first interval
        df['interval'] = intervals  # in microseconds
        df['value'] = df.apply(lambda x: x['value'] * x['interval'] / 1_000, axis=1)
        df['value'] = df.value.fillna(0) # maybe not needed
        df['value'] = df.value.astype(int)

        df = df.drop(columns='interval')  # clean up

        return df
