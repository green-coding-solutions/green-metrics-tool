import os

from metric_providers.cgroup import CgroupMetricProvider

class CpuTimeCgroupSystemProvider(CgroupMetricProvider):
    def __init__(self, sampling_rate, skip_check=False, cgroups: dict = None):
        super().__init__(
            metric_name='cpu_time_cgroup_system',
            metrics={'time': int, 'value': int},
            sampling_rate=sampling_rate,
            unit='us',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            cgroups=cgroups,
        )
