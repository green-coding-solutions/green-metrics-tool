import os

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError

class NetworkIoCgroupContainerProvider(BaseMetricProvider):
    def __init__(self, resolution, rootless=False):
        super().__init__(
            metric_name='network_io_cgroup_container',
            metrics={'time': int, 'value': int, 'container_id': str},
            resolution=resolution,
            unit='Bytes',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )
        self._rootless = rootless

    def check_system(self):
        if self._rootless:
            file_path_cgroup_procs = "/sys/fs/cgroup/user.slice/cgroup.procs"
        else:
            file_path_cgroup_procs = "/sys/fs/cgroup/system.slice/cgroup.procs"

        file_path_proc_stat = "/proc/net/dev"
        errors = []

        if not os.path.exists(file_path_cgroup_procs):
            errors.append(f"Could not find the path for the cgroup cpu stat file: {file_path_cgroup_procs}")
        else:
            # Check cgroup cpu stat file path for permission
            try:
                with open(file_path_cgroup_procs, 'r', encoding='utf-8') as file:
                    file.read()
            except PermissionError as exc:
                errors.append(f"Cannot read the path for the cgroup cpu stat file: {file_path_cgroup_procs}")
                errors.append(f"Error details: {exc}")

        # Check proc stat file path existence
        if not os.path.exists(file_path_proc_stat):
            errors.append(f"Could not find the path for the proc stat file: {file_path_proc_stat}")
        else:
            # Check proc stat file path for permission
            try:
                with open(file_path_proc_stat, 'r', encoding='utf-8') as file:
                    file.read()
            except PermissionError as exc:
                errors.append(f"Cannot read the path for the proc stat file: {file_path_proc_stat}")
                errors.append(f"Error details: {exc}")

        if errors:
            error_message = "\n".join(errors)
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\n{error_message}\n\nAre you running in a VM / cloud / shared hosting?\nIf so, please disable the {self._metric_name} provider in the config.yml")
