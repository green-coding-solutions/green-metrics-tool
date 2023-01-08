# pylint: disable=import-error,wrong-import-position,protected-access,unused-argument,no-name-in-module

import sys
import os
from io import StringIO
import pandas

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../../../../../lib")
sys.path.append(current_dir)

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../../../..')

from metric_providers.base import BaseMetricProvider
import model.xgb as mlmodel
from global_config import GlobalConfig

class PsuEnergyXgboostSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        self._current_dir = os.path.dirname(os.path.abspath(__file__))
        self._metric_name = 'psu_energy_xgboost_system'
        self._metrics = {'time': int, 'value': int}
        self._resolution = resolution
        self._unit = 'mJ'
        super().__init__()

    # Since no process is ever started we just return None
    def get_stderr(self):
        return None

    # All work is done by reading system cpu utilization file
    def start_profiling(self, containers=None):
        return  # noop

    def read_metrics(self, project_id, containers):

        if not os.path.isfile('/tmp/green-metrics-tool/cpu_utilization_procfs_system.log'):
            raise RuntimeError('could not find the /tmp/green-metrics-tool/cpu_utilization_procfs_system.log file. \
                Did you activate the CpuUtilizationProcfsSystemProvider in the config.yml too? \
                This is required to run PsuEnergyXgboostSystemProvider')

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

        df['detail_name'] = '[SYSTEM]'  # standard container name when only system was measured
        df['metric'] = self._metric_name
        df['project_id'] = project_id

        Z = df.loc[:, ['value']]

        provider_config = GlobalConfig(
        ).config['measurement']['metric-providers']['psu.energy.xgboost.system.provider.PsuEnergyXgboostSystemProvider']

        if 'HW_CPUFreq' not in provider_config:
            raise RuntimeError(
                'Please set the HW_CPUFreq config option for PsuEnergyXgboostSystemProvider in the config.yml')
        if 'CPUChips' not in provider_config:
            raise RuntimeError(
                'Please set the CPUChips config option for PsuEnergyXgboostSystemProvider in the config.yml')
        if 'CPUThreads' not in provider_config:
            raise RuntimeError(
                'Please set the CPUThreads config option for PsuEnergyXgboostSystemProvider in the config.yml')
        if 'TDP' not in provider_config:
            raise RuntimeError('Please set the TDP config option for PsuEnergyXgboostSystemProvider in the config.yml')
        if 'HW_MemAmountGB' not in provider_config:
            raise RuntimeError(
                'Please set the HW_MemAmountGB config option for PsuEnergyXgboostSystemProvider in the config.yml')

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

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    o = PsuEnergyXgboostSystemProvider(resolution=100)

    print('Starting to profile')
    dataframe = o.read_metrics(2321739821, None)
    print(dataframe)

    # Debugging REPL
    import code
    code.interact(local=dict(globals(), **locals()))
