from pydantic import BaseModel

from api import api_helpers
import pytest

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


def test_rescale_energy_value():
    assert api_helpers.rescale_energy_value(100, 'uJ') == [100, 'uJ']

    assert api_helpers.rescale_energy_value(10000, 'uJ') == [10, 'mJ']

    assert api_helpers.rescale_energy_value(10000, 'mJ') == [10, 'J']

    assert api_helpers.rescale_energy_value(324_000_000_000, 'uJ') == [324, 'kJ']

    assert api_helpers.rescale_energy_value(324_000_000_000, 'ugCO2e/Page Request') == [324, 'kgCO2e/Page Request']

    assert api_helpers.rescale_energy_value(222_000_000_000_000, 'ugCO2e/Kill') == [222, 'MgCO2e/Kill']

    assert api_helpers.rescale_energy_value(0.0003, 'ugCO2e/Kill') == [0.3, 'ngCO2e/Kill']


    with pytest.raises(ValueError):
        api_helpers.rescale_energy_value(100, 'xJ') # expecting only mJ and uJ

    with pytest.raises(ValueError):
        api_helpers.rescale_energy_value(100, 'uj') # expecting only mJ and uJ



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
