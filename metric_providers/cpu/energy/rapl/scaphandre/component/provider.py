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
            -> cmd.exe /c rapl_reader.exe -i <rate> [-x <disabled_domains>]
              -> ScaphandreDrv kernel driver (IOCTL)
                -> MSR registers (CPU hardware)
          -> stdout redirected to GMT log file
          -> parsed and stored in PostgreSQL
    """

    def __init__(self, sampling_rate, folder, skip_check=False,
                 rapl_reader_exe=None, domains=None):

        if rapl_reader_exe is None:
            raise MetricProviderConfigurationError(
                "CpuEnergyRaplScaphandreComponentProvider requires 'rapl_reader_exe' "
                "path in config.yml.\n"
                "Example:\n"
                "  cpu.energy.rapl.scaphandre.component.provider"
                ".CpuEnergyRaplScaphandreComponentProvider:\n"
                "    sampling_rate: 99\n"
                "    rapl_reader_exe: 'C:\\\\rapl\\\\rapl_reader.exe'\n"
                "    domains:\n"
                "      cpu_package: true\n"
                "      cpu_cores: true\n"
                "      cpu_gpu: false\n"
                "      dram: false\n"
                "      psys: true"
            )

        self._rapl_reader_exe = rapl_reader_exe

        # Build list of disabled domains from config
        self._disabled_domains = []
        if domains:
            for domain, enabled in domains.items():
                if not enabled:
                    self._disabled_domains.append(domain)

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
        """Pass exe path and optionally disabled domains to the Bash wrapper."""
        call_string = f"{call_string} -e \"{self._rapl_reader_exe}\""
        if self._disabled_domains:
            call_string += f" -x {','.join(self._disabled_domains)}"
        return call_string

    def _parse_metrics(self, df):
        return df
