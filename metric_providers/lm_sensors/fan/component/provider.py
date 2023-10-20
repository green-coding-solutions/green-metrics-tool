from metric_providers.lm_sensors.abstract_provider import LmSensorsProvider

class LmSensorsFanComponentProvider(LmSensorsProvider):
    def __init__(self, resolution, **_):
        self._provider_config_path = 'lm_sensors.fan.component.provider.LmSensorsFanComponentProvider'
        super().__init__(
            metric_name='lm_sensors_fan_component',
            resolution=resolution,
            unit='RPM',
        )

# We don't have a main here as this is just used to set the metric_name so we can use it in the frontend. Please
# run the LmSensorsProvider from abstract_provider to check if the provider works as expected
