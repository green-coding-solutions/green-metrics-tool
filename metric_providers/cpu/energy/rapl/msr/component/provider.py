import os

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from lib.utils import is_rapl_energy_filtering_deactivated

class CpuEnergyRaplMsrComponentProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='cpu_energy_rapl_msr_component',
            metrics={'time': int, 'value': int, 'package_id': str},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        super().check_system()
        if not is_rapl_energy_filtering_deactivated():
            raise MetricProviderConfigurationError('RAPL energy filtering is active and might skew results!')

    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        if df.empty:
            return df

        df['detail_name'] = df.package_id
        df = df.drop('package_id', axis=1)

        return df
