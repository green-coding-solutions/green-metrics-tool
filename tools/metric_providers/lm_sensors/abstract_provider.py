# We need to separate the lm sensor providers into multiple files as the frontend has the conversion and
# unit hardcoded. So it is currently not possible to have one provider return temperature and fan speed.
# Discussion is here https://github.com/green-coding-berlin/green-metrics-tool/issues/39

# pylint: disable=import-error,wrong-import-position,protected-access

import sys
import os

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../../.')
    sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../../../../lib')

from global_config import GlobalConfig

from metric_providers.base import BaseMetricProvider


class LmSensorsProvider(BaseMetricProvider):

    def _create_options(self):
        provider_config = GlobalConfig().config['measurement']['metric-providers'][self._provider_config_path]

        if 'chips' not in provider_config:
            raise RuntimeError(
                f"Please set the 'chips' config option for {self._provider_config_path} in the config.yml")
        if 'features' not in provider_config:
            raise RuntimeError(
                f"Please set the 'features' config option for {self._provider_config_path} in the config.yml")

        return ['-c'] + [f"'{i}'" for i in provider_config['chips']] \
            + ['-f'] + [f"'{i}'" for i in provider_config['features']]

    def __init__(self, resolution):

        if __name__ == '__main__':
            # If you run this on the command line you will need to set this in the config
            # This is separate so it is always clear what config is used.
            self._provider_config_path = 'lm_sensors.abstract_provider.LmSensorsProvider'
            self._current_dir = os.path.dirname(os.path.abspath(__file__))
            self._metric_name = 'lm_sensors'

        self._extra_switches = self._create_options()
        self._resolution = resolution
        self._metrics = {'time': int, 'value': int, 'sensor_name': str}

        super().__init__()


if __name__ == '__main__':
    import time

    o = LmSensorsProvider(resolution=100)

    print(o._current_dir)
    print('Starting to profile')
    o.start_profiling()
    time.sleep(5)
    o.stop_profiling()
    print('Done, check ', o._filename)
