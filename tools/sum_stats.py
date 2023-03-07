#pylint: disable=import-error,wrong-import-position
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/..")
sys.path.append(f"{CURRENT_DIR}/../lib")

import psycopg2.extras
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
            SELECT metric, unit, detail_name
            FROM stats
            WHERE project_id = %s
            GROUP BY metric, unit, detail_name
            """
    metrics = DB().fetch_all(query, (project_id, ))

    query = """
        SELECT phases
        FROM projects
        WHERE id = %s
        """
    phases = DB().fetch_one(query, (project_id, ))

    for phase in phases[0]:
        print(phase)
        # we do not want to overwrite already set phases. This will only happen in an error case
        # or manual workings on the DB. But we still need to check.
        query = """
            SELECT COUNT(id)
            FROM stats
            WHERE phase IS NOT NULL AND time > %s AND time < %s AND project_id = %s
            """
        results = DB().fetch_one(query, (phase['start'], phase['end'], project_id, ))
#        if results[0] != 0:
#            raise RuntimeError(f"Non-zero results for {phase}, were {results[0]} results")

        query = """
            UPDATE stats
            SET phase = %s
            WHERE phase IS NULL and time > %s and time < %s AND project_id = %s
            """
        DB().query(query, (phase['name'], phase['start'], phase['end'], project_id, ))

        # now we go through all metrics in the project and aggregate them by lagging the table
        for (metric, unit, detail_name) in metrics: # unpack
            print(metric, unit, detail_name)
            #    WITH times as (
            #        SELECT id, value, time, (time - LAG(time) OVER (ORDER BY detail_name ASC, time ASC)) AS diff, unit
            #        FROM stats
            #        WHERE project_id = %s AND metric = %s
            #        ORDER BY detail_name ASC, time ASC
            #    ) -- Backlog: if we need derivatives / integrations in the future

            query = """
                SELECT SUM(value), MAX(value), AVG(value)
                FROM stats
                WHERE project_id = %s AND metric = %s AND detail_name = %s AND time > %s and time < %s
            """
            results = DB().fetch_one(query,
                (project_id, metric, detail_name, phase['start'], phase['end'], ))
            print(results)

            value_sum = 0
            value_max = 0
            print(results)
            if results[0] is not None:
                (value_sum, value_max, value_avg) = results

            query = """
                INSERT INTO phase_stats
                    (project_id, metric, detail_name, phase, value, unit, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, NOW())
            """

            if metric == 'lm_sensors_temp' or metric == 'lm_sensors_fan'
                DB().query(query,
                        (project_id, f"{metric}_AVG", detail_name, phase['name'],
                            value_avg,
                        unit)
                )
            else:
                DB().query(query,
                        (project_id, f"{metric}_SUM", detail_name, phase['name'],
                            value_sum,
                        unit)
                )

            if ("_energy_" in metric and unit == 'mJ'): # alternative to sum
                DB().query(query,
                        (project_id, metric.replace('_energy_', '_power_'), detail_name, phase['name'],
                            value_sum / (phase['end'] - phase['start']), # sum of mJ / s => mW
                        'mW')
                )

            # always
            DB().query(query,
                    (project_id, f"{metric}_MAX", detail_name, phase['name'],
                        value_max,
                    unit)
            )

