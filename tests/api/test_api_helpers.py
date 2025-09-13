import math
from pydantic import BaseModel

from api import api_helpers

class Run(BaseModel):
    name: str
    url: str
    email: str
    branch: str
    machine_id: int

class CI_Measurement(BaseModel):
    value: int
    unit: str
    repo: str
    branch: str
    cpu: str
    commit_hash: str
    workflow: str
    run_id: str
    source: str
    label: str
    duration: int


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
