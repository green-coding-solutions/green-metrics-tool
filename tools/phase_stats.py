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


def generate_csv_line(project_id, metric, detail_name, phase_name, value, value_type, max_value, min_value, unit):
    return f"{project_id},{metric},{detail_name},{phase_name},{round(value)},{value_type},{round(max_value) if max_value is not None else ''},{round(min_value) if min_value is not None else ''},{unit},NOW()\n"

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

    csv_buffer = StringIO()

    for idx, phase in enumerate(phases[0]):
        network_io_bytes_total = [] # reset; # we use array here and sum later, because checking for 0 alone not enough

        select_query = """
            SELECT SUM(value), MAX(value), MIN(value), AVG(value), COUNT(value)
            FROM measurements
            WHERE project_id = %s AND metric = %s AND detail_name = %s AND time > %s and time < %s
        """

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
            max_value = 0
            min_value = 0
            avg_value = 0
            value_count = 0

            value_sum, max_value, min_value, avg_value, value_count = results

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
                csv_buffer.write(generate_csv_line(project_id, metric, detail_name, f"{idx:03}_{phase['name']}", avg_value, 'MEAN', max_value, min_value, unit))

            elif metric == 'network_io_cgroup_container':
                # These metrics are accumulating already. We only need the max here and deliver it as total
                csv_buffer.write(generate_csv_line(project_id, metric, detail_name, f"{idx:03}_{phase['name']}", max_value-min_value, 'TOTAL', None, None, unit))
                # No max here
                # But we need to build the energy
                network_io_bytes_total.append(max_value-min_value)

            elif metric == 'energy_impact_powermetrics_vm':
                csv_buffer.write(generate_csv_line(project_id, metric, detail_name, f"{idx:03}_{phase['name']}", avg_value, 'MEAN', max_value, min_value, unit))

            elif "_energy_" in metric and unit == 'mJ':
                csv_buffer.write(generate_csv_line(project_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', None, None, unit))
                # for energy we want to deliver an extra value, the watts.
                # Here we need to calculate the average differently
                power_sum = (value_sum * 10**6) / (phase['end'] - phase['start'])
                power_max = (max_value * 10**6) / ((phase['end'] - phase['start']) / value_count)
                power_min = (min_value * 10**6) / ((phase['end'] - phase['start']) / value_count)
                csv_buffer.write(generate_csv_line(project_id, f"{metric.replace('_energy_', '_power_')}", detail_name, f"{idx:03}_{phase['name']}", power_sum, 'MEAN', power_max, power_min, 'mW'))

                if metric.endswith('_machine'):
                    machine_co2 = (value_sum / 3_600) * 475
                    csv_buffer.write(generate_csv_line(project_id, f"{metric.replace('_energy_', '_co2_')}", detail_name, f"{idx:03}_{phase['name']}", machine_co2, 'TOTAL', None, None, 'ug'))


            else:
                csv_buffer.write(generate_csv_line(project_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', max_value, min_value, unit))
        # after going through detail metrics, create cumulated ones
        if network_io_bytes_total:
            # build the network energy
            # network via formula: https://www.green-coding.berlin/co2-formulas/
            # pylint: disable=invalid-name
            network_io_in_kWh = (sum(network_io_bytes_total) / 1_000_000_000) * 0.00375
            network_io_in_mJ = network_io_in_kWh * 3_600_000_000
            csv_buffer.write(generate_csv_line(project_id, 'network_energy_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_in_mJ, 'TOTAL', None, None, 'mJ'))
            # co2 calculations
            network_io_co2_in_ug = network_io_in_kWh * 475 * 1_000_000
            csv_buffer.write(generate_csv_line(project_id, 'network_co2_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_co2_in_ug, 'TOTAL', None, None, 'ug'))

        # also create the phase time metric
        csv_buffer.write(generate_csv_line(project_id, 'phase_time_syscall_system', '[SYSTEM]', f"{idx:03}_{phase['name']}", phase['end']-phase['start'], 'TOTAL', None, None, 'us'))

    csv_buffer.seek(0)  # Reset buffer position to the beginning
    DB().copy_from(
        csv_buffer,
        table='phase_stats',
        sep=',',
        columns=('project_id', 'metric', 'detail_name', 'phase', 'value', 'type', 'max_value', 'min_value', 'unit', 'created_at')
    )
    csv_buffer.close()  # Close the buffer


if __name__ == '__main__':
    #pylint: disable=broad-except,invalid-name

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('project_id', help='Project ID', type=str)

    args = parser.parse_args()  # script will exit if type is not present

    build_and_store_phase_stats(args.project_id)
