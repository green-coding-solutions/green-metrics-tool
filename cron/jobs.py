#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os
from datetime import datetime
import argparse

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import error_helpers
from lib.job.base import Job
from lib.global_config import GlobalConfig
from lib.terminal_colors import TerminalColors
from lib.system_checks import ConfigurationCheckError

"""
    The jobs.py file is effectively a state machine that can insert a job in the 'WAITING'
    state and then push it through the states 'RUNNING', 'FAILED/FINISHED', 'NOTIFYING'
    and 'NOTIFIED'.

    After 14 days all FAILED and NOTIFIED jobs will be deleted.
"""


if __name__ == '__main__':
    job_main = None # needs to be defined in case exception triggers

    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('type', help='Select the operation mode.', choices=['email', 'run'])
        parser.add_argument('--config-override', type=str, help='Override the configuration file with the passed in yml file. Supply full path.')
        parser.add_argument('--skip-system-checks', action='store_true', default=False, help='Skip system checks')
        parser.add_argument('--full-docker-prune', action='store_true', default=False, help='Prune all images and build caches on the system')
        parser.add_argument('--docker-prune', action='store_true', help='Prune all unassociated build caches, networks volumes and stopped containers on the system')

        args = parser.parse_args()  # script will exit if type is not present

        if args.type == 'run':
            print(TerminalColors.WARNING, '\nWarning: Calling Jobs.py with argument "run" directly is deprecated.\nPlease do not use this functionality in a cronjob and only in CLI for testing\n', TerminalColors.ENDC)

        if args.config_override is not None:
            if args.config_override[-4:] != '.yml':
                parser.print_help()
                error_helpers.log_error('Config override file must be a yml file')
                sys.exit(1)
            GlobalConfig(config_location=args.config_override)

        job_main = Job.get_job(args.type)
        if not job_main:
            print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'No job to process. Exiting')
            sys.exit(0)
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'Processing Job ID#: ', job_main._id)
        if args.type == 'run':
            job_main.process(skip_system_checks=args.skip_system_checks, docker_prune=args.docker_prune, full_docker_prune=args.full_docker_prune)
        elif args.type == 'email':
            job_main.process()
        print('Successfully processed jobs queue item.')
    except Exception as exception: #pylint: disable=broad-except
        if job_main:
            error_helpers.log_error('Base exception occurred in jobs.py: ', exception=exception, run_id=job_main._run_id, name=job_main._name, machine=job_main._machine_description)

            # reduced error message to client, but only if no ConfigurationCheckError
            if job_main._email and not isinstance(exception, ConfigurationCheckError):
                Job.insert(
                    'email',
                    user_id=job_main._user_id,
                    email=job_main._email,
                    name='Measurement Job on Green Metrics Tool Cluster failed',
                    message=f"Run-ID: {job_main._run_id}\nName: {job_main._name}\nMachine: {job_main._machine_description}\n\nDetails can also be found in the log under: {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={job_main._run_id}\n\nError message: {exception}\n"
                )
        else:
            error_helpers.log_error('Base exception occurred in jobs.py: ', exception=exception)
