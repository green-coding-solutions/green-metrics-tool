import os
import subprocess

from lib import host_platform
from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError


class CpuEnergyRaplScaphandreComponentProvider(BaseMetricProvider):

    def __init__(self, sampling_rate, folder, skip_check=False, domains=None):
        allowed_domains = {"cpu_package", "cpu_cores", "cpu_gpu", "dram", "psys"}
        self._disabled_domains = []
        self._stdout_file = None

        if domains:
            for domain, enabled in domains.items():
                if domain not in allowed_domains:
                    raise MetricProviderConfigurationError(
                        f"Unknown RAPL domain '{domain}'. "
                        f"Valid domains: {', '.join(sorted(allowed_domains))}"
                    )
                if not enabled:
                    self._disabled_domains.append(domain)

        super().__init__(
            metric_name='cpu_energy_rapl_msr_component',
            metrics={'time': int, 'value': int, 'detail_name': str},
            sampling_rate=sampling_rate,
            unit='uJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            metric_provider_executable='metric-provider-binary.exe',
            skip_check=skip_check,
            folder=folder,
            disable_buffer=False,
        )

    def check_system(self, check_command="default", check_error_message=None,
                     check_parallel_provider=False):
        call_string = os.path.join(self._current_dir, self._metric_provider_executable)
        return super().check_system(
            check_command=[call_string, '-c'],
            check_error_message=(
                "Make sure metric-provider-binary.exe exists in the provider folder "
                "and that the ScaphandreDrv driver is installed and running."
            ),
            check_parallel_provider=False,
        )

    def start_profiling(self):
        call_string = os.path.join(self._current_dir, self._metric_provider_executable)
        cmd = [call_string, '-i', str(self._sampling_rate)]
        if self._disabled_domains:
            cmd.extend(['-x', ','.join(self._disabled_domains)])

        print(' '.join(cmd))

        self._stdout_file = open(self._filename, 'w', encoding='utf-8')  # pylint: disable=consider-using-with
        self._ps = subprocess.Popen(
            cmd,
            stdout=self._stdout_file,
            stderr=subprocess.PIPE,
            **host_platform.popen_process_group_kwargs(),
        )
        host_platform.set_nonblocking(self._ps.stderr)
        self._has_started = True

    def stop_profiling(self):
        super().stop_profiling()
        if self._stdout_file is not None:
            self._stdout_file.close()
            self._stdout_file = None

    def _parse_metrics(self, df):
        return df
