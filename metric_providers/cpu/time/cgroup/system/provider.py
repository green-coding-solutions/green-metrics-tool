import os

from metric_providers.base import BaseMetricProvider

class CpuTimeCgroupSystemProvider(BaseMetricProvider):
    # disabling unused-argument because as a cgroup provider we always pass in rootless as a variable
    # even though this provider does not need/care about it
    #pylint: disable=unused-argument
    def __init__(self, resolution, rootless=False, skip_check=False):
        super().__init__(
            metric_name='cpu_time_cgroup_system',
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit='us',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self._rootless = False #this provider does not need or take --rootless flag, despite being a cgroup provider
