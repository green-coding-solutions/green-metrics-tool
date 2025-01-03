import os

from metric_providers.base import BaseMetricProvider

class PsuEnergyAcMcpMachineProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='psu_energy_ac_mcp_machine',
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit="uJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def _parse_metrics(self, df):
        df = super()._parse_metrics(df) # sets detail_name

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

        # we checked at ingest if it contains NA values. So NA can only occur if group diff resulted in only one value.
        # Since one value is useless for us we drop the row
        df.dropna(inplace=True)

        df['interval'] = intervals  # in microseconds
        df['value'] = df.apply(lambda x: x['value'] * x['interval'] / 1_00, axis=1) # value is in centiwatts (0.01 W), so divide by 1_00 to get Watts and multiply with us to get micro-Joules
        df['value'] = df.value.astype(int)

        df = df.drop(columns='interval')  # clean up

        return df
