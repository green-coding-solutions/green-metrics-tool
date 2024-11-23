#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import decimal
from io import StringIO

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import utils
from lib import error_helpers

def generate_csv_line(run_id, metric, detail_name, phase_name, value, value_type, max_value, min_value, unit):
    return f"{run_id},{metric},{detail_name},{phase_name},{round(value)},{value_type},{round(max_value) if max_value is not None else ''},{round(min_value) if min_value is not None else ''},{unit},NOW()\n"

def build_and_store_phase_stats(run_id, sci=None):
    config = GlobalConfig().config

    if not sci:
        sci = {}

    query = """
            SELECT metric, unit, detail_name
            FROM measurements
            WHERE run_id = %s
            GROUP BY metric, unit, detail_name
            ORDER BY metric ASC -- we need this ordering for later, when we read again
            """
    metrics = DB().fetch_all(query, (run_id, ))

    if not metrics:
        error_helpers.log_error('Metrics was empty and no phase_stats could be created. This can happen for failed runs, but should be very rare ...', run_id=run_id)
        return


    query = """
        SELECT phases, measurement_config
        FROM runs
        WHERE id = %s
        """
    data = DB().fetch_one(query, (run_id, ))

    if not data or not data[0] or not data[1]:
        error_helpers.log_error('Phases object was empty and no phase_stats could be created. This can happen for failed runs, but should be very rare ...', run_id=run_id)
        return

    phases, measurement_config = data # unpack

    csv_buffer = StringIO()

    machine_power_idle = None
    machine_power_runtime = None
    machine_energy_runtime = None


    for idx, phase in enumerate(phases):
        network_bytes_total = [] # reset; # we use array here and sum later, because checking for 0 alone not enough

        cpu_utilization_containers = {} # reset
        cpu_utilization_machine = None
        machine_carbon_in_ug = None # reset
        network_io_carbon_in_ug = None

        select_query = """
            SELECT SUM(value), MAX(value), MIN(value), AVG(value), COUNT(value)
            FROM measurements
            WHERE run_id = %s AND metric = %s AND detail_name = %s AND time > %s and time < %s
        """

        duration = phase['end']-phase['start']
        duration_in_s = duration / 1_000_000
        csv_buffer.write(generate_csv_line(run_id, 'phase_time_syscall_system', '[SYSTEM]', f"{idx:03}_{phase['name']}", duration, 'TOTAL', None, None, 'us'))

        # now we go through all metrics in the run and aggregate them
        for (metric, unit, detail_name) in metrics: # unpack
            # -- saved for future if I need lag time query
            #    WITH times as (
            #        SELECT id, value, time, (time - LAG(time) OVER (ORDER BY detail_name ASC, time ASC)) AS diff, unit
            #        FROM measurements
            #        WHERE run_id = %s AND metric = %s
            #        ORDER BY detail_name ASC, time ASC
            #    ) -- Backlog: if we need derivatives / integrations in the future

            provider_name = metric.replace('_', '.') + '.provider.' + utils.get_pascal_case(metric) + 'Provider'
            provider_resolution_in_ms = measurement_config['providers'][provider_name]['resolution']

            results = DB().fetch_one(select_query,
                (run_id, metric, detail_name, phase['start'], phase['end'], ))

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
                'lmsensors_temperature_component',
                'lmsensors_fan_component',
                'cpu_utilization_procfs_system',
                'cpu_utilization_mach_system',
                'cpu_utilization_cgroup_container',
                'memory_used_cgroup_container',
                'memory_used_procfs_system',
                'energy_impact_powermetrics_vm',
                'disk_used_statvfs_system',
                'cpu_frequency_sysfs_core',
            ):
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", avg_value, 'MEAN', max_value, min_value, unit))

                if metric in ('cpu_utilization_procfs_system', 'cpu_utilization_mach_system'):
                    cpu_utilization_machine = avg_value
                if metric in ('cpu_utilization_cgroup_container', ):
                    cpu_utilization_containers[detail_name] = avg_value

            elif metric in ['network_io_cgroup_container', 'network_io_procfs_system', 'disk_io_procfs_system', 'disk_io_cgroup_container']:
                # I/O values should be per second. However we have very different timing intervals.
                # So we do not directly use the average here, as this would be the average per sampling frequency. We go through the duration
                provider_conversion_factor_to_s = decimal.Decimal(provider_resolution_in_ms/1_000)
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", avg_value/provider_conversion_factor_to_s, 'MEAN', max_value/provider_conversion_factor_to_s, min_value/provider_conversion_factor_to_s, f"{unit}/s"))

                # we also generate a total line to see how much total data was processed
                csv_buffer.write(generate_csv_line(run_id, metric.replace('_io_', '_total_'), detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', None, None, unit))

                if metric == 'network_io_cgroup_container': # save to calculate CO2 later. We do this only for the cgroups. Not for the system to not double count
                    network_bytes_total.append(value_sum)

            elif "_energy_" in metric and unit == 'mJ':
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', None, None, unit))
                # for energy we want to deliver an extra value, the watts.
                # Here we need to calculate the average differently
                power_avg = (value_sum * 10**6) / duration
                power_max = (max_value * 10**6) / (duration / value_count)
                power_min = (min_value * 10**6) / (duration / value_count)
                csv_buffer.write(generate_csv_line(run_id, f"{metric.replace('_energy_', '_power_')}", detail_name, f"{idx:03}_{phase['name']}", power_avg, 'MEAN', power_max, power_min, 'mW'))

                if metric.endswith('_machine') and sci.get('I', None) is not None:
                    machine_carbon_in_ug = decimal.Decimal((value_sum / 3_600) * sci['I'])
                    csv_buffer.write(generate_csv_line(run_id, f"{metric.replace('_energy_', '_carbon_')}", detail_name, f"{idx:03}_{phase['name']}", machine_carbon_in_ug, 'TOTAL', None, None, 'ug'))

                    if phase['name'] == '[IDLE]':
                        machine_power_idle = power_avg
                    else:
                        machine_energy_runtime = value_sum
                        machine_power_runtime = power_avg

            else:
                error_helpers.log_error('Unmapped phase_stat found, using default', metric=metric, detail_name=detail_name, run_id=run_id)
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', max_value, min_value, unit))

        # after going through detail metrics, create cumulated ones
        if network_bytes_total:
            # build the network energy
            # network via formula: https://www.green-coding.io/co2-formulas/
            # pylint: disable=invalid-name
            network_io_in_kWh = float(sum(network_bytes_total) / 1_000_000_000) * 0.002651650429449553
            network_io_in_mJ = network_io_in_kWh * 3_600_000_000
            csv_buffer.write(generate_csv_line(run_id, 'network_energy_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", decimal.Decimal(network_io_in_mJ), 'TOTAL', None, None, 'mJ'))
            # co2 calculations
            network_io_carbon_in_ug = decimal.Decimal(network_io_in_kWh * config['sci']['I'] * 1_000_000)
            csv_buffer.write(generate_csv_line(run_id, 'network_carbon_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_carbon_in_ug, 'TOTAL', None, None, 'ug'))
        else:
            network_io_carbon_in_ug = decimal.Decimal(0)

        if sci.get('EL', None) is not None and sci.get('TE', None) is not None and sci.get('RS', None) is not None:
            duration_in_years = duration_in_s / (60 * 60 * 24 * 365)
            embodied_carbon_share_g = (duration_in_years / sci['EL'] ) * sci['TE'] * sci['RS']
            embodied_carbon_share_ug = decimal.Decimal(embodied_carbon_share_g * 1_000_000)
            csv_buffer.write(generate_csv_line(run_id, 'embodied_carbon_share_machine', '[SYSTEM]', f"{idx:03}_{phase['name']}", embodied_carbon_share_ug, 'TOTAL', None, None, 'ug'))

        if phase['name'] == '[RUNTIME]' and machine_carbon_in_ug is not None and sci is not None and sci.get('R', 0) != 0:
            csv_buffer.write(generate_csv_line(run_id, 'software_carbon_intensity_global', '[SYSTEM]', f"{idx:03}_{phase['name']}", (machine_carbon_in_ug + embodied_carbon_share_ug + network_io_carbon_in_ug) / sci['R'], 'TOTAL', None, None, f"ugCO2e/{sci['R_d']}"))

        if machine_power_idle and cpu_utilization_machine and cpu_utilization_containers:
            surplus_power_runtime = machine_power_runtime - machine_power_idle
            surplus_energy_runtime = machine_energy_runtime - (machine_power_idle * decimal.Decimal(duration / 10**6))

            total_container_utilization = sum(cpu_utilization_containers.values())
            if int(total_container_utilization) == 0:
                continue

            for detail_name, container_utilization in cpu_utilization_containers.items():
                csv_buffer.write(generate_csv_line(run_id, 'psu_energy_cgroup_slice', detail_name, f"{idx:03}_{phase['name']}", machine_energy_runtime * (container_utilization / total_container_utilization), 'TOTAL', None, None, 'mJ'))
                csv_buffer.write(generate_csv_line(run_id, 'psu_power_cgroup_slice', detail_name, f"{idx:03}_{phase['name']}", machine_power_runtime * (container_utilization / total_container_utilization), 'TOTAL', None, None, 'mW'))
                csv_buffer.write(generate_csv_line(run_id, 'psu_energy_cgroup_container', detail_name, f"{idx:03}_{phase['name']}", surplus_energy_runtime * (container_utilization / total_container_utilization), 'TOTAL', None, None, 'mJ'))
                csv_buffer.write(generate_csv_line(run_id, 'psu_power_cgroup_container', detail_name, f"{idx:03}_{phase['name']}", surplus_power_runtime * (container_utilization / total_container_utilization), 'TOTAL', None, None, 'mW'))

    csv_buffer.seek(0)  # Reset buffer position to the beginning
    DB().copy_from(
        csv_buffer,
        table='phase_stats',
        sep=',',
        columns=('run_id', 'metric', 'detail_name', 'phase', 'value', 'type', 'max_value', 'min_value', 'unit', 'created_at')
    )
    csv_buffer.close()  # Close the buffer
