import math
from collections import OrderedDict

import pytest

from api import api_helpers

def test_convert_value():
    [value, unit] = api_helpers.convert_value(100, 'uJ')

    assert unit == 'mWh'
    assert math.isclose(value, 0.00002777, rel_tol=1e-3)

    [value, unit] = api_helpers.convert_value(10000, 'uJ')

    assert unit == 'mWh'
    assert math.isclose(value, 0.002777, rel_tol=1e-3)

    [value, unit] = api_helpers.convert_value(10000, 'mJ')

    assert unit == 'mWh'
    assert math.isclose(value, 2.777, rel_tol=1e-3)

    assert api_helpers.convert_value(324_000_000_000, 'uJ') == [90000, 'mWh']

    assert api_helpers.convert_value(100, 'uJ', True) == [0.0001, 'J']

    assert api_helpers.convert_value(10000, 'uJ', True) == [0.01, 'J']

    assert api_helpers.convert_value(324_000_000_000, 'uJ', True) == [324000, 'J']

    assert api_helpers.convert_value(10000, 'mJ', True) == [10, 'J']


    assert api_helpers.convert_value(324_000_000_000, 'ugCO2e/Page Request') == [324000, 'gCO2e/Page Request']

    assert api_helpers.convert_value(222_000_000_000_000, 'ugCO2e/Kill') == [222000000, 'gCO2e/Kill']

    assert api_helpers.convert_value(0.0003, 'ugCO2e/Kill') == [0.0000000003, 'gCO2e/Kill']


    assert api_helpers.convert_value(100, 'xJ') == [100, 'xJ']

    assert api_helpers.convert_value(100, 'uj') == [100, 'uj']

def _repeated_run_key_stats(values):
    run_ids = [f"run-{i}" for i in range(len(values))]
    comparison_details = OrderedDict({'abc': OrderedDict((run_id, {'run_id': run_id, 'index': i}) for i, run_id in enumerate(run_ids))})
    phase_stats = [
        ['005_[RUNTIME]', 'cpu_energy_rapl_msr_component', 'Package_0', value, 'TOTAL', value, value, 100, 100, 100, 'uJ', False,
         'https://example.com/repo', 1, 'usage_scenario.yml', 'abc', 'main', run_id, {}]
        for run_id, value in zip(run_ids, values) if value is not None
    ]
    phase_stats_object = api_helpers.get_phase_stats_object(phase_stats, 'Repeated Run on same Commit Hash', comparison_details)
    phase_stats_object = api_helpers.add_phase_stats_statistics(phase_stats_object)

    return phase_stats_object['data']['[RUNTIME]']['data']['cpu_energy_rapl_msr_component']['data']['Package_0']['data']['abc']

def test_newest_run_within_normal_spread_is_not_significant():
    # newest run is ~1.2 stddev above the previous runs: well within normal spread
    # scipy.stats.ttest_1samp(previous, newest) wrongly reported p=0.0063 here
    key_stats = _repeated_run_key_stats([1000, 1010, 990, 1000, 1020, 980, 1000, 1010, 990, 1015])

    assert math.isclose(key_stats['p_value'], 0.27877, rel_tol=1e-4)
    assert key_stats['is_significant'] is False

@pytest.mark.parametrize('newest', [1100, 900]) # two-sided: regressions and improvements
def test_newest_run_outlier_is_significant(newest):
    key_stats = _repeated_run_key_stats([1000, 1010, 990, 1000, 1020, 980, 1000, 1010, 990, newest])

    assert math.isclose(key_stats['p_value'], 5.5045e-05, rel_tol=1e-4)
    assert key_stats['is_significant'] is True

def test_newest_run_skips_missing_values():
    key_stats = _repeated_run_key_stats([1000, None, 1010, 990, 1015])

    assert math.isclose(key_stats['p_value'], 0.32352, rel_tol=1e-4)
    assert key_stats['is_significant'] is False

@pytest.mark.parametrize('values, p_value, is_significant', [
    ([1000, 1100], None, None), # less than 3 values: no test
    ([1000, 1000, 1000, 1000], None, None), # no spread and no change: test undefined
    ([1000, 1000, 1000, 1010], 0.0, True), # no spread in previous runs: any change is significant
])
def test_newest_run_degenerate_cases(values, p_value, is_significant):
    key_stats = _repeated_run_key_stats(values)

    assert key_stats['p_value'] == p_value
    assert key_stats['is_significant'] is is_significant
