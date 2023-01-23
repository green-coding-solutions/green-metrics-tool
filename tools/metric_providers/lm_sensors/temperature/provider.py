#pylint: disable=import-error

import os

from metric_providers.lm_sensors.abstract_provider import LmSensorsProvider

class LmSensorsTempProvider(LmSensorsProvider):

    def __init__(self, resolution):

        self._provider_config_path = 'lm_sensors.temperature.provider.LmSensorsTempProvider'
        self._current_dir = os.path.dirname(os.path.abspath(__file__)) + '/..'
        self._metric_name = 'lm_sensors_temp'
        self._unit = 'centi°C'
        super().__init__(resolution)


# We don't have a main here as this is just used to set the metric_name so we can use it in the frontend. Please
# run the LmSensorsProvider from abstract_provider to check if the provider works as expected
