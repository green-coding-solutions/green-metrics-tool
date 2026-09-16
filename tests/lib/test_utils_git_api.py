import os

import pytest
import yaml

from lib import utils
from lib.global_config import GlobalConfig

BASE_CONFIG_PATH = f"{os.path.dirname(os.path.realpath(__file__))}/../test-config.yml"

class FakeResponse:
    status_code = 200

    def json(self):
        return [{'sha': 'abc123'}]

@pytest.fixture(name='captured_requests')
def fixture_captured_requests(monkeypatch):
    captured = []

    def fake_get(url, **kwargs):
        captured.append({'url': url, **kwargs})
        return FakeResponse()

    monkeypatch.setattr(utils.requests, 'get', fake_get)
    return captured

# GlobalConfig is immutable, so write a modified copy of the test config and load that.
# conftest.py reloads the regular test config before every test.
def set_github_api_token(tmp_path, token):
    with open(BASE_CONFIG_PATH, encoding='utf-8') as file:
        config = yaml.safe_load(file)

    config['cluster']['github_api_token'] = token

    tmp_config = tmp_path / 'test-config-github-api-token.yml'
    tmp_config.write_text(yaml.safe_dump(config), encoding='utf-8')
    GlobalConfig().override_config(config_location=tmp_config.as_posix())

def test_get_git_api_headers_without_token(tmp_path):
    set_github_api_token(tmp_path, None)

    assert not utils.get_git_api_headers('github')

def test_get_git_api_headers_with_token(tmp_path):
    set_github_api_token(tmp_path, 'ghp_test')

    assert utils.get_git_api_headers('github') == {'Authorization': 'Bearer ghp_test'}

@pytest.mark.parametrize('git_api', ['gitlab', 'custom', None])
def test_get_git_api_headers_never_sends_token_to_other_hosts(tmp_path, git_api):
    set_github_api_token(tmp_path, 'ghp_test')

    assert not utils.get_git_api_headers(git_api)

def test_check_repo_sends_token_to_github(tmp_path, captured_requests):
    set_github_api_token(tmp_path, 'ghp_test')

    utils.check_repo('https://github.com/green-coding-solutions/green-metrics-tool', 'main')

    assert captured_requests[0]['headers'] == {'Authorization': 'Bearer ghp_test'}

def test_get_repo_last_marker_sends_token_to_github(tmp_path, captured_requests):
    set_github_api_token(tmp_path, 'ghp_test')

    assert utils.get_repo_last_marker('https://github.com/green-coding-solutions/green-metrics-tool', 'commits') == 'abc123'
    assert captured_requests[0]['headers'] == {'Authorization': 'Bearer ghp_test'}

def test_check_repo_does_not_send_token_to_gitlab(tmp_path, captured_requests):
    set_github_api_token(tmp_path, 'ghp_test')

    utils.check_repo('https://gitlab.com/green-coding-solutions/green-metrics-tool', 'main')

    assert captured_requests[0]['headers'] == {}
