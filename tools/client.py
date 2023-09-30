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

# We currently have this dynamically as it will probably change quite a bit
STATUS_LIST = ['job_no', 'job_start', 'job_error', 'job_end', 'cleanup_start', 'cleanup_stop']

def set_status(status_code, data=None, run_id=None):
    if status_code not in STATUS_LIST:
        raise ValueError(f"Status code not valid: '{status_code}'. Should be in: {STATUS_LIST}")

    query = """
        INSERT INTO
            client_status (status_code, machine_id, data, run_id)
        VALUES (%s, %s, %s, %s)
    """
    params = (status_code, GlobalConfig().config['machine']['id'], data, run_id)
    DB().query(query=query, params=params)


# pylint: disable=broad-exception-caught
if __name__ == '__main__':

    while True:
        job = Job.get_job('run')

        if not job:
            set_status('job_no')
            time.sleep(GlobalConfig().config['client']['sleep_time_no_job'])
        else:
            set_status('job_start', '', job.run_id)
            try:
                job.process(docker_prune=True)
            except Exception as exc:
                set_status('job_error', str(exc), job.run_id)
                handle_job_exception(exc, job)
            else:
                set_status('job_end', '', job.run_id)

            set_status('cleanup_start')

            result = subprocess.run(['sudo', 'bash',
                                     os.path.join(os.path.dirname(os.path.abspath(__file__)),'cluster/cleanup.sh')],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    check=True,)

            set_status('cleanup_stop', f"stdout: {result.stdout}, stderr: {result.stderr}")

            time.sleep(GlobalConfig().config['client']['sleep_time_after_job'])
