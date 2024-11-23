import os
import sys
from io import StringIO
import pandas

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR) # needed to import model which is in subfolder

import model.xgb as mlmodel

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from lib.global_config import GlobalConfig

class PsuEnergyAcXgboostMachineProvider(BaseMetricProvider):
    def __init__(self, *, resolution, HW_CPUFreq, CPUChips, CPUThreads, TDP,
                 HW_MemAmountGB, CPUCores=None, Hardware_Availability_Year=None, VHost_Ratio=1, skip_check=False):
        super().__init__(
            metric_name="psu_energy_ac_xgboost_machine",
            metrics={"time": int, "value": int},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
        )
        self.HW_CPUFreq = HW_CPUFreq
        self.CPUChips = CPUChips
        self.CPUThreads = CPUThreads
        self.TDP = TDP
        self.HW_MemAmountGB = HW_MemAmountGB
        self.CPUCores = CPUCores
        self.Hardware_Availability_Year=Hardware_Availability_Year
        self.VHost_Ratio = VHost_Ratio

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

        with open(filename, 'r', encoding='utf-8') as file:
            csv_data = file.read()
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

        Z = df.loc[:, ['value']]

        Z['HW_CPUFreq'] = self.HW_CPUFreq
        Z['CPUThreads'] = self.CPUThreads
        Z['TDP'] = self.TDP
        Z['HW_MemAmountGB'] = self.HW_MemAmountGB

        # now we process the optional parameters
        if self.CPUCores:
            Z['CPUCores'] = self.CPUCores

        if self.Hardware_Availability_Year:
            Z['Hardware_Availability_Year'] = self.Hardware_Availability_Year

        mlmodel.set_silent()

        Z = Z.rename(columns={'value': 'utilization'})
        Z.utilization = Z.utilization / 100
        model = mlmodel.train_model(self.CPUChips, Z)

        inferred_predictions = mlmodel.infer_predictions(model, Z)
        interpolated_predictions = mlmodel.interpolate_predictions(inferred_predictions)


        df.value = df.value.apply(lambda x: interpolated_predictions[x / 100])  # will result in W
        df.value = df.value*self.VHost_Ratio  # apply vhost_ratio

        df.value = (df.value * df.time.diff()) / 1_000 # W * us / 1_000 will result in mJ

        # we checked at ingest if it contains NA values. So NA can only occur if group diff resulted in only one value.
        # Since one value is useless for us we drop the row
        df.dropna(inplace=True)

        df['unit'] = self._unit

        df.value = df.value.astype(int)

        return df
