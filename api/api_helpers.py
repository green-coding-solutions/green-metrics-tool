import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from cachetools import cached, TTLCache, Cache
from collections import OrderedDict
from functools import cache
import typing
import uuid
import ipaddress
import requests
import json
import math
import time

import orjson

from starlette.background import BackgroundTask
from fastapi.responses import ORJSONResponse
from fastapi import Depends, Request, HTTPException
from fastapi.security import APIKeyHeader
import numpy as np
import scipy.stats

from psycopg import sql

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers
from lib.user import User, UserAuthenticationError
from lib.secure_variable import SecureVariable

import redis
from enum import Enum

def get_artifact(artifact_type: Enum, key: str, decode_responses=True):
    host = GlobalConfig().config['redis']['host']
    port = GlobalConfig().config['redis']['port']
    if not host:
        return None

    data = None
    try:
        r = redis.Redis(host=host, port=port, db=artifact_type.value, protocol=3, decode_responses=decode_responses)

        data = r.get(key)
    except redis.RedisError as e:
        error_helpers.log_error('Redis get_artifact failed', exception=e)

    return None if data is None or data == [] else data

def store_artifact(artifact_type: Enum, key:str, data, ex=2592000):
    host = GlobalConfig().config['redis']['host']
    port = GlobalConfig().config['redis']['port']
    if not host:
        return

    try:
        r = redis.Redis(host=host, port=port, db=artifact_type.value, protocol=3)
        r.set(key, data, ex=ex) # Expiration => 2592000 = 30 days
    except redis.RedisError as e:
        error_helpers.log_error('Redis store_artifact failed', exception=e)


# Note
# ---------------
# we do not allow a dynamic rescaling here, as we need all the units we feed into
# to be on the same order of magnitude for comparisons and calcuations
#
# Function furthemore uses .substr instead of just replacing the unit, as some units have demominators like Bytes/s or
# ugCO2e/ page request which we want to retain
#
def convert_value(value, unit, display_in_joules=False):
    compare_unit = unit.split('/', 1)[0]

    if compare_unit == 'ugCO2e':
        return [value / 1_000_000, unit[1:]]
    elif compare_unit == 'mJ':
        if display_in_joules:
            return [value / 1_000, unit[1:]]
        else:
            return [value / (3_600) , f"mWh{unit[2:]}"]
    elif compare_unit == 'uJ':
        if display_in_joules:
            return [value / 1_000_000, unit[1:]]
        else:
            return [value / (1_000 * 3_600), f"mWh{unit[2:]}"]
    elif compare_unit == 'mW':
        return [value / 1_000, unit[1:]]
    elif compare_unit == 'Ratio':
        return [value / 100, f"%{unit[5:]}"]
    elif compare_unit == 'centi°C':
        return [value / 100, unit[5:]]
    elif compare_unit == 'Hz':
        return [value / 1_000_000_000, f"G{unit}"]
    elif compare_unit == 'ns':
        return [value / 1_000_000_000, unit[1:]]
    elif compare_unit == 'us':
        return [value / 1_000_000, unit[1:]]
    elif compare_unit == 'ug':
        return [value / 1_000_000, unit[1:]]
    elif compare_unit == 'Bytes':
        return [value / 1_000_000, f"MB{unit[5:]}"]
    else:
        return [value, unit]

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def get_machine_list():
    query = """
        WITH timings as (
            SELECT
                machine_id,
                AVG(end_measurement - start_measurement)/1000000 as avg_duration
            FROM runs
            WHERE
                end_measurement IS NOT NULL
                AND created_at > NOW() - INTERVAL '30 DAY'
            GROUP BY machine_id
        ) SELECT
                m.id, m.description, m.available,
                m.status_code, m.updated_at, m.jobs_processing,
                m.gmt_hash, m.gmt_timestamp,
                m.base_temperature, m.current_temperature, m.cooldown_time_after_job,
                (SELECT COUNT(id) FROM jobs as j WHERE j.machine_id = m.id AND j.state = 'WAITING') as job_amount,
                (SELECT avg_duration FROM timings WHERE timings.machine_id = m.id )::int as avg_duration_seconds,
                m.configuration

            FROM machines as m
            ORDER BY m.available DESC, m.id ASC
            """

    return DB().fetch_all(query)

def get_run_info(user, run_id):

    run_exists = DB().fetch_one(
        "SELECT 1 FROM runs WHERE id = %s",
        params=(run_id,)
    )
    if not run_exists:
        raise HTTPException(status_code=404, detail="Run not found")

    query = """
            SELECT
                id, name, uri, branch, commit_hash,
                (SELECT STRING_AGG(t.name, ', ' ) FROM unnest(runs.categories) as elements
                    LEFT JOIN categories as t on t.id = elements) as categories,
                filename, start_measurement, end_measurement,
                measurement_config, machine_specs, machine_id, usage_scenario, containers, container_dependencies,
                created_at,
                (SELECT COUNT(id) FROM warnings as w WHERE w.run_id = runs.id) as warnings,
                phases, logs, failed, gmt_hash, runner_arguments, archived, note, public
            FROM runs
            WHERE
                (TRUE = %s OR user_id = ANY(%s::int[]) OR public = TRUE)
                AND id = %s
        """
    params = (user.is_super_user(), user.visible_users(), run_id)
    run = DB().fetch_one(query, params=params, fetch_mode='dict')

    if not run:
        raise HTTPException(status_code=403, detail="You do not have access to this run")

    return run


def get_timeline_query(user, uri, filename, usage_scenario_variables, machine_id, branch, metric, phase, start_date=None, end_date=None, detail_name=None, sorting='run'):

    if filename is None or filename.strip() == '':
        filename =  'usage_scenario.yml'

    if branch is None or branch.strip() == '':
        branch = 'main'

    params = [user.is_super_user(), user.visible_users(), uri, branch, filename, f"%{phase}"]

    metric_condition = ''
    if metric is None or metric.strip() == '' or metric.strip() == 'key':
        metric_condition =  "AND (p.metric LIKE '%%_energy_%%' OR metric = 'software_carbon_intensity_global' OR metric = 'phase_time_syscall_system') AND p.metric NOT LIKE '%%_container' AND p.metric NOT LIKE '%%_slice' "
    elif metric.strip() != 'all':
        metric_condition =  "AND p.metric = %s"
        params.append(metric)

    start_date_condition = ''
    if start_date is not None:
        start_date_condition =  "AND DATE(r.created_at) >= %s"
        params.append(start_date)

    end_date_condition = ''
    if end_date is not None:
        end_date_condition =  "AND DATE(r.created_at) <= %s"
        params.append(end_date)

    detail_name_condition = ''
    if detail_name is not None and detail_name.strip() != '':
        detail_name_condition =  "AND p.detail_name = %s"
        params.append(detail_name)

    machine_id_condition = ''
    if machine_id is not None:
        check_int_field_api(machine_id, 'machine_id', 1024) # can cause exception
        machine_id_condition =  "AND r.machine_id = %s"
        params.append(machine_id)

    usage_scenario_variables_condition = ''
    if usage_scenario_variables is not None and usage_scenario_variables.strip() != '':
        try:
            orjson.loads(usage_scenario_variables) # pylint: disable=no-member
        except orjson.JSONDecodeError as exc: # pylint: disable=no-member
            raise HTTPException(status_code=422, detail=f"Usage Scenario Variables was not correctly JSON formatted: {exc}") from exc
        usage_scenario_variables_condition = 'AND r.usage_scenario_variables::text = %s'
        params.append(usage_scenario_variables)

    sorting_condition = 'r.commit_timestamp ASC, r.created_at ASC'
    if sorting is not None and sorting.strip() == 'run':
        sorting_condition = 'r.created_at ASC, r.commit_timestamp ASC'

    query = f"""
            SELECT
                r.id, r.name, r.created_at, p.metric, p.detail_name, p.phase,
                p.value, p.unit, r.commit_hash, r.commit_timestamp, r.gmt_hash,
                row_number() OVER () AS row_num
            FROM runs as r
            LEFT JOIN phase_stats as p ON
                r.id = p.run_id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]) OR r.public = TRUE)
                AND r.uri = %s
                AND r.branch = %s
                AND r.filename = %s
                AND r.end_measurement IS NOT NULL
                AND r.failed != TRUE
                AND p.phase LIKE %s
                {metric_condition}
                {start_date_condition}
                {end_date_condition}
                {detail_name_condition}
                {machine_id_condition}
                {usage_scenario_variables_condition}
                AND r.archived = FALSE
                AND r.commit_timestamp IS NOT NULL
                AND r.failed IS FALSE
            ORDER BY
                p.metric ASC, p.detail_name ASC,
                p.phase ASC, {sorting_condition}

            """

    return (query, params)

def get_comparison_details(user, ids, comparison_db_key):

    query = sql.SQL('''
        SELECT
            id, name, created_at, uri, commit_hash, commit_timestamp, gmt_hash, usage_scenario_variables, {}
        FROM runs
        WHERE
            (TRUE = %s OR user_id = ANY(%s::int[]) OR public = TRUE)
            AND id = ANY(%s::uuid[])
        ORDER BY created_at ASC -- must be same order as get_phase_stats so that the order in the comparison bar charts aligns with the comparsion_details array
    ''').format(sql.Identifier(comparison_db_key))

    params = (user.is_super_user(), user.visible_users(), ids)
    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        raise RuntimeError('Could not get comparison details')

    comparison_details = OrderedDict()

    for row in data:
        comparison_key = str(row[8])
        run_id = str(row[0]) # UUID must be converted
        if comparison_key not in comparison_details:
            comparison_details[comparison_key] = OrderedDict()
        comparison_details[comparison_key][run_id] = {
            'run_id': run_id,
            'name': row[1],
            'created_at': row[2],
            'repo': row[3],
            'commit_hash': row[4],
            'commit_timestamp': row[5],
            'gmt_hash': row[6],
            'usage_scenario_variables': row[7]
        }

    # to back-fill None values later we need to index every element
    for item in comparison_details.values():
        for index, inner_item in enumerate(item.values()):
            inner_item['index'] = index

    return comparison_details

def determine_comparison_case(user, ids, force_mode=None):

    query = '''
            WITH uniques as (
                SELECT uri, filename, machine_id, commit_hash, branch, usage_scenario_variables
                FROM runs
                WHERE
                    (TRUE = %s OR user_id = ANY(%s::int[]) OR public = TRUE)
                    AND id = ANY(%s::uuid[])
                GROUP BY uri, filename, usage_scenario_variables, machine_id, commit_hash, branch
            )
            SELECT
                COUNT(DISTINCT uri ), COUNT(DISTINCT filename), COUNT(DISTINCT machine_id),
                COUNT(DISTINCT commit_hash ), COUNT(DISTINCT branch), COUNT(DISTINCT usage_scenario_variables)
            FROM uniques
    '''
    params = (user.is_super_user(), user.visible_users(), ids)
    data = DB().fetch_one(query, params=params)
    if data is None or data == [] or data[1] is None: # special check for data[1] as this is aggregate query which always returns result
        raise RuntimeError('Could not determine compare case')

    [repos, usage_scenarios, machine_ids, commit_hashes, branches, usage_scenario_variables] = data

    # If we have one or more measurement in a phase_stat it will currently just be averaged
    # however, when we allow comparing runs we will get same phase_stats but with different repo etc.
    # these cannot be just averaged. But they have to be split and then compared via t-test
    # For the moment I think it makes sense to restrict to two repositories. Comparing three is too much to handle I believe if we do not want to drill down to one specific metric

    # Currently we support six cases:
    # case = 'Repository' # Case D : RequirementsEngineering Case
    # case = 'Branch' # Case C_3 : SoftwareDeveloper Case
    # case = 'Usage Scenario' # Case C_2 : SoftwareDeveloper Case
    # case = 'Machine' # Case C_1 : DataCenter Case
    # case = 'Commit' # Case B: DevOps Case
    # case = 'Repeated Run' # Case A: Blue Angel
    # case = 'Usage Scenario Variables' # Case E - Quick Development Case

    if force_mode:
        match force_mode:
            case 'repos':
                return_case = ('Repository', 'uri') # Case D
            case 'usage_scenarios':
                return_case = ('Usage Scenario', 'filename') # Case C_2
            case 'machine_ids':
                return_case =  ('Machine', 'machine_id') # Case C_1
            case 'branches':
                return_case = ('Branch', 'branch') # Case C_3
            case 'commit_hashes':
                return_case = ('Commit', 'commit_hash') # Case B
            case 'usage_scenario_variables':
                return_case = ('Usage Scenario Variables', 'usage_scenario_variables') # Case E
            case _:
                raise ValueError('Forcing a comparison mode for unknown mode')

        comparison_identifiers_amount = locals()[force_mode]
        if comparison_identifiers_amount not in (1,2):
            raise RuntimeError(f"You are trying to force {force_mode} mode, but you have {comparison_identifiers_amount} comparison options. Must be 1 or 2.")

        return return_case

    ### AUTO MODE ####

    #pylint: disable=no-else-raise,no-else-return
    if repos == 2:
        if usage_scenarios > 2:
            raise RuntimeError('Different repos & more than 2 usage scenarios not supported')
        if machine_ids > 1:
            raise RuntimeError('Different repos & machines not supported')
        if branches > 2:
            raise RuntimeError('Different repos & more than 2 branches not supported')
        if commit_hashes > 2:
            raise RuntimeError('Different repos & more than 2 different commits not supported')
        if usage_scenario_variables > 2:
            raise RuntimeError('Different repos & more than 2 sets of usage scenario variables not supported')

        return ('Repository', 'uri')  # Case D

    if repos != 1:
        raise RuntimeError('Less than 1 or more than 2 repos not supported.')

    # repos == 1
    if usage_scenarios == 2:
        if machine_ids > 1:
            raise RuntimeError('Different usage scenarios & machines not supported')
        if branches > 1:
            raise RuntimeError('Different usage scenarios & branches not supported')
        if commit_hashes > 1:
            raise RuntimeError('Different usage scenarios & commits not supported')
        if usage_scenario_variables > 1:
            raise RuntimeError('Different usage scenarios & usage scenario variables not supported')

        return ('Usage Scenario', 'filename')  # Case C_2

    if usage_scenarios != 1:
        raise RuntimeError('Less than 1 or more than 2 usage scenarios per repo not supported.')

    if machine_ids == 2:
        if branches > 1:
            raise RuntimeError('Different machines & branches not supported')
        if commit_hashes > 1:
            raise RuntimeError('Different machines & commits not supported')
        if usage_scenario_variables > 1:
            raise RuntimeError('Different machines & usage scenario variables not supported')

        return ('Machine', 'machine_id')  # Case C_1

    if machine_ids != 1:
        raise RuntimeError('Less than 1 or more than 2 Machines per repo not supported.')

    if branches == 2:
        if commit_hashes > 2:
            raise RuntimeError('Different branches and more than 2 commits not supported')
        if usage_scenario_variables > 1:
            raise RuntimeError('Different branches & usage scenario variables not supported')

        return ('Branch', 'branch')  # Case C_3

    if branches != 1:
        raise RuntimeError('Less than 1 or more than 2 branches per repo not supported.')

    if commit_hashes == 2:
        if usage_scenario_variables > 1:
            raise RuntimeError('Different commit hashes & usage scenario variables not supported')
        return ('Commit', 'commit_hash')  # Case B

    if commit_hashes > 2:
        raise RuntimeError('Multiple commits comparison not supported. Please switch to Timeline view')

    if commit_hashes != 1:
        raise RuntimeError('Less than 1 or more than 2 commit hashes per repo not supported.')

    if usage_scenario_variables == 2:
        return ('Usage Scenario Variables', 'usage_scenario_variables')  # Case E

    if usage_scenario_variables > 3:
        raise RuntimeError('Multiple usage scenario variables comparison not supported.')

    if usage_scenario_variables == 1:
        return ('Repeated Run', 'commit_hash')  # Case A - Everything is identical and just repeating runs

    raise RuntimeError('Could not determine comparison case after checking all conditions')

def check_run_failed(user, ids):
    query = """
            SELECT
               COUNT(failed)
            FROM runs
            WHERE
                (TRUE = %s OR user_id = ANY(%s::int[]) OR public = TRUE)
                AND id = ANY(%s::uuid[])
                AND failed IS TRUE
            """
    params = (user.is_super_user(), user.visible_users(), ids)
    return DB().fetch_one(query, params=params)[0]

def get_phase_stats(user, ids):
    query = """
            SELECT
                a.phase, a.metric, a.detail_name, a.value, a.type, a.max_value, a.min_value,
                a.sampling_rate_avg, a.sampling_rate_max, a.sampling_rate_95p, a.unit, a.hidden,
                b.uri, c.id, b.filename, b.commit_hash, b.branch,
                b.id, b.usage_scenario_variables
            FROM phase_stats as a
            LEFT JOIN runs as b on b.id = a.run_id
            LEFT JOIN machines as c on c.id = b.machine_id

            WHERE
                (TRUE = %s OR b.user_id = ANY(%s::int[]) OR b.public = TRUE)
                AND a.run_id = ANY(%s::uuid[])
            ORDER BY
                b.created_at ASC, -- at least the first sorting key which determinse the order of run_ids must be same order as get_comparison_details so that the order in the comparison bar charts aligns with the comparsion_details array
                a.phase ASC,
                a.id ASC
            """
    params = (user.is_super_user(), user.visible_users(), ids)
    return DB().fetch_all(query, params=params)

# Would be interesting to know if in an application server like gunicor @cache
# Will also work for subsequent requests ...?
# Update: It does, but only for the same worker. We are caching this request anyway now in Redis
'''  Object structure
    comparison_case: str
    statistics: dict
                                        // MEAN of the detailed-metric over all repos -> non-sense
                                        // MEAN of the detailed-metric over all usage_scenarios -> debateable
                                        // MEAN of the detailed-metric per machines  -> interesting
                                        // MEAN of the detailed-metric per commits -> debateable

                                        // Case A: No T-Test necessary, as only repetition. STDDEV only important
                                        // Case B: comparison as T-test betweeen every commit ???
                                        // => Technically possible, but we will most likely only have 1 commit.
                                        // => So maybe only compare last commit against all before?
                                        // => Yes, that sounds best! Still
                                        // Case C_1: comparison as T-test betweeen the two machines
                                        // => Impossible if we have only one sample
                                        // => Problematic if samples are < 20
                                        // Case C_2: comparison as T-test betweeen the two usage scenarios
                                        // => Impossible if we have only one sample
                                        // => Problematic if samples are < 20
                                        // Case C_3: comparison as T-test betweeen the two usage scenarios
                                        // => Impossible if we have only one sample
                                        // => Problematic if samples are < 20
                                        // Case D: comparison as T-test betweeen the two repos
                                        // => Impossible if we have only one sample
                                        // => Problematic if samples are < 20

                                        // although we can have 2 commits on 2 repos, we do not keep
                                        // track of the multiple commits here as key
                                        // currently the system is limited to compare only two runs until we have
                                        // figured out how big our StdDev is and how many runs we can run per day
                                        // at all (and how many repetitions are needed and possbile time-wise)
                                        repo/usage_scenarios/machine/commit/:
                                            mean: // mean per commit/repo etc.
                                            stddev:
                                            ci:
                                            p_value: // Only case A for last key vs compare to the rest. one-sided t-test
                                            is_significant: // Only case A .... one-sided t-test
                                            values: [] // 1 for stats.html. 1+ for cases
                                            max_values: []


    data: dict -> key: repo/usage_scenarios/machine/commit/branch
        run_1: dict
        run_2: dict
        ...
        run_x : dict  -> key: phase_name
            [BASELINE]: dict
            [INSTALLATION]: dict
            ....
            [PHASE]: dict:
               hidden: bool
               data : dict:
                 metric_name:dict
                    -mean: - // will NOT be implemented. See explanation
                        // mean of the phase for all the metrics and their details
                        // this really only makes sense for all the energy values, and then only for selected ones ...
                        // actually only really helpful if we have multiple metrics that report the same value
                        // this shall NOT be supported
                    // we reserve this level for phase-level data
                    // atm there is only the data key
                    core_energy_powermetrics_component: dict
                    ...
                    ane_energy_powermetrics_component: dict
                        clean_name: str
                        explanation: str
                        source: str
                        ....
                        mean: float
                            // mean of the metric over all details per per repo / usage_scenario etc.
                            // => Interesting for multiple docker containers
                            repo/usage_scenarios/machine/commit/: number
                            repo/usage_scenarios/machine/commit/: number
                            ...
                        stddev: float
                        p-value: float

                        data: dict -> key: detail_name
                            [COMPONENT]: dict
                            [SYSTEM]: dict
                            ...
                            [MACHINE]:
                                    mean: float // mean of the metric for this detail for this phase
                                    stddev: float
                                    ci: float
                                    max: float
                                    values: list // the actual values
            ...
'''
def get_phase_stats_object(phase_stats, case=None, comparison_details=None, comparison_identifiers=None):

    phase_stats_object = {
        'comparison_case': case,
        'comparison_details': comparison_details,
        'comparison_identifiers': comparison_identifiers,
        'data': OrderedDict()
    }

    if comparison_details: # override with parsed data
        phase_stats_object['comparison_details'] = transform_dict_to_list_two_level(comparison_details) # list, becase better parseable in echarts and lower overhead in JSON
        phase_stats_object['comparison_identifiers'] = list(comparison_details.keys())

    for phase_stat in phase_stats:
        [
            phase, metric_name, detail_name, value, metric_type, max_value, min_value,
            sampling_rate_avg, sampling_rate_max, sampling_rate_95p, unit, hidden,
            repo, machine_id, filename, commit_hash, branch,
            run_id, usage_scenario_variables
        ] = phase_stat

        run_id = str(run_id)

        phase = phase.split('_', maxsplit=1)[1] # remove the 001_ prepended stuff again, which is only for ordering

        if case == 'Repository':
            key = repo # Case D : RequirementsEngineering Case
        elif case == 'Branch':
            key = branch # Case C_3 : SoftwareDeveloper Case
        elif case == 'Usage Scenario':
            key = filename # Case C_2 : SoftwareDeveloper Case
        elif case == 'Machine':
            key = str(machine_id) # Case C_1 : DataCenter Case
        elif case in ('Commit', 'Repeated Run'):
            key = commit_hash # Repeated Run
        elif case == 'Usage Scenario Variables':
            key = str(usage_scenario_variables) # Case E: Quick Development Case
        else:
            key = run_id # No comparison case - Single view

        if phase not in phase_stats_object['data']:
            phase_stats_object['data'][phase] = OrderedDict({'hidden': hidden, 'data': {}})

        if metric_name not in phase_stats_object['data'][phase]['data']:
            phase_stats_object['data'][phase]['data'][metric_name] = {
                'type': metric_type,
                'unit': unit,
                #'mean': None, # currently no use for that
                #'stddev': None,  # currently no use for that
                #'ci': None,  # currently no use for that
                #'p_value': None,  # currently no use for that
                #'is_significant': None,  # currently no use for that
                'data': OrderedDict(),
            }
        elif phase_stats_object['data'][phase]['data'][metric_name]['unit'] != unit:
            raise ValueError(f"Metric cannot be compared as units have changed: {unit} vs. {phase_stats_object['data'][phase]['data'][metric_name]['unit']}")


        if detail_name not in phase_stats_object['data'][phase]['data'][metric_name]['data']:
            phase_stats_object['data'][phase]['data'][metric_name]['data'][detail_name] = {
                'name': detail_name,
                # 'mean': None, # mean for a detail over multiple machines / branches makes no sense
                # 'max': max_value, # max for a detail over multiple machines / branches makes no sense
                # 'min': min_value, # min for a detail over multiple machines / branches makes no sense
                # 'stddev': None, # stddev for a detail over multiple machines / branches makes no sense
                # 'ci': None, # since we only compare two keys atm this  could no be calculated.
                'p_value': None, # comparing the means of two machines, branches etc. Both cases must have multiple values for this to get populated
                'is_significant': None, # comparing the means of two machines, branches etc. Both cases must have multiple values for this to get populated
                'data': OrderedDict(),
            }

        detail_data = phase_stats_object['data'][phase]['data'][metric_name]['data'][detail_name]['data']
        if key not in detail_data:
            detail_data[key] = {
                'mean': value, # this is the mean over all repetitions of the detail_name for the key
                'max': max_value,
                'min': min_value,
                'max_mean': max_value,
                'min_mean': min_value,
                'stddev': None,
                'sr_avg_avg': sampling_rate_avg,
                'sr_max_max': sampling_rate_max,
                'sr_95p_max': sampling_rate_95p,
                'sr_avg_values': [sampling_rate_avg], # temporary, we will delete this later
                'sr_max_values': [sampling_rate_max], # temporary, we will delete this later
                'sr_95p_values': [sampling_rate_95p], # temporary, we will delete this later
                'ci': None,
                'p_value': None, # only for the last key the list compare to the rest. one-sided t-test
                'is_significant': None, # only for the last key the list compare to the rest. one-sided t-test
                'values': [value],
            }
            if comparison_details: # create None filled lists in comparison casese so that we can later understand which values are missing when parsing in JS for example
                detail_data[key]['values'] = [None for _ in comparison_details[key]] # Debug: if this line errors it means we have not inserted a new at the beginning of the function (L584++)
                detail_data[key]['sr_avg_values'] = [None for _ in comparison_details[key]]
                detail_data[key]['sr_max_values'] = [None for _ in comparison_details[key]]
                detail_data[key]['sr_95p_values'] = [None for _ in comparison_details[key]]

        # we replace None where we can with actual values
        if comparison_details:
            detail_data[key]['values'][comparison_details[key][run_id]['index']] = value
            detail_data[key]['sr_avg_values'][comparison_details[key][run_id]['index']] = sampling_rate_avg
            detail_data[key]['sr_max_values'][comparison_details[key][run_id]['index']] = sampling_rate_max
            detail_data[key]['sr_95p_values'][comparison_details[key][run_id]['index']] = sampling_rate_95p

        # since we do not save the min/max values we need to to the comparison here in every loop again
        # all other statistics are derived later in add_phase_stats_statistics()
        detail_data[key]['max'] = max((x for x in [max_value, detail_data[key]['max']] if x is not None), default=max_value)
        detail_data[key]['min'] = min((x for x in [min_value, detail_data[key]['min']] if x is not None), default=min_value)

    return phase_stats_object

def transform_dict_to_list_two_level(my_dict):
    my_list = [[] for _ in range(len(my_dict))]
    for index, item in enumerate(my_dict.values()):
        my_list[index] = list(item.values())
    return list(my_list)


'''
    Here we need to traverse the object again and calculate all the averages we need
    This could have also been done while constructing the object through checking when a change
    in phase / detail_name etc. occurs., however this is more efficient
'''
def add_phase_stats_statistics(phase_stats_object):

    for _, phase_data in phase_stats_object['data'].items():
        for _, metric in phase_data['data'].items():
            for _, detail in metric['data'].items():
                for _, key_obj in detail['data'].items():

                    # if a detail has multiple values we calculate a std.dev and the one-sided t-test for the last value

                    values_none_filtered = [item for item in key_obj['values'] if item is not None]
                    sr_avg_values_none_filtered = [item for item in key_obj['sr_avg_values'] if item is not None]
                    sr_max_values_none_filtered = [item for item in key_obj['sr_max_values'] if item is not None]
                    sr_95p_values_none_filtered = [item for item in key_obj['sr_95p_values'] if item is not None]

                    if len(values_none_filtered) > 1:

                        t_stat = get_t_stat(len(values_none_filtered))

                        # JSON does not recognize the numpy data types. Sometimes int64 is returned
                        key_obj['mean'] = np.mean(values_none_filtered).item()

                        key_obj['stddev'] = np.std(values_none_filtered, correction=1).item()
                        # We are using now the STDDEV of the sample for two reasons:
                        # It is required by the Blue Angel for Software
                        # We got many debates that in cases where the average is only estimated through measurements and is not absolute
                        # one MUST use the sample STDDEV.
                        # Still one could argue that one does not want to characterize the measured software but rather the measurement setup
                        # it is safer to use the sample STDDEV as it is always higher

                        key_obj['max_mean'] = np.max(values_none_filtered).item()
                        key_obj['min_mean'] = np.min(values_none_filtered).item()

                        if sr_avg_values_none_filtered:
                            key_obj['sr_avg_avg'] = np.mean(sr_avg_values_none_filtered).item()
                        if sr_max_values_none_filtered:
                            key_obj['sr_max_max'] = np.max(sr_max_values_none_filtered).item()
                        if sr_95p_values_none_filtered:
                            key_obj['sr_95p_max'] = np.max(sr_95p_values_none_filtered).item()

                        key_obj['ci'] = (key_obj['stddev']*t_stat).item()

                        if len(values_none_filtered) > 2:
                            data_c = values_none_filtered.copy()
                            pop_mean = data_c.pop()
                            _, p_value = scipy.stats.ttest_1samp(data_c, pop_mean)
                            if not np.isnan(p_value):
                                key_obj['p_value'] = p_value.item()
                                if key_obj['p_value'] > 0.05:
                                    key_obj['is_significant'] = False
                                else:
                                    key_obj['is_significant'] = True

                    # remove temporary keys only needed for mean/max/min calculations
                    del key_obj['sr_avg_values']
                    del key_obj['sr_max_values']
                    del key_obj['sr_95p_values']



    ## builds stats between the keys
    if len(phase_stats_object['comparison_identifiers']) == 2:
        # since we currently allow only two comparisons we hardcode this here
        # this is then needed to rebuild if we would allow more !IMPROVEMENT
        key1 = phase_stats_object['comparison_identifiers'][0]
        key2 = phase_stats_object['comparison_identifiers'][1]

        # we need to traverse only one branch of the tree like structure, as we only need to compare matching metrics
        for _, phase_data in phase_stats_object['data'].items():
            for _, metric in phase_data['data'].items():
                for _, detail in metric['data'].items():
                    if key1 not in detail['data'] or key2 not in detail['data']:
                        continue

                    # Welch-Test because we cannot assume equal variances
                    values_none_filtered_1 = [item for item in detail['data'][key1]['values'] if item is not None]
                    values_none_filtered_2 = [item for item in detail['data'][key2]['values'] if item is not None]

                    _, p_value = scipy.stats.ttest_ind(values_none_filtered_1, values_none_filtered_2, equal_var=False)

                    if not np.isnan(p_value):
                        detail['p_value'] = p_value.item()
                        if detail['p_value'] > 0.05:
                            detail['is_significant'] = False
                        else:
                            detail['is_significant'] = True

    return phase_stats_object



@cache
def get_t_stat(length):
    #alpha = .05
    if length <= 1: return None
    dof = length-1
    t_crit = np.abs(scipy.stats.t.ppf((.05)/2,dof)) # for two sided!
    return t_crit/np.sqrt(length)

# As the ORJSONResponse renders the object on init we need to keep the original around as otherwise we need to reparse
# it when we use these functions in our code. The header is a copy from starlette/responses.py JSONResponse
class ORJSONResponseObjKeep(ORJSONResponse):
    def __init__(
        self,
        content: typing.Any,
        status_code: int = 200,
        headers: typing.Optional[typing.Dict[str, str]] = None,
        media_type: typing.Optional[str] = None,
        background: typing.Optional[BackgroundTask] = None,
    ) -> None:
        self.content = content
        super().__init__(content, status_code, headers, media_type, background)


header_scheme = APIKeyHeader(
    name='X-Authentication',
    scheme_name='Header',
    description='Authentication key',
    auto_error=False
)

def authenticate(authentication_token=Depends(header_scheme), request: Request = None):

    try:
        if not authentication_token or authentication_token.strip() == '': # Note that if no token is supplied this will authenticate as the DEFAULT user, which in FOSS systems has full capabilities
            authentication_token = 'DEFAULT'

        user = User.authenticate(SecureVariable(authentication_token))

        if not user.can_use_route(request.scope["route"].path):
            raise HTTPException(status_code=401, detail=f"Route not allowed for user {user._name}") from UserAuthenticationError

        if not user.has_api_quota(request.scope["route"].path):
            raise HTTPException(status_code=401, detail=f"Quota exceeded for user {user._name}") from UserAuthenticationError

        user.deduct_api_quota(request.scope["route"].path, 1)

    except UserAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from UserAuthenticationError
    return user

def get_connecting_ip(request):
    connecting_ip = request.headers.get("x-forwarded-for")

    if connecting_ip:
        return connecting_ip.split(",")[0]

    return request.client.host

def check_int_field_api(field, name, max_value):
    if not isinstance(field, int):
        raise HTTPException(status_code=422, detail=f'{name} must be integer')

    if field <= 0:
        raise HTTPException(status_code=422, detail=f'{name} must be > 0')

    if field > max_value:
        raise HTTPException(status_code=422, detail=f'{name} must be <= {max_value}')

    return True

class NoNoneOrNegativeValuesCache(TTLCache):
    def __setitem__(self, key, value, cache_setitem=Cache.__setitem__):
        if value and value != -1 and value != (None, None):  # Only cache valid values
            super().__setitem__(key, value, cache_setitem)

# The decorator will not work between workers, but since uvicorn_worker.UvicornWorker is using asyncIO it has some functionality between requests
@cached(cache=NoNoneOrNegativeValuesCache(maxsize=1024, ttl=86400)) # 24 hours
def get_geo(ip):
    ip_obj = ipaddress.ip_address(ip) # may raise a ValueError
    if ip_obj.is_private:
        error_helpers.log_error(f"Private IP was submitted to get_geo {ip}. This is normal in development, but should not happen in production.")
        return('52.53721666833642', '13.424863870661927')

    query = "SELECT ip_address, data FROM ip_data WHERE created_at > NOW() - INTERVAL '24 hours' AND ip_address=%s;"
    db_data = DB().fetch_all(query, (ip,))

    if db_data is not None and len(db_data) != 0:
        return (db_data[0][1].get('latitude'), db_data[0][1].get('longitude'))

    latitude, longitude = get_geo_ip_api_com(ip)

    if not latitude:
        latitude, longitude = get_geo_ipapi_co(ip)
    if not latitude:
        latitude, longitude = get_geo_ip_ipinfo(ip)
    if not latitude:
        error_helpers.log_error(f"Could not get Geo-IP for {ip} after 3 tries")

    return (latitude, longitude)


def get_geo_ipapi_co(ip):

    print(f"Accessing https://ipapi.co/{ip}/json/")
    try:
        response = requests.get(f"https://ipapi.co/{ip}/json/", timeout=10)
    except Exception as exc: #pylint: disable=broad-exception-caught
        error_helpers.log_error('API request to ipapi.co failed ...', exception=exc)
        return (None, None)

    if response.status_code == 200:
        resp_data = response.json()

        if 'error' in resp_data or 'latitude' not in resp_data or 'longitude' not in resp_data:
            return (None, None)

        resp_data['source'] = 'ipapi.co'

        query = "INSERT INTO ip_data (ip_address, data) VALUES (%s, %s)"
        DB().query(query=query, params=(ip, json.dumps(resp_data)))

        return (resp_data.get('latitude'), resp_data.get('longitude'))

    error_helpers.log_error(f"Could not get Geo-IP from ipapi.co for {ip}. Trying next ...", response=response)

    return (None, None)

def get_geo_ip_api_com(ip):

    print(f"Accessing http://ip-api.com/json/{ip}")
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=10)
    except Exception as exc: #pylint: disable=broad-exception-caught
        error_helpers.log_error('API request to ip-api.com failed ...', exception=exc)
        return (None, None)

    if response.status_code == 200:
        resp_data = response.json()

        if ('status' in resp_data and resp_data.get('status') == 'fail') or 'lat' not in resp_data or 'lon' not in resp_data:
            return (None, None)

        resp_data['latitude'] = resp_data.get('lat')
        resp_data['longitude'] = resp_data.get('lon')
        resp_data['source'] = 'ip-api.com'

        query = "INSERT INTO ip_data (ip_address, data) VALUES (%s, %s)"
        DB().query(query=query, params=(ip, json.dumps(resp_data)))

        return (resp_data.get('latitude'), resp_data.get('longitude'))

    error_helpers.log_error(f"Could not get Geo-IP from ip-api.com for {ip}. Trying next ...", response=response)

    return (None, None)

def get_geo_ip_ipinfo(ip):

    print(f"Accessing https://ipinfo.io/{ip}/json")
    try:
        response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=10)
    except Exception as exc: #pylint: disable=broad-exception-caught
        error_helpers.log_error('API request to ipinfo.io failed ...', exception=exc)
        return (None, None)

    if response.status_code == 200:
        resp_data = response.json()

        if 'bogon' in resp_data or 'loc' not in resp_data:
            return (None, None)

        lat_lng = resp_data.get('loc').split(',')

        resp_data['latitude'] = lat_lng[0]
        resp_data['longitude'] = lat_lng[1]
        resp_data['source'] = 'ipinfo.io'

        query = "INSERT INTO ip_data (ip_address, data) VALUES (%s, %s)"
        DB().query(query=query, params=(ip, json.dumps(resp_data)))

        return (resp_data.get('latitude'), resp_data.get('longitude'))

    error_helpers.log_error(f"Could not get Geo-IP from ipinfo.io for {ip}. Trying next ...", response=response)

    return (None, None)

# The decorator will not work between workers, but since uvicorn_worker.UvicornWorker is using asyncIO it has some functionality between requests
@cached(cache=NoNoneOrNegativeValuesCache(maxsize=1024, ttl=3600)) # 60 Minutes
def get_carbon_intensity(latitude, longitude):

    if latitude is None or longitude is None:
        error_helpers.log_error('Calling get_carbon_intensity without lat/long')
        return None

    query = "SELECT latitude, longitude, data FROM carbon_intensity WHERE created_at > NOW() - INTERVAL '1 hours' AND latitude=%s AND longitude=%s;"
    db_data = DB().fetch_all(query, (latitude, longitude))

    if db_data is not None and len(db_data) != 0:
        return db_data[0][2].get('carbonIntensity')

    if not (electricitymaps_token := GlobalConfig().config.get('electricity_maps_token')):
        raise ValueError('You need to specify an electricitymap token in the config!')

    if electricitymaps_token == 'testing':
        # If we are running tests we always return 1000
        return 1000

    headers = {'auth-token': electricitymaps_token }
    params = {'lat': latitude, 'lon': longitude }

    response = requests.get('https://api.electricitymap.org/v3/carbon-intensity/latest', params=params, headers=headers, timeout=10)
    print(f"Accessing electricitymap with {latitude} {longitude}")
    if response.status_code == 200:
        resp_data = response.json()
        query = "INSERT INTO carbon_intensity (latitude, longitude, data) VALUES (%s, %s, %s)"
        DB().query(query=query, params=(latitude, longitude, json.dumps(resp_data)))

        return resp_data.get('carbonIntensity')

    error_helpers.log_error(f"Could not get carbon intensity from Electricitymaps.org for {params}", response=response)

    return None


def carbondb_add(connecting_ip, data, source, user_id):

    merge_window_max = 30 # merge window hardcoded for now. Might be a user setting later. This entails also that carbondb_copy_over_and_remove_duplicates.py makes queries PER USER
    current_time_us = int(time.time()  * 1e6)
    if data['time'] < current_time_us - merge_window_max * 24 * 60 * 60 * 1e6 : # microseconds
        raise ValueError(f"CarbonDB is configured to not accept values older than {merge_window_max} days. Your timestamp was: {data['time']}")
    if data['time'] > current_time_us:
        raise ValueError(f"CarbonDB does not accept timestamps in the future. Your timestamp was: {data['time']}")


    query = '''
            INSERT INTO carbondb_data_raw
                ("type", "project", "machine", "source", "tags","time","energy_kwh","carbon_kg","carbon_intensity_g","latitude","longitude","ip_address","user_id","created_at")
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    '''

    used_client_ip = data.get('ip', None) # An ip has been given with the data. We prioritize that
    if used_client_ip is None:
        used_client_ip = connecting_ip

    carbon_intensity_g_per_kWh = data.get('carbon_intensity_g', None)

    if carbon_intensity_g_per_kWh is not None: # we need this check explicitely as we want to allow 0 as possible value
        latitude = None # no use to derive if we get supplied data. We rather indicate with NULL that user supplied
        longitude = None # no use to derive if we get supplied data. We rather indicate with NULL that user supplied
    else:
        latitude, longitude = get_geo(used_client_ip) # cached
        carbon_intensity_g_per_kWh = get_carbon_intensity(latitude, longitude) # cached

    energy_J = float(data['energy_uj']) / 1e6
    energy_kWh = energy_J / (3_600*1_000)
    if carbon_intensity_g_per_kWh is None:
        carbon_kg = None
    else:
        carbon_kg = (energy_kWh * carbon_intensity_g_per_kWh)/1_000

    DB().query(
        query=query,
        params=(
            data['type'],
            data['project'], data['machine'], source, data['tags'], data['time'], energy_kWh, carbon_kg, carbon_intensity_g_per_kWh, latitude, longitude, used_client_ip, user_id))

def replace_nan_with_zero(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                replace_nan_with_zero(v)
            elif isinstance(v, float) and math.isnan(v):
                obj[k] = 0
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                replace_nan_with_zero(item)
            elif isinstance(item, float) and math.isnan(item):
                obj[i] = 0
    return obj

# Refactor have this in the Pydantic model?
# https://github.com/green-coding-solutions/green-metrics-tool/issues/907
def validate_hog_measurement_data(data):
    required_top_level_fields = [
        'coalitions', 'all_tasks', 'elapsed_ns', 'processor', 'thermal_pressure'
    ]
    for field in required_top_level_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    # Validate 'coalitions' structure
    if not isinstance(data['coalitions'], list):
        raise ValueError("Expected 'coalitions' to be a list")

    for coalition in data['coalitions']:
        required_coalition_fields = [
            'name', 'tasks', 'energy_impact_per_s', 'cputime_ms_per_s',
            'diskio_bytesread', 'diskio_byteswritten', 'intr_wakeups', 'idle_wakeups'
        ]
        for field in required_coalition_fields:
            if field not in coalition:
                raise ValueError(f"Missing required coalition field: {field}")
            if field == 'tasks' and not isinstance(coalition['tasks'], list):
                raise ValueError(f"Expected 'tasks' to be a list in coalition: {coalition['name']}")

    # Validate 'all_tasks' structure
    if 'energy_impact_per_s' not in data['all_tasks']:
        raise ValueError("Missing 'energy_impact_per_s' in 'all_tasks'")

    # Validate 'processor' structure based on the processor type
    processor_fields = data['processor'].keys()
    if 'ane_energy' in processor_fields:
        required_processor_fields = ['combined_power', 'cpu_energy', 'gpu_energy', 'ane_energy']
    elif 'package_joules' in processor_fields:
        required_processor_fields = ['package_joules', 'cpu_joules', 'igpu_watts']
    else:
        raise ValueError("Unknown processor type")

    for field in required_processor_fields:
        if field not in processor_fields:
            raise ValueError(f"Missing required processor field: {field}")

    # All checks passed
    return True
