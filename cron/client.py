#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os
import time
import subprocess
import json
import argparse

from lib.job.base import Job
from lib.global_config import GlobalConfig
from lib.db import DB
from lib.repo_info import get_repo_info
from lib import validate
from lib.temperature import get_temperature
from lib import error_helpers
from lib.configuration_check_error import ConfigurationCheckError, Status

# We currently have this dynamically as it will probably change quite a bit
STATUS_LIST = ['cooldown', 'warmup', 'job_no', 'job_start', 'job_error', 'job_end', 'cleanup_start', 'cleanup_end', 'measurement_control_start', 'measurement_control_end', 'measurement_control_error']
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def set_status(status_code, cur_temp, cooldown_time_after_job, data=None, run_id=None):
    if not hasattr(set_status, "last_status"):
        set_status.last_status = status_code  # static variable
    elif set_status.last_status == status_code:
        return # no need to update status, if it has not changed since last time
    set_status.last_status = status_code

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
        json.dumps({'measurement': config['measurement'], 'machine': config['machine'], 'cluster': config['cluster']}),
        config['machine']['id'],

    )
    DB().query(query=query, params=params)

def do_cleanup(cur_temp, cooldown_time_after_job):
    set_status('cleanup_start', cur_temp, cooldown_time_after_job)

    result = subprocess.run(['sudo',
                             os.path.join(os.path.dirname(os.path.abspath(__file__)),'../tools/cluster/cleanup.sh')],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=True,)

    set_status('cleanup_end', cur_temp, cooldown_time_after_job, data=f"stdout: {result.stdout}, stderr: {result.stderr}")


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--testing', action='store_true', help='End after processing one run for testing')
        parser.add_argument('--config-override', type=str, help='Override the configuration file with the passed in yml file. Supply full path.')

        args = parser.parse_args()

        if args.config_override is not None:
            if args.config_override[-4:] != '.yml':
                parser.print_help()
                error_helpers.log_error('Config override file must be a yml file')
                sys.exit(1)
            GlobalConfig(config_location=args.config_override) # will create a singleton and subsequent calls will retrieve object with altered default config file

        config_main = GlobalConfig().config

        client_main = config_main['cluster']['client']
        cwl = client_main['control_workload']
        cooldown_time = 0
        last_cooldown_time = 0
        current_temperature = -1
        temperature_errors = 0
        last_cleanup = 0

        while True:
            job = Job.get_job('run')
            if job and job.check_job_running():
                error_helpers.log_error('Job is still running. This is usually an error case! Continuing for now ...', machine=config_main['machine']['description'])
                if not args.testing:
                    time.sleep(client_main['sleep_time_no_job'])
                continue

            if not args.testing:

                if last_cleanup < (time.time() - 43200): # every 12 hours
                    do_cleanup(current_temperature, last_cooldown_time)
                    last_cleanup = time.time()

                current_temperature = get_temperature(
                    GlobalConfig().config['machine']['base_temperature_chip'],
                    GlobalConfig().config['machine']['base_temperature_feature']
                )

                if current_temperature > config_main['machine']['base_temperature_value']:
                    if temperature_errors >= 10:
                        raise RuntimeError(f"Temperature could not be stabilized in time. Was {current_temperature} but should be {GlobalConfig().config['machine']['base_temperature_value']}. Pleae check logs ...")

                    print(f"Machine is still too hot: {current_temperature}°. Sleeping for 1 minute")
                    set_status('cooldown', current_temperature, last_cooldown_time)
                    cooldown_time += 60
                    temperature_errors += 1
                    if not args.testing:
                        time.sleep(60)
                    continue

                if current_temperature <= (config_main['machine']['base_temperature_value'] - 10):
                    if temperature_errors >= 10:
                        raise RuntimeError(f"Temperature could not be stabilized in time. Was {current_temperature} but should be {GlobalConfig().config['machine']['base_temperature_value']}. Pleae check logs ...")

                    print(f"Machine is too cool: {current_temperature}°. Warming up and retrying")
                    set_status('warmup', current_temperature, last_cooldown_time)
                    temperature_errors += 1
                    current_time = time.time()
                    while True: # spinlock
                        if time.time() > (current_time + 10):
                            break
                    continue # still retry loop and make all checks again

                print('Machine is temperature is good. Continuing ...')
                last_cooldown_time = cooldown_time
                cooldown_time = 0
                temperature_errors = 0

            if not args.testing and validate.is_validation_needed(config_main['machine']['id'], client_main['time_between_control_workload_validations']):
                set_status('measurement_control_start', current_temperature, last_cooldown_time)
                validate.run_workload(cwl['name'], cwl['uri'], cwl['filename'], cwl['branch'])
                set_status('measurement_control_end', current_temperature, last_cooldown_time)

                stddev_data = validate.get_workload_stddev(cwl['uri'], cwl['filename'], cwl['branch'], config_main['machine']['id'], cwl['comparison_window'], cwl['phase'], cwl['metrics'])
                print('get_workload_stddev returned: ', stddev_data)

                try:
                    message = validate.validate_workload_stddev(stddev_data, cwl['metrics'])
                    if client_main['send_control_workload_status_mail'] and config_main['admin']['notification_email']:
                        Job.insert(
                            'email',
                            user_id=0, # User 0 is the [GMT-SYSTEM] user
                            email=config_main['admin']['notification_email'],
                            name=f"{config_main['machine']['description']} is operating normally. All STDDEV fine.",
                            message='\n'.join(message)
                        )
                except Exception as exception: # pylint: disable=broad-except
                    validate.handle_validate_exception(exception)
                    set_status('measurement_control_error', current_temperature, last_cooldown_time)
                    # the process will now go to sleep for 'time_between_control_workload_validations''
                    # This is as long as the next validation is needed and thus it will loop
                    # endlessly in validation until manually handled, which is what we want.
                    if not args.testing:
                        time.sleep(client_main['time_between_control_workload_validations'])

            elif job:
                set_status('job_start', current_temperature, last_cooldown_time, run_id=job._run_id)
                try:
                    job.process(docker_prune=True)
                    set_status('job_end', current_temperature, last_cooldown_time, run_id=job._run_id)
                except ConfigurationCheckError as exc: # ConfigurationChecks indicate that before the job ran, some setup with the machine was incorrect. So we soft-fail here with sleeps
                    set_status('job_error', current_temperature, last_cooldown_time, data=str(exc), run_id=job._run_id)
                    if exc.status == Status.WARN: # Warnings is something like CPU% too high. Here short sleep
                        error_helpers.log_error('Job processing in cluster failed (client.py)', exception_context=exc.__context__, last_exception=exc, status=exc.status, run_id=job._run_id, name=job._name, url=job._url, machine=config_main['machine']['description'], sleep_duration=600)
                        if not args.testing:
                            time.sleep(600)
                    else: # Hard fails won't resolve on it's own. We sleep until next cluster validation
                        error_helpers.log_error('Job processing in cluster failed (client.py)', exception_context=exc.__context__, last_exception=exc, status=exc.status, run_id=job._run_id, name=job._name, url=job._url, machine=config_main['machine']['description'], sleep_duration=client_main['time_between_control_workload_validations'])
                        if not args.testing:
                            time.sleep(client_main['time_between_control_workload_validations'])

                except Exception as exc: # pylint: disable=broad-except
                    set_status('job_error', current_temperature, last_cooldown_time, data=str(exc), run_id=job._run_id)
                    error_helpers.log_error('Job processing in cluster failed (client.py)',
                        exception_context=exc.__context__,
                        last_exception=exc,
                        stdout=(exc.stdout if hasattr(exc, 'stdout') else None),
                        stderr=(exc.stderr if hasattr(exc, 'stderr') else None),
                        run_id=job._run_id,
                        machine=config_main['machine']['description'],
                        name=job._name,
                        url=job._url
                    )

                    # reduced error message to client, but only if no ConfigurationCheckError
                    if job._email:
                        Job.insert(
                            'email',
                            user_id=job._user_id,
                            email=job._email,
                            name='Measurement Job on Green Metrics Tool Cluster failed',
                            message=f"Run-ID: {job._run_id}\nName: {job._name}\nMachine: {job._machine_description}\n\nDetails can also be found in the log under: {config_main['cluster']['metrics_url']}/stats.html?id={job._run_id}\n\nError message: {exc.__context__}\n{exc}\n"
                        )

            else:
                set_status('job_no', current_temperature, last_cooldown_time)
                if client_main['shutdown_on_job_no']:
                    subprocess.check_output(['sudo', 'systemctl', client_main['shutdown_on_job_no']])
                if not args.testing:
                    time.sleep(client_main['sleep_time_no_job'])
            if args.testing:
                print('Successfully ended testing run of client.py')
                break

    except BaseException as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception_context=exc.__context__, last_exception=exc, machine=config_main['machine']['description'])
