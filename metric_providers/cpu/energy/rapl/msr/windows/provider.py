import os
import subprocess
from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError


class CpuEnergyRaplMsrWindowsProvider(BaseMetricProvider):

    def __init__(self, sampling_rate, folder, skip_check=False, rapl_reader_exe=None):

        if rapl_reader_exe is None:
            raise MetricProviderConfigurationError(
                "cpu_energy_rapl_msr_windows provider requires 'rapl_reader_exe' path in config.yml.\n"
                "Example:\n"
                "  cpu.energy.rapl.msr.windows.provider.CpuEnergyRaplMsrWindowsProvider:\n"
                "    sampling_rate: 100\n"
                "    rapl_reader_exe: 'C:\\\\path\\\\to\\\\rapl_reader.exe'"
            )

        self._rapl_reader_exe = rapl_reader_exe

        super().__init__(
            metric_name='cpu_energy_rapl_msr_component',
            metrics={'time': int, 'value': int, 'detail_name': str},
            sampling_rate=sampling_rate,
            unit='uJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )

    def check_system(self, check_command=None, check_error_message=None, check_parallel_provider=False):
        # Check that rapl_reader.exe exists and driver is accessible
        binary = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'metric-provider-binary')
        check_command = [binary, '-c', '-e', self._rapl_reader_exe]

        ps = subprocess.run(check_command, capture_output=True, encoding='UTF-8', errors='replace', check=False)
        if ps.returncode != 0:
            raise MetricProviderConfigurationError(
                f"cpu_energy_rapl_msr_windows provider could not be started.\n"
                f"Error: Cannot access ScaphandreDrv driver via {self._rapl_reader_exe}\n"
                f"Make sure the driver is installed and running:\n"
                f"  .\\DriverLoader.exe install\n"
                f"  sc.exe start ScaphandreDrv"
            )
        return True

    def _add_extra_switches(self, call_string):
        # Pass exe path to the shell script via -e flag
        return f"{call_string} -e \"{self._rapl_reader_exe}\""

    def _parse_metrics(self, df):
        df['detail_name'] = df['detail_name'].fillna('cpu_package')
        return df
