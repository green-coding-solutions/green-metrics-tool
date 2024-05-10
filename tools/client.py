#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import os
import sys
import time
import subprocess
import json
from pathlib import Path

from lib.job.base import Job
from lib.global_config import GlobalConfig
from lib.db import DB
from lib.repo_info import get_repo_info
from tools import validate
from tools.temperature import get_temperature
from lib import error_helpers
from lib.configuration_check_error import ConfigurationCheckError, Status

# We currently have this dynamically as it will probably change quite a bit
STATUS_LIST = ['cooldown', 'job_no', 'job_start', 'job_error', 'job_end', 'cleanup_start', 'cleanup_end', 'measurement_control_start', 'measurement_control_end', 'measurement_control_error']
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def set_status(status_code, cur_temp, cooldown_time_after_job, data=None, run_id=None):
    # pylint: disable=redefined-outer-name
    config = GlobalConfig().config
    client = config['cluster']['client']

    if status_code not in STATUS_LIST:
        raise ValueError(f"Status code not valid: '{status_code}'. Should be in: {STATUS_LIST}")

    query = """
        INSERT INTO
            client_status (status_code, machine_id, data, run_id)
        VALUES (%s, %s, %s, %s)
    """
    params = (status_code, config['machine']['id'], data, run_id)
    DB().query(query=query, params=params)

    query = """
        UPDATE machines
        SET status_code=%s, cooldown_time_after_job=%s, current_temperature=%s, base_temperature=%s, jobs_processing=%s, gmt_hash=%s, gmt_timestamp=%s, configuration=%s
        WHERE id = %s
    """

    gmt_hash, gmt_timestamp = get_repo_info(CURRENT_DIR)

    params = (
        status_code, cooldown_time_after_job, cur_temp,
        config['machine']['base_temperature_value'], client['jobs_processing'],
        gmt_hash, gmt_timestamp,
        json.dumps({"measurement": config['measurement'], "machine": config['machine']}),
        config['machine']['id'],

    )
    DB().query(query=query, params=params)

def do_cleanup(cur_temp, cooldown_time_after_job):
    set_status('cleanup_start', cur_temp, cooldown_time_after_job)

    result = subprocess.run(['sudo',
                             os.path.join(os.path.dirname(os.path.abspath(__file__)),'cluster/cleanup.sh')],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=True,)

    set_status('cleanup_end', cur_temp, cooldown_time_after_job, data=f"stdout: {result.stdout}, stderr: {result.stderr}")


# pylint: disable=broad-except
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--testing', action='store_true', help='End after processing one run for testing')
    parser.add_argument('--config-override', type=str, help='Override the configuration file with the passed in yml file. Must be located in the same directory as the regular configuration file. Pass in only the name.')

    args = parser.parse_args()

    if args.config_override is not None:
        if args.config_override[-4:] != '.yml':
            parser.print_help()
            error_helpers.log_error('Config override file must be a yml file')
            sys.exit(1)
        if not Path(f"{CURRENT_DIR}/../{args.config_override}").is_file():
            parser.print_help()
            error_helpers.log_error(f"Could not find config override file on local system. Please double check: {CURRENT_DIR}/../{args.config_override}")
            sys.exit(1)
        GlobalConfig(config_name=args.config_override) # will create a singleton and subsequent calls will retrieve object with altered default config file

    config_main = GlobalConfig().config


    try:
        client_main = config_main['cluster']['client']
        cwl = client_main['control_workload']
        cooldown_time = 0
        last_cooldown_time = 0
        current_temperature = -1


        while True:
            job = Job.get_job('run')
            if job and job.check_job_running():
                error_helpers.log_error('Job is still running. This is usually an error case! Continuing for now ...')
                time.sleep(client_main['sleep_time_no_job'])
                continue

            if not args.testing:
                current_temperature = get_temperature(
                    GlobalConfig().config['machine']['base_temperature_chip'],
                    GlobalConfig().config['machine']['base_temperature_feature']
                )

                if current_temperature > config_main['machine']['base_temperature_value']:
                    print(f"Machine is still too hot: {current_temperature}°. Sleeping for 1 minute")
                    set_status('cooldown', current_temperature, last_cooldown_time)
                    cooldown_time += 60
                    time.sleep(60)
                    continue

                print('Machine is cool enough. Continuing')
                last_cooldown_time = cooldown_time
                cooldown_time = 0

            if not args.testing and validate.is_validation_needed(config_main['machine']['id'], client_main['time_between_control_workload_validations']):
                set_status('measurement_control_start', current_temperature, last_cooldown_time)
                validate.run_workload(cwl['name'], cwl['uri'], cwl['filename'], cwl['branch'])
                set_status('measurement_control_end', current_temperature, last_cooldown_time)

                stddev_data = validate.get_workload_stddev(cwl['uri'], cwl['filename'], cwl['branch'], config_main['machine']['id'], cwl['comparison_window'], cwl['phase'], cwl['metrics'])
                print('get_workload_stddev returned: ', stddev_data)

                try:
                    message = validate.validate_workload_stddev(stddev_data, cwl['threshold'])
                    if client_main['send_control_workload_status_mail'] and config_main['admin']['notification_email']:
                        Job.insert(
                            'email',
                            email=config_main['admin']['notification_email'],
                            name=f"Machine is operating normally. All STDDEV below {cwl['threshold'] * 100} %",
                            message='\n'.join(message)
                        )
                except Exception as exception:
                    validate.handle_validate_exception(exception)
                    set_status('measurement_control_error', current_temperature, last_cooldown_time)
                    # the process will now go to sleep for 'time_between_control_workload_validations''
                    # This is as long as the next validation is needed and thus it will loop
                    # endlessly in validation until manually handled, which is what we want.
                    time.sleep(client_main['time_between_control_workload_validations'])
                finally:
                    do_cleanup(current_temperature, last_cooldown_time)

            elif job:
                set_status('job_start', current_temperature, last_cooldown_time, run_id=job._run_id)
                try:
                    job.process(docker_prune=True)
                    set_status('job_end', current_temperature, last_cooldown_time, run_id=job._run_id)
                except ConfigurationCheckError as exc: # ConfigurationChecks indicate that before the job ran, some setup with the machine was incorrect. So we soft-fail here with sleeps
                    set_status('job_error', current_temperature, last_cooldown_time, data=str(exc), run_id=job._run_id)
                    if exc.status == Status.WARN: # Warnings is something like CPU% too high. Here short sleep
                        error_helpers.log_error('Job processing in cluster failed (client.py)', exception=exc, status=exc.status, run_id=job._run_id, sleep_duration=600)
                        time.sleep(600)
                    else: # Hard fails won't resolve on it's own. We sleep until next cluster validation
                        error_helpers.log_error('Job processing in cluster failed (client.py)', exception=exc, status=exc.status, run_id=job._run_id, sleep_duration=client_main['time_between_control_workload_validations'])
                        time.sleep(client_main['time_between_control_workload_validations'])

                except Exception as exc:
                    set_status('job_error', current_temperature, last_cooldown_time, data=str(exc), run_id=job._run_id)
                    error_helpers.log_error('Job processing in cluster failed (client.py)', exception=exc, run_id=job._run_id)
                finally:
                    if not args.testing:
                        do_cleanup(current_temperature, last_cooldown_time)

            else:
                do_cleanup(current_temperature, last_cooldown_time)
                set_status('job_no', current_temperature, last_cooldown_time)
                if client_main['shutdown_on_job_no'] is True:
                    subprocess.check_output(['sudo', 'shutdown'])
                time.sleep(client_main['sleep_time_no_job'])
            if args.testing:
                print('Successfully ended testing run of client.py')
                break
    except Exception as exc:
        error_helpers.log_error('Processing in cluster failed (client.py)', exception=exc, machine=config_main['machine']['description'])
