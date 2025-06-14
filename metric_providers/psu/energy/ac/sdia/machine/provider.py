import os

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from lib.global_config import GlobalConfig

class PsuEnergyAcSdiaMachineProvider(BaseMetricProvider):
    def __init__(self, *, sampling_rate, CPUChips, TDP, skip_check=False, filename=None):
        super().__init__(
            metric_name='psu_energy_ac_sdia_machine',
            metrics={'time': int, 'value': int},
            sampling_rate=sampling_rate,
            unit='uJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self.cpu_chips = CPUChips
        self.tdp = TDP
        self._filename = filename

        if not self.cpu_chips:
            raise MetricProviderConfigurationError(
                'Please set the CPUChips config option for PsuEnergyAcSdiaMachineProvider in the config.yml')
        if not self.tdp:
            raise MetricProviderConfigurationError('Please set the TDP config option for PsuEnergyAcSdiaMachineProvider in the config.yml')


    # Since no process is ever started we just return None
    def get_stderr(self):
        return None

    # All work is done by reading system cpu utilization file
    def start_profiling(self, containers=None):
        self._has_started = True


    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        # We want to skip both the normal binary check, as well as the parallel provider check
        # as there is no metric_provider_executable to check
        super().check_system(check_command=None, check_parallel_provider=False)

        config = GlobalConfig().config
        file_path = os.path.dirname(os.path.abspath(__file__))
        provider_name = file_path[file_path.find("metric_providers") + len("metric_providers") + 1:].replace("/", ".") + ".provider." + self.__class__.__name__
        provider_config = config['measurement']['metric_providers']['common'][provider_name]

        if not provider_config['CPUChips']:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nPlease set the CPUChips config option for PsuEnergyAcSdiaMachineProvider in the config.yml")
        if not provider_config['TDP']:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nPlease set the TDP config option for PsuEnergyAcSdiaMachineProvider in the config.yml")

        if 'cpu.utilization.procfs.system.provider.CpuUtilizationProcfsSystemProvider' not in config['measurement']['metric_providers']['linux']:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nPlease activate the CpuUtilizationProcfsSystemProvider in the config.yml\n \
                This is required to run PsuEnergyAcSdiaMachineProvider")

    def _read_metrics(self):

        if not self._filename:
            if os.path.isfile('/tmp/green-metrics-tool/cpu_utilization_procfs_system.log'):
                self._filename = '/tmp/green-metrics-tool/cpu_utilization_procfs_system.log'
            elif os.path.isfile('/tmp/green-metrics-tool/cpu_utilization_mach_system.log'):
                self._filename = '/tmp/green-metrics-tool/cpu_utilization_mach_system.log'
            else:
                raise RuntimeError('could not find the /tmp/green-metrics-tool/cpu_utilization_procfs_system.log or /tmp/green-metrics-tool/cpu_utilization_mach_system.log file. \
                    Did you activate the CpuUtilizationProcfsSystemProvider or CpuUtilizationMacSystemProvider in the config.yml too? \
                    This is required to run PsuEnergyAcSdiaMachineProvider')

        return super()._read_metrics()

    # SDIA Provider does only use CPU utilization as an input metric and thus cannot actually suffer from an underflow
    def _check_resolution_underflow(self, df):
        pass

    def _parse_metrics(self, df):
        df = super()._parse_metrics(df)

        # since the CPU-Utilization is a ratio, we technically have to divide by 10,000 to get a 0...1 range.
        # And then again at the end multiply with 1000 to get mW. We take the
        # shortcut and just mutiply the 0.65 ratio from the SDIA by 10 -> 6.5
        df.value = ((df.value * self.tdp) / 6.5) * self.cpu_chips # will result in mW
        df.value = (df.value * df.time.diff()) / 1_000 # mW * us / 1_000 will result in uJ

        # we checked at ingest if it contains NA values. So NA can only occur if group diff resulted in only one value.
        # Since one value is useless for us we drop the row
        df.dropna(inplace=True)

        df.value = df.value.astype('int64')

        if df.empty:
            raise RuntimeError(f"Metrics provider {self._metric_name} metrics log file was empty.")

        return df
