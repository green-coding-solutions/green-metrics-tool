import os
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib import utils
from lib.watchlist import Watchlist
from cron.watchlist import schedule_watchlist_item

WATCHLIST_ITEM = {
        'name':'My Name',
        'image_url': 'not-set',
        'repo_url':'https://github.com/green-coding-solutions/green-metrics-tool',
        'branch':'main',
        'filename':'usage_scenario.yml',
        'machine_id':1,
        'user_id':1,
        'schedule_mode':'daily',
        'last_marker':None,
        'category_ids': None,
        'usage_scenario_variables': {}
}

GMT_LAST_COMMIT_HASH = utils.get_repo_last_marker(WATCHLIST_ITEM['repo_url'], 'commits', branch='main')

@pytest.fixture(autouse=True, scope="function")
def delete_jobs_from_DB():
    DB().query('DELETE FROM jobs')
    yield


def test_run_schedule_one_off_broken():
    watchlist_item_modified = WATCHLIST_ITEM.copy()
    watchlist_item_modified['schedule_mode'] = 'one-off'

    Watchlist.insert(**watchlist_item_modified)
    with pytest.raises(ValueError):
        schedule_watchlist_item()

def test_run_schedule_daily_multiple():
    jobs = get_jobs()
    assert len(jobs) == 0

    Watchlist.insert(**WATCHLIST_ITEM)
    Watchlist.insert(**WATCHLIST_ITEM)

    schedule_watchlist_item()

    jobs = get_jobs()
    assert len(jobs) == 2


def test_run_schedule_daily():
    jobs = get_jobs()
    assert len(jobs) == 0

    Watchlist.insert(**WATCHLIST_ITEM)

    schedule_watchlist_item()

    jobs = get_jobs()
    assert len(jobs) == 1
    assert jobs[0]['url'] == WATCHLIST_ITEM['repo_url']
    assert jobs[0]['branch'] == WATCHLIST_ITEM['branch']
    assert jobs[0]['name'] == WATCHLIST_ITEM['name']
    assert jobs[0]['state'] == 'WAITING'
    assert jobs[0]['category_ids'] == WATCHLIST_ITEM['category_ids']

def test_run_schedule_with_category():
    jobs = get_jobs()
    assert len(jobs) == 0

    watchlist_item_modified = WATCHLIST_ITEM.copy()
    watchlist_item_modified['category_ids'] = [2,1]

    Watchlist.insert(**watchlist_item_modified)
    schedule_watchlist_item()

    jobs = get_jobs()
    assert len(jobs) == 1
    assert jobs[0]['url'] == watchlist_item_modified['repo_url']
    assert jobs[0]['branch'] == watchlist_item_modified['branch']
    assert jobs[0]['name'] == watchlist_item_modified['name']
    assert jobs[0]['state'] == 'WAITING'
    assert jobs[0]['category_ids'] == watchlist_item_modified['category_ids']

def test_run_schedule_daily_repeated():
    jobs = get_jobs()
    assert len(jobs) == 0

    Watchlist.insert(**WATCHLIST_ITEM)
    schedule_watchlist_item()
    schedule_watchlist_item()

    jobs = get_jobs()
    assert len(jobs) == 1 # we still expect only one item


def test_run_schedule_watchlist_item_update_commit():
    jobs = get_jobs()
    assert len(jobs) == 0

    watchlist_item_modified = WATCHLIST_ITEM.copy()
    watchlist_item_modified['last_marker'] = '23rfq'
    watchlist_item_modified['schedule_mode'] = 'commit'
    watchlist_item_modified['usage_scenario_variables'] = {'Yes': 'no'}

    Watchlist.insert(**watchlist_item_modified)

    schedule_watchlist_item()

    jobs = get_jobs()
    assert len(jobs) == 1

    watchlist_item_db = utils.get_watchlist_item(watchlist_item_modified['repo_url'])
    assert watchlist_item_db['last_marker'] == GMT_LAST_COMMIT_HASH
    assert watchlist_item_db['usage_scenario_variables'] == {'Yes': 'no'}

    # And another schedule will NOT create a new item
    schedule_watchlist_item()

    jobs = get_jobs()
    assert len(jobs) == 1

    watchlist_item_db = utils.get_watchlist_item(watchlist_item_modified['repo_url'])
    assert watchlist_item_db['last_marker'] == GMT_LAST_COMMIT_HASH


def test_run_schedule_daily_redacts_credentials_in_stdout(capsys):
    watchlist_item_modified = WATCHLIST_ITEM.copy()
    watchlist_item_modified['repo_url'] = 'https://admin:s3cr3t@github.com/green-coding-solutions/green-metrics-tool'

    Watchlist.insert(**watchlist_item_modified)
    schedule_watchlist_item()

    captured = capsys.readouterr()
    assert 'admin' not in captured.out
    assert 's3cr3t' not in captured.out
    assert '*****GMT-REDACTED*****' in captured.out

    # the DB copy must stay usable so the cluster worker can actually clone the repo later
    jobs = get_jobs()
    assert len(jobs) == 1
    assert jobs[0]['url'] == watchlist_item_modified['repo_url']


def test_run_schedule_watchlist_item_non_existing_branch(capsys):
    watchlist_item_modified = WATCHLIST_ITEM.copy()
    watchlist_item_modified['branch'] = 'non-existing-branch-for-testing'
    watchlist_item_modified['schedule_mode'] = 'commit'
    watchlist_item_modified['last_marker'] = 'dummy'

    Watchlist.insert(**watchlist_item_modified)

    # A single unresolvable watchlist item (e.g. a deleted branch) must be logged and skipped,
    # not raise and abort the scheduling pass for every other watchlist item.
    schedule_watchlist_item()

    jobs = get_jobs()
    assert len(jobs) == 0 # no job may be scheduled off an unresolvable branch

    watchlist_item_db = utils.get_watchlist_item(watchlist_item_modified['repo_url'])
    assert watchlist_item_db['last_marker'] == 'dummy' # must remain untouched, not advanced

    captured = capsys.readouterr()
    assert 'Could not determine last commit marker for watchlist item. Skipping.' in captured.err

## helpers

def get_jobs():
    query = """
            SELECT
                *
            FROM
                jobs
            """
    data = DB().fetch_all(query, fetch_mode='dict')
    return data
