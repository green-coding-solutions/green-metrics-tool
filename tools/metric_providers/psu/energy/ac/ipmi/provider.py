# pylint: disable=import-error,wrong-import-position,protected-access

import sys
import os

if __name__ == '__main__':
    sys.path.append(f'{os.path.dirname(os.path.abspath(__file__))}/../../../../..')

from metric_providers.base import BaseMetricProvider


class PsuEnergyAcIpmiProvider(BaseMetricProvider):
    def __init__(self, resolution):
        super().__init__()
        self._current_dir = os.path.dirname(os.path.abspath(__file__))
        self._metric_name = 'psu_energy_ac_ipmi'
        self._metrics = {'time': int, 'value': int}
        self._resolution = 0.001 * resolution
        self._unit = 'W'
        self._metric_provider_executable = 'ipmi-get-system-power-stat.sh'


if __name__ == '__main__':
    import time
    import argparse

    parser = argparse.ArgumentParser()
    args = parser.parse_args()

    o = PsuEnergyAcIpmiProvider(resolution=100)

    print('Starting to profile')
    o.start_profiling()
    time.sleep(2)
    o.stop_profiling()
    print('Done, check ', o._filename)
