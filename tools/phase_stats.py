#pylint: disable=import-error,wrong-import-position
from io import StringIO
import sys
import os
import faulthandler

faulthandler.enable()  # will catch segfaults and write to STDERR

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/..")
sys.path.append(f"{CURRENT_DIR}/../lib")

from db import DB



def generate_csv_line(project_id, metric, detail_name, phase_name, value, value_type, max_value, unit):
    print(f"--> {project_id},{metric},{detail_name},{phase_name},{round(value)},{value_type},{max_value or ''},{unit},NOW()\n")
    return f"{project_id},{metric},{detail_name},{phase_name},{round(value)},{value_type},{max_value or ''},{unit},NOW()\n"

def build_and_store_phase_stats(project_id):
    query = """
            SELECT metric, unit, detail_name
            FROM measurements
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
        query = """
            UPDATE measurements
            SET phase = %s
            WHERE phase IS NULL and time > %s and time < %s AND project_id = %s
            """
        DB().query(query, (phase['name'], phase['start'], phase['end'], project_id, ))

        network_io_bytes_total = [] # reset; # we use array here and sum later, because checking for 0 alone not enough

        select_query = """
            SELECT SUM(value), MAX(value), AVG(value), COUNT(value)
            FROM measurements
            WHERE project_id = %s AND metric = %s AND detail_name = %s AND time > %s and time < %s
        """

        csv_buffer = StringIO()

        # now we go through all metrics in the project and aggregate them
        for (metric, unit, detail_name) in metrics: # unpack
            # -- saved for future if I need lag time query
            #    WITH times as (
            #        SELECT id, value, time, (time - LAG(time) OVER (ORDER BY detail_name ASC, time ASC)) AS diff, unit
            #        FROM measurements
            #        WHERE project_id = %s AND metric = %s
            #        ORDER BY detail_name ASC, time ASC
            #    ) -- Backlog: if we need derivatives / integrations in the future

            results = DB().fetch_one(select_query,
                (project_id, metric, detail_name, phase['start'], phase['end'], ))

            value_sum = 0
            value_max = 0
            value_avg = 0
            value_count = 0


            value_sum, value_max, value_avg, value_count = results

            # no need to calculate if we have no results to work on
            # This can happen if the phase is too short
            if value_count == 0: continue

            if metric in (
                'lm_sensors_temperature_component',
                'lm_sensors_fan_component',
                'cpu_utilization_procfs_system',
                'cpu_utilization_cgroup_container',
                'memory_total_cgroup_container',
                'cpu_frequency_sysfs_core',
            ):
                csv_buffer.write(generate_csv_line(project_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_avg, 'MEAN', value_max, unit))

            elif metric == 'network_io_cgroup_container':
                # These metrics are accumulating already. We only need the max here and deliver it as total
                csv_buffer.write(generate_csv_line(project_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_max, 'TOTAL', None, unit))
                # No max here
                # But we need to build the energy
                network_io_bytes_total.append(value_max)

            elif metric == 'energy_impact_powermetrics_vm':
                csv_buffer.write(generate_csv_line(project_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_avg, 'MEAN', value_max, unit))

            elif "_energy_" in metric and unit == 'mJ':
                csv_buffer.write(generate_csv_line(project_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', None, unit))
                # for energy we want to deliver an extra value, the watts.
                # Here we need to calculate the average differently
                power_sum = (value_sum * 10**6) / (phase['end'] - phase['start'])
                power_max = (value_max * 10**6) / ((phase['end'] - phase['start']) / value_count)
                csv_buffer.write(generate_csv_line(project_id, f"{metric.replace('_energy_', '_power_')}", detail_name, f"{idx:03}_{phase['name']}", power_sum, 'MEAN', power_max, 'mW'))

                if metric.endswith('_machine'):
                    machine_co2 = ((value_sum / 3_600) * 519)
                    csv_buffer.write(generate_csv_line(project_id, f"{metric.replace('_energy_', '_co2_')}", detail_name, f"{idx:03}_{phase['name']}", machine_co2, 'TOTAL', None, 'ug'))


            else:
                csv_buffer.write(generate_csv_line(project_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', value_max, unit))
        # after going through detail metrics, create cumulated ones
        if network_io_bytes_total != []:
            # build the network energy
            # network via formula: https://www.green-coding.berlin/co2-formulas/
            network_io_in_kWh = (sum(network_io_bytes_total) / 1_000_000_000) * 0.00375
            network_io_in_mJ = network_io_in_kWh * 3_600_000_000
            csv_buffer.write(generate_csv_line(project_id, 'network_energy_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_in_mJ, 'TOTAL', None, 'mJ'))
            # co2 calculations
            network_io_co2_in_ug = network_io_in_kWh * 475 * 1_000_000
            csv_buffer.write(generate_csv_line(project_id, 'network_co2_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_co2_in_ug, 'TOTAL', None, 'ug'))

        # also create the phase time metric
        csv_buffer.write(generate_csv_line(project_id, 'phase_time_syscall_system', '[SYSTEM]', f"{idx:03}_{phase['name']}", phase['end']-phase['start'], 'TOTAL', None, 'us'))

        csv_buffer.seek(0)  # Reset buffer position to the beginning
        DB().copy_from(
            csv_buffer,
            table='phase_stats',
            sep=',',
            columns=('project_id', 'metric', 'detail_name', 'phase', 'value', 'type', 'max_value', 'unit', 'created_at')
        )
        csv_buffer.close()  # Close the buffer


if __name__ == '__main__':
    #pylint: disable=broad-except,invalid-name

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('project_id', help='Project ID', type=str)

    args = parser.parse_args()  # script will exit if type is not present

    project_id = args.project_id
    build_and_store_phase_stats(project_id)
