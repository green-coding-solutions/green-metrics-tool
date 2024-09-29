from metric_providers.lmsensors.abstract_provider import LmSensorsProvider

class LmSensorsTemperatureComponentProvider(LmSensorsProvider):
    def __init__(self, resolution, **_):
        self._provider_config_path = 'lmsensors.temperature.component.provider.LmSensorsTemperatureComponentProvider'
        super().__init__(
            metric_name='lmsensors_temperature_component',
            resolution=resolution,
            unit='centi°C',
        )

# We don't have a main here as this is just used to set the metric_name so we can use it in the frontend. Please
# run the LmSensorsProvider from abstract_provider to check if the provider works as expected
