#!/usr/bin/env python3

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import re
import time
import subprocess
import json
import argparse
from pathlib import Path

from lib.job.base import Job
from lib.global_config import GlobalConfig
from lib.db import DB
from lib.repo_info import get_repo_info
from lib import validate
from lib.temperature import get_temperature
from lib import error_helpers
from lib.configuration_check_error import ConfigurationCheckError, Status

# We currently have this dynamically as it will probably change quite a bit
STATUS_LIST = ['cooldown', 'warmup', 'job_no', 'job_start', 'job_error', 'job_end', 'maintenance_start', 'maintenance_end', 'maintenance_error', 'measurement_control_start', 'measurement_control_end', 'measurement_control_error']

GMT_ROOT_DIR = Path(__file__).resolve().parent.parent

def set_status(status_code, data=None, run_id=None):
    if not hasattr(set_status, "last_status"):
        set_status.last_status = status_code  # static variable
    elif set_status.last_status == status_code:
        return # no need to update status, if it has not changed since last time
    set_status.last_status = status_code

    config = GlobalConfig().config # pylint: disable=redefined-outer-name

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
        SET status_code=%s, base_temperature=%s, jobs_processing=%s, gmt_hash=%s, gmt_timestamp=%s, configuration=%s
        WHERE id = %s
    """

    gmt_hash, gmt_timestamp = get_repo_info(GMT_ROOT_DIR)

    params = (
        status_code,
        config['machine']['base_temperature_value'], config['cluster']['client']['jobs_processing'],
        gmt_hash, gmt_timestamp,
        json.dumps({'measurement': config['measurement'], 'machine': config['machine'], 'cluster': config['cluster']}),
        config['machine']['id'],

    )
    DB().query(query=query, params=params)

def do_maintenance():
    config = GlobalConfig().config # pylint: disable=redefined-outer-name

    set_status('maintenance_start')

    python_realpath = Path('/usr/bin/python3').resolve(strict=True) # bc typically symlinked to python3.12 or similar

    maintenance_cmd = ['sudo', python_realpath, Path(__file__).parent.joinpath('../tools/cluster/maintenance.py').resolve().as_posix()]

    # first we need to determine if an apt update is also necessary. We only want to update once a day
    now = time.time()
    if not config['cluster']['client']['update_os_packages']:
        print('Cluster OS Package updates are disabled. Skipping in maintenance ...')
    elif (not Path('/var/log/apt/history.log').exists()) or ((now - Path('/var/log/apt/history.log').stat().st_mtime) > 86400):
        print("history.log is older than 24 hours. Updating OS packages in maintenance")
        maintenance_cmd.append('--update-os-packages')
    else:
        print("history.log is still newer than 24 hours. Skipping OS updates in maintenance ...")

    ps = subprocess.run(
        maintenance_cmd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # put both in one stream
        encoding='UTF-8',
        errors='replace',
    )
    if ps.returncode != 0:
        set_status('maintenance_error')
        error_helpers.log_error('Cluster maintenance failed', stdout=ps.stdout)
        time.sleep(config['cluster']['client']['time_between_control_workload_validations'])

    set_status('maintenance_end', data=ps.stdout)

    if updated_apt_packages := re.findall(r'<<<< UPDATED APT PACKAGES >>>>\n(.*)\n<<<< END UPDATED APT PACKAGES >>>>', ps.stdout, re.DOTALL):
        updated_apt_packages_list = updated_apt_packages[0].split('\n')
        DB().query('INSERT INTO cluster_changelog (message, machine_id) VALUES (%s, %s)', params=(updated_apt_packages_list, config['machine']['id']))

        return True # must run validation workload again. New packages installed

    return None

def validate_temperature():
    config = GlobalConfig().config # pylint: disable=redefined-outer-name

    if not hasattr(validate_temperature, "temperature_errors") or not hasattr(validate_temperature, "cooldown_time"):
        validate_temperature.temperature_errors = 0  # initialize static variable
        validate_temperature.cooldown_time = 0  # initialize static variable

    current_temperature = get_temperature(
        config['machine']['base_temperature_chip'],
        config['machine']['base_temperature_feature']
    )

    DB().query('UPDATE machines SET current_temperature=%s WHERE id = %s', params=(current_temperature, config['machine']['id']))

    if current_temperature > config['machine']['base_temperature_value']:
        if validate_temperature.temperature_errors >= 10:
            raise RuntimeError(f"Temperature could not be stabilized in time. Was {current_temperature} but should be {config['machine']['base_temperature_value']}. Pleae check logs ...")

        print(f"Machine is still too hot: {current_temperature}°. Sleeping for 1 minute")
        set_status('cooldown')
        validate_temperature.cooldown_time += 60
        validate_temperature.temperature_errors += 1
        time.sleep(60)
        return False

    if current_temperature <= (config['machine']['base_temperature_value'] - 10):
        if validate_temperature.temperature_errors >= 10:
            raise RuntimeError(f"Temperature could not be stabilized in time. Was {current_temperature} but should be {config['machine']['base_temperature_value']}. Pleae check logs ...")

        print(f"Machine is too cool: {current_temperature}°. Warming up and retrying")
        set_status('warmup')
        validate_temperature.temperature_errors += 1

        # stress all cores with constant yes operation
        subprocess.check_output('for i in $(seq $(nproc)); do yes > /dev/null & done', shell=True, encoding='UTF-8', errors='replace')
        time.sleep(300)
        subprocess.check_output(['killall', 'yes'], encoding='UTF-8', errors='replace')

        return False

    DB().query('UPDATE machines SET cooldown_time_after_job=%s WHERE id = %s', params=(validate_temperature.cooldown_time, config['machine']['id']))

    validate_temperature.temperature_errors = 0 # reset
    validate_temperature.cooldown_time = 0 # reset

    return True

def do_measurement_control():
    config = GlobalConfig().config # pylint: disable=redefined-outer-name
    cwl = config['cluster']['client']['control_workload']

    set_status('measurement_control_start')
    validate.run_workload(cwl['name'], cwl['uri'], cwl['filename'], cwl['branch'])
    set_status('measurement_control_end')

    stddev_data = validate.get_workload_stddev(cwl['uri'], cwl['filename'], cwl['branch'], config['machine']['id'], cwl['comparison_window'], cwl['phase'], cwl['metrics'])
    print('get_workload_stddev returned: ', stddev_data)

    try:
        message = validate.validate_workload_stddev(stddev_data, cwl['metrics'])
        if config['cluster']['client']['send_control_workload_status_mail'] and config['admin']['notification_email']:
            Job.insert(
                'email-simple',
                user_id=0, # User 0 is the [GMT-SYSTEM] user
                email=config['admin']['notification_email'],
                name=f"{config['machine']['description']} is operating normally. All STDDEV fine.",
                message='\n'.join(message)
            )

    except Exception as exception: # pylint: disable=broad-except
        validate.handle_validate_exception(exception)
        set_status('measurement_control_error')
        # the process will now go to sleep for 'time_between_control_workload_validations''
        # This is as long as the next validation is needed and thus it will loop
        # endlessly in validation until manually handled, which is what we want.
        time.sleep(config['cluster']['client']['time_between_control_workload_validations'])

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

        config = GlobalConfig().config

        must_revalidate_bc_new_packages = False
        last_24h_maintenance = 0

        while True:

            # run forced maintenance with maintenance every 24 hours
            if not args.testing and last_24h_maintenance < (time.time() - 43200): # every 12 hours
                must_revalidate_bc_new_packages = do_maintenance()
                last_24h_maintenance = time.time()

            job = Job.get_job('run')
            if job and job.check_job_running():
                error_helpers.log_error('Job is still running. This is usually an error case! Continuing for now ...', machine=config['machine']['description'])
                if not args.testing:
                    time.sleep(config['cluster']['client']['sleep_time_no_job'])
                continue

            if not args.testing:
                if validate_temperature():
                    print('Machine is temperature is good. Continuing ...')
                else:
                    continue # retry all checks

            if not args.testing and (must_revalidate_bc_new_packages or validate.is_validation_needed(config['machine']['id'], config['cluster']['client']['time_between_control_workload_validations'])):
                do_measurement_control()
                must_revalidate_bc_new_packages = False # reset as measurement control has run. even if failed
                continue # re-do temperature checks

            if job:
                set_status('job_start', run_id=job._run_id)
                try:
                    job.process(docker_prune=config['cluster']['client']['docker_prune'], full_docker_prune=config['cluster']['client']['full_docker_prune'])
                    set_status('job_end', run_id=job._run_id)
                except ConfigurationCheckError as exc: # ConfigurationChecks indicate that before the job ran, some setup with the machine was incorrect. So we soft-fail here with sleeps
                    set_status('job_error', data=str(exc), run_id=job._run_id)
                    if exc.status == Status.WARN: # Warnings is something like CPU% too high. Here short sleep
                        sleep_duration=600 # seconds = 5 Min
                        error_helpers.log_error('Job processing in cluster failed (client.py)',
                            exception_context=exc.__context__,
                            last_exception=exc,
                            status=exc.status,
                            run_id=job._run_id,
                            name=job._name,
                            url=job._url,
                            filename=job._filename,
                            branch=job._branch,
                            machine=config['machine']['description'],
                            user_id=job._user_id,
                            sleep_duration=sleep_duration,
                        )
                        if not args.testing:
                            time.sleep(sleep_duration)
                    else: # Hard fails won't resolve on it's own. We sleep until next cluster validation
                        sleep_duration=config['cluster']['client']['time_between_control_workload_validations']
                        error_helpers.log_error('Job processing in cluster failed (client.py)',
                            exception_context=exc.__context__,
                            last_exception=exc,
                            status=exc.status,
                            run_id=job._run_id,
                            name=job._name,
                            url=job._url,
                            filename=job._filename,
                            branch=job._branch,
                            machine=config['machine']['description'],
                            user_id=job._user_id,
                            sleep_duration=sleep_duration,
                        )
                        if not args.testing:
                            time.sleep(sleep_duration)

                except Exception as exc: # pylint: disable=broad-except
                    set_status('job_error', data=str(exc), run_id=job._run_id)
                    error_helpers.log_error('Job processing in cluster failed (client.py)',
                        exception_context=exc.__context__,
                        last_exception=exc,
                        stdout=(exc.stdout if hasattr(exc, 'stdout') else None),
                        stderr=(exc.stderr if hasattr(exc, 'stderr') else None),
                        run_id=job._run_id,
                        name=job._name,
                        url=job._url,
                        filename=job._filename,
                        branch=job._branch,
                        machine=config['machine']['description'],
                        user_id=job._user_id,
                    )

                    # reduced error message to client, but only if no ConfigurationCheckError
                    if job._email:
                        Job.insert(
                            'email-simple',
                            user_id=job._user_id,
                            email=job._email,
                            name='Measurement Job on Green Metrics Tool Cluster failed',
                            message=f"Run-ID: {job._run_id}\nName: {job._name}\nMachine: {job._machine_description}\n\nDetails can also be found in the log under: {config['cluster']['metrics_url']}/stats.html?id={job._run_id}\n\nError message: {exc.__context__}\n{exc}\n\nStdout:{exc.stdout if hasattr(exc, 'stdout') else None}\nStderr:{exc.stderr if hasattr(exc, 'stderr') else None}\n"
                        )
                finally: # run periodic maintenance between every run
                    if not args.testing:
                        must_revalidate_bc_new_packages = do_maintenance() # when new packages are installed, we must revalidate
                        last_24h_maintenance = time.time()

            else:
                set_status('job_no')
                if config['cluster']['client']['shutdown_on_job_no']:
                    subprocess.check_output(['sync'], encoding='UTF-8', errors='replace')
                    time.sleep(60) # sleep for 60 before going to suspend to allow logins to cluster when systems are fresh rebooted for maintenance
                    subprocess.check_output(['sudo', 'systemctl', config['cluster']['client']['shutdown_on_job_no']], encoding='UTF-8', errors='replace')

                if not args.testing:
                    time.sleep(config['cluster']['client']['sleep_time_no_job'])

            if args.testing:
                print('Successfully ended testing run of client.py')
                break

    except KeyboardInterrupt:
        pass
    except BaseException as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception_context=exc.__context__, last_exception=exc, machine=config['machine']['description'])

    DB().shutdown()
