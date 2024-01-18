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
            # TODO: Query the API and get an average value
            from entsoe import EntsoeRawClient
            # import pandas as pd

            # client = EntsoeRawClient(api_key=<YOUR API KEY>)

            # start = pd.Timestamp('20171201', tz='Europe/Brussels')
            # end = pd.Timestamp('20180101', tz='Europe/Brussels')
            # country_code = 'DE'  # Belgium
            # country_code_from = 'FR'  # France
            # country_code_to = 'DE_LU' # Germany-Luxembourg
            # type_marketagreement_type = 'A01'
            # contract_marketagreement_type = 'A01'
            # process_type = 'A51'

            # # methods that return XML
            #
            intensity = get_intensity(start=data['phase']['start'], end=data['phase']['end'])
            intensity = transformToMicrogram(intensity)
            yield (run_id, 'carbon_intensity_entsoe', '[SYSTEM]', f"{idx:03}_{data['phase']['name']}", intensity, 'MEAN', None, None, f"ugCO2e")
