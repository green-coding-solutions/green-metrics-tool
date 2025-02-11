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

    assert unit == 'Wh'
    assert math.isclose(value, 0.00000002777777777777777, rel_tol=1e-10)

    [value, unit] = api_helpers.convert_value(10000, 'uJ')

    assert unit == 'Wh'
    assert math.isclose(value, 0.000002777777777777777, rel_tol=1e-10)

    [value, unit] = api_helpers.convert_value(10000, 'mJ')

    assert unit == 'Wh'
    assert math.isclose(value, 0.002777777777777, rel_tol=1e-10)

    assert api_helpers.convert_value(324_000_000_000, 'uJ') == [90, 'Wh']

    assert api_helpers.convert_value(100, 'uJ', False) == [0.0001, 'J']

    assert api_helpers.convert_value(10000, 'uJ', False) == [0.01, 'J']

    assert api_helpers.convert_value(324_000_000_000, 'uJ', False) == [324000, 'J']

    assert api_helpers.convert_value(10000, 'mJ', False) == [10, 'J']


    assert api_helpers.convert_value(324_000_000_000, 'ugCO2e/Page Request') == [324000, 'gCO2e/Page Request']

    assert api_helpers.convert_value(222_000_000_000_000, 'ugCO2e/Kill') == [222000000, 'gCO2e/Kill']

    assert api_helpers.convert_value(0.0003, 'ugCO2e/Kill') == [0.0000000003, 'gCO2e/Kill']


    assert api_helpers.convert_value(100, 'xJ') == [100, 'xJ']

    assert api_helpers.convert_value(100, 'uj') == [100, 'uj']


def test_escape_dict():
    messy_dict = {"link": '<a href="http://www.github.com">Click me</a>'}
    escaped_link = '&lt;a href=&quot;http://www.github.com&quot;&gt;Click me&lt;/a&gt;'
    escaped = api_helpers.html_escape_multi(messy_dict.copy())

    assert escaped['link'] == escaped_link

def test_escape_run():
    messy_run = Run(name="test<?>", url='testURL', email='testEmail', branch='main', machine_id=0)
    escaped_name = 'test&lt;?&gt;'
    escaped = api_helpers.html_escape_multi(messy_run.model_copy())

    assert escaped.name == escaped_name

def test_escape_measurement():
    measurement = CI_Measurement(
        value=123,
        unit='mJ',
        repo='link<some_place>',
        branch='main',
        cpu='',
        commit_hash='',
        workflow='',
        run_id='',
        source='',
        label='',
        duration=13,
    )
    escaped_repo = 'link&lt;some_place&gt;'
    escaped = api_helpers.html_escape_multi(measurement.model_copy())

    assert escaped.repo == escaped_repo
