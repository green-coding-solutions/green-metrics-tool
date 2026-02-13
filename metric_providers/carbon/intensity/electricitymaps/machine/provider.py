import os
from datetime import datetime, timedelta, timezone

import pandas
import requests

from metric_providers.base import BaseMetricProvider, MetricProviderConfigurationError

error_string = ""

API_PAST_URL = "https://api.electricitymaps.com/v3/carbon-intensity/past-range"
API_FUTURE_URL = "https://api.electricitymaps.com/v3/carbon-intensity/forecast"

TEMPORAL_GRANULARITY = "5_minutes"

class CarbonIntensityElectricityMapsMachineProvider(BaseMetricProvider):
    def __init__(self, region, token, folder, skip_check=False):

        self.region = region
        self.token = token
        self._folder = folder
        self.__start_time = None
        self.__end_time = None

        if not self.region:
            raise MetricProviderConfigurationError(
                'Please set the region config option for CarbonIntensityElectricityMapsMachineProvider (electricity_maps) in the config.yml')

        if not self.token:
            raise MetricProviderConfigurationError(
                'Please set the token config option for CarbonIntensityElectricityMapsMachineProvider (electricity_maps) in the config.yml')

        super().__init__(
            metric_name='carbon_intensity_electricity_maps_machine',
            metrics={'time': int, 'value': int, 'provider': str},
            sampling_rate=-1,
            unit='gCO2e/kWh',
            current_dir=os.path.dirname(os.path.abspath(__file__)),
            skip_check=skip_check,
            folder=folder,
        )


    def check_system(self, check_command="default", check_error_message=None, check_parallel_provider=True):
        super().check_system(check_command=None, check_parallel_provider=False)

        response = None
        try:
            params = {
                'zone': self.region,
                'start': self._format_time(datetime.now(timezone.utc) - timedelta(hours=1)),
                'end': self._format_time(datetime.now(timezone.utc)),
                'temporalGranularity': TEMPORAL_GRANULARITY,
            }
            with requests.get(API_PAST_URL, params=params, headers={'auth-token': self.token}, timeout=10) as response:
                if response.status_code in (401, 403):
                    raise MetricProviderConfigurationError(
                        'Electricity Maps token was rejected. Please verify electricity_maps_token in the config.yml'
                    )

        except requests.RequestException as exc:
            raise MetricProviderConfigurationError(f"Electricity Maps base URL {API_PAST_URL} could not be reached: {exc}") from exc

    def get_stderr(self):
        return error_string

    def start_profiling(self, _=None):
        self.__start_time = datetime.now(timezone.utc)
        self._has_started = True

    def stop_profiling(self):
        self.__end_time = datetime.now(timezone.utc)
        self._has_started = False

    def _format_time(self, timestamp):
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.strftime('%Y-%m-%dT%H:%M:%SZ')

    def _parse_time(self, time_value):
        try:
            if time_value.endswith('Z'):
                parsed = datetime.fromisoformat(time_value.replace('Z', '+00:00'))
            else:
                parsed = datetime.fromisoformat(time_value)
        except ValueError as exc:
            raise RuntimeError(f"Invalid time in Electricity Maps response: {time_value}") from exc

        return int(parsed.timestamp() * 1_000_000)

    def _read_metrics(self):
        global error_string #pylint: disable=global-statement

        headers = {'auth-token': self.token}

        if self.__start_time is None or self.__end_time is None:
            raise RuntimeError(
                f"{self._metric_name} provider did not record start/end times. Did start_profiling and stop_profiling run?")

        params = {
                'zone': self.region,
                'start': self._format_time(self.__start_time),
                'end': self._format_time(self.__end_time),
                'temporalGranularity': TEMPORAL_GRANULARITY,
            }

        response = None
        try:
            response = requests.get(API_PAST_URL, params=params, headers=headers, timeout=30)
        except requests.RequestException as exc:
            error_string += f"Failed to query Electricity Maps carbon intensity service: {exc}\n"
            return None
        finally:
            if response is not None:
                response.close()

        if response.status_code != 200:
            error_string += f"Electricity Maps carbon intensity request failed with status {response.status_code}: {response.text}\n"
            return None

        data = response.json().get('data')

        if len(data) == 0:
            # As the providers take quite some time to provide data it can happen that short running
            # jobs don't have any data. So we get predictions
            params = {
                'zone': self.region,
                'temporalGranularity': TEMPORAL_GRANULARITY,
            }
            try:
                fallback_response = requests.get(
                    API_FUTURE_URL,
                    params=params,
                    headers=headers,
                    timeout=30,
                )

                if fallback_response.status_code != 200:
                    error_string += f"Electricity Maps carbon intensity fallback request failed with status {fallback_response.status_code}: {fallback_response.text}\n"
                    return None

                fallback_data = fallback_response.json()
            except requests.RequestException as exc:
                error_string += f"Failed to query Electricity Maps carbon intensity service for fallback: {exc}\n"
                return None
            finally:
                fallback_response.close()


            data = fallback_data.get('data')

            if not isinstance(data, list):
                raise RuntimeError(f"Unexpected Electricity Maps response for carbon intensity: {data}")

        records = []
        start_us = int(self.__start_time.timestamp() * 1_000_000)
        end_us = int(self.__end_time.timestamp() * 1_000_000)
        closest_entry = None
        closest_distance = None

        for entry in data:
            time_value = entry.get('datetime')
            value = entry.get('carbonIntensity')
            provider = "electricity_maps"

            if time_value is None or value is None:
                continue

            parsed_time = self._parse_time(time_value)
            if parsed_time < start_us:
                distance = start_us - parsed_time
            elif parsed_time > end_us:
                distance = parsed_time - end_us
            else:
                distance = 0

            if closest_distance is None or distance < closest_distance:
                closest_distance = distance
                closest_entry = (parsed_time, value, provider)

            if parsed_time < start_us or parsed_time > end_us:
                continue

            records.append({
                'time': parsed_time,
                'value': float(value),
                'detail_name': provider,
            })

        if not records and closest_entry is not None:
            parsed_time, value, provider = closest_entry
            records.append({
                'time': parsed_time,
                'value': float(value),
                'detail_name': provider,
            })

        df = pandas.DataFrame.from_records(records)

        if df.empty:
            return df

        df = df.sort_values(by=['time'], ascending=True)
        df['value'] = df['value'].round().astype('int64') # We don't save floats in GMT

        return df

    def _parse_metrics(self, df):
        return df

    def _add_and_validate_sampling_rate_and_jitter(self, df):
        return df
