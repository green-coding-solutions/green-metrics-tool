import os

from metric_providers.base import BaseMetricProvider

class CpuThrottlingMsrComponentProvider(BaseMetricProvider):
    def __init__(self, sampling_rate, skip_check=False):
        super().__init__(
            metric_name='cpu_throttling_msr_component',
            metrics={'time': int, 'thermal_throttling_status': int, 'power_limit_throttling_status': int, 'package_id': str},
            sampling_rate=sampling_rate,
            unit='boolean',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self._sub_metrics_name = ['cpu_throttling_thermal_msr_component', 'cpu_throttling_power_msr_component']


    def _parse_metrics(self, df):
        df['detail_name'] = df.package_id
        df = df.drop('package_id', axis=1)

        base_cols = ['time', 'detail_name']

        df_thermal_throttling_status = (
            df[base_cols + ['thermal_throttling_status']]
            .rename(columns={'thermal_throttling_status': 'value'})
            .copy()
        )
        df_thermal_throttling_status['unit'] = self._unit
        df_thermal_throttling_status['metric'] = self._sub_metrics_name[0]

        df_power_limit_throttling_status = (
            df[base_cols + ['power_limit_throttling_status']]
            .rename(columns={'power_limit_throttling_status': 'value'})
            .copy()
        )
        df_power_limit_throttling_status['unit'] = self._unit
        df_power_limit_throttling_status['metric'] = self._sub_metrics_name[1]

        return [df_thermal_throttling_status, df_power_limit_throttling_status]
