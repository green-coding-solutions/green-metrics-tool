import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR) # needed to import model which is in subfolder

import model.xgb as mlmodel

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError
from lib.global_config import GlobalConfig

class PsuEnergyAcXgboostMachineProvider(BaseMetricProvider):
    def __init__(self, *, folder, HW_CPUFreq, CPUChips, CPUThreads, TDP,
                 HW_MemAmountGB, CPUCores=None, Hardware_Availability_Year=None, VHost_Ratio=1, skip_check=False, filename=None):
        super().__init__(
            metric_name="psu_energy_ac_xgboost_machine",
            metrics={"time": int, "value": int},
            sampling_rate=-1,
            unit="uJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )
        self.HW_CPUFreq = HW_CPUFreq
        self.CPUChips = CPUChips
        self.CPUThreads = CPUThreads
        self.TDP = TDP
        self.HW_MemAmountGB = HW_MemAmountGB
        self.CPUCores = CPUCores
        self.Hardware_Availability_Year=Hardware_Availability_Year
        self.VHost_Ratio = VHost_Ratio
         # we overwrite the parent class set default, bc this provider has not source file it writes on its own
         # It must be either supplied in the constructor or will be set None for auto detect later
        self._filename = filename

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
        if 'cpu.utilization.procfs.system.provider.CpuUtilizationProcfsSystemProvider' not in config['measurement']['metric_providers']['linux']:
            raise MetricProviderConfigurationError(f"{self._metric_name} provider could not be started.\nPlease activate the CpuUtilizationProcfsSystemProvider in the config.yml\n \
                This is required to run PsuEnergyAcXgboostMachineProvider")

    def _read_metrics(self):

        if not self._filename:
            if self._folder.joinpath('cpu_utilization_procfs_system.log').exists():
                self._filename = self._folder.joinpath('cpu_utilization_procfs_system.log')
            elif self._folder.joinpath('cpu_utilization_mach_system.log').exists():
                self._filename = self._folder.joinpath('cpu_utilization_mach_system.log')
            else:
                raise RuntimeError(f"could not find the cpu_utilization_procfs_system.log or cpu_utilization_mach_system.log file in {self._folder}. \
                    Did you activate the CpuUtilizationProcfsSystemProvider or CpuUtilizationMacSystemProvider in the config.yml too? \
                    This is required to run PsuEnergyAcXgboostMachineProvider")

        return super()._read_metrics()

    # Cloud-Energy does only use CPU utilization as an input metric and thus cannot actually suffer from an underflow
    def _check_resolution_underflow(self, df):
        pass

    # Provider does not sample on it's own and thus does not have to be checked
    def _add_and_validate_sampling_rate_and_jitter(self, df):
        return df

    def _parse_metrics(self, df):

        df = super()._parse_metrics(df)

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

        df.value = df.value * df.time.diff() # W * us will result in uJ

        # we checked at ingest if it contains NA values. So NA can only occur if group diff resulted in only one value.
        # Since one value is useless for us we drop the row
        df.dropna(inplace=True)

        df.value = df.value.astype('int64')

        if df.empty:
            raise RuntimeError(f"Metrics provider {self._metric_name} metrics log file was empty.")

        return df
