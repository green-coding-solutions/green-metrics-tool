import os
import subprocess
from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError


class CpuEnergyRaplScaphandreComponentProvider(BaseMetricProvider):
    """
    GMT Metric Provider for Windows RAPL energy measurements.

    Communicates with the ScaphandreDrv kernel driver on Windows via
    a compiled C binary (rapl_reader.exe) that reads MSR registers
    directly using IOCTL.

    The metric-provider-binary is a Bash wrapper script that calls
    rapl_reader.exe via cmd.exe, bridging WSL2 (where GMT runs) and
    Windows (where the kernel driver lives).

    Data flow:
        GMT runner.py
          -> metric-provider-binary (Bash, WSL2)
            -> cmd.exe /c rapl_reader.exe -i <rate> (Windows)
              -> ScaphandreDrv kernel driver (IOCTL)
                -> MSR registers (CPU hardware)
          -> stdout redirected to GMT log file
          -> parsed and stored in PostgreSQL
    """

    def __init__(self, sampling_rate, folder, skip_check=False, rapl_reader_exe=None):

        if rapl_reader_exe is None:
            raise MetricProviderConfigurationError(
                "CpuEnergyRaplScaphandreComponentProvider requires 'rapl_reader_exe' "
                "path in config.yml.\n"
                "Example:\n"
                "  cpu.energy.rapl.scaphandre.component.provider"
                ".CpuEnergyRaplScaphandreComponentProvider:\n"
                "    sampling_rate: 99\n"
                "    rapl_reader_exe: 'C:\\\\rapl\\\\rapl_reader.exe'"
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

    def check_system(self, check_command=None, check_error_message=None,
                     check_parallel_provider=False):
        """
        Verifies that:
        1. The metric-provider-binary Bash wrapper script is present
        2. rapl_reader.exe can access the ScaphandreDrv kernel driver

        The metric-provider-binary is a Bash script located in the same
        directory as this provider. It bridges WSL2 and Windows by calling
        rapl_reader.exe via cmd.exe.
        """
        binary = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'metric-provider-binary')

        check_command = [binary, '-c', '-e', self._rapl_reader_exe]

        ps = subprocess.run(check_command, capture_output=True,
                            encoding='UTF-8', errors='replace', check=False)

        if ps.returncode != 0:
            raise MetricProviderConfigurationError(
                f"CpuEnergyRaplScaphandreComponentProvider could not be started.\n"
                f"Cannot access ScaphandreDrv driver via {self._rapl_reader_exe}\n"
                f"Make sure the driver is installed and running on Windows:\n"
                f"  .\\DriverLoader.exe install\n"
                f"  sc.exe start ScaphandreDrv\n"
                f"And that rapl_reader.exe is at: {self._rapl_reader_exe}"
            )
        return True

    def _add_extra_switches(self, call_string):
        """Pass the Windows exe path to the Bash wrapper via -e flag."""
        return f"{call_string} -e \"{self._rapl_reader_exe}\""

    def _parse_metrics(self, df):
        """
        detail_name is always set by rapl_reader.exe stdout output
        (cpu_package, cpu_cores, cpu_gpu, dram) - no transformation needed.
        """
        return df
