#pylint: disable=import-error,wrong-import-position

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib'))
from phase_stats import build_and_store_phase_stats

from db import DB

if __name__ == '__main__':
    print('This will remove ALL phase_stats and completely rebuild them. No data will get lost, but it will take some time. Continue? (y/N)')
    answer = sys.stdin.readline()
    if answer.strip().lower() == 'y':
        print('Deleting old phase_stats ...')
        DB().query('DELETE FROM phase_stats')
        print('Fetching projects ...')
        query = '''
            SELECT id
            FROM projects
            WHERE
                end_measurement IS NOT NULL AND phases IS NOT NULL
        '''
        projects = DB().fetch_all(query)

        print(f"Fetched {len(projects)} projects. Commencing ...")
        for idx, project_id in enumerate(projects):

            print(f"Rebuilding phase_stats for project #{idx} {project_id[0]}")
            build_and_store_phase_stats(project_id[0])
        print('Done')