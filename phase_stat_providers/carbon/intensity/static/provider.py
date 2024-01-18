import os

# from phase_stat_providers.base import BasePhaseStatProvider

class CarbonIntensityStaticProvider(BasePhaseStatProvider):
    def __init__(self, value):
        self._value = value
        self._data = []

    def input(metric, detail_name, phase, value, type, max_value, min_value, unit, created_at)
        self._data.append([
            'metric': metric,
            'detail_name': detail_name,
            'phase': phase,
            'value': value,
            'type': type,
            'max_value': max_value,
            'min_value': min_value,
            'unit': unit,
            'created_at': created_at
        ])

    def output():
        for data in self._data:
            yield (run_id, 'carbon_intensity_static', '[SYSTEM]', f"{idx:03}_{data['phase']['name']}", self._value, 'MEAN', None, None, f"ugCO2e")
