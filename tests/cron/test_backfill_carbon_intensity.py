from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from cron import backfill_carbon_intensity
from cron.backfill_carbon_intensity import (
    get_carbon_intensity,
    get_elephant_history,
    get_elephant_providers,
    get_yearly_carbon_intensities,
)
from cron.carbondb_copy_over_and_remove_duplicates import validate_table_constraints
from lib.global_config import GlobalConfig, freeze_dict

ELEPHANT_URL = 'http://elephant.test'
PROVIDERS_URL = f"{ELEPHANT_URL}/providers"
HISTORY_URL = f"{ELEPHANT_URL}/carbon-intensity/history"
NOW = datetime.now(timezone.utc)
MAX_WAIT_HOURS = 6
WAITED = NOW - timedelta(hours=MAX_WAIT_HOURS, minutes=5)
MEASURED_AT = datetime(2026, 11, 4, 1, 5, tzinfo=timezone.utc)

YEARLY_DATA = {
    'DE': {'carbonIntensity': {'value': 342}},
    'FR': {'carbonIntensity': {'value': 31}},
    'US': {'carbonIntensity': {'value': 414}},
}

# Format as returned by /providers
PROVIDERS_RESPONSE = [
    ['bundesnetzagentur', 'DE', 'bundesnetzagentur_de'],
    ['energycharts', 'DE', 'energycharts_de'],
    ['entsoe', 'DE', 'entsoe_de'],
    ['entsoe', 'FR', 'entsoe_fr'],
    ['energycharts', 'AT', 'energycharts_at'],
]

def _point(time, carbon_intensity, provider='entsoe_de', estimation=False):
    # Format as returned by /carbon-intensity/history
    return {'time': time, 'carbon_intensity': carbon_intensity, 'provider': provider, 'estimation': estimation}

BEFORE = _point('2026-11-04T01:00:00Z', 192.7)
AFTER = _point('2026-11-04T01:15:00Z', 250.2)
OTHER_BEFORE = _point('2026-11-04T01:00:00Z', 400.0, provider='energycharts_de')
OTHER_AFTER = _point('2026-11-04T01:15:00Z', 500.0, provider='energycharts_de')

def _config(overrides):
    # GlobalConfig().config is frozen, so we swap it for a changed copy instead of changing it
    return patch.object(GlobalConfig(), 'config', freeze_dict({**GlobalConfig().config, **overrides}))

def _config_without(key):
    return patch.object(GlobalConfig(), 'config', freeze_dict({k: v for k, v in GlobalConfig().config.items() if k != key}))

def _response(status_code, payload=None):
    response = MagicMock(status_code=status_code, text=str(payload))
    response.json.return_value = payload
    return response

def _elephant(history):
    def _get(url, **_):
        if url == PROVIDERS_URL:
            return _response(200, PROVIDERS_RESPONSE)
        if url == HISTORY_URL:
            return _response(200, history)
        raise AssertionError(f"Only /providers and /carbon-intensity/history may be used. Got: {url}")
    return _get

def _history_calls(get_mock):
    return [call for call in get_mock.call_args_list if call.args[0] == HISTORY_URL]

@pytest.fixture(autouse=True)
def elephant_config():
    get_elephant_providers.cache_clear()
    get_elephant_history.cache_clear()
    config = {
        'elephant_url': ELEPHANT_URL,
        'elephant_preferred_providers': ['entsoe'],
        'elephant_max_wait_hours': MAX_WAIT_HOURS,
        'elephant_fence_minutes': 60,
        'elephant_fence_bucket_minutes': 15,
    }
    with _config(config), \
         patch.object(backfill_carbon_intensity, 'get_yearly_carbon_intensities', return_value=YEARLY_DATA):
        yield
    get_elephant_providers.cache_clear()
    get_elephant_history.cache_clear()

def test_selects_closest_data_point_to_time_of_row():
    with patch('requests.get', side_effect=_elephant([BEFORE, AFTER])):
        assert get_carbon_intensity('de', MEASURED_AT, NOW) == 193
        assert get_carbon_intensity('DE', MEASURED_AT + timedelta(minutes=5), NOW) == 250

def test_history_request_is_fenced_around_time_of_row_and_not_filtered_by_provider():
    with patch('requests.get', side_effect=_elephant([BEFORE, AFTER])) as get_mock:
        get_carbon_intensity('DE', MEASURED_AT, NOW)

    assert _history_calls(get_mock)[0].kwargs['params'] == {
        'region': 'DE',
        'startTime': '2026-11-04T00:00:00Z',
        'endTime': '2026-11-04T02:00:00Z',
    }

def test_preferred_provider_is_used_when_others_are_in_response():
    with patch('requests.get', side_effect=_elephant([OTHER_BEFORE, OTHER_AFTER, BEFORE, AFTER])):
        assert get_carbon_intensity('DE', MEASURED_AT, NOW) == 193

def test_preferred_provider_is_configurable_and_in_order_of_config():
    history = [BEFORE, AFTER, OTHER_BEFORE, OTHER_AFTER]

    with _config({'elephant_preferred_providers': ['energycharts', 'entsoe']}), \
         patch('requests.get', side_effect=_elephant(history)):
        assert get_carbon_intensity('DE', MEASURED_AT, NOW) == 400

@pytest.mark.parametrize('key', ['elephant_preferred_providers', 'elephant_max_wait_hours', 'elephant_fence_minutes', 'elephant_fence_bucket_minutes'])
def test_settings_have_no_default_in_the_code(key):
    with _config_without(key), patch('requests.get', side_effect=_elephant([BEFORE, AFTER])):
        with pytest.raises(KeyError, match=key):
            get_carbon_intensity('DE', MEASURED_AT, NOW)

def test_max_wait_is_configurable():
    created_at = NOW - timedelta(hours=2)

    with patch('requests.get', side_effect=_elephant([BEFORE])):
        assert get_carbon_intensity('DE', MEASURED_AT, created_at) is None

        with _config({'elephant_max_wait_hours': 1}):
            assert get_carbon_intensity('DE', MEASURED_AT, created_at) == 193

def test_fence_is_configurable():
    with _config({'elephant_fence_minutes': 30}), \
         patch('requests.get', side_effect=_elephant([BEFORE, AFTER])) as get_mock:
        get_carbon_intensity('DE', MEASURED_AT, NOW)

    params = _history_calls(get_mock)[0].kwargs['params']
    assert params['startTime'] == '2026-11-04T00:30:00Z'
    assert params['endTime'] == '2026-11-04T01:30:00Z'

def test_fence_bucket_is_configurable():
    with _config({'elephant_fence_bucket_minutes': 60}), \
         patch('requests.get', side_effect=_elephant([BEFORE, AFTER])) as get_mock:
        get_carbon_intensity('DE', MEASURED_AT, NOW)
        get_carbon_intensity('DE', MEASURED_AT + timedelta(minutes=30), NOW)

    assert len(_history_calls(get_mock)) == 1

@pytest.mark.parametrize('key, value', [
    ('elephant_max_wait_hours', 0),
    ('elephant_max_wait_hours', 24),
    ('elephant_max_wait_hours', '6'),
    ('elephant_max_wait_hours', True),
    ('elephant_fence_minutes', 0),
    ('elephant_fence_minutes', '60'),
    ('elephant_fence_bucket_minutes', 0),
    ('elephant_fence_bucket_minutes', 61),
    ('elephant_fence_bucket_minutes', 15.5),
])
def test_invalid_settings_raise(key, value):
    with _config({key: value}), patch('requests.get', side_effect=_elephant([BEFORE, AFTER])):
        with pytest.raises(ValueError, match=key):
            get_carbon_intensity('DE', MEASURED_AT, NOW)

def test_copy_over_validation_gives_rows_max_wait_from_config_plus_one_hour():
    with patch('cron.carbondb_copy_over_and_remove_duplicates.DB') as db_mock:
        db_mock.return_value.fetch_all.return_value = []

        with _config({'elephant_max_wait_hours': 10}):
            validate_table_constraints(60)

    assert db_mock.return_value.fetch_all.call_args.kwargs['params'] == (False, 60, 11)

def test_region_without_preferred_provider_falls_back_immediately():
    history = [_point('2026-11-04T01:00:00Z', 120.0, provider='energycharts_at'), _point('2026-11-04T01:15:00Z', 130.0, provider='energycharts_at')]

    with patch('requests.get', side_effect=_elephant(history)):
        assert get_carbon_intensity('AT', MEASURED_AT, NOW) == 120

def test_preferred_provider_not_reported_yet_waits_instead_of_falling_back():
    with patch('requests.get', side_effect=_elephant([OTHER_BEFORE, OTHER_AFTER])):
        assert get_carbon_intensity('DE', MEASURED_AT, NOW) is None

def test_preferred_provider_not_reported_after_max_wait_falls_back_to_other_in_response():
    with patch('requests.get', side_effect=_elephant([OTHER_BEFORE, OTHER_AFTER])):
        assert get_carbon_intensity('DE', MEASURED_AT, WAITED) == 400

def test_preferred_provider_with_only_older_data_points_is_still_used_after_max_wait():
    with patch('requests.get', side_effect=_elephant([OTHER_AFTER, BEFORE])):
        assert get_carbon_intensity('DE', MEASURED_AT, WAITED) == 193

def test_rows_in_same_bucket_share_one_request():
    with patch('requests.get', side_effect=_elephant([BEFORE, AFTER])) as get_mock:
        get_carbon_intensity('DE', MEASURED_AT, NOW)
        get_carbon_intensity('DE', MEASURED_AT + timedelta(minutes=5), NOW)
        assert len(_history_calls(get_mock)) == 1

        get_carbon_intensity('DE', MEASURED_AT + timedelta(minutes=10), NOW) # next 15 minute bucket
        assert len(_history_calls(get_mock)) == 2

def test_only_older_data_points_wait_as_closer_one_can_still_arrive():
    with patch('requests.get', side_effect=_elephant([BEFORE])):
        assert get_carbon_intensity('DE', MEASURED_AT, NOW) is None

def test_no_data_point_waits_for_next_run():
    with patch('requests.get', side_effect=_elephant([])):
        assert get_carbon_intensity('DE', MEASURED_AT, NOW) is None

def test_no_data_point_after_max_wait_uses_yearly():
    with patch('requests.get', side_effect=_elephant([])):
        assert get_carbon_intensity('DE', MEASURED_AT, WAITED) == 342
        assert get_carbon_intensity('FR', MEASURED_AT, WAITED) == 31

def test_estimated_data_points_are_skipped():
    with patch('requests.get', side_effect=_elephant([BEFORE, _point('2026-11-04T01:05:00Z', 500.0, estimation=True)])):
        assert get_carbon_intensity('DE', MEASURED_AT, NOW) is None # the estimate must also not count as data point after the row

def test_value_rounding_to_zero_still_satisfies_check_constraint():
    with patch('requests.get', side_effect=_elephant([_point('2026-11-04T01:05:00Z', 0.2)])):
        assert get_carbon_intensity('DE', MEASURED_AT, NOW) == 1

def test_country_without_provider_uses_yearly_without_history_request():
    with patch('requests.get', side_effect=_elephant([])) as get_mock:
        assert get_carbon_intensity('us', MEASURED_AT, NOW) == 414

    assert not _history_calls(get_mock)

@pytest.mark.parametrize('country_code', ['ZZ', None])
def test_unknown_country_returns_none(country_code):
    with patch('requests.get', side_effect=_elephant([])) as get_mock:
        assert get_carbon_intensity(country_code, MEASURED_AT, NOW) is None

    assert not _history_calls(get_mock)

def test_testing_sentinel_needs_no_request_or_country():
    with _config({'elephant_url': 'testing'}), patch('requests.get') as get_mock:
        assert get_carbon_intensity(None, MEASURED_AT, NOW) == 1000

    get_mock.assert_not_called()

@pytest.mark.parametrize('url', [PROVIDERS_URL, HISTORY_URL])
def test_elephant_server_error_raises(url):
    def _get(request_url, **_):
        return _response(500, 'Internal Server Error') if request_url == url else _elephant([])(request_url)

    with patch('requests.get', side_effect=_get):
        with pytest.raises(RuntimeError, match='Status: 500'):
            get_carbon_intensity('DE', MEASURED_AT, NOW)

def test_missing_elephant_url_raises():
    with _config({'elephant_url': None}):
        with pytest.raises(ValueError, match='elephant_url'):
            get_carbon_intensity('DE', MEASURED_AT, NOW)

def test_process_does_not_raise_and_only_writes_rows_with_data():
    rows = [
        (1, 'DE', MEASURED_AT, NOW),
        (2, 'US', MEASURED_AT, NOW),
        (3, None, MEASURED_AT, NOW),
        (4, 'DE', MEASURED_AT + timedelta(minutes=20), NOW), # data point after the row still outstanding
    ]

    with patch.object(backfill_carbon_intensity, 'DB') as db_mock, \
         patch.object(backfill_carbon_intensity, 'fetch_carbon_intensity_missing', return_value=rows), \
         patch('requests.get', side_effect=_elephant([BEFORE, AFTER])):
        backfill_carbon_intensity.process('ci_measurements')

    updates = [call.kwargs['params'] for call in db_mock.return_value.query.call_args_list]
    assert updates == [(193, 1), (414, 2)]

def test_bundled_yearly_file_can_be_parsed():
    # Uses the real function imported above. The autouse fixture only patches the reference inside the cron module
    get_yearly_carbon_intensities.cache_clear()
    data = get_yearly_carbon_intensities()

    assert data['DE']['carbonIntensity']['value'] > 0
    assert data['US']['carbonIntensity']['value'] > 0
