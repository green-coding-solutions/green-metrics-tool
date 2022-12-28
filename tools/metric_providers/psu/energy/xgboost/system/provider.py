# pylint: disable=import-error,wrong-import-position,protected-access,unused-argument,invalid-name,no-name-in-module

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
        self._unit = 'mW'
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

        with open('/tmp/green-metrics-tool/cpu_utilization_procfs_system.log', 'r', encoding='utf-8') as f:
            csv_data = f.read()
        # remove the last line from the string, as it may be broken due to the output buffering of the metrics reporter
        csv_data = csv_data[:csv_data.rfind('\n')]
        csv = pandas.read_csv(StringIO(csv_data),
                              sep=' ',
                              names={'time': int, 'value': int}.keys(),
                              dtype={'time': int, 'value': int}
                              )

        csv['detail_name'] = '[SYSTEM]'  # standard container name when only system was measured
        csv['metric'] = self._metric_name
        csv['project_id'] = project_id

        Z = csv.loc[:, ['value']]

        provider_config = GlobalConfig(
        ).config['measurement']['metric-providers']['psu.energy.xgboost.system.provider.PsuEnergyXgboostSystemProvider']

        if 'HW_CPUFreq' not in provider_config:
            raise RuntimeError(
                'Please set the HW_CPUFreq config option for PsuEnergyXgboostSystemProvider in the config.yml')
        if 'CPUChips' not in provider_config:
            raise RuntimeError(
                'Please set the CPUChips config option for PsuEnergyXgboostSystemProvider in the config.yml')
        if 'CPUCores' not in provider_config:
            raise RuntimeError(
                'Please set the CPUCores config option for PsuEnergyXgboostSystemProvider in the config.yml')
        if 'TDP' not in provider_config:
            raise RuntimeError('Please set the TDP config option for PsuEnergyXgboostSystemProvider in the config.yml')
        if 'HW_MemAmountGB' not in provider_config:
            raise RuntimeError(
                'Please set the HW_MemAmountGB config option for PsuEnergyXgboostSystemProvider in the config.yml')

        Z['HW_CPUFreq'] = provider_config['HW_CPUFreq']
        Z['CPUCores'] = provider_config['CPUCores']
        Z['TDP'] = provider_config['TDP']
        Z['HW_MemAmountGB'] = provider_config['HW_MemAmountGB']

        Z = Z.rename(columns={'value': 'utilization'})
        Z.utilization = Z.utilization / 100
        model = mlmodel.train_model(provider_config['CPUChips'], Z)

        predictions = mlmodel.infer_predictions(model, Z)
        #predicitons = mlmodel.interpolate_predictions(predictions)

        csv['value'] = csv['value'].apply(lambda x: predictions[x / 100] * 1000)  # will result in mW
        csv['unit'] = self._unit
        csv.value = csv.value.astype(int)

        return csv


if __name__ == '__main__':
    import time
    import argparse

    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    o = PsuEnergyXgboostSystemProvider(resolution=100)

    print('Starting to profile')
    o.start_profiling()
    time.sleep(0)
    o.stop_profiling()
    o.read_metrics(21371289321, None)
    print('Done, check ', o._filename)
