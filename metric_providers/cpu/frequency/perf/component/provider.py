import os
import shlex

from metric_providers.base import BaseMetricProvider

class CpuFrequencyPerfComponentProvider(BaseMetricProvider):
    def __init__(self, sampling_rate, folder, base_ghz=2.4, uncore=False, uncore_pmu=None, uncore_event=None, skip_check=False):
        self._base_ghz = base_ghz
        self._uncore = uncore
        # optional overrides in case auto-detection of the uncore PMU does not fit the CPU
        self._uncore_pmu = uncore_pmu
        self._uncore_event = uncore_event
        if (self._uncore_pmu or self._uncore_event) and not self._uncore:
            raise ValueError('cpu_frequency_perf_component: "uncore_pmu" / "uncore_event" require "uncore: true"')
        if self._uncore_event and not self._uncore_pmu:
            raise ValueError('cpu_frequency_perf_component: "uncore_event" can only be set together with "uncore_pmu"')

        super().__init__(
            metric_name='cpu_frequency_perf_component',
            metrics={'time': int, 'value': int, 'detail_name': str},
            sampling_rate=sampling_rate,
            unit='Hz',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )

    def _uncore_switches(self):
        switches = []
        if self._uncore:
            switches.append('-u')
        if self._uncore_pmu:
            switches += ['-p', self._uncore_pmu]
        if self._uncore_event:
            switches += ['-e', self._uncore_event]
        return switches

    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        if check_command == "default":
            check_command = [f"{self._current_dir}/{self._metric_provider_executable}", '-c', *self._uncore_switches()]
        return super().check_system(check_command=check_command, check_error_message=check_error_message, check_parallel_provider=check_parallel_provider)

    def _add_extra_switches(self, call_string):
        return f"{call_string} {shlex.join(['-f', str(self._base_ghz), *self._uncore_switches()])}"

    # The binary already emits the detail_name per row: Core_<cpu_id> or Uncore_Package_<id>[_Die_<id>]
    def _parse_metrics(self, df):
        return df
