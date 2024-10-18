import os
import pytest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib import utils
from lib.timeline_project import TimelineProject
from cron.timeline_projects import schedule_timeline_projects

TIMELINE_PROJECT = {
        'name':'My Name',
        'url':'https://github.com/green-coding-solutions/green-metrics-tool',
        'branch':'main',
        'filename':'usage_scenario.yml',
        'machine_id':'1',
        'user_id':1,
        'schedule_mode':'daily',
        'last_marker':None
}

GMT_LAST_COMMIT_HASH = utils.get_repo_last_marker(TIMELINE_PROJECT['url'], 'commits')

def test_run_schedule_one_off_broken():
    timeline_project_modified = TIMELINE_PROJECT.copy()
    timeline_project_modified['schedule_mode'] = 'one-off'

    TimelineProject.insert(**timeline_project_modified)
    with pytest.raises(ValueError):
        schedule_timeline_projects()

def test_run_schedule_daily_multiple():
    jobs = get_jobs()
    assert len(jobs) == 0

    TimelineProject.insert(**TIMELINE_PROJECT)
    TimelineProject.insert(**TIMELINE_PROJECT)

    schedule_timeline_projects()

    jobs = get_jobs()
    assert len(jobs) == 2


def test_run_schedule_daily():
    jobs = get_jobs()
    assert len(jobs) == 0

    TimelineProject.insert(**TIMELINE_PROJECT)

    schedule_timeline_projects()

    jobs = get_jobs()
    assert len(jobs) == 1
    assert jobs[0]['url'] == TIMELINE_PROJECT['url']
    assert jobs[0]['branch'] == TIMELINE_PROJECT['branch']
    assert jobs[0]['name'] == TIMELINE_PROJECT['name']
    assert jobs[0]['state'] == 'WAITING'

def test_run_schedule_daily_repeated():
    jobs = get_jobs()
    assert len(jobs) == 0

    TimelineProject.insert(**TIMELINE_PROJECT)
    schedule_timeline_projects()
    schedule_timeline_projects()

    jobs = get_jobs()
    assert len(jobs) == 1 # we still expect only one project


def test_run_schedule_timeline_projects_update_commit():
    jobs = get_jobs()
    assert len(jobs) == 0

    timeline_project_modified = TIMELINE_PROJECT.copy()
    timeline_project_modified['last_marker'] = '23rfq'
    timeline_project_modified['schedule_mode'] = 'commit'

    TimelineProject.insert(**timeline_project_modified)

    schedule_timeline_projects()

    jobs = get_jobs()
    assert len(jobs) == 1

    timeline_project_db = utils.get_timeline_project(timeline_project_modified['url'])
    assert timeline_project_db['last_marker'] == GMT_LAST_COMMIT_HASH

    # And another schedule will NOT create a new project
    schedule_timeline_projects()

    jobs = get_jobs()
    assert len(jobs) == 1

    timeline_project_db = utils.get_timeline_project(timeline_project_modified['url'])
    assert timeline_project_db['last_marker'] == GMT_LAST_COMMIT_HASH


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
