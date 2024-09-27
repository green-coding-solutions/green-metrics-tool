import os

from metric_providers.base import BaseMetricProvider

class CpuFrequencySysfsCoreProvider(BaseMetricProvider):
    def __init__(self, resolution, skip_check=False):
        super().__init__(
            metric_name='cpu_frequency_sysfs_core',
            metrics={'time': int, 'value': int, 'core_id': int},
            resolution=resolution,
            unit='Hz',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable='get-scaling-cur-freq.sh',
            skip_check=skip_check,
        )

    def read_metrics(self, run_id, containers=None):
        df = super().read_metrics(run_id, containers)

        if df.empty:
            return df

        df['detail_name'] = df.core_id
        df = df.drop('core_id', axis=1)

        return df
