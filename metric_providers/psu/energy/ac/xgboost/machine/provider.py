import sys
import os
from io import StringIO
import pandas

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/../../../../../../lib")
sys.path.append(CURRENT_DIR)

#pylint: disable=import-error
import model.xgb as mlmodel
from global_config import GlobalConfig
from metric_providers.base import BaseMetricProvider

class PsuEnergyAcXgboostMachineProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__(
            metric_name="psu_energy_ac_xgboost_machine",
            metrics={"time": int, "value": int},
            resolution=resolution,
            unit="mJ",
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )

    # Since no process is ever started we just return None
    def get_stderr(self):
        return None

    # All work is done by reading system cpu utilization file
    def start_profiling(self, containers=None):
        self._has_started = True
        return  # noop

    def read_metrics(self, project_id, containers):

        if not os.path.isfile('/tmp/green-metrics-tool/cpu_utilization_procfs_system.log'):
            raise RuntimeError('could not find the /tmp/green-metrics-tool/cpu_utilization_procfs_system.log file. \
                Did you activate the CpuUtilizationProcfsSystemProvider in the config.yml too? \
                This is required to run PsuEnergyAcXgboostMachineProvider')

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
        df['project_id'] = project_id

        Z = df.loc[:, ['value']]

        provider_config = GlobalConfig().config['measurement']['metric-providers']['common']\
        ['psu.energy.ac.xgboost.machine.provider.PsuEnergyAcXgboostMachineProvider']

        if 'HW_CPUFreq' not in provider_config:
            raise RuntimeError(
                'Please set the HW_CPUFreq config option for PsuEnergyAcXgboostMachineProvider in the config.yml')
        if 'CPUChips' not in provider_config:
            raise RuntimeError(
                'Please set the CPUChips config option for PsuEnergyAcXgboostMachineProvider in the config.yml')
        if 'CPUThreads' not in provider_config:
            raise RuntimeError(
                'Please set the CPUThreads config option for PsuEnergyAcXgboostMachineProvider in the config.yml')
        if 'TDP' not in provider_config:
            raise RuntimeError('Please set the TDP config option for \
                PsuEnergyAcXgboostMachineProvider in the config.yml')
        if 'HW_MemAmountGB' not in provider_config:
            raise RuntimeError(
                'Please set the HW_MemAmountGB config option for PsuEnergyAcXgboostMachineProvider in the config.yml')

        Z['HW_CPUFreq'] = provider_config['HW_CPUFreq']
        Z['CPUThreads'] = provider_config['CPUThreads']
        Z['TDP'] = provider_config['TDP']
        Z['HW_MemAmountGB'] = provider_config['HW_MemAmountGB']

        # now we process the optional parameters
        if 'CPUCores' in provider_config:
            Z['CPUCores'] = provider_config['CPUCores']

        if 'Hardware_Availability_Year' in provider_config:
            Z['Hardware_Availability_Year'] = provider_config['Hardware_Availability_Year']


        Z = Z.rename(columns={'value': 'utilization'})
        Z.utilization = Z.utilization / 100
        model = mlmodel.train_model(provider_config['CPUChips'], Z)

        inferred_predictions = mlmodel.infer_predictions(model, Z)
        interpolated_predictions = mlmodel.interpolate_predictions(inferred_predictions)


        df.value = df.value.apply(lambda x: interpolated_predictions[x / 100])  # will result in W
        df.value = (df.value * df.time.diff()) / 1_000 # W * us / 1_000 will result in mJ

        df['unit'] = self._unit

        df.value = df.value.fillna(0)
        df.value = df.value.astype(int)

        return df
