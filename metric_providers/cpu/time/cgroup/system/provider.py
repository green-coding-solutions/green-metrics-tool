import os

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError

class CpuTimeCgroupSystemProvider(BaseMetricProvider):
    def __init__(self, resolution, rootless=False):
        super().__init__(
            metric_name='cpu_time_cgroup_system',
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit='us',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )
        self._rootless = rootless

    def check_system(self):
        file_path = "/sys/fs/cgroup/cpu.stat"
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    file.read()
            except PermissionError as exc:
                raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCannot read {file_path}.\n\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml") from exc
        else:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCould not find {file_path}.\n\nAre you running in a VM / cloud / shared hosting? \nIf so please disable the {self._metric_name} provider in the config.yml")
