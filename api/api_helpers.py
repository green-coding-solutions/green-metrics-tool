import faulthandler
import sys
import os
import uuid
import numpy as np
import scipy.stats
from functools import cache

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../lib')
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../tools')

from db import DB


METRIC_MAPPINGS = {
    'ane_power_powermetrics_system': {
        'clean_name': 'ANE Power',
        'explanation': 'Apple Neural Engine',
        'color': 'orange',
        'icon': 'power off'
    },
    'ane_energy_powermetrics_system': {
        'clean_name': 'ANE Energy',
        'explanation': 'Apple Neural Engine',
        'color': 'blue',
        'icon': 'battery three quarters'
    },
    'gpu_power_powermetrics_system': {
        'clean_name': 'GPU Power',
        'explanation': 'Apple M1 GPU / Intel GPU',
        'color': 'orange',
        'icon': 'power off'
    },
    'gpu_energy_powermetrics_system': {
        'clean_name': 'GPU Energy',
        'explanation': 'Apple M1 GPU / Intel GPU',
        'color': 'blue',
        'icon': 'battery three quarters'
    },

    'cores_power_powermetrics_system': {
        'clean_name': 'CPU Power (Cores)',
        'explanation': 'Power of the cores only without GPU, ANE, GPU, DRAM etc.',
        'color': 'orange',
        'icon': 'power off'
    },
    'cores_energy_powermetrics_system': {
        'clean_name': 'CPU Energy (Cores)',
        'explanation': 'Energy of the cores only without GPU, ANE, GPU, DRAM etc.',
        'color': 'blue',
        'icon': 'battery three quarters'
    },
    'cpu_time_powermetrics_vm': {
        'clean_name': 'CPU time',
        'explanation': 'Effective execution time of the CPU for all cores combined',
        'color': 'brown',
        'icon': 'stopwatch'
    },
    'disk_io_bytesread_powermetrics_vm': {
        'clean_name': 'Bytes read (HDD/SDD)',
        'explanation': 'Effective execution time of the CPU for all cores combined',
        'color': 'green',
        'icon': 'upload'
    },
    'disk_io_byteswritten_powermetrics_vm': {
        'clean_name': 'Bytes written (HDD/SDD)',
        'explanation': 'Effective execution time of the CPU for all cores combined',
        'color': 'green',
        'icon': 'download'
    },
    'energy_impact_powermetrics_vm': {
        'clean_name': 'Energy impact',
        'explanation': 'macOS proprietary value for relative energy impact on device',
        'color': 'red',
        'icon': 'cat'
    },
    'cpu_utilization_cgroup_container': {
        'clean_name': 'CPU %',
        'explanation': 'CPU Utilization per container',
        'color': 'yellow',
        'icon': 'microchip'
    },
    'memory_total_cgroup_container': {
        'clean_name': 'Memory Usage',
        'explanation': 'Memory Usage per container',
        'color': 'purple',
        'icon': 'memory'
    },
    'network_io_cgroup_container': {
        'clean_name': 'Network I/O',
        'explanation': 'Network I/O. Details on docs.green-coding.berlin/docs/measuring/metric-providers/network-io-cgroup-container',
        'color': 'olive',
        'icon': 'exchange alternate'
    },
    'cpu_energy_rapl_msr_system': {
        'clean_name': 'CPU Energy (Package)',
        'explanation': 'RAPL based CPU energy of package domain',
        'color': 'blue',
        'icon': 'batter three quarters'
    },
    'cpu_power_rapl_msr_system': {
        'clean_name': 'CPU Power (Package)',
        'explanation': 'Derived RAPL based CPU energy of package domain',
        'color': 'orange',
        'icon': 'power off'
    },
    'cpu_utilization_procfs_system': {
        'clean_name': 'CPU %',
        'explanation': 'CPU Utilization of total system',
        'color': 'purple',
        'icon': 'power off'
    },
    'memory_energy_rapl_msr_system': {
        'clean_name': 'Memory Energy (DRAM)',
        'explanation': 'RAPL based memory energy of DRAM domain',
        'color': 'blue',
        'icon': 'batter three quarters'
    },
    'memory_power_rapl_msr_system': {
        'clean_name': 'Memory Power (DRAM)',
        'explanation': 'Derived RAPL based memory energy of DRAM domain',
        'color': 'orange',
        'icon': 'power off'
    },
}


def rescale_energy_value(value, unit):
    # We only expect values to be mJ for energy!
    if unit != 'mJ':
        raise RuntimeError('Unexpected unit occured for energy rescaling: ', unit)

    energy_rescaled = [value, unit]

    # pylint: disable=multiple-statements
    if value > 1_000_000_000: energy_rescaled = [value/(10**12), 'GJ']
    elif value > 1_000_000_000: energy_rescaled = [value/(10**9), 'MJ']
    elif value > 1_000_000: energy_rescaled = [value/(10**6), 'kJ']
    elif value > 1_000: energy_rescaled = [value/(10**3), 'J']
    elif value < 0.001: energy_rescaled = [value*(10**3), 'nJ']

    return energy_rescaled

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def convertValue(value, unit):
    if unit == 'mJ':
        return [value / 1000, 'J']
    if unit == 'mW':
        return [value / 1000, 'W']
    if unit == 'Ratio':
        return [value / 100, '%']
    if unit == 'centi°C':
        return [value / 100, '°C']
    if unit == 'Hz':
        return [value / 1000000, 'GHz']
    if unit == 'ns':
        return [value / 1000000000, 's']
    if unit == 'Bytes':
        return [value / 1000000, 'MB']
    return [value, unit]        # no conversion in default case

def determineComparisonCase(ids):

    query = '''
            WITH uniques as (
                SELECT b.uri, b.usage_scenario_file, b.machine_id, b.commit_hash FROM phase_stats as a
                LEFT JOIN projects as b ON a.project_id = b.id
                WHERE project_id = ANY(%s::uuid[])
                GROUP BY b.uri, b.usage_scenario_file, b.machine_id, b.commit_hash
            )
            SELECT COUNT(DISTINCT uri ), COUNT(DISTINCT usage_scenario_file), COUNT(DISTINCT machine_id), COUNT(DISTINCT commit_hash ) from uniques
    '''

    data = DB().fetch_one(query, (ids, ))
    if data is None or data == []:
        raise RuntimeError('Could not determine compare case')

    [repos, usage_scenarios, machine_ids, commit_hashes] = data

    # If we have one or more measurement in a phase_stat it will currently just be averaged
    # however, when we allow comparing projects we will get same phase_stats but with different repo etc.
    # these cannot be just averaged. But they have to be split and then compared via t-test
    # For the moment I think it makes sense to restrict to two repositories. Comparing three is too much to handle I believe if we do not want to drill down to one specific metric

    # Currently we support five cases:
    # case = 'Repositories' # Case D : RequirementsEngineering Case
    # case = 'Usage Scenarios' # Case C_2 : SoftwareDeveloper Case
    # case = 'Machines' # Case C_1 : DataCenter Case
    # case = 'Commits' # Case B: DevOps Case
    # case = 'Repeated Runs' # Case A: Blue Angel


    if repos == 2: # diff repos
        if usage_scenarios <= 2: # diff repo, diff usage scenarios. diff usage scenarios are NORMAL for now
            if machine_ids == 2: # diff repo, diff usage scenarios, diff machine_ids
                raise RuntimeError('Different repos & machines not supported')
            elif machine_ids == 1: # diff repo, diff usage scenarios, same machine_ids
                if commit_hashes == 2: # diff repo, diff usage scenarios, same machine_ids, diff commits_hashes
                    # for two repos we expect two different hashes, so this is actually a normal case
                    case = 'Repositories' # Case D
                elif commit_hashes == 1: # diff repo, diff usage scenarios, same machine_ids, same commit_hashes
                    raise RuntimeError('Same commit hash for different repos?!?!')
                else:
                    raise RuntimeError('Different repos & multiple commits not supported')
            else:
                raise RuntimeError('3+ Machines and different repos not supported.')
        else:
            raise RuntimeError('2+ Usage scenarios for different repos not supported.')
    elif repos == 1: # same repos
        if usage_scenarios == 2: # same repo, diff usage scenarios
            if machine_ids == 2: # same repo, diff usage scenarios, diff machines
                raise RuntimeError('Different usage scenarios & machines not supported')
            else: # same repo, diff usage scenarios, same machines
                if commit_hashes > 1: # same repo, diff usage scenarios, same machines, diff commit hashes
                    raise RuntimeError('Different usage scenarios & commits not supported')
                else: # same repo, diff usage scenarios, same machines, same commit hashes
                    case = 'Usage Scenarios' # Case C_2
        elif usage_scenarios == 1: # same repo, same usage scenario
            if machine_ids == 2: # same repo, same usage scenarios, diff machines
                if commit_hashes > 1: # same repo, same usage scenarios, diff machines, diff commit hashes
                    raise RuntimeError('Different machines & commits not supported')
                else: # same repo, same usage scenarios, diff machines, same commit hashes
                    case = 'Machines' # Case C_1
            elif machine_ids == 1: # same repo, same usage scenarios, same machines
                if commit_hashes > 1: # same repo, same usage scenarios, same machines, diff commit hashes
                    case = 'Commits' # Case B
                else: # same repo, same usage scenarios, same machines, same commit hashes
                    case = 'Repeated Runs' # Case A
            else:
                raise RuntimeError('3+ Machines per repo not supported.')
        else:
            raise RuntimeError('3+ Usage scenarios per repo not supported.')

    else:
        # TODO: Metric drilldown has to be implemented at some point ...
        # The functionality I imagine here is, because comparing more than two repos is very complex with
        # multiple t-tests / ANOVA etc. and hard to grasp, only a focus on one metric shall be provided.
        raise RuntimeError('Multiple repos not supported for overview. Please apply metric filter.')

    return case

def getPhaseStats(ids):
    query = """
            SELECT
                a.phase, a.metric, a.detail_name, a.value, a.type, a.max_value, a.unit,
                b.uri, b.machine_id, b.usage_scenario_file, b.commit_hash
            FROM phase_stats as a
            LEFT JOIN projects as b on b.id = a.project_id
            WHERE
                a.project_id = ANY(%s::uuid[])
                AND
                a.metric NOT LIKE '%%_MAX'
            ORDER BY
                a.phase ASC,
                a.metric ASC,
                a.detail_name ASC,
                b.uri ASC,
                b.machine_id ASC,
                b.usage_scenario_file ASC,
                b.commit_hash ASC
            """
    data = DB().fetch_all(query, (ids, ))
    if data is None or data == []:
        raise RuntimeError('Data is empty')
    return data

# TODO: This method needs proper database caching
# Would be interesting to know if in an application server like gunicor @cache
# Will also work for subsequent requests ...?
def getPhaseStatsObject(phase_stats, case):
    '''  Object structure
    comparison_type: STRING
        [BASELINE]:
            -mean: - // will NOT be implemented. See explanation
                // mean of the phase for all the metrics and their details per repo / usage_scenario ...
                // this really only makes sense for all the energy values, and then only for selected ones ...
                // actually only really helpful if we have multiple metrics that report the same value
                // this shall NOT be supported
            ane_energy_powermetrics_system:
                clean_name:
                icon:
                ....
                mean:
                    // mean of the metric over all details per per repo / usage_scenario etc.
                    // => Interesting for multiple docker containers
                    repo/usage_scenarios/machine/commit/: number
                    repo/usage_scenarios/machine/commit/: number
                    ...
                stddev:
                p-value:

                data:
                    [SYSTEM]:
                            mean:
                                // MEAN of the detailed-metric over all repos -> non-sense
                                // MEAN of the detailed-metric over all usage_scenarios -> debateable
                                // MEAN of the detailed-metric per machines  -> interesting
                                // MEAN of the detailed-metric per commits -> debateable
                            stddev:
                            ci:
                            p-value:
                                // p-value for detailed-metric between repos / usage_scenarios etc.
                                // p-value in case A and B non existent
                            significant

                            data:
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
                                // Case D: comparison as T-test betweeen the two repos
                                // => Impossible if we have only one sample
                                // => Problematic if samples are < 20

                                // although we can have 2 commits on 2 repos, we do not keep
                                // track of the multiple commits here as key
                                // currently the system is limited to compare only two projects until we have
                                // figured out how big our StdDev is and how many projects we can run per day
                                // at all (and how many repetitions are needed and possbile time-wise)

                                repo/usage_scenarios/machine/commit/:
                                    mean: // mean per commit/repo etc.
                                    stddev:
                                    ci:
                                    p_value: // Only case A for last key vs compare to the rest. one-sided t-test
                                    significant: // Only case A .... one-sided t-test
                                    values: [] // 1 for stats.html. 1+ for cases
                                    max_values: []
                                repo/usage_scenarios/machine/commit/:
                                repo/usage_scenarios/machine/commit/:
                                    ...
                        container_1: {...},
                        ...
            ane_power_powermetrics_system: {...},
            ...
    '''

    phase_stats_object = {
        'comparison_type': case,
        'comparison_details': set(),
        'data': {}
    }

    prev_key = None

    for phase_stat in phase_stats:
        [
            phase, metric_name, detail_name, value, metric_type, max_value, unit,
            repo, machine_id, usage_scenario_file, commit_hash
        ] = phase_stat # unpack

        phase = phase.split('_', maxsplit=1)[1] # remove the 001_ prepended stuff again, which is only for ordering

        system_energy = False

        # do not set unit, cause otherwise next conversion will fail
        # do not convert if null, cause null/number = number. We want to keep null
        if max_value is not None:  [max_value, _] = convertValue(max_value, unit)
        [value, unit] = convertValue(value, unit)

        if phase not in phase_stats_object['data']: phase_stats_object['data'][phase] = {}

        if metric_name not in phase_stats_object['data'][phase]:
            phase_stats_object['data'][phase][metric_name] = {
                'clean_name': METRIC_MAPPINGS[metric_name]['clean_name'],
                'name': metric_name,
                'explanation': METRIC_MAPPINGS[metric_name]['explanation'],
                'type': metric_type,
                'unit': unit,
                'detail_name': detail_name,
                'color': METRIC_MAPPINGS[metric_name]['color'],
                'icon': METRIC_MAPPINGS[metric_name]['icon'],
                'system_energy': system_energy,
                #'mean': None, # currently no use for that
                #'stddev': None,  # currently no use for that
                #'ci': None,  # currently no use for that
                #'p_value': None,  # currently no use for that
                #'significant': None,  # currently no use for that
                'data': {},
            }

        if detail_name not in phase_stats_object['data'][phase][metric_name]['data']:
            phase_stats_object['data'][phase][metric_name]['data'][detail_name] = {
                'mean': None,
                'stddev': None,
                'ci': None,
                'p_value': None,
                'significant': None,
                'data': {}
            }

        if case == 'Repositories':
            key = repo # Case D : RequirementsEngineering Case
        elif case == 'Usage Scenarios':
            key = usage_scenario_file # Case C_2 : SoftwareDeveloper Case
        elif case == 'Machines':
            key = machine_id # Case C_1 : DataCenter Case
        else:
            key = commit_hash # No comparison case / Case A: Blue Angel / Case B: DevOps Case

        if key not in phase_stats_object['data'][phase][metric_name]['data'][detail_name]['data']:
            phase_stats_object['comparison_details'].add(key)
            phase_stats_object['data'][phase][metric_name]['data'][detail_name]['data'][key] = {
                'mean': None,
                'stddev': None,
                'ci': None,
                'p_value': None, # only for the last key the list compare to the rest. one-sided t-test
                'significant': None, # only for the last key the list compare to the rest. one-sided t-test
                'values': [],
                'max_values': [],

            }

        phase_stats_object['data'][phase][metric_name]['data'][detail_name]['data'][key]['values'].append(value)
        phase_stats_object['data'][phase][metric_name]['data'][detail_name]['data'][key]['max_values'].append(max_value)

    phase_stats_object['comparison_details'] = list(phase_stats_object['comparison_details'])

    # now we need to traverse the object again and calculate all the averages we need
    # This could have also been done while constructing the object through checking when a change
    # in phase / detail_name etc. occurs. But we choose

    for phase, phase_data in phase_stats_object['data'].items():
        for metric_name, metric in phase_data.items():
            for detail_name, detail in metric['data'].items():
                data_list = []
                for comparison_key, data in detail['data'].items():
                    data_list.append(data['values'])
                    t_stat = get_t_stat(len(data['values']))
                    if t_stat is None:
                        data['mean'] = data['values'][0]
                    else:
                        data['mean'] = np.mean(data['values'])
                        data['stddev'] = np.std(data['values'])
                        data['ci'] = data['stddev']*t_stat
                        if len(data['values']) > 2:
                            data_c = data['values'].copy()
                            pop_mean = data_c.pop()
                            _, p_value = scipy.stats.ttest_1samp(data_c, pop_mean)
                            if not np.isnan(p_value):
                                data['p_value'] = p_value
                                if data['p_value'] > 0.05:
                                    data['significant'] = False
                                else:
                                    data['significant'] = True

                        # TODO: data['max'] = np.max(data['max_values'])
                        # TODO: One-sided t-test for the last value

                # detail loop level
                # We can now make a t-test between comparsion_keys on detail level, if we have at least 2 values
                if len(data_list) == 2:
                    # Welch-Test because we cannot assume equal variances
                    _, p_value = scipy.stats.ttest_ind(data_list[0], data_list[1], equal_var=False) #
                    if not np.isnan(p_value):
                        detail['p_value'] = p_value
                        if detail['p_value'] > 0.05:
                            detail['significant'] = False
                        else:
                            detail['significant'] = True
            # metric loop level
            # here we have t-tests between the different metrics between the two compare keys
            # does that make sense though? what would be the average over all details if there are more than one?
            # This makes sense only if we have multiple containers for a metric
            # But these containers could actually measure totally different stuff, like Redis and NGINX
            # What good is a mean here?
        # phase loop level
    return phase_stats_object

@cache
def get_t_stat(length):
    #alpha = .05
    if length <= 1: return None
    dof = length-1
    t_crit = np.abs(scipy.stats.t.ppf((.05)/2,dof)) # for two sided!
    return t_crit/np.sqrt(length)