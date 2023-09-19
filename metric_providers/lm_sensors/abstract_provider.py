# We need to separate the lm sensor providers into multiple files as the frontend has the conversion and
# unit hardcoded. So it is currently not possible to have one provider return temperature and fan speed.
# Discussion is here https://github.com/green-coding-berlin/green-metrics-tool/issues/39

import os
from global_config import GlobalConfig
from metric_providers.base import BaseMetricProvider

class LmSensorsProvider(BaseMetricProvider):

    def _create_options(self):
        provider_config = GlobalConfig().config['measurement']['metric-providers']['linux']\
            [self._provider_config_path]

        if 'chips' not in provider_config:
            raise RuntimeError(
                f"Please set the 'chips' config option for {self._provider_config_path} in the config.yml")
        if 'features' not in provider_config:
            raise RuntimeError(
                f"Please set the 'features' config option for {self._provider_config_path} in the config.yml")

        return ['-c'] + [f"'{i}'" for i in provider_config['chips']] \
            + ['-f'] + [f"'{i}'" for i in provider_config['features']]

    def __init__(self, metric_name, resolution, unit):
        if __name__ == '__main__':
            # If you run this on the command line you will need to set this in the config
            # This is separate so it is always clear what config is used.
            self._provider_config_path = 'lm_sensors.abstract_provider.LmSensorsProvider'


        super().__init__(
            metric_name=metric_name,
            metrics={'time': int, 'value': int, 'sensor_name': str},
            resolution=resolution,
            unit=unit,
            current_dir=os.path.dirname(os.path.abspath(__file__)),
        )
        self._extra_switches = self._create_options()
