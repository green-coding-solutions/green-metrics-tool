#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import os
import pprint

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib.job.base import Job

"""
    This file schedules new Timeline Projects by inserting jobs in the jobs table


"""

class TimelineProject():
    #pylint:disable=redefined-outer-name
    @classmethod
    def insert(cls, name, url, branch, filename, machine_id, schedule_mode):
        # Timeline projects never insert / use emails as they are always premium and made by admin
        # So they need no notification on success / add
        insert_query = """
                INSERT INTO
                    timeline_projects (name, url, branch, filename, machine_id, schedule_mode, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, NOW()) RETURNING id;
                """
        params = (name, url, branch, filename, machine_id, schedule_mode,)
        return DB().fetch_one(insert_query, params=params)[0]


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['show', 'schedule'], help='Show will show all projects. Schedule will insert a job.')

    args = parser.parse_args()  # script will exit if arguments not present

    if args.mode == 'show':
        query = """
            SELECT
                p.id, p.name, p.url,
                (SELECT STRING_AGG(t.name, ', ' ) FROM unnest(p.categories) as elements
                        LEFT JOIN categories as t on t.id = elements) as categories,
                p.branch, p.filename, m.description, p.last_scheduled, p.schedule_mode,
                p.created_at, p.updated_at
            FROM timeline_projects as p
            LEFT JOIN machines as m on m.id = p.machine_id
            ORDER BY p.url ASC
        """
        data = DB().fetch_all(query, fetch_mode='dict')
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(data)

    else:
        query = """
            SELECT
                id, name, url, branch, filename, machine_id, schedule_mode, last_scheduled,
                DATE(last_scheduled) >= DATE(NOW()) as "scheduled_today",
                DATE(last_scheduled) >= DATE(NOW() - INTERVAL '7 DAYS') as "scheduled_last_week"
            FROM timeline_projects
           """
        data = DB().fetch_all(query)

        for [project_id, name, url, branch, filename, machine_id, schedule_mode, last_scheduled, scheduled_today, scheduled_last_week] in data:
            if not last_scheduled:
                print('Project was not scheduled yet ', url, branch, filename, machine_id)
                DB().query('UPDATE timeline_projects SET last_scheduled = NOW() WHERE id = %s', params=(project_id,))
                Job.insert('run', name=name, url=url, email=None, branch=branch, filename=filename, machine_id=machine_id)
                print('\tInserted ')
            elif schedule_mode == 'daily':
                print('Project is on daily schedule', url, branch, filename, machine_id)
                if scheduled_today is False:
                    print('\tProject was not scheduled today', scheduled_today)
                    DB().query('UPDATE timeline_projects SET last_scheduled = NOW() WHERE id = %s', params=(project_id,))
                    Job.insert('run', name=name, url=url, email=None, branch=branch, filename=filename, machine_id=machine_id)
                    print('\tInserted')
            elif schedule_mode == 'weekly':
                print('Project is on daily schedule', url, branch, filename, machine_id)
                if scheduled_last_week is False:
                    print('\tProject was not scheduled in last 7 days', scheduled_last_week)
                    DB().query('UPDATE timeline_projects SET last_scheduled = NOW() WHERE id = %s', params=(project_id,))
                    Job.insert('run', name=name, url=url, email=None, branch=branch, filename=filename, machine_id=machine_id)
                    print('\tInserted')
            elif schedule_mode == 'commit':
                print('Project is on time schedule', url, branch, filename, machine_id)
                print('This functionality is not yet implemented ...')
