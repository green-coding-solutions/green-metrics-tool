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
'''

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import sys
import time

from lib.global_config import GlobalConfig
from lib.db import DB
from lib.terminal_colors import TerminalColors
from lib import email_helpers
from lib import error_helpers

from runner import Runner
from tools.phase_stats import build_and_store_phase_stats
from tools.client import set_status

def validate_stddev(repo_uri, filename, branch, machine_id, comparison_window, phase, metrics):
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
            ORDER BY created_at DESC
            LIMIT %s
        ) SELECT
            metric, detail_name, phase, type,
            AVG(value) as "avg",
            COALESCE(STDDEV(value), 0) as "stddev",
            COALESCE(STDDEV(value) / AVG(value), 0) as "rel_stddev",
            unit
          FROM phase_stats
          WHERE
            phase = %s
            AND metric IN ($list_replace)
            AND run_id IN (SELECT id FROM LastXRows)
          GROUP BY
            metric, detail_name, phase, type, unit
    """

    placeholders = ', '.join(['%s'] * len(metrics))
    query = query.replace('$list_replace', placeholders)

    params = (repo_uri, filename, branch, machine_id, comparison_window, phase, *(metrics))
    return DB().fetch_all(query=query, params=params)


# pylint: disable=broad-except
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-run', action='store_true', help='Skips running a workload and will just check for STDDEV')

    args = parser.parse_args()

    run_id = None
    config = GlobalConfig().config
    try:
        set_status('measurement_control_start')
        if not args.skip_run:
            runner = Runner(
                name=config['machine']['control_workload']['name'],
                uri=config['machine']['control_workload']['uri'],
                uri_type='URL',
                filename=config['machine']['control_workload']['filename'],
                branch=config['machine']['control_workload']['branch'],
                skip_unsafe=True,
                skip_system_checks=None,
                full_docker_prune=False,
                docker_prune=True,
                job_id=None,
            )
            # Start main code. Only URL is allowed for cron jobs
            run_id = runner.run()
            build_and_store_phase_stats(run_id, runner._sci)

        set_status('measurement_control_end')

        data = validate_stddev(
            config['machine']['control_workload']['uri'],
            config['machine']['control_workload']['filename'],
            config['machine']['control_workload']['branch'],
            config['machine']['id'],
            config['machine']['control_workload']['comparison_window'],
            config['machine']['control_workload']['phase'],
            config['machine']['control_workload']['metrics'],
        )

        print('Validate_stddev returned: ')
        warning = False
        info_string_acc = ''
        for el in data:
            info_string = f"{el[0]} {el[1]}: {el[4]} +/- {el[5]} {el[6]*100} %"
            print(info_string)
            info_string_acc = f"{info_string_acc}\n{info_string}"
            if el[6] > config['machine']['control_workload']['threshhold']:
                print(TerminalColors.FAIL, 'Warning. Threshhold exceeded!', TerminalColors.ENDC)
                warning = True
        if warning:
            print(TerminalColors.FAIL, 'Aborting!', TerminalColors.ENDC)
            raise RuntimeError(info_string_acc)
        print(TerminalColors.OKGREEN, f"Machine is operating normally. All STDDEV below {config['machine']['control_workload']['threshhold'] * 100} %", TerminalColors.ENDC)

        if config['admin']['no_emails'] is False and config['machine']['control_workload']['send_status_mail']:
            email_helpers.send_admin_email(f"Machine is operating normally. All STDDEV below {config['machine']['control_workload']['threshhold'] * 100} %", info_string_acc)

        time.sleep(config['client']['sleep_time_after_job'])

    except Exception as exc:
        error_helpers.log_error('Base exception occurred in validate.py: ', exc, f"Please check under {config['cluster']['metrics_url']}/timeline.html?uri={config['machine']['control_workload']['uri']}&branch={config['machine']['control_workload']['branch']}&filename={config['machine']['control_workload']['filename']}&machine_id={config['machine']['id']}")
        if GlobalConfig().config['admin']['no_emails'] is False:
            email_helpers.send_error_email(config['admin']['email'], error_helpers.format_error(
                'Base exception occurred in validate.py: ', exc, f"Please check under {config['cluster']['metrics_url']}/timeline.html?uri={config['machine']['control_workload']['uri']}&branch={config['machine']['control_workload']['branch']}&filename={config['machine']['control_workload']['filename']}&machine_id={config['machine']['id']}"), run_id=run_id, name='Measurement control Workload (on boot)', machine=config['machine'].get('description'))
        set_status('measurement_control_error')
        sys.exit(1)
