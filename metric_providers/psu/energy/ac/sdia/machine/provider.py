import os
from io import StringIO
import pandas

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from lib.global_config import GlobalConfig

class PsuEnergyAcSdiaMachineProvider(BaseMetricProvider):
    def __init__(self, *, resolution, CPUChips, TDP):
        super().__init__(
            metric_name='psu_energy_ac_sdia_machine',
            metrics={'time': int, 'value': int},
            resolution=resolution,
            unit='mJ',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )
        self.cpu_chips = CPUChips
        self.tdp = TDP


    # Since no process is ever started we just return None
    def get_stderr(self):
        return None

    # All work is done by reading system cpu utilization file
    def start_profiling(self, containers=None):
        self._has_started = True


    #TODO: not a fan of using the full key name here. any way to avoid this?
    # keeping original checks in read_metrics for now
    def check_system(self):
        config = GlobalConfig().config
        provider_config = config['measurement']['metric-providers']['common']['psu.energy.ac.sdia.machine.provider.PsuEnergyAcSdiaMachineProvider']

        if not provider_config['CPUChips']:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nPlease set the CPUChips config option for PsuEnergyAcSdiaMachineProvider in the config.yml")
        if not provider_config['TDP']:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nPlease set the TDP config option for PsuEnergyAcSdiaMachineProvider in the config.yml")

        if 'cpu.utilization.procfs.system.provider.CpuUtilizationProcfsSystemProvider' not in config['measurement']['metric-providers']['linux']:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nPlease activate the CpuUtilizationProcfsSystemProvider in the config.yml\n \
                This is required to run PsuEnergyAcSdiaMachineProvider")

    def read_metrics(self, run_id, containers=None):

        if not os.path.isfile('/tmp/green-metrics-tool/cpu_utilization_procfs_system.log'):
            raise RuntimeError('could not find the /tmp/green-metrics-tool/cpu_utilization_procfs_system.log file.\
                Did you activate the CpuUtilizationProcfsSystemProvider in the config.yml too? \
                This is required to run PsuEnergyAcSdiaMachineProvider')

        with open('/tmp/green-metrics-tool/cpu_utilization_procfs_system.log', 'r', encoding='utf-8') as file:
            csv_data = file.read()

        # remove the last line from the string, as it may be broken due to the output buffering of the metrics reporter
        csv_data = csv_data[:csv_data.rfind('\n')]
        # pylint: disable=invalid-name
        df = pandas.read_csv(StringIO(csv_data),
                             sep=' ',
                             names={'time': int, 'value': int}.keys(),
                             dtype={'time': int, 'value': int}
                             )

        df['detail_name'] = '[DEFAULT]'  # standard container name when no further granularity was measured
        df['metric'] = self._metric_name
        df['run_id'] = run_id

        #Z = df.loc[:, ['value']]


        if not self.cpu_chips:
            raise RuntimeError(
                'Please set the CPUChips config option for PsuEnergyAcSdiaMachineProvider in the config.yml')
        if not self.tdp:
            raise RuntimeError('Please set the TDP config option for PsuEnergyAcSdiaMachineProvider in the config.yml')

        # since the CPU-Utilization is a ratio, we technically have to divide by 10,000 to get a 0...1 range.
        # And then again at the end multiply with 1000 to get mW. We take the
        # shortcut and just mutiply the 0.65 ratio from the SDIA by 10 -> 6.5
        df.value = ((df.value * self.tdp) / 6.5) * self.cpu_chips # will result in mW
        df.value = (df.value * df.time.diff()) / 1_000_000 # mW * us / 1_000_000 will result in mJ

        df['unit'] = self._unit

        df.value = df.value.fillna(0)
        df.value = df.value.astype(int)

        return df
