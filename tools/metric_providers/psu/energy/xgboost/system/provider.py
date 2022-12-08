import sys, os
import subprocess
from io import StringIO
import glob
import pandas
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../../../../../lib")
sys.path.append(current_dir)

from global_config import GlobalConfig

import model.xgb as mlmodel

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../../../..')

from metric_providers.base import BaseMetricProvider

class PsuEnergyXgboostSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        self._current_dir = os.path.dirname(os.path.abspath(__file__))
        self._metric_name = "psu_energy_xgboost_system"
        self._metrics = {"time":int, "value":int}
        self._resolution = resolution
        super().__init__()

    # Since no process is ever started we just return None
    def get_stderr(self):
        return None

    # All work is done by reading system cpu utilization file
    def start_profiling(self, containers=None):
        return # noop

    def read_metrics(self, project_id, containers):

        if not os.path.isfile("/tmp/green-metrics-tool/cpu_utilization_procfs_system.log"):
            raise RuntimeError("could not find the /tmp/green-metrics-tool/cpu_utilization_procfs_system.log file. did you activate the CpuUtilizationProcfsSystemProvider in the config.yml too? This is required to run PsuEnergyXgboostSystemProvider")

        with open("/tmp/green-metrics-tool/cpu_utilization_procfs_system.log", 'r') as f:
            csv_data = f.read()
        csv_data = csv_data[:csv_data.rfind('\n')] # remove the last line from the string, as it may be broken due to the output buffering of the metrics reporter
        df = pandas.read_csv(StringIO(csv_data),
            sep=" ",
            names={"time":int, "value":int}.keys(),
            dtype={"time":int, "value":int}
        )

        df['detail_name'] = '[SYSTEM]' # standard container name when only system was measured
        df['metric'] = self._metric_name
        df['project_id'] = project_id

        Z = df.loc[:,['value']]

        provider_config = GlobalConfig().config['measurement']['metric-providers']['psu.energy.xgboost.system.provider.PsuEnergyXgboostSystemProvider']

        if not 'HW_CPUFreq' in provider_config: raise RuntimeError("Please set the HW_CPUFreq config option for PsuEnergyXgboostSystemProvider in the config.yml")
        if not 'CPUChips' in provider_config: raise RuntimeError("Please set the CPUChips config option for PsuEnergyXgboostSystemProvider in the config.yml")
        if not 'CPUCores' in provider_config: raise RuntimeError("Please set the CPUCores config option for PsuEnergyXgboostSystemProvider in the config.yml")
        if not 'TDP' in provider_config: raise RuntimeError("Please set the TDP config option for PsuEnergyXgboostSystemProvider in the config.yml")
        if not 'HW_MemAmountGB' in provider_config: raise RuntimeError("Please set the HW_MemAmountGB config option for PsuEnergyXgboostSystemProvider in the config.yml")

        Z['HW_CPUFreq'] = provider_config['HW_CPUFreq']
        Z['CPUCores'] = provider_config['CPUCores']
        Z['TDP'] = provider_config['TDP']
        Z['HW_MemAmountGB'] = provider_config['HW_MemAmountGB']

        Z = Z.rename(columns={'value': 'utilization'})
        Z.utilization = Z.utilization / 100
        model = mlmodel.train_model(provider_config['CPUChips'], Z)

        predictions = mlmodel.infer_predictions(model, Z)
        predicitons = mlmodel.interpolate_predictions(predictions)

        df['value'] = df['value'].apply(lambda x: predictions[x/100]*1000) # will result in mW
        df.value = df.value.astype(int)

        return df


if __name__ == "__main__":
    import time
    import argparse

    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    o = PsuEnergyXgboostSystemProvider(resolution=100)

    print("Starting to profile")
    o.start_profiling()
    time.sleep(0)
    o.stop_profiling()
    o.read_metrics(21371289321,None)
    print("Done, check ", o._filename)
