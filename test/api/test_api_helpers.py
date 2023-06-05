#pylint: disable=wrong-import-position,import-error
import os
import sys

from pydantic import BaseModel

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../api")

import api_helpers

class Project(BaseModel):
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
    project_id: str
    source: str
    label: str
    duration: int


def test_sanitize_dict():
    messy_dict = {"link": '<a href="http://www.github.com">Click me</a>'}
    escaped_link = '&lt;a href="http://www.github.com"&gt;Click me&lt;/a&gt;'
    sanitized = api_helpers.sanitize(messy_dict.copy())

    assert sanitized['link'] == escaped_link

def test_sanitize_project():
    messy_project = Project(name="test<?>", url='testURL', email='testEmail', branch='', machine_id=0)
    escaped_name = 'test&lt;?&gt;'
    sanitized = api_helpers.sanitize(messy_project.copy())

    assert sanitized.name == escaped_name

def test_sanitize_measurement():
    measurement = CI_Measurement(
        value=123,
        unit='mJ',
        repo='link<some_place>',
        branch='',
        cpu='',
        commit_hash='',
        workflow='',
        run_id='',
        project_id='',
        source='',
        label='',
        duration=13,
    )
    escaped_repo = 'link&lt;some_place&gt;'
    sanitized = api_helpers.sanitize(measurement.copy())

    assert sanitized.repo == escaped_repo
