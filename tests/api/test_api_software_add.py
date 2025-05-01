import json
import os
import requests
import re

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.user import User
from lib.db import DB
from lib import utils
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

API_URL = GlobalConfig().config['cluster']['api_url']

from api.scenario_runner import Software

def test_post_run_add_github_one_off():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='https://github.com/green-coding-solutions/green-metrics-tool', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='one-off')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)
    data = response.json()
    assert isinstance(data['data'], list)
    assert len(data['data']) == 1

    job_ids = get_job_ids(run_name)
    assert job_ids == data['data']



def test_post_run_add_github_tags():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, image_url="test-image", repo_url='https://github.com/green-coding-solutions/green-metrics-tool', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='tag')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)
    data = response.json()
    assert isinstance(data['data'], list)
    assert len(data['data']) == 1

    job_ids = get_job_ids(run_name)
    assert job_ids == data['data']

    watchlist_item = utils.get_watchlist_item('https://github.com/green-coding-solutions/green-metrics-tool')

    assert re.match(r'v\d+\.\d+\.?\d*',watchlist_item['last_marker'])
    assert watchlist_item['schedule_mode'] == 'tag'
    assert watchlist_item['image_url'] == 'test-image'

def test_post_run_add_github_commit():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='https://github.com/green-coding-solutions/green-metrics-tool', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='commit-variance')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    data = response.json()
    assert isinstance(data['data'], list)
    assert len(data['data']) == 3

    job_ids = get_job_ids(run_name)
    assert job_ids == data['data']

    watchlist_item = utils.get_watchlist_item('https://github.com/green-coding-solutions/green-metrics-tool')
    assert re.match(r'^[a-fA-F0-9]{40}$',watchlist_item['last_marker'])
    assert watchlist_item['schedule_mode'] == 'commit-variance'
    assert watchlist_item['image_url'] == ''

    # also retrieve from API
    response = requests.get(f"{API_URL}/v1/jobs?id={job_ids[0]}", timeout=15)
    assert response.status_code == 200, Tests.assertion_info('success', response.text)
    data = response.json()

    assert data['data'][0][0] == job_ids[0]
    assert data['data'][0][3] == 'https://github.com/green-coding-solutions/green-metrics-tool'


def test_post_run_add_gitlab_commit():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='https://gitlab.com/green-coding-solutions/ci-carbon-testing', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='commit')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    watchlist_item = utils.get_watchlist_item('https://gitlab.com/green-coding-solutions/ci-carbon-testing')
    assert re.match(r'^[a-fA-F0-9]{40}$',watchlist_item['last_marker'])
    assert watchlist_item['schedule_mode'] == 'commit'

def test_post_run_add_gitlab_tag_none_tag():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='https://gitlab.com/green-coding-solutions/ci-carbon-testing', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='tag')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    watchlist_item = utils.get_watchlist_item('https://gitlab.com/green-coding-solutions/ci-carbon-testing')
    assert watchlist_item['last_marker'] is None
    assert watchlist_item['schedule_mode'] == 'tag'

def test_post_run_add_gitlab_tag():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='https://gitlab.com/green-coding-solutions/green-metrics-tool', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='tag')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    watchlist_item = utils.get_watchlist_item('https://gitlab.com/green-coding-solutions/green-metrics-tool')
    assert re.match(r'v\d+\.\d+\.?\d*',watchlist_item['last_marker'])
    assert watchlist_item['schedule_mode'] == 'tag'

def test_post_run_add_gitlab_custom_api_base():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='https://gitlab.rlp.net/green-software-engineering/oscar', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='commit')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 202, Tests.assertion_info('success', response.text)

    watchlist_item = utils.get_watchlist_item('https://gitlab.rlp.net/green-software-engineering/oscar')
    assert re.match(r'^[a-fA-F0-9]{40}$',watchlist_item['last_marker'])
    assert watchlist_item['schedule_mode'] == 'commit'


def test_post_run_add_no_permissions():
    user = User(1)
    user._capabilities['machines'] = []
    user.update()

    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='https://github.com/green-coding-solutions/green-metrics-tool', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='eisen')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 422, Tests.assertion_info('success', response.text)
    assert json.loads(response.text)['err'] == 'Your user does not have the permissions to use that machine.'

def test_post_run_add_machine_does_not_exist():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='https://github.com/green-coding-solutions/green-metrics-tool', email='testEmail', branch='', filename='', machine_id=30, schedule_mode='eisen')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 422, Tests.assertion_info('success', response.text)
    assert json.loads(response.text)['err'] == 'Machine does not exist'


def test_post_run_add_unknown_measurement_interval():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='https://github.com/no-company-here/and-no-repo/', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='eisen')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 422, Tests.assertion_info('success', response.text)
    assert json.loads(response.text)['err'] == 'Please select a valid measurement interval. (eisen) is unknown.'

def test_post_run_add_broken_repo_url():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='h8gw4hruihuf', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='one-off')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 422, Tests.assertion_info('success', response.text)
    assert json.loads(response.text)['err'] == 'Could not find repository h8gw4hruihuf and branch main. Is the repo publicly accessible, not empty and does the branch main exist?'

def test_post_run_add_non_existent_repo():
    run_name = 'test_' + utils.randomword(12)
    run = Software(name=run_name, repo_url='https://github.com/no-company-here/and-no-repo/', email='testEmail', branch='', filename='', machine_id=1, schedule_mode='one-off')
    response = requests.post(f"{API_URL}/v1/software/add", json=run.model_dump(), timeout=15)
    assert response.status_code == 422, Tests.assertion_info('success', response.text)
    assert json.loads(response.text)['err'] == 'Could not find repository https://github.com/no-company-here/and-no-repo/ and branch main. Is the repo publicly accessible, not empty and does the branch main exist?'




## helpers
def get_job_ids(run_name):
    query = """
            SELECT
                id
            FROM
                jobs
            WHERE name = %s
            """
    data = DB().fetch_all(query, (run_name, ))
    if data is None or data == []:
        return None
    return [el[0] for el in data] # unpack
