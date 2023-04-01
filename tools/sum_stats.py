#pylint: disable=import-error,wrong-import-position
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/..")
sys.path.append(f"{CURRENT_DIR}/../lib")

import faulthandler
from db import DB

faulthandler.enable()  # will catch segfaults and write to STDERR

if __name__ == '__main__':
    #pylint: disable=broad-except,invalid-name

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('project_id', help='Project ID', type=str)


    args = parser.parse_args()  # script will exit if type is not present

    project_id = args.project_id

    query = """
            SELECT metric, unit, detail_name
            FROM stats
            WHERE project_id = %s
            GROUP BY metric, unit, detail_name
            ORDER BY metric ASC -- we need this ordering for later, when we read again
            """
    metrics = DB().fetch_all(query, (project_id, ))

    query = """
        SELECT phases
        FROM projects
        WHERE id = %s
        """
    phases = DB().fetch_one(query, (project_id, ))

    for idx, phase in enumerate(phases[0]):
        # we do not want to overwrite already set phases. This will only happen in an error case
        # or manual workings on the DB. But we still need to check.
        query = """
            SELECT COUNT(id)
            FROM stats
            WHERE phase IS NOT NULL AND time > %s AND time < %s AND project_id = %s
            """
        results = DB().fetch_one(query, (phase['start'], phase['end'], project_id, ))
        # TODO
        #if results[0] != 0:
        #    raise RuntimeError(f"Non-zero results for {phase}, were {results[0]} results")

        query = """
            UPDATE stats
            SET phase = %s
            WHERE phase IS NULL and time > %s and time < %s AND project_id = %s
            """
        DB().query(query, (phase['name'], phase['start'], phase['end'], project_id, ))

        # now we go through all metrics in the project and aggregate them
        for (metric, unit, detail_name) in metrics: # unpack
            # -- saved for future if I need lag time query
            #    WITH times as (
            #        SELECT id, value, time, (time - LAG(time) OVER (ORDER BY detail_name ASC, time ASC)) AS diff, unit
            #        FROM stats
            #        WHERE project_id = %s AND metric = %s
            #        ORDER BY detail_name ASC, time ASC
            #    ) -- Backlog: if we need derivatives / integrations in the future

            query = """
                SELECT SUM(value), MAX(value), AVG(value), COUNT(value)
                FROM stats
                WHERE project_id = %s AND metric = %s AND detail_name = %s AND time > %s and time < %s
            """
            results = DB().fetch_one(query,
                (project_id, metric, detail_name, phase['start'], phase['end'], ))

            value_sum = 0
            value_max = 0
            value_avg = 0
            value_count = 0


            if results[0] is not None:
                (value_sum, value_max, value_avg, value_count) = results

            insert_query = """
                INSERT INTO phase_stats
                    (project_id, metric, detail_name, phase, value, type, max_value, unit, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """

            if metric in (
                'lm_sensors_temp',
                'lm_sensors_fan',
                'cpu_utilization_procfs_system',
                'cpu_utilization_cgroup_container',
                'memory_total_cgroup_container'
            ):
                DB().query(insert_query,
                        (project_id, metric, detail_name, f"{idx:03}_{phase['name']}", # phase name mod. for order
                            value_avg, 'MEAN', value_max,
                        unit)
                )

            elif metric == 'network_io_cgroup_container':
                # These metrics are accumulating already. We only need the max here and deliver it as total
                DB().query(insert_query,
                        (project_id, metric, detail_name, f"{idx:03}_{phase['name']}",# phase name mod. for order
                            value_max, 'TOTAL', None,
                        unit)
                )
                # No max here
            elif metric == 'energy_impact_powermetrics_vm':
                DB().query(insert_query,
                        (project_id, metric, detail_name, f"{idx:03}_{phase['name']}",# phase name mod. for order
                            value_avg, 'MEAN', value_max,
                        unit)
                )

            elif "_energy_" in metric and unit == 'mJ':
                DB().query(insert_query,
                        (project_id, metric, detail_name, f"{idx:03}_{phase['name']}",# phase name mod. for order
                            value_sum, 'TOTAL', None,
                        unit)
                )

                # for energy we want to deliver an extra value, the watts.
                # Here we need to calculate the average differently
                DB().query(insert_query,
                        (project_id,
                        f"{metric.replace('_energy_', '_power_')}",
                        detail_name,
                        f"{idx:03}_{phase['name']}", # phase name mod. for order
                            # sum of mJ / s => mW
                            (value_sum  * 10**6) / (phase['end'] - phase['start']),
                            'MEAN',
                            # max_value / avg_measurement_interval
                            (value_max * 10**6) / ((phase['end'] - phase['start']) / value_count),
                        'mW')
                )

            else:
                DB().query(insert_query,
                        (project_id, metric, detail_name, f"{idx:03}_{phase['name']}",# phase name mod. for order
                            value_sum, 'TOTAL', value_max,
                        unit)
                )
