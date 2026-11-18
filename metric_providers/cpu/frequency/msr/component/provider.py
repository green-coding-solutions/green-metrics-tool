import os

from metric_providers.base import BaseMetricProvider

class CpuFrequencyMsrComponentProvider(BaseMetricProvider):
    def __init__(self, sampling_rate, folder, base_ghz=2.4, uncore=False, skip_check=False):
        self._base_ghz = base_ghz
        self._uncore = uncore
        super().__init__(
            metric_name='cpu_frequency_msr_component',
            metrics={'time': int, 'value': int, 'detail_name': str},
            sampling_rate=sampling_rate,
            unit='Hz',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        if check_command == "default" and self._uncore:
            check_command = [f"{self._current_dir}/{self._metric_provider_executable}", '-c', '-u']
        return super().check_system(check_command=check_command, check_error_message=check_error_message, check_parallel_provider=check_parallel_provider)

    def _add_extra_switches(self, call_string):
        call_string = f"{call_string} -f {self._base_ghz}"
        if self._uncore:
            call_string = f"{call_string} -u"
        return call_string

    # The binary already emits the detail_name per row: Core_<cpu_id> or Uncore_Package_<package_id>
    def _parse_metrics(self, df):
        return df
