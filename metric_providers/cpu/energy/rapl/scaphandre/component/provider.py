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

    Path resolution order for rapl_reader.exe:
      1. 'rapl_reader_exe' key in config.yml  (explicit, always wins)
      2. Windows environment variable RAPL_READER_EXE             (set once, forget)
      3. Error with clear instructions for both options

    Setting the Windows env var (PowerShell, once):
      [System.Environment]::SetEnvironmentVariable(
          'RAPL_READER_EXE', 'C:\\rapl\\rapl_reader.exe', 'Machine')
    Then restart WSL2:
      wsl --shutdown

    Data flow:
        GMT runner.py
          -> provider.py start_profiling()
            -> cmd.exe /c rapl_reader.exe -i <rate> [-x <disabled_domains>]
              -> ScaphandreDrv kernel driver (IOCTL)
                -> MSR registers (CPU hardware)
          -> stdout redirected to GMT log file
          -> parsed and stored in PostgreSQL

    config.yml example (explicit path):
      cpu.energy.rapl.scaphandre.component.provider.CpuEnergyRaplScaphandreComponentProvider:
        sampling_rate: 99
        rapl_reader_exe: 'C:\\rapl\\rapl_reader.exe'
        domains:
          cpu_package: true
          cpu_cores: true
          cpu_gpu: false
          dram: false
          psys: true

    config.yml example (rely on env var, no rapl_reader_exe key needed):
      cpu.energy.rapl.scaphandre.component.provider.CpuEnergyRaplScaphandreComponentProvider:
        sampling_rate: 99
        domains:
          cpu_package: true
          cpu_cores: true
          cpu_gpu: false
          dram: false
          psys: true
    """

    # Windows environment variable name. Set this on the Windows side once:
    #   [System.Environment]::SetEnvironmentVariable('RAPL_READER_EXE',
    #       'C:\\rapl\\rapl_reader.exe', 'Machine')
    # then: wsl --shutdown  (so WSL2 picks up the new env)
    ENV_VAR_NAME = 'RAPL_READER_EXE'

    def __init__(self, sampling_rate, folder, skip_check=False,
                 rapl_reader_exe=None, domains=None):

        # --- Path resolution ---
        resolved_path = rapl_reader_exe  # 1. explicit config.yml value

        if not resolved_path:
            # 2. Try Windows environment variable via cmd.exe
            #    cmd.exe /c echo %RAPL_READER_EXE%  returns the value or
            #    the literal string "%RAPL_READER_EXE%" if unset.
            resolved_path = self._resolve_path_from_windows_env()

        if not resolved_path:
            raise MetricProviderConfigurationError(
                "CpuEnergyRaplScaphandreComponentProvider: rapl_reader.exe path not found.\n"
                "\n"
                "Option A – set it in config.yml:\n"
                "  rapl_reader_exe: 'C:\\\\rapl\\\\rapl_reader.exe'\n"
                "\n"
                "Option B – set Windows environment variable once (PowerShell as Admin):\n"
                f"  [System.Environment]::SetEnvironmentVariable(\n"
                f"      '{self.ENV_VAR_NAME}',\n"
                f"      'C:\\\\rapl\\\\rapl_reader.exe',\n"
                f"      'Machine')\n"
                f"  Then restart WSL2:  wsl --shutdown\n"
            )

        self._rapl_reader_exe = resolved_path

        # --- Domain validation ---
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
	    disable_buffer=False,  # rapl_reader.exe handles buffering internally via setvbuf()
        )

    @classmethod
    def _resolve_path_from_windows_env(cls):
        """
        Read RAPL_READER_EXE from the Windows environment via cmd.exe.

        Why cmd.exe and not os.environ?
        WSL2 does NOT inherit Windows system environment variables into
        the Linux environment. The only reliable way to read them is to
        ask cmd.exe directly.

        Returns the path string if found and non-empty, None otherwise.
        """
        try:
            result = subprocess.run(
                ['cmd.exe', '/c', f'echo %{cls.ENV_VAR_NAME}%'],
                capture_output=True,
                encoding='UTF-8',
                errors='replace',
                timeout=5,
                check=False,
            )
            value = result.stdout.strip()

            # cmd.exe echoes the literal "%VAR%" if the variable is not set
            if value and not value.startswith('%'):
                return value
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # cmd.exe not available (native Linux, not WSL2) – silently skip
            pass

        return None

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
        call_string = f'cmd.exe /c "{win_cmd}"'
        call_string += f' > {self._filename} 2>/dev/null'

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
