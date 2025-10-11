#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from decimal import Decimal
from io import StringIO

from lib.db import DB
from lib import error_helpers

def reconstruct_runtime_phase(run_id, runtime_phase_idx):
    # First we create averages for all types. This includes means and totals
    DB().query('''
        INSERT INTO phase_stats
            ("run_id", "metric", "detail_name", "phase", "value", "type", "max_value", "min_value", "sampling_rate_avg", "sampling_rate_max", "sampling_rate_95p", "unit", "created_at")

            SELECT
                run_id,
                metric,
                detail_name,
                %s,
                SUM(value),
                type,
                MAX(value),
                MIN(value),
                AVG(sampling_rate_avg), -- approx, but good enough for overview.
                MAX(sampling_rate_max),
                AVG(sampling_rate_95p), -- approx, but good enough for overview
                unit,
                NOW()
            FROM phase_stats
            WHERE run_id = %s AND phase NOT LIKE '%%[%%'
            GROUP BY run_id, metric, detail_name, type, unit
        ''', params=(f"{runtime_phase_idx:03}_[RUNTIME]", run_id, ))

    # now we need to actually fix the totals. This is done in a separate step as we could not reference the total phase
    # time for the runtime phases and their aggreagate value in one query

    total_runtime_sub_phase_duration = DB().fetch_one(
        "SELECT value FROM phase_stats WHERE phase = %s AND run_id = %s AND metric = 'phase_time_syscall_system' AND detail_name = '[SYSTEM]' AND unit = 'us' AND type = 'TOTAL' ",
        params=(f"{runtime_phase_idx:03}_[RUNTIME]", run_id,)
    )[0]

    DB().query('''
        WITH tvt as (
            SELECT
                metric, detail_name, unit,
                (SELECT p2.value FROM phase_stats as p2 WHERE p2.metric = 'phase_time_syscall_system' AND p2.detail_name = '[SYSTEM]' AND p2.unit = 'us' AND p2.run_id = phase_stats.run_id AND p2.phase = phase_stats.phase) as time_of_the_sub_phase,
                value
            FROM phase_stats
            WHERE run_id = %s AND phase NOT LIKE '%%[%%'
        )
        UPDATE phase_stats
            SET value =
                (SELECT COALESCE(SUM(tvt.value * (tvt.time_of_the_sub_phase::DOUBLE PRECISION / %s)), 0) FROM tvt WHERE tvt.metric = phase_stats.metric AND tvt.detail_name = phase_stats.detail_name AND tvt.unit = phase_stats.unit)::BIGINT

        WHERE phase = %s AND run_id = %s AND type = 'MEAN'
        ''', params=(run_id, total_runtime_sub_phase_duration, f"{runtime_phase_idx:03}_[RUNTIME]", run_id)
    )


def generate_csv_line(run_id, metric, detail_name, phase_name, value, value_type, max_value, min_value, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit):
    # else '' resolves to NULL
    return f"{run_id},{metric},{detail_name},{phase_name},{round(value)},{value_type},{round(max_value) if max_value is not None else ''},{round(min_value) if min_value is not None else ''},{round(sampling_rate_avg) if sampling_rate_avg is not None else ''},{round(sampling_rate_max) if sampling_rate_max is not None else ''},{round(sampling_rate_95p) if sampling_rate_95p is not None else ''},{unit},NOW()\n"

def build_and_store_phase_stats(run_id, sci=None):
    if not sci:
        sci = {}

    software_carbon_intensity_global = {}

    query = """
            SELECT id, metric, unit, detail_name
            FROM measurement_metrics
            WHERE run_id = %s
            ORDER BY metric ASC -- we need this ordering for later, when we read again
    """
    metrics = DB().fetch_all(query, (run_id, ))

    if not metrics:
        error_helpers.log_error('Metrics was empty and no phase_stats could be created. This can happen for failed runs, but should be very rare ...', run_id=run_id)
        return


    query = """
        SELECT phases
        FROM runs
        WHERE id = %s
        """
    phases = DB().fetch_one(query, (run_id, ))

    if not phases or not phases[0]:
        error_helpers.log_error('Phases object was empty and no phase_stats could be created. This can happen for failed runs, but should be very rare ...', run_id=run_id)
        return

    csv_buffer = StringIO()

    machine_power_baseline = None
    machine_power_current_phase = None
    machine_energy_current_phase = None

    runtime_phase_idx = None

    for idx, phase in enumerate(phases[0]):
        if phase['name'] == '[RUNTIME]': # do not process runtime like this, but rather reconstruct it later. Still advance the idx counter though as we want to use the number later
            runtime_phase_idx = idx
            continue

        network_bytes_total = [] # reset; # we use array here and sum later, because checking for 0 alone not enough

        cpu_utilization_containers = {} # reset
        cpu_utilization_machine = None
        network_io_carbon_in_ug = None

        select_query = """
            WITH lag_table as (
                SELECT time, value, (time - LAG(time) OVER (ORDER BY time ASC)) AS diff
                FROM measurement_values
                WHERE measurement_metric_id = %s AND time > %s and time < %s
                ORDER BY time ASC
            )
            SELECT
                SUM(value), MAX(value), MIN(value),
                AVG(value), -- This would be the normal average. we only use that when there is less than three values available and we cannot build a weighted average
                (SUM(value*diff))::DOUBLE PRECISION/(SUM(diff)), -- weighted average -- we are missing the first row, which is NULL by concept. We could estimate it with an AVG, but this would increase complexity of this query as well as create fake values in case of network, where we cannot assume that the value before the first measurement is linearly extraploateable. thus we do skip it
                AVG(value/diff) as derivative_avg, -- this is only a true derivate if value is already a difference, which is the case for energy values and for _io_ providers
                MAX(value/diff) as derivative_max, -- this is only a true derivate if value is already a difference, which is the case for energy values and for _io_ providers
                MIN(value/diff) as derivative_min, -- this is only a true derivate if value is already a difference, which is the case for energy values and for _io_ providers
                COUNT(value),
                AVG(diff) as sampling_rate_avg,
                MAX(diff) as sampling_rate_max,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY diff) AS sampling_rate_95p
            FROM lag_table
        """

        duration = Decimal(phase['end']-phase['start'])
        duration_in_s = Decimal(duration / 1_000_000)
        csv_buffer.write(generate_csv_line(run_id, 'phase_time_syscall_system', '[SYSTEM]', f"{idx:03}_{phase['name']}", duration, 'TOTAL', None, None, None, None, None, 'us'))

        # now we go through all metrics in the run and aggregate them
        for measurement_metric_id, metric, unit, detail_name in metrics: # unpack
            params = (measurement_metric_id, phase['start'], phase['end'])
            results = DB().fetch_one(select_query, params=params)

            value_sum, max_value, min_value, classic_value_avg, weighted_value_avg, derivative_avg, derivative_max, derivative_min, value_count, sampling_rate_avg, sampling_rate_max, sampling_rate_95p = results

            # no need to calculate if we have no results to work on
            # This can happen if the phase is too short
            if value_count == 0: continue

            # Since we need to LAG the table the first value will be NULL. So it means we need at least 3 rows to make a useful weighted average.
            # In case we cannot do that we use the classic average
            if value_count <= 2:
                value_avg = classic_value_avg
            else:
                value_avg = weighted_value_avg

            # we make everything Decimal so in subsequent divisions these values stay Decimal
            value_sum = Decimal(value_sum)
            value_avg = Decimal(value_avg)
            max_value = Decimal(max_value)
            min_value = Decimal(min_value)
            derivative_avg = Decimal(derivative_avg)
            derivative_max = Decimal(derivative_max)
            derivative_min = Decimal(derivative_min)
            value_count = Decimal(value_count)


            if metric in (
                'lmsensors_temperature_component',
                'lmsensors_fan_component',
                'cpu_utilization_procfs_system',
                'cpu_utilization_mach_system',
                'cpu_utilization_cgroup_container',
                'cpu_utilization_cgroup_system',
                'memory_used_cgroup_container',
                'memory_used_cgroup_system',
                'memory_used_procfs_system',
                'energy_impact_powermetrics_vm',
                'disk_used_statvfs_system',
                'cpu_frequency_sysfs_core',
                'cpu_throttling_thermal_msr_component',
                'cpu_throttling_power_msr_component',
            ):
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_avg, 'MEAN', max_value, min_value, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit))

                if metric in ('cpu_utilization_procfs_system', 'cpu_utilization_mach_system'):
                    cpu_utilization_machine = value_avg
                if metric in ('cpu_utilization_cgroup_container', 'cpu_utilization_cgroup_system', ):
                    cpu_utilization_containers[detail_name] = value_avg

            elif metric in ['network_io_cgroup_system',
                            'network_io_cgroup_container',
                            'network_io_procfs_system',
                            'disk_io_read_procfs_system',
                            'disk_io_write_procfs_system',
                            'disk_io_cgroup_container',
                            'disk_io_bytesread_powermetrics_vm',
                            'disk_io_byteswritten_powermetrics_vm',
                            'disk_io_read_cgroup_container',
                            'disk_io_write_cgroup_container',
                            'disk_io_write_cgroup_system',
                            'disk_io_read_cgroup_system',
                            ]:

                derivative_avg_s = derivative_avg * 1e6
                derivative_max_s = derivative_max * 1e6
                derivative_min_s = derivative_min * 1e6

                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", derivative_avg_s, 'MEAN', derivative_max_s, derivative_min_s, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, f"{unit}/s"))

                # we also generate a total line to see how much total data was processed
                csv_buffer.write(generate_csv_line(run_id, metric.replace('_io_', '_total_'), detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', None, None, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit))

                if metric == 'network_io_cgroup_container': # save to calculate CO2 later. We do this only for the cgroups. Not for the system to not double count
                    network_bytes_total.append(value_sum)

            elif "_energy_" in metric and unit == 'uJ':
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', None, None, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit))
                # for energy we want to deliver an extra value, the watts.
                # Here we need to calculate the average differently

                power_avg_mW = derivative_avg * 1e3
                power_max_mW = derivative_max * 1e3
                power_min_mW = derivative_min * 1e3

                csv_buffer.write(generate_csv_line(run_id, f"{metric.replace('_energy_', '_power_')}", detail_name, f"{idx:03}_{phase['name']}", power_avg_mW, 'MEAN', power_max_mW, power_min_mW, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, 'mW'))

                if sci.get('I', None) is not None:
                    value_carbon_ug = (value_sum / 3_600_000) * Decimal(sci['I'])

                    csv_buffer.write(generate_csv_line(run_id, f"{metric.replace('_energy_', '_carbon_')}", detail_name, f"{idx:03}_{phase['name']}", value_carbon_ug, 'TOTAL', None, None, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, 'ug'))

                    if '[' not in phase['name'] and metric.endswith('_machine'): # only for runtime sub phases to not double count ... needs refactor ... see comment at beginning of file
                        software_carbon_intensity_global['machine_carbon_ug'] = software_carbon_intensity_global.get('machine_carbon_ug', 0) + value_carbon_ug


                if metric.endswith('_machine'):
                    if phase['name'] == '[BASELINE]':
                        machine_power_baseline = power_avg_mW
                    else: # this will effectively happen for all subsequent phases where energy data is available
                        machine_energy_current_phase = value_sum
                        machine_power_current_phase = power_avg_mW

            else: # Default
                if metric not in ('cpu_time_powermetrics_vm', ):
                    error_helpers.log_error('Unmapped phase_stat found, using default', metric=metric, detail_name=detail_name, run_id=run_id)
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', max_value, min_value, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit))

        # after going through detail metrics, create cumulated ones
        if network_bytes_total:
            if sci.get('N', None) is not None and sci.get('I', None) is not None:
                # build the network energy by using a formula: https://www.green-coding.io/co2-formulas/
                # pylint: disable=invalid-name
                network_io_in_kWh = Decimal(sum(network_bytes_total)) / 1_000_000_000 * Decimal(sci['N'])
                network_io_in_uJ = network_io_in_kWh * 3_600_000_000_000
                csv_buffer.write(generate_csv_line(run_id, 'network_energy_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_in_uJ, 'TOTAL', None, None, None, None, None, 'uJ'))

                #power calculations
                network_io_power_in_mW = network_io_in_kWh * Decimal(3_600) / duration_in_s
                csv_buffer.write(generate_csv_line(run_id, 'network_power_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_power_in_mW, 'TOTAL', None, None, None, None, None, 'mW'))

                # co2 calculations
                network_io_carbon_in_ug = network_io_in_kWh * Decimal(sci['I']) * 1_000_000
                csv_buffer.write(generate_csv_line(run_id, 'network_carbon_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_carbon_in_ug, 'TOTAL', None, None, None, None, None, 'ug'))
            else:
                error_helpers.log_error('Cannot calculate the total network energy consumption. SCI values I and N are missing in the config.', run_id=run_id)
                network_io_carbon_in_ug = 0
        else:
            network_io_carbon_in_ug = 0

        if sci.get('EL', None) is not None and sci.get('TE', None) is not None and sci.get('RS', None) is not None:
            duration_in_years = duration_in_s / (60 * 60 * 24 * 365)
            embodied_carbon_share_g = (duration_in_years / Decimal(sci['EL']) ) * Decimal(sci['TE']) * Decimal(sci['RS'])
            embodied_carbon_share_ug = Decimal(embodied_carbon_share_g * 1_000_000)
            if '[' not in phase['name']: # only for runtime sub phases
                software_carbon_intensity_global['embodied_carbon_share_ug'] = software_carbon_intensity_global.get('embodied_carbon_share_ug', 0) + embodied_carbon_share_ug
            csv_buffer.write(generate_csv_line(run_id, 'embodied_carbon_share_machine', '[SYSTEM]', f"{idx:03}_{phase['name']}", embodied_carbon_share_ug, 'TOTAL', None, None, None, None, None, 'ug'))


        if machine_power_current_phase and machine_power_baseline and cpu_utilization_machine and cpu_utilization_containers:
            surplus_power_runtime = machine_power_current_phase - machine_power_baseline
            surplus_energy_runtime = machine_energy_current_phase - (machine_power_baseline * (Decimal(duration) / 1_000_000)) # we do not subtract phase energy here but calculate, becuase phases have different length

            total_container_utilization = Decimal(sum(cpu_utilization_containers.values()))

            for detail_name, container_utilization in cpu_utilization_containers.items():
                if int(total_container_utilization) == 0:
                    splitting_ratio = 0
                else:
                    splitting_ratio = container_utilization / total_container_utilization

                csv_buffer.write(generate_csv_line(run_id, 'psu_energy_cgroup_slice', detail_name, f"{idx:03}_{phase['name']}", machine_energy_current_phase * splitting_ratio, 'TOTAL', None, None, None, None, None, 'uJ'))
                csv_buffer.write(generate_csv_line(run_id, 'psu_power_cgroup_slice', detail_name, f"{idx:03}_{phase['name']}", machine_power_current_phase * splitting_ratio, 'TOTAL', None, None, None, None, None, 'mW'))
                csv_buffer.write(generate_csv_line(run_id, 'psu_energy_cgroup_container', detail_name, f"{idx:03}_{phase['name']}", surplus_energy_runtime * splitting_ratio, 'TOTAL', None, None, None, None, None, 'uJ'))
                csv_buffer.write(generate_csv_line(run_id, 'psu_power_cgroup_container', detail_name, f"{idx:03}_{phase['name']}", surplus_power_runtime * splitting_ratio, 'TOTAL', None, None, None, None, None, 'mW'))

    # TODO: refactor to be a metric provider. Than it can also be per phase # pylint: disable=fixme
    if software_carbon_intensity_global.get('machine_carbon_ug', None) is not None \
        and software_carbon_intensity_global.get('embodied_carbon_share_ug', None) is not None \
        and sci.get('R', 0) != 0 \
        and sci.get('R_d', None) is not None:

        csv_buffer.write(generate_csv_line(run_id, 'software_carbon_intensity_global', '[SYSTEM]', f"{runtime_phase_idx:03}_[RUNTIME]", (software_carbon_intensity_global['machine_carbon_ug'] + software_carbon_intensity_global['embodied_carbon_share_ug']) / Decimal(sci['R']), 'TOTAL', None, None, None, None, None, f"ugCO2e/{sci['R_d']}"))
    # TODO End # pylint: disable=fixme

    csv_buffer.seek(0)  # Reset buffer position to the beginning
    DB().copy_from(
        csv_buffer,
        table='phase_stats',
        sep=',',
        columns=('run_id', 'metric', 'detail_name', 'phase', 'value', 'type', 'max_value', 'min_value', 'sampling_rate_avg', 'sampling_rate_max', 'sampling_rate_95p', 'unit', 'created_at')
    )
    csv_buffer.close()  # Close the buffer

    if runtime_phase_idx:
        reconstruct_runtime_phase(run_id, runtime_phase_idx)
