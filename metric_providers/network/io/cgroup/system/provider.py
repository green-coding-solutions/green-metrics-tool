import os

from lib import utils
from metric_providers.cgroup import CgroupMetricProvider

class NetworkIoCgroupSystemProvider(CgroupMetricProvider):
    def __init__(self, sampling_rate, skip_check=False, cgroups: dict = None):
        super().__init__(
            metric_name='network_io_cgroup_system',
            metrics={'time': int, 'received_bytes': int, 'transmitted_bytes': int, 'cgroup_str': str},
            sampling_rate=sampling_rate,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            cgroups=cgroups,
        )

    def _parse_metrics(self, df):
        df = super()._parse_metrics(df) # sets detail_name

        df = df.sort_values(by=['detail_name', 'time'], ascending=True)

        df['transmitted_bytes_intervals'] = df.groupby(['detail_name'])['transmitted_bytes'].diff()
        df['transmitted_bytes_intervals'] = df.groupby('detail_name')['transmitted_bytes_intervals'].transform(utils.df_fill_mean) # fill first NaN value resulted from diff()

        df['received_bytes_intervals'] = df.groupby(['detail_name'])['received_bytes'].diff()
        df['received_bytes_intervals'] = df.groupby('detail_name')['received_bytes_intervals'].transform(utils.df_fill_mean) # fill first NaN value resulted from diff()

        # we checked at ingest if it contains NA values. So NA can only occur if group diff resulted in only one value.
        # Since one value is useless for us we drop the row
        df.dropna(inplace=True)

        if (df['received_bytes_intervals'] < 0).any():
            raise ValueError('NetworkIoCgroupSystemProvider data column received_bytes_intervals had negative values.')

        if (df['transmitted_bytes_intervals'] < 0).any():
            raise ValueError('NetworkIoCgroupSystemProvider data column transmitted_bytes_intervals had negative values.')

        df['value'] = df['received_bytes_intervals'] + df['transmitted_bytes_intervals']
        df['value'] = df.value.astype('int64')

        df = df.drop(columns=['received_bytes','transmitted_bytes', 'transmitted_bytes_intervals', 'received_bytes_intervals'])  # clean up

        return df
