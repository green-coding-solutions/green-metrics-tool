import os

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
