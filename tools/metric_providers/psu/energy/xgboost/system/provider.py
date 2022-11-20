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

        with open("/tmp/green-metrics-tool/cpu_utilization_procfs_system.log", 'r') as f:
            csv_data = f.read()
        csv_data = csv_data[:csv_data.rfind('\n')] # remove the last line from the string, as it may be broken due to the output buffering of the metrics reporter
        df = pandas.read_csv(StringIO(csv_data),
            sep=" ",
            names={"time":int, "value":int}.keys(),
            dtype={"time":int, "value":int}
        )

        if self._metrics.get('container_id') is None:
            df['container_name'] = '[SYSTEM]' # standard container name when only system was measured
        else:
            df['container_name'] = df.container_id
            for container_id in containers:
                df.loc[df.container_name == container_id, 'container_name'] = containers[container_id]
            df = df.drop('container_id', axis=1)

        df['metric'] = self._metric_name
        df['project_id'] = project_id

        Z = df.loc[:,['value']]

        provider_config = GlobalConfig().config['measurement']['metric-providers']['psu.energy.xgboost.system.provider.PsuEnergyXgboostSystemProvider']

        Z['HW_CPUFreq'] = provider_config['HW_CPUFreq']
        Z['CPUCores'] = provider_config['CPUCores']
        Z['TDP'] = provider_config['TDP']
        Z['HW_MemAmountGB'] = provider_config['HW_MemAmountGB']

        Z = Z.rename(columns={'value': 'utilization'})
        Z.utilization = Z.utilization / 100
        model = mlmodel.train_model(provider_config['CPUChips'], Z)

        df['value'] = model.predict(Z)
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
