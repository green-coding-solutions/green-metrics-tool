# pylint: disable=import-error
# pylint: disable=wrong-import-position

import sys
import os
import faulthandler
import time
import subprocess

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../lib')

from jobs import get_job, process_job
from global_config import GlobalConfig
from db import DB


faulthandler.enable()  # will catch segfaults and write to STDERR

# We currently have this dynamically as it will probably change quite a bit
STATUS_LIST = ['job_no', 'job_start', 'job_error', 'job_end', 'cleanup_start', 'cleanup_stop']


def set_status(status_code, data=None, project_id=None):
    if status_code not in STATUS_LIST:
        raise ValueError(f"Status code not valid: '{status_code}'. Should be in: {STATUS_LIST}")

    query = """
        INSERT INTO
            client_status (status_code, machine_id, data, project_id)
        VALUES (%s, %s, %s, %s)
    """
    params = (status_code, GlobalConfig().config['config']['machine_id'], data, project_id)
    DB().query(query=query, params=params)



if __name__ == '__main__':

    while True:
        job = get_job('project')

        if (job is None or job == []):
            set_status('job_no')
            time.sleep(GlobalConfig().config['client']['sleep_time'])
        else:
            project_id = job[2]
            set_status('job_start', '', project_id)
            try:
                process_job(*job)
            except Exception as exc:
                set_status('job_error', str(exc), project_id)
            else:
                set_status('job_end', '', project_id)

            set_status('cleanup_start')

            result = subprocess.run(['sudo',
                                     os.path.join(os.path.dirname(os.path.abspath(__file__)),'cluster/cleanup.sh')],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    check=True,)

            set_status('cleanup_stop', f"stdout: {result.stdout}, stderr: {result.stderr}")
