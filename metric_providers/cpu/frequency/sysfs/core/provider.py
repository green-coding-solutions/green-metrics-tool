import os

from metric_providers.base import MetricProviderConfigurationError, BaseMetricProvider

class CpuFrequencySysfsCoreProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name='cpu_frequency_sysfs_core',
            metrics={'time': int, 'value': int, 'core_id': int},
            resolution=0.001*resolution,
            unit='Hz',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable='get-scaling-cur-freq.sh',
        )

    def check_system(self):
        file_path = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    file.read()
            except PermissionError as exc:
                raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCannot read the path for the CPU frequency in sysfs.\n\nAre you running in a VM / cloud / shared hosting?\nIf so please disable the {self._metric_name} provider in the config.yml") from exc
        raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nCould not find the path for the CPU frequency in sysfs.\n\nAre you running in a VM / cloud / shared hosting? \nIf so please disable the {self._metric_name} provider in the config.yml")
