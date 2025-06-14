import os

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from lib.utils import is_rapl_energy_filtering_deactivated

class MemoryEnergyRaplMsrComponentProvider(BaseMetricProvider):
    def __init__(self, sampling_rate, skip_check=False):
        super().__init__(
            metric_name='memory_energy_rapl_msr_component',
            metrics={'time': int, 'value': int, 'dram_id': str},
            sampling_rate=sampling_rate,
            unit='uJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        call_string = f"{self._current_dir}/{self._metric_provider_executable}"
        super().check_system(check_command=[f"{call_string}", '-c', '-d'])

        if not is_rapl_energy_filtering_deactivated():
            raise MetricProviderConfigurationError('RAPL energy filtering is active and might skew results!')

    def _add_extra_switches(self, call_string):
        return f"{call_string} -d"

    def _parse_metrics(self, df):

        df['detail_name'] = df.dram_id
        df = df.drop('dram_id', axis=1)

        return df
