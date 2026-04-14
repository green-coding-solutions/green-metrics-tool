import os
import platform
import subprocess
from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError


class CpuEnergyRaplScaphandreComponentProvider(BaseMetricProvider):
    """
    GMT Metric Provider for Windows RAPL energy measurements.

    Communicates with the ScaphandreDrv kernel driver on Windows via
    a compiled C binary (rapl_reader.exe) that reads MSR registers
    directly using IOCTL.

    Overrides start_profiling() to call cmd.exe directly from WSL2,
    eliminating the need for a separate bash wrapper script.

    Data flow:
        GMT runner.py
          -> provider.py start_profiling()
            -> cmd.exe /c rapl_reader.exe -i <rate> [-x <disabled_domains>]
              -> ScaphandreDrv kernel driver (IOCTL)
                -> MSR registers (CPU hardware)
          -> stdout redirected to GMT log file
          -> parsed and stored in PostgreSQL

    config.yml example:
      cpu.energy.rapl.scaphandre.component.provider.CpuEnergyRaplScaphandreComponentProvider:
        sampling_rate: 99
        rapl_reader_exe: 'C:\\rapl\\rapl_reader.exe'
        domains:
          cpu_package: true
          cpu_cores: true
          cpu_gpu: false
          dram: false
          psys: true
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
        allowed_domains = {"cpu_package", "cpu_cores", "cpu_gpu", "dram", "psys"}
        self._disabled_domains = []
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
            skip_check=skip_check,
            folder=folder,
        )

    def check_system(self, check_command=None, check_error_message=None,
                     check_parallel_provider=False):
        """
        Verifies that rapl_reader.exe can access the ScaphandreDrv kernel driver.
        Calls rapl_reader.exe -c directly via cmd.exe from WSL2.
        """
        ps = subprocess.run(
            ['cmd.exe', '/c', f'{self._rapl_reader_exe} -c'],
            capture_output=True, encoding='UTF-8', errors='replace', check=False
        )
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

    def start_profiling(self):
        
        # Build Windows command
        win_cmd = f'{self._rapl_reader_exe} -i {self._sampling_rate}'
        if self._disabled_domains:
            win_cmd += f' -x {",".join(self._disabled_domains)}'

        # Bridge WSL2 -> Windows via cmd.exe
        call_string = f'cmd.exe /c "{win_cmd}" 2>/dev/null'
        call_string += f' > {self._filename}'

        if platform.system() == 'Linux':
            call_string = f'taskset -c 0 {call_string}'
        if self._disable_buffer:
            call_string = f'stdbuf -o0 {call_string}'

        print(call_string)

        #pylint: disable=consider-using-with,subprocess-popen-preexec-fn
        self._ps = subprocess.Popen(
            [call_string],
            shell=True,
            preexec_fn=os.setsid,
            stderr=subprocess.PIPE,
        )
        os.set_blocking(self._ps.stderr.fileno(), False)
        self._has_started = True

    def _parse_metrics(self, df):
        """
        detail_name is always set by rapl_reader.exe stdout output
        (cpu_package, cpu_cores, cpu_gpu, dram, psys) 
        """
        return df
