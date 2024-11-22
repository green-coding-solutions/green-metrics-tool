import os

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from lib.utils import is_rapl_energy_filtering_deactivated

class PsuEnergyDcRaplMsrMachineProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='psu_energy_dc_rapl_msr_machine',
            metrics={'time': int, 'value': int, 'psys_id': str},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self._extra_switches = ['-p']

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        call_string = f"{self._current_dir}/{self._metric_provider_executable}"
        super().check_system(check_command=[f"{call_string}", '-c', '-p'])

        if not is_rapl_energy_filtering_deactivated():
            raise MetricProviderConfigurationError('RAPL energy filtering is active and might skew results!')


    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        if df.empty:
            return df

        df['detail_name'] = df.psys_id
        df = df.drop('psys_id', axis=1)

        return df
