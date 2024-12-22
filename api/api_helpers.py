import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from urllib.parse import urlparse

from collections import OrderedDict
from functools import cache
from html import escape as html_escape
import typing
import uuid

from starlette.background import BackgroundTask
from fastapi.responses import ORJSONResponse
from fastapi import Depends, Request, HTTPException
from fastapi.security import APIKeyHeader
import numpy as np
import scipy.stats
from pydantic import BaseModel

from psycopg import sql

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers
from lib.user import User, UserAuthenticationError
from lib.secure_variable import SecureVariable

import redis
from enum import Enum

def get_artifact(artifact_type: Enum, key: str, decode_responses=True):
    if not GlobalConfig().config['redis']['host']:
        return None

    data = None
    try:
        r = redis.Redis(host=GlobalConfig().config['redis']['host'], port=6379, db=artifact_type.value, protocol=3, decode_responses=decode_responses)

        data = r.get(key)
    except redis.RedisError as e:
        error_helpers.log_error('Redis get_artifact failed', exception=e)

    return None if data is None or data == [] else data

def store_artifact(artifact_type: Enum, key:str, data, ex=2592000):
    if not GlobalConfig().config['redis']['host']:
        return

    try:
        r = redis.Redis(host=GlobalConfig().config['redis']['host'], port=6379, db=artifact_type.value, protocol=3)
        r.set(key, data, ex=ex) # Expiration => 2592000 = 30 days
    except redis.RedisError as e:
        error_helpers.log_error('Redis store_artifact failed', exception=e)


# Note
# ---------------
# Use this function never in the phase_stats. The metrics must always be on
# The same unit for proper comparison!
#
def rescale_metric_value(value, unit):
    if unit == 'mJ':
        value = value * 1_000
        unit = 'uJ'

    # We only expect values to be uJ for energy in the future. Changing values now temporarily.
    # TODO: Refactor this once all data in the DB is uJ
    if unit not in ('uJ', 'ug') and not unit.startswith('ugCO2e/'):
        raise ValueError('Unexpected unit occured for metric rescaling: ', unit)

    unit_type = unit[1:]

    if value > 1_000_000_000_000_000: return [value/(10**15), f"G{unit_type}"]
    if value > 1_000_000_000_000: return [value/(10**12), f"M{unit_type}"]
    if value > 1_000_000_000: return [value/(10**9), f"k{unit_type}"]
    if value > 1_000_000: return [value/(10**6), f"{unit_type}"]
    if value > 1_000: return [value/(10**3), f"m{unit_type}"]
    if value < 0.001: return [value*(10**3), f"n{unit_type}"]

    return [value, unit] # default, no change

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def html_escape_multi(item):
    """Replace special characters "'", "\"", "&", "<" and ">" to HTML-safe sequences."""
    if item is None:
        return None

    if isinstance(item, str):
        return html_escape(item)

    if isinstance(item, list):
        return [html_escape_multi(element) for element in item]

    if isinstance(item, dict):
        for key, value in item.items():
            if isinstance(value, str):
                item[key] = html_escape(value)
            elif isinstance(value, dict):
                item[key] = html_escape_multi(value)
            elif isinstance(value, list):
                item[key] = [
                    html_escape_multi(item)
                    if isinstance(item, dict)
                    else html_escape(item)
                    if isinstance(item, str)
                    else item
                    for item in value
                ]
        return item

    if isinstance(item, BaseModel):
        item_copy = item.model_copy(deep=True)
        # we ignore keys that begin with model_ because pydantic v2 renamed a lot of their fields from __fields to model_fields:
        # https://docs.pydantic.dev/dev-v2/migration/#changes-to-pydanticbasemodel
        # This could cause an error if we ever make a BaseModel that has keys that begin with model_
        keys = [key for key in dir(item_copy) if not key.startswith('_') and not key.startswith('model_') and not callable(getattr(item_copy, key))]
        for key in keys:
            setattr(item_copy, key, html_escape_multi(getattr(item_copy, key)))
        return item_copy

    return item

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
            ORDER BY m.description DESC
            """

    return DB().fetch_all(query)

def get_run_info(run_id):
    query = """
            SELECT
                id, name, uri, branch, commit_hash,
                (SELECT STRING_AGG(t.name, ', ' ) FROM unnest(runs.categories) as elements
                    LEFT JOIN categories as t on t.id = elements) as categories,
                filename, start_measurement, end_measurement,
                measurement_config, machine_specs, machine_id, usage_scenario,
                created_at, invalid_run, phases, logs, failed
            FROM runs
            WHERE id = %s
            """
    params = (run_id,)
    return DB().fetch_one(query, params=params, fetch_mode='dict')

def get_timeline_query(uri, filename, machine_id, branch, metrics, phase, start_date=None, end_date=None, detail_name=None, limit_365=False, sorting='run'):

    if filename is None or filename.strip() == '':
        filename =  'usage_scenario.yml'

    if branch is None or branch.strip() == '':
        branch = 'main'

    params = [uri, filename, branch, machine_id, f"%{phase}"]

    metrics_condition = ''
    if metrics is None or metrics.strip() == '' or metrics.strip() == 'key':
        metrics_condition =  "AND (p.metric LIKE '%%_energy_%%' OR metric = 'software_carbon_intensity_global')"
    elif metrics.strip() != 'all':
        metrics_condition =  "AND p.metric = %s"
        params.append(metrics)

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

    limit_365_condition = ''
    if limit_365:
        limit_365_condition = "AND r.created_at >= CURRENT_DATE - INTERVAL '365 days'"

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
                r.uri = %s
                AND r.filename = %s
                AND r.branch = %s
                AND r.end_measurement IS NOT NULL
                AND r.failed != TRUE
                AND r.machine_id = %s
                AND p.phase LIKE %s
                {metrics_condition}
                {start_date_condition}
                {end_date_condition}
                {detail_name_condition}
                {limit_365_condition}
                AND r.commit_timestamp IS NOT NULL
                AND r.failed IS FALSE
            ORDER BY
                p.metric ASC, p.detail_name ASC,
                p.phase ASC, {sorting_condition}

            """

    return (query, params)

def get_comparison_details(ids, comparison_db_key):

    query = sql.SQL('''
        SELECT
            id, name, created_at, commit_hash, commit_timestamp, gmt_hash, {}
        FROM runs
        WHERE id = ANY(%s::uuid[])
        ORDER BY created_at  -- Must be same order as in get_phase_stats
    ''').format(sql.Identifier(comparison_db_key))

    data = DB().fetch_all(query, (ids, ))
    if data is None or data == []:
        raise RuntimeError('Could not get comparison details')

    comparison_details = OrderedDict()

    for row in data:
        comparison_key = row[6]
        run_id = str(row[0]) # UUID must be converted
        if comparison_key not in comparison_details:
            comparison_details[comparison_key] = OrderedDict()
        comparison_details[comparison_key][run_id] = {
            'run_id': run_id,
            'name': row[1],
            'created_at': row[2],
            'commit_hash': row[3],
            'commit_timestamp': row[4],
            'gmt_hash': row[5],
        }

    # to back-fill None values later we need to index every element
    for item in comparison_details.values():
        for index, inner_item in enumerate(item.values()):
            inner_item['index'] = index

    return comparison_details

def determine_comparison_case(ids):

    query = '''
            WITH uniques as (
                SELECT uri, filename, machine_id, commit_hash, branch FROM runs
                WHERE id = ANY(%s::uuid[])
                GROUP BY uri, filename, machine_id, commit_hash, branch
            )
            SELECT
                COUNT(DISTINCT uri ), COUNT(DISTINCT filename), COUNT(DISTINCT machine_id),
                COUNT(DISTINCT commit_hash ), COUNT(DISTINCT branch)
            FROM uniques
    '''

    data = DB().fetch_one(query, (ids, ))
    if data is None or data == [] or data[1] is None: # special check for data[1] as this is aggregate query which always returns result
        raise RuntimeError('Could not determine compare case')

    [repos, usage_scenarios, machine_ids, commit_hashes, branches] = data

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
    # case = 'Multi-Commit' # Case D: Evolution of repo over time

    #pylint: disable=no-else-raise,no-else-return
    if repos == 2: # diff repos
        if usage_scenarios <= 2: # diff repo, diff usage scenarios. diff usage scenarios are NORMAL for now
            if machine_ids == 2: # diff repo, diff usage scenarios, diff machine_ids
                raise RuntimeError('Different repos & machines not supported')
            if machine_ids == 1: # diff repo, diff usage scenarios, same machine_ids
                if branches <= 2:
                    if commit_hashes <= 2: # diff repo, diff usage scenarios, same machine_ids,  same branches, diff/same commits_hashes
                        # for two repos we expect two different hashes, so this is actually a normal case
                        # even if they are identical we do not care, as the repos are different anyway
                        return ('Repository', 'uri') # Case D
                    else:
                        raise RuntimeError('Different repos & more than 2 different commits commits not supported')
                else:
                    raise RuntimeError('Different repos & more than 2 branches not supported')
            else:
                raise RuntimeError('Less than 1 or more than 2 Machines and different repos not supported.')
        else:
            raise RuntimeError('Only 2 or less usage scenarios for different repos not supported.')
    elif repos == 1: # same repos
        if usage_scenarios == 2: # same repo, diff usage scenarios
            if machine_ids == 2: # same repo, diff usage scenarios, diff machines
                raise RuntimeError('Different usage scenarios & machines not supported')
            if branches <= 1:
                if commit_hashes == 1: # same repo, diff usage scenarios, same machines, same branches, same commit hashes
                    return ('Usage Scenario', 'filename') # Case C_2
                else: # same repo, diff usage scenarios, same machines, same branches, diff commit hashes
                    raise RuntimeError('Different usage scenarios & commits not supported')
            else: # same repo, diff usage scenarios, same machines, diff branches
                raise RuntimeError('Different usage scenarios & branches not supported')
        elif usage_scenarios == 1: # same repo, same usage scenario
            if machine_ids == 2: # same repo, same usage scenarios, diff machines
                if branches <= 1:
                    if commit_hashes == 1: # same repo, same usage scenarios, diff machines, same branches, same commit hashes
                        return ('Machine', 'machine_id') # Case C_1
                    else: # same repo, same usage scenarios, diff machines, same branches, diff commit hashes
                        raise RuntimeError('Different machines & commits not supported')
                else: # same repo, same usage scenarios, diff machines, diff branches
                    raise RuntimeError('Different machines & branches not supported')

            elif machine_ids == 1: # same repo, same usage scenarios, same machines
                if branches <= 1:
                    if commit_hashes == 2: # same repo, same usage scenarios, same machines, diff commit hashes
                        return ('Commit', 'commit_hash') # Case B
                    elif commit_hashes > 2: # same repo, same usage scenarios, same machines, many commit hashes
                        raise RuntimeError('Multiple commits comparison not supported. Please switch to Timeline view')
                    else: # same repo, same usage scenarios, same machines, same branches, same commit hashes
                        return ('Repeated Run', 'commit_hash') # Case A
                else: # same repo, same usage scenarios, same machines, diff branch
                    # diff branches will have diff commits in most cases. so we allow 2, but no more
                    if commit_hashes <= 2:
                        return ('Branch', 'branch') # Case C_3
                    else:
                        raise RuntimeError('Different branches and more than 2 commits not supported')
            else:
                raise RuntimeError('Less than 1 or more than 2 Machines per repo not supported.')
        else:
            raise RuntimeError('Less than 1 or more than 2 Usage scenarios per repo not supported.')

    else:
        # The functionality I imagine here is, because comparing more than two repos is very complex with
        # multiple t-tests / ANOVA etc. and hard to grasp, only a focus on one metric shall be provided.
        raise RuntimeError('Less than 1 or more than 2 repos not supported for overview. Please apply metric filter.')

    raise RuntimeError('Could not determine comparison case after checking all conditions')

def get_phase_stats(ids):
    query = """
            SELECT
                a.phase, a.metric, a.detail_name, a.value, a.type, a.max_value, a.min_value, a.unit,
                b.uri, c.description, b.filename, b.commit_hash, b.branch,
                b.id
            FROM phase_stats as a
            LEFT JOIN runs as b on b.id = a.run_id
            LEFT JOIN machines as c on c.id = b.machine_id

            WHERE
                a.run_id = ANY(%s::uuid[])
            ORDER BY
                b.created_at ASC -- Must be same order as in get_comparison_details
            """
    return DB().fetch_all(query, (ids, ))

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
            [PHASE]: dict -> key: metric_name
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
            phase, metric_name, detail_name, value, metric_type, max_value, min_value, unit,
            repo, machine_description, filename, commit_hash, branch,
            run_id
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
            key = machine_description # Case C_1 : DataCenter Case
        elif case in ('Commit', 'Repeated Run'):
            key = commit_hash # Repeated Run
        else:
            key = run_id # No comparison case - Single view

        if phase not in phase_stats_object['data']: phase_stats_object['data'][phase] = OrderedDict()

        if metric_name not in phase_stats_object['data'][phase]:
            phase_stats_object['data'][phase][metric_name] = {
                'type': metric_type,
                'unit': unit,
                #'mean': None, # currently no use for that
                #'stddev': None,  # currently no use for that
                #'ci': None,  # currently no use for that
                #'p_value': None,  # currently no use for that
                #'is_significant': None,  # currently no use for that
                'data': OrderedDict(),
            }
        elif phase_stats_object['data'][phase][metric_name]['unit'] != unit:
            raise RuntimeError(f"Metric cannot be compared as units have changed: {unit} vs. {phase_stats_object['data'][phase][metric_name]['unit']}")


        if detail_name not in phase_stats_object['data'][phase][metric_name]['data']:
            phase_stats_object['data'][phase][metric_name]['data'][detail_name] = {
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

        detail_data = phase_stats_object['data'][phase][metric_name]['data'][detail_name]['data']
        if key not in detail_data:
            detail_data[key] = {
                'mean': None, # this is the mean over all repetitions of the detail_name for the key
                'max': max_value,
                'min': min_value,
                'max_mean': None,
                'min_mean': None,
                'stddev': None,
                'ci': None,
                'p_value': None, # only for the last key the list compare to the rest. one-sided t-test
                'is_significant': None, # only for the last key the list compare to the rest. one-sided t-test
                'values': [value],
            }
            if comparison_details:
                detail_data[key]['values'] = [None for _ in comparison_details[key]] # create None filled list in comparision casese so that we can later understand which values are missing when parsing in JS for example

        # we replace None where we can with actual values
        if comparison_details:
            detail_data[key]['values'][comparison_details[key][run_id]['index']] = value

        # since we do not save the min/max values we need to to the comparison here in every loop again
        # all other statistics are derived later in add_phase_stats_statistics()
        detail_data[key]['max'] = max((x for x in [max_value, detail_data[key]['max']] if x is not None), default=None)
        detail_data[key]['min'] = min((x for x in [min_value, detail_data[key]['min']] if x is not None), default=None)

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
        for _, metric in phase_data.items():
            for _, detail in metric['data'].items():
                for _, key_obj in detail['data'].items():

                    # if a detail has multiple values we calculate a std.dev and the one-sided t-test for the last value

                    values_none_filtered = [item for item in key_obj['values'] if item is not None]
                    key_obj['mean'] = values_none_filtered[0] # default. might be overridden
                    key_obj['max_mean'] = values_none_filtered[0] # default. might be overridden
                    key_obj['min_mean'] = values_none_filtered[0] # default. might be overridden

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

                        key_obj['max_mean'] = np.max(values_none_filtered).item() # overwrite with max of list
                        key_obj['min_mean'] = np.min(values_none_filtered).item() # overwrite with min of list
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


    ## builds stats between the keys
    if len(phase_stats_object['comparison_identifiers']) == 2:
        # since we currently allow only two comparisons we hardcode this here
        # this is then needed to rebuild if we would allow more !IMPROVEMENT
        key1 = phase_stats_object['comparison_identifiers'][0]
        key2 = phase_stats_object['comparison_identifiers'][1]

        # we need to traverse only one branch of the tree like structure, as we only need to compare matching metrics
        for _, phase_data in phase_stats_object['data'].items():
            for _, metric in phase_data.items():
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
    parsed_url = urlparse(str(request.url))
    try:
        if not authentication_token or authentication_token.strip() == '': # Note that if no token is supplied this will authenticate as the DEFAULT user, which in FOSS systems has full capabilities
            authentication_token = 'DEFAULT'

        user = User.authenticate(SecureVariable(authentication_token))

        if not user.can_use_route(parsed_url.path):
            raise HTTPException(status_code=401, detail="Route not allowed") from UserAuthenticationError

        if not user.has_api_quota(parsed_url.path):
            raise HTTPException(status_code=401, detail="Quota exceeded") from UserAuthenticationError

        user.deduct_api_quota(parsed_url.path, 1)

    except UserAuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid token") from UserAuthenticationError
    return user

def get_connecting_ip(request):
    connecting_ip = request.headers.get("x-forwarded-for")

    if connecting_ip:
        return connecting_ip.split(",")[0]

    return request.client.host
