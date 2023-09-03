#pylint: disable=import-error,too-many-instance-attributes
import sys
import os
import faulthandler
from datetime import datetime

faulthandler.enable()  # will catch segfaults and write to STDERR

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/..")
sys.path.append(f"{CURRENT_DIR}/../lib")

import email_helpers
import error_helpers
from db import DB
from global_config import GlobalConfig
from phase_stats import build_and_store_phase_stats
from terminal_colors import TerminalColors

"""
    The jobs.py file is effectively a state machine that can insert a job in the 'WAITING'
    state and then push it through the states 'RUNNING', 'FAILED/FINISHED', 'NOTIFYING'
    and 'NOTIFIED'.

    After 14 days all FAILED and NOTIFIED jobs will be deleted.
"""

class Job:
    def __init__(self, state, name, email, url,  branch, filename, machine_id, run_id=None, job_id=None, machine_description=None):
        self.id = job_id
        self.state = state
        self.name = name
        self.email = email
        self.url = url
        self.branch = branch
        self.filename = filename
        self.machine_id = machine_id
        self.machine_description = machine_description
        self.run_id = run_id

    def check_measurement_job_running(self):
        query = "SELECT id FROM jobs WHERE state = 'RUNNING' AND machine_id = %s"
        params = (self.machine_id,)
        data = DB().fetch_one(query, params=params)
        if data:
            # No email here, only debug
            error_helpers.log_error('Measurement-Job was still running: ', data)
            return True
        return False

    def check_email_job_running(self):
        query = "SELECT id FROM jobs WHERE state = 'NOTIFYING'"
        data = DB().fetch_one(query)
        if data:
            # No email here, only debug
            error_helpers.log_error('Notifying-Job was still running: ', data)
            return True
        return False

    def update_state(self, state):
        query_update = "UPDATE jobs SET state = %s WHERE id=%s"
        params_update = (state, self.id,)
        DB().query(query_update, params=params_update)


    def process(self, skip_system_checks=False, docker_prune=False, full_docker_prune=False):
        try:
            if self.state == 'FINISHED':
                self._do_email_job()
            elif self.state == 'WAITING':
                self._do_run_job(skip_system_checks, docker_prune, full_docker_prune)
            else:
                raise RuntimeError(
                    f"Job w/ id {self.id} has unknown state: {self.state}.")
        except Exception as exc:
            self.update_state('FAILED')
            raise exc

    # should not be called without enclosing try-except block
    def _do_email_job(self):
        if self.check_email_job_running():
            return

        if GlobalConfig().config['admin']['no_emails'] is False and self.email:
            email_helpers.send_report_email(self.email, self.run_id, self.name, machine=self.machine_description)

        self.update_state('NOTIFIED')

    # should not be called without enclosing try-except block
    def _do_run_job(self, skip_system_checks=False, docker_prune=False, full_docker_prune=False):

        if self.check_measurement_job_running():
            return

        #pylint: disable=import-outside-toplevel
        from runner import Runner

        runner = Runner(
            name=self.name,
            uri=self.url,
            uri_type='URL',
            filename=self.filename,
            branch=self.branch,
            skip_unsafe=True,
            skip_system_checks=skip_system_checks,
            full_docker_prune=full_docker_prune,
            docker_prune=docker_prune,
            job_id=self.id,
        )
        try:
            # Start main code. Only URL is allowed for cron jobs
            self.run_id = runner.run()
            build_and_store_phase_stats(self.run_id, runner._sci)
            self.update_state('FINISHED')
        except Exception as exc:
            raise exc

    @classmethod
    def insert(cls, name, url,  email, branch, filename, machine_id):
        query = """
                INSERT INTO
                    jobs (name, url,  email, branch, filename, machine_id, state, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, 'WAITING', NOW()) RETURNING id;
                """
        params = (name, url,  email, branch, filename, machine_id,)
        return DB().fetch_one(query, params=params)[0]

    # A static method to get a job object
    @classmethod
    def get_job(cls, job_type):
        cls.clear_old_jobs()
        state = 'WAITING' if job_type == 'run' else 'FINISHED'
        query = """
            SELECT
                j.id, j.state, j.name, j.email, j.url, j.branch,
                j.filename, j.machine_id, j.run_id, m.description
            FROM jobs as j
            LEFT JOIN machines as m on m.id = j.machine_id
            WHERE j.state = %s AND j.machine_id = %s
            ORDER BY j.created_at ASC
            LIMIT 1
        """

        job = DB().fetch_one(query, params=(state, GlobalConfig().config['machine']['id']))
        if not job:
            return False

        return Job(
            job_id=job[0],
            state=job[1],
            name=job[2],
            email=job[3],
            url=job[4],
            branch=job[5],
            filename=job[6],
            machine_id=job[7],
            run_id=job[8],
            machine_description=job[9]
        )

    @classmethod
    def clear_old_jobs(cls):
        query = '''
            DELETE FROM jobs
            WHERE
                (state = 'RUNNING' AND updated_at < NOW() - INTERVAL '60 minutes')
                OR
                (state = 'NOTIFIED' AND updated_at < NOW() - INTERVAL '14 DAYS')
                OR
                (state = 'FAILED' AND updated_at < NOW() - INTERVAL '14 DAYS')
            '''
        DB().query(query)


# a simple helper method unrelated to the class
def handle_job_exception(exce, job):
    error_helpers.log_error('Base exception occurred in jobs.py: ', exce)

    if GlobalConfig().config['admin']['no_emails'] is False:
        email_helpers.send_error_email(GlobalConfig().config['admin']['email'], error_helpers.format_error(
        'Base exception occurred in jobs.py: ', exce), run_id=job.run_id, name=job.name, machine=job.machine_description)

        # reduced error message to client
        if job.email and GlobalConfig().config['admin']['email'] != job.email:
            email_helpers.send_error_email(job.email, exce, run_id=job.run_id, name=job.name, machine=job.machine_description)

if __name__ == '__main__':
    #pylint: disable=broad-except,invalid-name

    print(TerminalColors.WARNING, '\nWarning: Calling Jobs.py directly is deprecated. Please do not use this functionality in a cronjob and only in CLI for testing\n', TerminalColors.ENDC)

    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument('type', help='Select the operation mode.', choices=['email', 'run'])
    parser.add_argument('--config-override', type=str, help='Override the configuration file with the passed in yml file. Must be located in the same directory as the regular configuration file. Pass in only the name.')
    parser.add_argument('--skip-system-checks', action='store_true', default=False, help='Skip system checks')
    parser.add_argument('--full-docker-prune', action='store_true', default=False, help='Prune all images and build caches on the system')
    parser.add_argument('--docker-prune', action='store_true', help='Prune all unassociated build caches, networks volumes and stopped containers on the system')

    args = parser.parse_args()  # script will exit if type is not present

    if args.config_override is not None:
        if args.config_override[-4:] != '.yml':
            parser.print_help()
            error_helpers.log_error('Config override file must be a yml file')
            sys.exit(1)
        if not Path(f"{CURRENT_DIR}/../{args.config_override}").is_file():
            parser.print_help()
            error_helpers.log_error(f"Could not find config override file on local system.\
                Please double check: {CURRENT_DIR}/../{args.config_override}")
            sys.exit(1)
        GlobalConfig(config_name=args.config_override)

    job_main = None
    try:
        job_main = Job.get_job(args.type)
        if not job_main:
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'No job to process. Exiting')
            sys.exit(0)
        job_main.process(args.skip_system_checks, args.docker_prune, args.full_docker_prune)
        print('Successfully processed jobs queue item.')
    except Exception as exception:
        handle_job_exception(exception, job_main)
