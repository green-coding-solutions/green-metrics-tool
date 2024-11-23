#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
This script can validate the current machines energy profile
when a control workload is given.

It will do so by running the workload and comparing it to the last 5 occurences it
can find in the database.

The configuration decides which metrics to take into accoutnt. We recommend using only
energy metrics.

However if your workload also incorporates an SCI value it makes sense to also have that integrated
as it also tries to compare the throughput of the machine then.

This script is designed to be run manually via direct call or to be utilized as includes in the client.py

'''

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.global_config import GlobalConfig
from lib.db import DB
from lib.terminal_colors import TerminalColors
from lib import error_helpers

from runner import Runner

class ValidationWorkloadStddevError(RuntimeError):
    pass


def get_workload_stddev(repo_uri, filename, branch, machine_id, comparison_window, phase, metrics):
    query = """
        WITH LastXRows AS (
            SELECT id
            FROM runs
            WHERE
                uri = %s
                AND filename = %s
                AND branch = %s
                AND machine_id = %s
                AND end_measurement IS NOT NULL
                AND failed != TRUE
            ORDER BY created_at DESC
            LIMIT %s
        ) SELECT
            metric, detail_name, phase, type,
            AVG(value) as "avg",
            COALESCE(STDDEV(value), 0) as "stddev",
            COALESCE(STDDEV(value) / AVG(value), 0) as "stddev_rel",
            unit
          FROM phase_stats
          WHERE
            phase = %s
            AND metric IN ($list_replace)
            AND run_id IN (SELECT id FROM LastXRows)
          GROUP BY
            metric, detail_name, phase, type, unit
    """
    # We are using now the STDDEV of the sample for two reasons:
    # It is required by the Blue Angel for Software
    # We got many debates that in cases where the average is only estimated through measurements and is not absolute
    # one MUST use the sample STDDEV.
    # Still one could argue that one does not want to characterize the measured software but rather the measurement setup
    # it is safer to use the sample STDDEV as it is always higher

    placeholders = ', '.join(['%s'] * len(metrics))
    query = query.replace('$list_replace', placeholders)

    params = (repo_uri, filename, branch, machine_id, comparison_window, phase, *(metrics))
    return DB().fetch_all(query=query, params=params, fetch_mode='dict')


def run_workload(name, uri, filename, branch):
    runner = Runner(
        name=name,
        uri=uri,
        uri_type='URL',
        filename=filename,
        branch=branch,
        skip_unsafe=True,
        skip_system_checks=None,
        full_docker_prune=False,
        docker_prune=True,
        job_id=None,
    )
    # Start main code. Only URL is allowed for cron jobs
    runner.run()

def validate_workload_stddev(data, metrics):
    warning = False
    info_string_acc = []
    for el in data:
        info_string = f"{el['metric']} {el['detail_name']}: {el['avg']} +/- {el['stddev']} {el['stddev_rel']*100} %"
        info_string_acc.append(info_string)

        if metrics[el['metric']]['type'] == 'stddev_rel':
            if el['stddev_rel'] > metrics[el['metric']]['threshold']:
                info_string_acc.append(f"=> Warning! Threshold of {metrics[el['metric']]['threshold']} exceeded. Value is: {el['stddev_rel']}. Metric: {el['metric']}")
                warning = True
        elif metrics[el['metric']]['type'] == 'stddev':
            if el['stddev'] > metrics[el['metric']]['threshold']:
                info_string_acc.append(f"=> Warning! Threshold of {metrics[el['metric']]['threshold']} exceeded. Value is: {el['stddev']}. Metric: {el['metric']}")
                warning = True
        else:
            raise ValueError(f"{el['metric']} had unknown threshhold validation type: {metrics[el['metric']]['type']}")

    if warning:
        print(TerminalColors.FAIL, 'Aborting!', TerminalColors.ENDC)
        raise ValidationWorkloadStddevError("\n".join(info_string_acc))
    print(TerminalColors.OKGREEN, 'Machine is operating normally. All STDDEV fine.', TerminalColors.ENDC)

    return info_string_acc

def is_validation_needed(machine_id, duration):
    query = '''
        SELECT id
        FROM client_status
        WHERE
            status_code = 'measurement_control_end'
            AND EXTRACT(EPOCH FROM CURRENT_TIMESTAMP - created_at) < %s
            AND machine_id = %s
        ORDER BY created_at DESC
    '''
    data = DB().fetch_one(query=query, params=(duration, machine_id))
    return data is None or data == []

def handle_validate_exception(exc):
    config = GlobalConfig().config
    control_workload = config['cluster']['client']['control_workload']

    error_helpers.log_error('handle_validate_exception: ', exception=exc, details=f"Please check under {config['cluster']['metrics_url']}/timeline.html?uri={control_workload['uri']}&branch={control_workload['branch']}&filename={control_workload['filename']}&machine_id={config['machine']['id']}", name='Measurement control Workload (on boot)', machine=config['machine']['description'])

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-run', action='store_true', help='Skips running a workload and will just check for STDDEV')

    args = parser.parse_args()

    config_main = GlobalConfig().config
    client = config_main['cluster']['client']
    cwl = client['control_workload']

    if not args.skip_run:
        run_workload(cwl['name'], cwl['uri'], cwl['filename'], cwl['branch'])

    stddev_data = get_workload_stddev(cwl['uri'], cwl['filename'], cwl['branch'], config_main['machine']['id'], cwl['comparison_window'], cwl['phase'], cwl['metrics'])
    print('get_workload_stddev returned: ', stddev_data)

    message = validate_workload_stddev(stddev_data, cwl['metrics'])
    print('validate_workload_stddev returned:', message)
