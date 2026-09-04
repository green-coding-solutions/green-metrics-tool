#!/usr/bin/env python3

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import bisect
import math
from decimal import Decimal
from io import StringIO

from lib.db import DB
from lib import error_helpers

MAX_POSTGRES_BIGINT = 2**63 - 1

def _is_carbon_intensity_metric(metric, unit):
    # Matched by naming convention (any provider under metric_providers/carbon/intensity/*/machine) instead of
    # an explicit list of provider names, so a newly added provider is picked up automatically. The unit check
    # excludes metrics like carbon_intensitylevel_electricitymaps_machine, which also matches the naming
    # convention but reports a categorical 1/2/3 'level' rather than an actual gCO2e/kWh value and must never
    # be used as the source for the SCI carbon math.
    return metric.startswith('carbon_intensity_') and metric.endswith('_machine') and unit == 'gCO2e/kWh'

# Metrics whose providers do not sample anything but emit a value that stays in effect until the next
# one, and pad it onto a time grid (metric_providers/carbon/intensity/helpers.py) so it looks like a
# sampled metric. _compute_metric_phase_stats() must treat such a step function differently at the
# phase boundaries. A new provider that pads this way must be registered here, just like every new
# metric must be registered in the MEAN / TOTAL mapping in build_and_store_phase_stats().
STEP_FUNCTION_METRICS = (
    'carbon_intensity_static_machine',
    'carbon_intensity_electricity_maps_machine',
    'carbon_intensity_elephant_machine',
    'carbon_intensitylevel_electricitymaps_machine',
)

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
                MAX(max_value),
                MIN(min_value),
                AVG(sampling_rate_avg), -- approx, but good enough for overview.
                MAX(sampling_rate_max),
                AVG(sampling_rate_95p), -- approx, but good enough for overview
                unit,
                NOW()
            FROM phase_stats
            WHERE run_id = %s AND phase NOT LIKE '%%[%%' AND hidden IS FALSE
            GROUP BY run_id, metric, detail_name, type, unit
            ORDER BY MAX(id) ASC
        ''', params=(f"{runtime_phase_idx:03}_[RUNTIME]", run_id, ))

    # now we need to actually fix the totals. This is done in a separate step as we could not reference the total phase
    # time for the runtime phases and their aggreagate value in one query

    result = DB().fetch_one(
        "SELECT value FROM phase_stats WHERE phase = %s AND run_id = %s AND metric = 'phase_time_syscall_system' AND detail_name = '[SYSTEM]' AND unit = 'us' AND type = 'TOTAL' AND hidden IS FALSE ",
        params=(f"{runtime_phase_idx:03}_[RUNTIME]", run_id,)
    )
    if not result or result == []:
        return # can happen if no runtime phase was produced data

    total_runtime_sub_phase_duration = result[0]

    DB().query('''
        WITH tvt as (
            SELECT
                metric, detail_name, unit,
                (SELECT p2.value FROM phase_stats as p2 WHERE p2.metric = 'phase_time_syscall_system' AND p2.detail_name = '[SYSTEM]' AND p2.unit = 'us' AND p2.run_id = phase_stats.run_id AND p2.phase = phase_stats.phase) as time_of_the_sub_phase,
                value
            FROM phase_stats
            WHERE run_id = %s AND phase NOT LIKE '%%[%%' AND hidden IS FALSE AND type = 'MEAN'
        )
        UPDATE phase_stats
            SET value =
                -- we divide by /s here inside the bracket to make it more numerically stable. The sum of tvt*value * tvt.time_... will get too large otherwise
                (
                    SELECT ROUND(COALESCE(SUM(tvt.value * (tvt.time_of_the_sub_phase::DOUBLE PRECISION / %s)), 0))
                    FROM tvt WHERE tvt.metric = phase_stats.metric AND tvt.detail_name = phase_stats.detail_name AND tvt.unit = phase_stats.unit
                )::BIGINT

        WHERE phase = %s AND run_id = %s AND type = 'MEAN'
        ''', params=(run_id, total_runtime_sub_phase_duration, f"{runtime_phase_idx:03}_[RUNTIME]", run_id)
    )


def generate_csv_line(hidden, run_id, metric, detail_name, phase_name, value, value_type, max_value, min_value, sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit):
    # else '' resolves to NULL
    return f"{hidden},{run_id},{metric},{detail_name},{phase_name},{round(value)},{value_type},{round(max_value) if max_value is not None else ''},{round(min_value) if min_value is not None else ''},{round(sampling_rate_avg) if sampling_rate_avg is not None else ''},{round(sampling_rate_max) if sampling_rate_max is not None else ''},{round(sampling_rate_95p) if sampling_rate_95p is not None else ''},{unit},NOW()\n"


def _percentile_cont(sorted_values, p):
    # mirrors postgres' percentile_cont(p) WITHIN GROUP (ORDER BY ...): linear interpolation
    # between the two closest ranks. sorted_values must not contain None/NULL entries.
    n = len(sorted_values)
    if n == 0:
        return None
    if n == 1:
        return float(sorted_values[0])
    rank = p * (n - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(sorted_values[lower])
    frac = rank - lower
    return float(sorted_values[lower] + frac * (sorted_values[upper] - sorted_values[lower]))


def _compute_metric_phase_stats(times, values, phase_start, phase_end, next_phase_start, duration, step_function=False):
    # Re-implements in Python what used to be a per (metric, phase) SQL query against
    # measurement_values: sum/max/min/avg over the phase, a time-weighted average and
    # a derivative (both based on a LAG-style diff to the previous sample), plus the
    # sampling rate stats. `times`/`values` must already be sorted by time ascending.
    #
    # To be able to compute a diff/derivative at the phase boundary, the first sample
    # at or after phase_end (but still before the next phase starts) is folded into the
    # aggregates too - exactly like the previous query's "next_one" CTE did.
    # Derivative Values
    # These are only a true derivate if value is already a difference, which is the case for energy values
    # and for _io_ providers or any other that outputs increments instead of totals
    # using the derivative for other providers makes no sense atm

    left = bisect.bisect_right(times, phase_start)
    right = bisect.bisect_left(times, phase_end)

    combined_times = list(times[left:right])
    combined_values = list(values[left:right])

    # Which ONE sample from outside the phase boundaries may be used depends on what a sample means:
    #
    # - A step function (see STEP_FUNCTION_METRICS): the sample at time t is the value in effect
    #   FROM t onward. So the value at phase_start is the last sample at or before it. It belongs to
    #   this phase even if no padded grid point falls inside the boundaries, which is the case for
    #   phases shorter than the padding interval. We add it as a virtual sample at phase_start.
    #   The sample after phase_end is never used, it may already hold a value that was not in effect
    #   during this phase.
    #
    # - A sampled quantity (energy, utilization, network, ... - everything else): the sample at time t
    #   describes the interval that ENDS at t. The first sample after phase_end may still contain
    #   activity from the tail of the phase, e.g. the kernel reporting during the sleep of the sampler,
    #   so it is folded in unless it already belongs to the next phase. This is the "phase padding".
    if step_function and left > 0: # left == 0: provider only came up after phase_start, nothing to carry in
        combined_times.insert(0, phase_start)
        combined_values.insert(0, values[left - 1])

    if not combined_values:
        # No sample at all -> no value. We deliberately do not pad an empty phase with the next sample,
        # as that would report the same energy for a 10ms and a 1ms window at a 100ms sampling rate.
        # Even with one real sample the error of the padding is still substantial
        # (100 ms + 10 ms => 2 samples @ 100ms sampling rate ==> energy of a 200 ms window instead of 110 ms),
        # but here we at least have seen something. This could be improved by forcing a sample tick
        # in the provider at the phase boundaries.
        return {
            'value_sum': None, 'max_value': None, 'min_value': None, 'value_avg': None,
            'derivative_avg': None, 'derivative_max': None, 'derivative_min': None, 'value_count': 0,
            'sampling_rate_avg': None, 'sampling_rate_max': None, 'sampling_rate_95p': None,
        }

    if not step_function and right < len(times) and times[right] < next_phase_start:
        combined_times.append(times[right])
        combined_values.append(values[right])

    # we make everything Decimal so in subsequent divisions these values stay Decimal
    value_count = Decimal(len(combined_values))
    value_sum = Decimal(sum(combined_values))
    max_value = Decimal(max(combined_values))
    min_value = Decimal(min(combined_values))
    classic_value_avg = Decimal(value_sum) / Decimal(value_count)

    # sampling rate is derivable as soon as there is at least one diff between two samples,
    # independent of whether that diff is trusted enough to build the weighted average from
    # (see the value_count <= 2 case below) - this matches the original query, where the LAG-based
    # diff column was never gated on how many rows the phase had.
    if value_count > 1:
        weighted_num = Decimal(0)
        weighted_den = 0
        derivative_values = []
        diff_values = []
        # index 0 has no predecessor, its diff is NULL by concept
        # We could estimate it with an AVG, but this would increase complexity of this query as well as create fake values in case of network,
        # where we cannot assume that the value before the first measurement is linearly extraploateable. thus we do skip it
        for i in range(1, int(value_count)):
            diff = combined_times[i] - combined_times[i - 1]
            weighted_num += Decimal(combined_values[i]) * diff
            weighted_den += diff
            derivative_values.append(Decimal(combined_values[i]) / diff) # can flake with division by zero if database is corrupted which should never be. Thus no guard. we simply fail
            diff_values.append(diff)
        weighted_value_avg = weighted_num / Decimal(weighted_den)

        weighted_derivative_avg = sum(derivative_values) / len(derivative_values)
        weighted_derivative_max = max(derivative_values)
        weighted_derivative_min = min(derivative_values)

        sampling_rate_avg = sum(diff_values) / len(diff_values)
        sampling_rate_max = max(diff_values)
        sampling_rate_95p = _percentile_cont(sorted(diff_values), 0.95)
    else:
        sampling_rate_avg = sampling_rate_max = sampling_rate_95p = None

    # Since we need to LAG the table the first value will be NULL. So it means we need at least
    # 3 rows to make a useful weighted average. In case we cannot do that we use the classic average.
    if value_count in (1,2):
        value_avg = classic_value_avg
        # This derivative is only an approximation, but better than delivering no value as it is at least based on one sample
        derivative_avg = classic_value_avg / (duration / value_count)
        derivative_max = Decimal(max_value) / (duration / value_count)
        derivative_min = Decimal(min_value) / (duration / value_count)
    else:
        value_avg = weighted_value_avg # pylint: disable=possibly-used-before-assignment
        derivative_avg = weighted_derivative_avg # pylint: disable=possibly-used-before-assignment
        derivative_max = weighted_derivative_max # pylint: disable=possibly-used-before-assignment
        derivative_min = weighted_derivative_min # pylint: disable=possibly-used-before-assignment


    return {
        'value_sum': value_sum, 'max_value': max_value, 'min_value': min_value, 'value_avg': value_avg,
        'derivative_avg': derivative_avg, 'derivative_max': derivative_max, 'derivative_min': derivative_min, 'value_count': value_count,
        'sampling_rate_avg': sampling_rate_avg, 'sampling_rate_max': sampling_rate_max, 'sampling_rate_95p': sampling_rate_95p,
    }



def build_and_store_phase_stats(run_id, sci=None, sci_metrics=None):
    if not sci:
        sci = {}
    if not sci_metrics:
        sci_metrics = []

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

    # Determined once here, from the full set of metrics available for the run, instead of inside the
    # per-phase/per-metric loop below. Doing it there made the outcome depend on iteration order: whichever
    # metric happened to be processed first would see chosen_carbon_metric_name still as None, so any
    # '_carbon_' metric processed before its matching carbon_intensity_* metric silently failed to
    # accumulate into sci_phase_data['machine_carbon_ug'].
    chosen_carbon_metric_name = None
    for _, metric, unit, _ in metrics:
        if _is_carbon_intensity_metric(metric, unit):
            chosen_carbon_metric_name = metric
            break

    query = """
        SELECT phases
        FROM runs
        WHERE id = %s
        """
    phase_data = DB().fetch_one(query, (run_id, ))

    if not phase_data or not phase_data[0]:
        error_helpers.log_error('Phases object was empty and no phase_stats could be created. This can happen for failed runs, but should be very rare ...', run_id=run_id)
        return

    phases = phase_data[0]

    # Fetch every measurement value for the whole run in one go, pre-ordered by metric and
    # time, instead of issuing one SELECT per (phase, metric) pair further down. All the
    # window/aggregate math that used to live in that per-pair SQL query is now done in
    # _compute_metric_phase_stats() on these in-memory, per-metric time series.
    #
    # Note: This function is suprisingly efficient on CPU as even a 3 hour run only takes 11 seconds to process here
    # However it is very costly on memory as a 3 hour run uses 800 MB resident memory here
    # If we ever want to support really long runs like 24h+ or even monitoring mode this must be chunked / stream
    # or we need to process it on a machine directly locally connected to the database to not have connection overhead

    measurement_values_query = """
        SELECT mv.measurement_metric_id, mv.time, mv.value
        FROM measurement_values mv
        JOIN measurement_metrics mm ON mm.id = mv.measurement_metric_id
        WHERE mm.run_id = %s
        ORDER BY mv.measurement_metric_id ASC, mv.time ASC
    """
    metric_time_series = {}
    for measurement_metric_id, m_time, m_value in DB().fetch_all(measurement_values_query, (run_id, )):
        metric_time_series.setdefault(measurement_metric_id, ([], []))
        metric_time_series[measurement_metric_id][0].append(m_time)
        metric_time_series[measurement_metric_id][1].append(m_value)

    csv_buffer = StringIO()

    machine_power_baseline = None
    runtime_phase_idx = None

    for idx, phase in enumerate(phases):
        if phase['name'] == '[RUNTIME]': # do not process runtime like this, but rather reconstruct it later. Still advance the idx counter though as we want to use the number later
            runtime_phase_idx = idx
            continue

        # reset all phase specific values
        phase_warnings = set()
        network_bytes_total = [] # we use array here and sum later, because checking for 0 alone not enough
        cpu_utilization_containers = {}
        cpu_utilization_machine = None
        network_io_carbon_in_ug = None
        carbon_intensity = None
        sci_phase_data = {}
        sci_phase_data_custom = {}
        machine_power_current_phase = None
        machine_energy_current_phase = None

        duration = Decimal(phase['end']-phase['start'])
        next_phase_start = phases[idx+1]['start'] if idx+1 < len(phases) else MAX_POSTGRES_BIGINT
        duration_in_s = Decimal(duration / 1_000_000)
        csv_buffer.write(generate_csv_line(phase['hidden'], run_id, 'phase_time_syscall_system', '[SYSTEM]', f"{idx:03}_{phase['name']}", duration, 'TOTAL', None, None, None, None, None, 'us'))

        # we go through all metrics in the run and aggregate them, using the pre-fetched
        # per-metric time series instead of running a SELECT per (phase, metric) pair
        for measurement_metric_id, metric, unit, detail_name in metrics: # unpack
            times = metric_time_series[measurement_metric_id][0] # can fail if metric does not exist. This should never be. Thus we simply crash
            values = metric_time_series[measurement_metric_id][1] # can fail if metric does not exist. This should never be. Thus we simply crash

            is_step_function_metric = metric in STEP_FUNCTION_METRICS

            metric_stats = _compute_metric_phase_stats(times, values, phase['start'], phase['end'], next_phase_start, duration, step_function=is_step_function_metric)

            # no need to calculate if we have no results to work on
            # This can happen if the phase is too short
            if metric_stats['value_count'] == 0:
                continue

            if _is_carbon_intensity_metric(metric, unit):
                if metric == chosen_carbon_metric_name:
                    carbon_intensity = metric_stats['value_avg']
                else:
                    phase_warnings.add(f"More than one carbon intensity provider is configured. Now using {chosen_carbon_metric_name}")

            # Dynamic undersampling warning: flag when actual samples < 50% of what the observed
            # sampling rate implies we should have received over the phase duration.
            # Custom metrics are not flagged. Neither are step functions: their value holds for the whole
            # interval by definition, so the sample count says nothing about the accuracy of the MEAN.
            if not metric.startswith('custom_') and not is_step_function_metric:
                if metric_stats['sampling_rate_avg'] is not None and metric_stats['sampling_rate_avg'] > 0:
                    # sampling_rate_avg and duration are both in microseconds
                    expected_samples = duration / Decimal(metric_stats['sampling_rate_avg'])
                    is_undersampled = Decimal(metric_stats['value_count']) < expected_samples * Decimal('0.5')
                else:
                    # value_count == 1: no LAG diff available, cannot estimate rate — always undersampled
                    is_undersampled = True
                if is_undersampled:
                    phase_warnings.add(f"Very few samples (< 50% of observed duration or < 2) encountered in phase '{phase['name']}' and metric '{metric}', MEAN values might be inaccurate")

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
                'cpu_frequency_msr_core',
                'cpu_throttling_thermal_msr_component',
                'cpu_throttling_power_msr_component',
                'carbon_intensity_elephant_machine',
                'carbon_intensity_electricity_maps_machine',
                'carbon_intensity_static_machine',
                'carbon_intensitylevel_electricitymaps_machine',
            ):
                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, metric, detail_name, f"{idx:03}_{phase['name']}", metric_stats['value_avg'], 'MEAN', metric_stats['max_value'], metric_stats['min_value'], metric_stats['sampling_rate_avg'], metric_stats['sampling_rate_max'], metric_stats['sampling_rate_95p'], unit))

                if metric in ('cpu_utilization_procfs_system', 'cpu_utilization_mach_system'):
                    cpu_utilization_machine = metric_stats['value_avg']
                if metric in ('cpu_utilization_cgroup_container', 'cpu_utilization_cgroup_system', ):
                    cpu_utilization_containers[detail_name] = metric_stats['value_avg']
                if metric in ('cpu_throttling_thermal_msr_component', 'cpu_throttling_power_msr_component') and metric_stats['max_value']:
                    throttle_kind = 'Thermal' if metric == 'cpu_throttling_thermal_msr_component' else 'Power limit'
                    phase_warnings.add(f"{throttle_kind} throttling detected on {detail_name} during phase '{phase['name']}'. Measurements might be inaccurate.")

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

                derivative_avg_s = metric_stats['derivative_avg'] * Decimal(1e6)
                derivative_max_s = metric_stats['derivative_max'] * Decimal(1e6)
                derivative_min_s = metric_stats['derivative_min'] * Decimal(1e6)

                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, metric, detail_name, f"{idx:03}_{phase['name']}", derivative_avg_s, 'MEAN', derivative_max_s, derivative_min_s, metric_stats['sampling_rate_avg'], metric_stats['sampling_rate_max'], metric_stats['sampling_rate_95p'], f"{unit}/s"))

                # we also generate a total line to see how much total data was processed
                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, metric.replace('_io_', '_total_'), detail_name, f"{idx:03}_{phase['name']}", metric_stats['value_sum'], 'TOTAL', None, None, metric_stats['sampling_rate_avg'], metric_stats['sampling_rate_max'], metric_stats['sampling_rate_95p'], unit))

                if metric == 'network_io_cgroup_container': # save to calculate CO2 later. We do this only for the cgroups. Not for the system to not double count
                    network_bytes_total.append(metric_stats['value_sum'])

            elif metric in ('cpu_time_powermetrics_vm', ):
                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, metric, detail_name, f"{idx:03}_{phase['name']}", metric_stats['value_sum'], 'TOTAL', metric_stats['max_value'], metric_stats['min_value'], metric_stats['sampling_rate_avg'], metric_stats['sampling_rate_max'], metric_stats['sampling_rate_95p'], unit))

            elif "_energy_" in metric and unit == 'uJ':
                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, metric, detail_name, f"{idx:03}_{phase['name']}", metric_stats['value_sum'], 'TOTAL', None, None, metric_stats['sampling_rate_avg'], metric_stats['sampling_rate_max'], metric_stats['sampling_rate_95p'], unit))

                power_avg_mW = metric_stats['derivative_avg'] * Decimal(1e3)
                power_max_mW = metric_stats['derivative_max'] * Decimal(1e3)
                power_min_mW = metric_stats['derivative_min'] * Decimal(1e3)

                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, f"{metric.replace('_energy_', '_power_')}", detail_name, f"{idx:03}_{phase['name']}", power_avg_mW, 'MEAN', power_max_mW, power_min_mW, metric_stats['sampling_rate_avg'], metric_stats['sampling_rate_max'], metric_stats['sampling_rate_95p'], 'mW'))

                if metric.endswith('_machine'):
                    if phase['name'] == '[BASELINE]':
                        machine_power_baseline = power_avg_mW
                    else: # this will effectively happen for all subsequent phases where energy data is available
                        machine_energy_current_phase = metric_stats['value_sum']
                        machine_power_current_phase = power_avg_mW

            elif '_carbon_' in metric and unit in ('ug', 'ugCO2e'):
                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, metric, detail_name, f"{idx:03}_{phase['name']}", metric_stats['value_sum'], 'TOTAL', None, None, metric_stats['sampling_rate_avg'], metric_stats['sampling_rate_max'], metric_stats['sampling_rate_95p'], unit))

                if metric.endswith('_machine') and chosen_carbon_metric_name is not None and chosen_carbon_metric_name in detail_name:
                    sci_phase_data['machine_carbon_ug'] = sci_phase_data.get('machine_carbon_ug', 0) + Decimal(metric_stats['value_sum'])

            else: # Default
                if metric.startswith('custom_'):
                    sci_phase_data_custom.setdefault(metric, {})[detail_name] = {'value': metric_stats['value_sum'], 'unit': unit}
                else:
                    error_helpers.log_error('Unmapped phase_stat found, using default', metric=metric, detail_name=detail_name, run_id=run_id)

                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, metric, detail_name, f"{idx:03}_{phase['name']}", metric_stats['value_sum'], 'TOTAL', metric_stats['max_value'], metric_stats['min_value'], metric_stats['sampling_rate_avg'], metric_stats['sampling_rate_max'], metric_stats['sampling_rate_95p'], unit))


        # after going through detail metrics, create cumulated ones
        if network_bytes_total:
            if sci.get('N', None) is not None:
                # build the network energy by using a formula: https://www.green-coding.io/co2-formulas/
                # pylint: disable=invalid-name
                network_io_in_kWh = Decimal(sum(network_bytes_total)) / 1_000_000_000 * Decimal(sci['N'])
                network_io_in_uJ = network_io_in_kWh * 3_600_000_000_000
                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, 'network_energy_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_in_uJ, 'TOTAL', None, None, None, None, None, 'uJ'))

                #power calculations
                network_io_power_in_mW = network_io_in_kWh * Decimal(3_600) / duration_in_s
                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, 'network_power_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_power_in_mW, 'TOTAL', None, None, None, None, None, 'mW'))

                # co2 calculations
                if carbon_intensity is not None:
                    network_io_carbon_in_ug = network_io_in_kWh * Decimal(carbon_intensity) * 1_000_000
                    csv_buffer.write(generate_csv_line(phase['hidden'], run_id, 'network_carbon_formula_global', '[FORMULA]', f"{idx:03}_{phase['name']}", network_io_carbon_in_ug, 'TOTAL', None, None, None, None, None, 'ug'))
                else:
                    error_helpers.log_error('Cannot calculate the total network carbon consumption. No carbon intensity provider data was found. Configure a carbon_intensity_*_machine provider (e.g. carbon_intensity_static_machine) in the config.', run_id=run_id)
                    network_io_carbon_in_ug = 0
            else:
                error_helpers.log_error('Cannot calculate the total network energy consumption. SCI value N is missing in the config.', run_id=run_id)
                network_io_carbon_in_ug = 0
        else:
            network_io_carbon_in_ug = 0

        if sci.get('EL', None) is not None and sci.get('TE', None) is not None and sci.get('RS', None) is not None:
            duration_in_years = duration_in_s / (60 * 60 * 24 * 365)
            embodied_carbon_share_g = (duration_in_years / Decimal(sci['EL']) ) * Decimal(sci['TE']) * Decimal(sci['RS'])
            embodied_carbon_share_ug = Decimal(embodied_carbon_share_g * 1_000_000)
            sci_phase_data['embodied_carbon_share_ug'] = sci_phase_data.get('embodied_carbon_share_ug', 0) + embodied_carbon_share_ug
            csv_buffer.write(generate_csv_line(phase['hidden'], run_id, 'embodied_carbon_share_machine', '[SYSTEM]', f"{idx:03}_{phase['name']}", embodied_carbon_share_ug, 'TOTAL', None, None, None, None, None, 'ug'))


        if machine_power_current_phase and machine_power_baseline and cpu_utilization_machine and cpu_utilization_containers:
            surplus_power_runtime = machine_power_current_phase - machine_power_baseline
            surplus_energy_runtime = machine_energy_current_phase - (machine_power_baseline * duration * Decimal('1e-3')) # we cannot directly subtract baseline energy, but need to stretch it to not subtract phase energy here but calculate, bc phases have different length

            total_container_utilization = Decimal(sum(cpu_utilization_containers.values()))

            for detail_name, container_utilization in cpu_utilization_containers.items():
                if int(total_container_utilization) == 0:
                    splitting_ratio = 0
                else:
                    splitting_ratio = container_utilization / total_container_utilization

                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, 'psu_energy_cgroup_slice', detail_name, f"{idx:03}_{phase['name']}", machine_energy_current_phase * splitting_ratio, 'TOTAL', None, None, None, None, None, 'uJ'))
                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, 'psu_power_cgroup_slice', detail_name, f"{idx:03}_{phase['name']}", machine_power_current_phase * splitting_ratio, 'MEAN', None, None, None, None, None, 'mW'))
                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, 'psu_energy_cgroup_container', detail_name, f"{idx:03}_{phase['name']}", surplus_energy_runtime * splitting_ratio, 'TOTAL', None, None, None, None, None, 'uJ'))
                csv_buffer.write(generate_csv_line(phase['hidden'], run_id, 'psu_power_cgroup_container', detail_name, f"{idx:03}_{phase['name']}", surplus_power_runtime * splitting_ratio, 'MEAN', None, None, None, None, None, 'mW'))

        if sci_metrics and sci_phase_data_custom \
            and sci_phase_data.get('machine_carbon_ug', None) is not None \
            and sci_phase_data.get('embodied_carbon_share_ug', None) is not None:

            for sci_metric in sci_metrics:
                if sci_phase_data_custom.get(sci_metric):
                    for detail_name, metric_data in sci_phase_data_custom[sci_metric].items():
                        if metric_data['value']:
                            csv_buffer.write(generate_csv_line(phase['hidden'], run_id, f"{sci_metric}_sci_global", detail_name, f"{idx:03}_{phase['name']}", (sci_phase_data['machine_carbon_ug'] + sci_phase_data['embodied_carbon_share_ug']) / Decimal(metric_data['value']), 'TOTAL', None, None, None, None, None, f"ugCO2e/{metric_data['unit']}"))
                        else:
                            phase_warnings.add(f"Custom metric '{sci_metric} [{detail_name}]'  had a total value of 0 and thus SCI could not be calculated (Division by zero error)")


        for phase_warning in phase_warnings:
            DB().query("INSERT INTO warnings (run_id, message) VALUES (%s, %s)", (run_id, phase_warning))


    csv_buffer.seek(0)  # Reset buffer position to the beginning
    DB().copy_from(
        csv_buffer,
        table='phase_stats',
        sep=',',
        columns=('hidden', 'run_id', 'metric', 'detail_name', 'phase', 'value', 'type', 'max_value', 'min_value', 'sampling_rate_avg', 'sampling_rate_max', 'sampling_rate_95p', 'unit', 'created_at')
    )
    csv_buffer.close()  # Close the buffer

    if runtime_phase_idx is not None:
        reconstruct_runtime_phase(run_id, runtime_phase_idx)
