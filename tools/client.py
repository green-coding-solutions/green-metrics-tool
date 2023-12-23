#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import os
import time
import subprocess

from tools.jobs import Job, handle_job_exception
from lib.global_config import GlobalConfig
from lib.db import DB
from tools import validate
from lib import email_helpers

# We currently have this dynamically as it will probably change quite a bit
STATUS_LIST = ['job_no', 'job_start', 'job_error', 'job_end', 'cleanup_start', 'cleanup_stop', 'measurement_control_start', 'measurement_control_end', 'measurement_control_error']

def set_status(status_code, data=None, run_id=None):
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
        SET status_code=%s, cooldown_time_after_job=%s
        WHERE id = %s
    """
    params = (status_code, client['cooldown_time_after_job'], config['machine']['id'])
    DB().query(query=query, params=params)

def do_cleanup():
    set_status('cleanup_start')

    result = subprocess.run(['sudo',
                             os.path.join(os.path.dirname(os.path.abspath(__file__)),'cluster/cleanup.sh')],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            check=True,)

    set_status('cleanup_stop', f"stdout: {result.stdout}, stderr: {result.stderr}")


# pylint: disable=broad-except
if __name__ == '__main__':
    client_main = GlobalConfig().config['cluster']['client']
    cwl = client_main['control_workload']

    first_start = True

    while True:
        job = Job.get_job('run')

        if first_start or validate.is_validation_needed(client_main['time_between_control_workload_validations']):
            set_status('measurement_control_start')
            validate.run_workload(cwl['name'], cwl['uri'], cwl['filename'], cwl['branch'])
            set_status('measurement_control_end')

            stddev_data = validate.get_workload_stddev(cwl['repo_uri'], cwl['filename'], cwl['branch'], GlobalConfig().config['machine']['id'], cwl['comparison_window'], cwl['phase'], cwl['metrics'])
            print('get_workload_stddev returned: ', stddev_data)

            try:
                message = validate.validate_workload_stddev(stddev_data, cwl['threshold'])
                if GlobalConfig().config['admin']['no_emails'] is False and cwl['send_control_workload_status_mail']:
                    email_helpers.send_admin_email(f"Machine is operating normally. All STDDEV below {cwl['threshold'] * 100} %", "\n".join(message))
            except Exception as exception:
                validate.handle_validate_exception(exception)
                set_status('measurement_control_error')
                # the process will now go to sleep for 'time_between_control_workload_validations''
                # This is as long as the next validation is needed and thus it will loop
                # endlessly in validation until manually handled, which is what we want.
                time.sleep(client_main['time_between_control_workload_validations'])
            finally:
                time.sleep(client_main['cooldown_time_after_job'])
                do_cleanup()

        elif job:
            set_status('job_start', '', job._run_id)
            try:
                job.process(docker_prune=True)
                set_status('job_end', '', job._run_id)
            except Exception as exc:
                set_status('job_error', str(exc), job._run_id)
                handle_job_exception(exc, job)
            finally:
                time.sleep(client_main['cooldown_time_after_job'])
                do_cleanup()

        else:
            do_cleanup()
            set_status('job_no')
            time.sleep(client_main['sleep_time_no_job'])

        first_start = False
