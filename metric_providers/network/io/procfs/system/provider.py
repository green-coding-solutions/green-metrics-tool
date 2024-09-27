import os
from lib import utils

from metric_providers.base import BaseMetricProvider

class NetworkIoProcfsSystemProvider(BaseMetricProvider):
    def __init__(self, resolution, remove_virtual_interfaces=True, skip_check=False):
        super().__init__(
            metric_name='network_io_procfs_system',
            metrics={'time': int, 'received_bytes': int, 'transmitted_bytes': int, 'interface': str},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self._remove_virtual_interfaces = remove_virtual_interfaces

    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        if df.empty:
            return df

        if self._remove_virtual_interfaces:
            non_virtual_interfaces = utils.get_network_interfaces(mode='physical')
            mask = df['interface'].isin(non_virtual_interfaces)
            df = df[mask]

        df = df.sort_values(by=['interface', 'time'], ascending=True)

        df['transmitted_bytes_intervals'] = df.groupby(['interface'])['transmitted_bytes'].diff()
        df['transmitted_bytes_intervals'] = df.groupby('interface')['transmitted_bytes_intervals'].transform(utils.df_fill_mean) # fill first NaN value resulted from diff()

        df['received_bytes_intervals'] = df.groupby(['interface'])['received_bytes'].diff()
        df['received_bytes_intervals'] = df.groupby('interface')['received_bytes_intervals'].transform(utils.df_fill_mean) # fill first NaN value resulted from diff()

        # we checked at ingest if it contains NA values. So NA can only occur if group diff resulted in only one value.
        # Since one value is useless for us we drop the row
        df.dropna(inplace=True)

        if (df['transmitted_bytes_intervals'] < 0).any():
            raise ValueError('NetworkIoProcfsSystemProvider data column transmitted_bytes_intervals had negative values.')

        if (df['received_bytes_intervals'] < 0).any():
            raise ValueError('NetworkIoProcfsSystemProvider data column received_bytes_intervals had negative values.')

        df['value'] = df['received_bytes_intervals'] + df['transmitted_bytes_intervals']
        df['value'] = df.value.astype(int)

        df['detail_name'] = df['interface']

        df = df.drop(columns=['received_bytes','transmitted_bytes', 'transmitted_bytes_intervals', 'received_bytes_intervals', 'interface'])  # clean up

        return df
