#pylint: disable=import-error,wrong-import-position
import sys
import os
import faulthandler
import pprint
from psycopg.rows import dict_row as psycopg_rows_dict_row
faulthandler.enable()  # will catch segfaults and write to STDERR

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/..")
sys.path.append(f"{CURRENT_DIR}/../lib")

from jobs import Job
from db import DB

"""
    This file schedules new Timeline Projects by inserting jobs in the jobs table


"""

class TimelineProject():
    @classmethod
    def insert(cls, url, branch, filename, machine_id, schedule_mode):
        # Timeline projects never insert / use emails as they are always premium and made by admin
        # So they need no notification on success / add
        insert_query = """
                INSERT INTO
                    timeline_projects (url, branch, filename, machine_id, schedule_mode, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, NOW()) RETURNING id;
                """
        params = (url, branch, filename, machine_id, schedule_mode,)
        return DB().fetch_one(insert_query, params=params)[0]


# pylint: disable=broad-exception-caught
if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['show', 'schedule'], help='Show will show all projects. Schedule will insert a job.')

    args = parser.parse_args()  # script will exit if arguments not present

    if args.mode == 'show':
        query = """
            SELECT
                p.id, p.url,
                (SELECT STRING_AGG(t.name, ', ' ) FROM unnest(p.categories) as elements
                        LEFT JOIN categories as t on t.id = elements) as categories,
                p.branch, p.filename, m.description, p.last_scheduled, p.schedule_mode,
                p.created_at, p.updated_at
            FROM timeline_projects as p
            LEFT JOIN machines as m on m.id = p.machine_id
            ORDER BY p.url ASC
        """
        data = DB().fetch_all(query, row_factory=psycopg_rows_dict_row)
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(data)

    else:
        query = """
            SELECT
                id, url, branch, filename, machine_id, schedule_mode, last_scheduled,
                DATE(last_scheduled) >= DATE(NOW()) as "scheduled_today"
            FROM timeline_projects
           """
        data = DB().fetch_all(query)

        for [project_id, url, branch, filename, machine_id, schedule_mode, last_scheduled, scheduled_today] in data:
            if not last_scheduled:
                print('Project was not scheduled yet ', url, branch, filename, machine_id)
                DB().query('UPDATE timeline_projects SET last_scheduled = NOW() WHERE id = %s', params=(project_id,))
                Job.insert('Timeline project', url,  None, branch, filename, machine_id)
                print('\tInserted ')
            elif schedule_mode == 'time':
                print('Project is on time schedule', url, branch, filename, machine_id)
                if scheduled_today is False:
                    print('\tProject was not scheduled today', scheduled_today)
                    DB().query('UPDATE timeline_projects SET last_scheduled = NOW() WHERE id = %s', params=(project_id,))
                    Job.insert('Timeline project', url,  None, branch, filename, machine_id)
                    print('\tInserted')
            elif schedule_mode == 'commit':
                print('Project is on time schedule', url, branch, filename, machine_id)
                print('This functionality is not yet implemented ...')
