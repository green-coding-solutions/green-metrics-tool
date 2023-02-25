#pylint: disable=import-error,wrong-import-position
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/..")
sys.path.append(f"{CURRENT_DIR}/../lib")

import faulthandler
import email_helpers
import error_helpers
from db import DB
from global_config import GlobalConfig
from runner import Runner

faulthandler.enable()  # will catch segfaults and write to STDERR



if __name__ == '__main__':
    #pylint: disable=broad-except,invalid-name

    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument('project_id', help='Project ID', type=str)


    args = parser.parse_args()  # script will exit if type is not present

    project_id = args.project_id

    query = """
            SELECT metric, unit
            FROM stats
            WHERE project_id = %s
            GROUP BY metric, unit
            """
    metrics = DB().fetch_all(query, (project_id, ))

    query = """
        SELECT phases
        FROM projects
        WHERE id = %s
        """
    phases = DB().fetch_one(query, (project_id, ))
    for metric in metrics:
        print(metric)
        for phase in phases[0]:
            print(phase)
            query = """
            INSERT INTO phase_stats
                (project_id, metric, phase, sum, derivative, unit, created_at)

                # TODO: Lag functionWITH times as (
    SELECT id, value, time, (time - LAG(time) OVER (ORDER BY project_id ASC, metric ASC, detail_name ASC, time ASC)) AS diff, unit
    FROM stats
    WHERE unit = 'mW'
    ORDER BY project_id ASC, metric ASC, detail_name ASC, time ASC
    LIMIT 10000

) UPDATE stats SET value = (value * (SELECT diff FROM times where id = stats.id) / (1000000)), unit = 'mJ'
WHERE EXISTS (SELECT id FROM times WHERE times.id = stats.id);


-- this code assumes that all times are in us as is default for the GMT
            VALUES
                (%s, %s, %s,
                    (
                        SELECT SUM(value)
                        FROM stats
                        WHERE project_id = %s AND metric = %s AND time > %s and time < %s
                    ),
                %s, NOW())
            """
            metrics = DB().query(query,
                    (project_id, metric[0], phase['name'],
                        project_id, metric[0], phase['start'], phase['end'],
                    metric[1])
            )