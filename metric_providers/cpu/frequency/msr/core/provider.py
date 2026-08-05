import os

from metric_providers.base import BaseMetricProvider

class CpuFrequencyMsrCoreProvider(BaseMetricProvider):
    def __init__(self, sampling_rate, folder, base_ghz=2.4, skip_check=False):
        self._base_ghz = base_ghz
        super().__init__(
            metric_name='cpu_frequency_msr_core',
            metrics={'time': int, 'value': int, 'core_id': int},
            sampling_rate=sampling_rate,
            unit='Hz',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )

    def _add_extra_switches(self, call_string):
        return f"{call_string} -f {self._base_ghz}"

    def _parse_metrics(self, df):

        df['detail_name'] = df.core_id
        df = df.drop('core_id', axis=1)

        return df
