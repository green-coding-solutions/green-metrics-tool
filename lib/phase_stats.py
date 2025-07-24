#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from decimal import Decimal
from io import StringIO

from lib.global_config import GlobalConfig
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
    config = GlobalConfig().config

    if not sci:
        sci = {}

    software_carbon_intensity_global = {}

    query = """
            SELECT id, metric, unit, detail_name, sampling_rate_configured
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
        machine_carbon_ug = None # reset
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
                (SUM(value*diff))::DOUBLE PRECISION/(SUM(diff)), -- weighted average -- we are missing the first row, which is NULL by concept. We could estimate it with an AVG, but this would increase complexity of this query for diminishing results the longer the measurement runs. we thus skip that
                COUNT(value),
                AVG(diff) as sampling_rate_avg,
                MAX(diff) as sampling_rate_max,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY diff) AS sampling_rate_95p
            FROM lag_table
        """

        duration = Decimal(phase['end']-phase['start'])
        duration_in_s = duration / 1_000_000
        csv_buffer.write(generate_csv_line(run_id, 'phase_time_syscall_system', '[SYSTEM]', f"{idx:03}_{phase['name']}", duration, 'TOTAL', None, None, None, None, None, 'us'))

        # now we go through all metrics in the run and aggregate them
        for measurement_metric_id, metric, unit, detail_name, sampling_rate_configured in metrics: # unpack
            # -- saved for future if I need lag time query
            #    WITH times as (
            #        SELECT id, value, time, (time - LAG(time) OVER (ORDER BY detail_name ASC, time ASC)) AS diff, unit
            #        FROM measurements
            #        WHERE run_id = %s AND metric = %s
            #        ORDER BY detail_name ASC, time ASC
            #    ) -- Backlog: if we need derivatives / integrations in the future

            params = (measurement_metric_id, phase['start'], phase['end'])
            results = DB().fetch_one(select_query, params=params)

            value_sum, max_value, min_value, classic_avg_value, weighted_avg_value, value_count, sampling_rate_avg, sampling_rate_max, sampling_rate_95p = results

            # no need to calculate if we have no results to work on
            # This can happen if the phase is too short
            if value_count == 0: continue

            # Since we need to LAG the table the first value will be NULL. So it means we need at least 3 rows to make a useful weighted average.
            # In case we cannot do that we use the classic average
            if value_count <= 2:
                avg_value = classic_avg_value
            else:
                avg_value = weighted_avg_value

            # we make everything Decimal so in subsequent divisions these values stay Decimal
            value_sum = Decimal(value_sum)
            avg_value = Decimal(avg_value)
            max_value = Decimal(max_value)
            min_value = Decimal(min_value)
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
                'power_limit_throttling_status',
                'thermal_throttling_status',
            ):
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", avg_value, 'MEAN', max_value, min_value, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit))

                if metric in ('cpu_utilization_procfs_system', 'cpu_utilization_mach_system'):
                    cpu_utilization_machine = avg_value
                if metric in ('cpu_utilization_cgroup_container', 'cpu_utilization_cgroup_system', ):
                    cpu_utilization_containers[detail_name] = avg_value

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

                # if we only have one value, we cannot determine the effective sampling rate.
                # Thus we have to use the configured sampling_rate from the settings
                if value_count == 1:
                    sampling_rate_avg = sampling_rate_max = sampling_rate_95p = Decimal(sampling_rate_configured)*1000

                # I/O values should be per second. However we have very different timing intervals.
                # So we do not directly use the average here, as this would be the average per sampling frequency. We go through the duration
                if not sampling_rate_avg:
                    raise RuntimeError(f"Sampling rate (AVG) was missing and avg_value_per_s could not be derived for metric provider: {metric}")
                provider_conversion_factor_to_s = Decimal(round(sampling_rate_avg)/1_000_000)
                max_value_per_s = max_value/provider_conversion_factor_to_s
                min_value_per_s = min_value/provider_conversion_factor_to_s
                avg_value_per_s = avg_value/provider_conversion_factor_to_s

                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", avg_value_per_s, 'MEAN', max_value_per_s, min_value_per_s, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, f"{unit}/s"))

                # we also generate a total line to see how much total data was processed
                csv_buffer.write(generate_csv_line(run_id, metric.replace('_io_', '_total_'), detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', None, None, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit))

                if metric == 'network_io_cgroup_container': # save to calculate CO2 later. We do this only for the cgroups. Not for the system to not double count
                    network_bytes_total.append(value_sum)

            elif "_energy_" in metric and unit == 'uJ':
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', None, None, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit))
                # for energy we want to deliver an extra value, the watts.
                # Here we need to calculate the average differently
                power_avg = (value_sum * 10**3) / duration
                power_max = (max_value * 10**3) / (duration / value_count)
                power_min = (min_value * 10**3) / (duration / value_count)
                csv_buffer.write(generate_csv_line(run_id, f"{metric.replace('_energy_', '_power_')}", detail_name, f"{idx:03}_{phase['name']}", power_avg, 'MEAN', power_max, power_min, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, 'mW'))

                if metric.endswith('_machine') and sci.get('I', None) is not None:
                    machine_carbon_ug = (value_sum / 3_600_000) * Decimal(sci['I'])
                    if '[' not in phase['name']: # only for runtime sub phases
                        software_carbon_intensity_global['machine_carbon_ug'] = software_carbon_intensity_global.get('machine_carbon_ug', 0) + machine_carbon_ug

                    csv_buffer.write(generate_csv_line(run_id, f"{metric.replace('_energy_', '_carbon_')}", detail_name, f"{idx:03}_{phase['name']}", machine_carbon_ug, 'TOTAL', None, None, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, 'ug'))

                    if phase['name'] == '[BASELINE]':
                        machine_power_baseline = power_avg
                    else: # this will effectively happen for all subsequent phases where energy data is available
                        machine_energy_current_phase = value_sum
                        machine_power_current_phase = power_avg

            else: # Default
                if metric not in ('cpu_time_powermetrics_vm', ):
                    error_helpers.log_error('Unmapped phase_stat found, using default', metric=metric, detail_name=detail_name, run_id=run_id)
                csv_buffer.write(generate_csv_line(run_id, metric, detail_name, f"{idx:03}_{phase['name']}", value_sum, 'TOTAL', max_value, min_value, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit))

        # after going through detail metrics, create cumulated ones
        if network_bytes_total:
            # build the network energy
            # network via formula: https://www.green-coding.io/co2-formulas/
            # pylint: disable=invalid-name
            network_io_in_kWh = Decimal(sum(network_bytes_total)) / 1_000_000_000 * Decimal(0.002651650429449553)
            network_io_in_uJ = network_io_in_kWh * 3_600_000_000_000
            csv_buffer.write(generate_csv_line(run_id, 'network_energy_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_in_uJ, 'TOTAL', None, None, None, None, None, 'uJ'))
            # co2 calculations
            network_io_carbon_in_ug = network_io_in_kWh * Decimal(config['sci']['I']) * 1_000_000
            if '[' not in phase['name']: # only for runtime sub phases
                software_carbon_intensity_global['network_io_carbon_in_ug'] = software_carbon_intensity_global.get('network_io_carbon_in_ug', 0) + network_io_carbon_in_ug
            csv_buffer.write(generate_csv_line(run_id, 'network_carbon_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_carbon_in_ug, 'TOTAL', None, None, None, None, None, 'ug'))
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

    # TODO: refactor to be a metric provider. Than it can also be per phase
    if software_carbon_intensity_global.get('machine_carbon_ug', None) is not None \
        and software_carbon_intensity_global.get('embodied_carbon_share_ug', None) is not None \
        and sci.get('R', 0) != 0 \
        and sci.get('R_d', None) is not None:

        csv_buffer.write(generate_csv_line(run_id, 'software_carbon_intensity_global', '[SYSTEM]', f"{runtime_phase_idx:03}_[RUNTIME]", (software_carbon_intensity_global['machine_carbon_ug'] + software_carbon_intensity_global['embodied_carbon_share_ug'] + software_carbon_intensity_global.get('network_io_carbon_in_ug', 0)) / Decimal(sci['R']), 'TOTAL', None, None, None, None, None, f"ugCO2e/{sci['R_d']}"))
    # TODO End

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
