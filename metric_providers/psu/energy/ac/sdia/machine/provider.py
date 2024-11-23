import os
from io import StringIO
import pandas

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from lib.global_config import GlobalConfig

class PsuEnergyAcSdiaMachineProvider(BaseMetricProvider):
    def __init__(self, *, resolution, CPUChips, TDP, skip_check=False):
        super().__init__(
            metric_name='psu_energy_ac_sdia_machine',
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self.cpu_chips = CPUChips
        self.tdp = TDP


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
        provider_config = config['measurement']['metric-providers']['common'][provider_name]

        if not provider_config['CPUChips']:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nPlease set the CPUChips config option for PsuEnergyAcSdiaMachineProvider in the config.yml")
        if not provider_config['TDP']:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nPlease set the TDP config option for PsuEnergyAcSdiaMachineProvider in the config.yml")

        if 'cpu.utilization.procfs.system.provider.CpuUtilizationProcfsSystemProvider' not in config['measurement']['metric-providers']['linux']:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nPlease activate the CpuUtilizationProcfsSystemProvider in the config.yml\n \
                This is required to run PsuEnergyAcSdiaMachineProvider")

    def read_metrics(self, run_id, containers=None):

        filename = None

        if os.path.isfile('/tmp/green-metrics-tool/cpu_utilization_procfs_system.log'):
            filename = '/tmp/green-metrics-tool/cpu_utilization_procfs_system.log'
        elif os.path.isfile('/tmp/green-metrics-tool/cpu_utilization_mach_system.log'):
            filename = '/tmp/green-metrics-tool/cpu_utilization_mach_system.log'
        else:
            raise RuntimeError('could not find the /tmp/green-metrics-tool/cpu_utilization_procfs_system.log or /tmp/green-metrics-tool/cpu_utilization_mach_system.log file. \
                Did you activate the CpuUtilizationProcfsSystemProvider or CpuUtilizationMacSystemProvider in the config.yml too? \
                This is required to run PsuEnergyAcXgboostMachineProvider')

        with open(filename, 'r', encoding='utf-8') as file:            csv_data = file.read()

        # remove the last line from the string, as it may be broken due to the output buffering of the metrics reporter
        csv_data = csv_data[:csv_data.rfind('\n')]
        # pylint: disable=invalid-name
        df = pandas.read_csv(StringIO(csv_data),
                             sep=' ',
                             names={'time': int, 'value': int}.keys(),
                             dtype={'time': int, 'value': int}
                             )

        if df.empty:
            return df

        df['detail_name'] = '[DEFAULT]'  # standard container name when no further granularity was measured
        df['metric'] = self._metric_name
        df['run_id'] = run_id

        #Z = df.loc[:, ['value']]


        if not self.cpu_chips:
            raise MetricProviderConfigurationError(
                'Please set the CPUChips config option for PsuEnergyAcSdiaMachineProvider in the config.yml')
        if not self.tdp:
            raise MetricProviderConfigurationError('Please set the TDP config option for PsuEnergyAcSdiaMachineProvider in the config.yml')

        # since the CPU-Utilization is a ratio, we technically have to divide by 10,000 to get a 0...1 range.
        # And then again at the end multiply with 1000 to get mW. We take the
        # shortcut and just mutiply the 0.65 ratio from the SDIA by 10 -> 6.5
        df.value = ((df.value * self.tdp) / 6.5) * self.cpu_chips # will result in mW
        df.value = (df.value * df.time.diff()) / 1_000_000 # mW * us / 1_000_000 will result in mJ

        # we checked at ingest if it contains NA values. So NA can only occur if group diff resulted in only one value.
        # Since one value is useless for us we drop the row
        df.dropna(inplace=True)

        df['unit'] = self._unit

        df.value = df.value.astype(int)

        return df
