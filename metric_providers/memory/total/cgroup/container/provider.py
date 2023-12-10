import os

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError

class MemoryTotalCgroupContainerProvider(BaseMetricProvider):
    def __init__(self, resolution, rootless=False):
        super().__init__(
            metric_name='memory_total_cgroup_container',
            metrics={'time': int, 'value': int, 'container_id': str},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )
        self._rootless = rootless

    def check_system(self):
        if self._rootless:
            file_path = "/sys/fs/cgroup/user.slice/memory.current"
        else:
            file_path = "/sys/fs/cgroup/system.slice/memory.current"

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    file.read()
            except PermissionError as exc:
                raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCannot open {file_path}.\n\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml") from exc
        else:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCould not find {file_path}.\n\nAre you running in a VM / cloud / shared hosting? \nIf so please disable the {self._metric_name} provider in the config.yml")
