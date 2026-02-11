import os

from metric_providers.base import BaseMetricProvider

class GpuEnergyNvidiaNvmlComponentProvider(BaseMetricProvider):
    def __init__(self, sampling_rate, folder, skip_check=False):
        super().__init__(
            metric_name='gpu_energy_nvidia_nvml_component',
            metrics={'time': int, 'value': int, 'card_model': str},
            sampling_rate=sampling_rate,
            unit='uJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )

    def _parse_metrics(self, df):
        df = super()._parse_metrics(df) # sets detail_name
        df['detail_name'] = df.card_model

        '''
        Conversion to Joules

        If ever in need to convert the database from Joules back to a power format:

        WITH times as (
                    SELECT id, value, detail_name, time, (time - LAG(time) OVER (ORDER BY detail_name ASC, time ASC)) AS diff, unit
                    FROM measurements
                    WHERE run_id = RUN_ID AND metric = 'gpu_energy_nvidia_nvml_component'

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
        # value is initially in milliWatts. So we multiply by 1_000 to get uW and then divide by 1_000_000 to get from us to s  => / 1_000
        df['value'] = df.apply(lambda x: x['value'] * x['interval'] / 1_000, axis=1)
        df['value'] = df.value.astype('int64')

        df = df.drop(columns='interval')  # clean up

        return df
