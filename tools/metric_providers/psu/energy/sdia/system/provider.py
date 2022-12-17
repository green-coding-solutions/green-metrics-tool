import sys, os
import subprocess
from io import StringIO
import glob
import pandas
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../../../../lib")
sys.path.append(current_dir)

from global_config import GlobalConfig

if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../../..')

from metric_providers.base import BaseMetricProvider

class PsuEnergySdiaSystemProvider(BaseMetricProvider):
    def __init__(self, resolution):
        self._current_dir = os.path.dirname(os.path.abspath(__file__))
        self._metric_name = "psu_energy_sdia_system"
        self._metrics = {"time":int, "value":int}
        self._resolution = resolution
        self._unit = 'mW'
        super().__init__()

    # Since no process is ever started we just return None
    def get_stderr(self):
        return None

    # All work is done by reading system cpu utilization file
    def start_profiling(self, containers=None):
        return # noop

    def read_metrics(self, project_id, containers):

        if not os.path.isfile("/tmp/green-metrics-tool/cpu_utilization_procfs_system.log"):
            raise RuntimeError("could not find the /tmp/green-metrics-tool/cpu_utilization_procfs_system.log file. did you activate the CpuUtilizationProcfsSystemProvider in the config.yml too? This is required to run PsuEnergySdiaSystemProvider")

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

        provider_config = GlobalConfig().config['measurement']['metric-providers']['psu.energy.sdia.system.provider.PsuEnergySdiaSystemProvider']

        if not 'CPUChips' in provider_config: raise RuntimeError("Please set the CPUChips config option for PsuEnergySdiaSystemProvider in the config.yml")
        if not 'TDP' in provider_config: raise RuntimeError("Please set the TDP config option for PsuEnergySdiaSystemProvider in the config.yml")



        # since the CPU-Utilization is a ratio, we technically have to divide by 10,000 to get a 0...1 range.
        # And then again at the end multiply with 1000 to get mW. We take the shortcut and just mutiply the 0.65 ratio from the SDIA by 10 -> 6.5
        df['value'] = ( (df['value'] * provider_config['TDP']) / 6.5) * provider_config['CPUChips'] # will result in mW
        df.value = df.value.astype(int)

        df['unit'] = self._unit

        return df


if __name__ == "__main__":
    import time
    import argparse

    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    o = PsuEnergySdiaSystemProvider(resolution=100)

    print("Starting to profile")
    o.start_profiling()
    time.sleep(0)
    o.stop_profiling()
    o.read_metrics(21371289321,None)
    print("Done, check ", o._filename)
