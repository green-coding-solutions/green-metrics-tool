#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=cyclic-import

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.job.base import Job
from lib.global_config import GlobalConfig
from lib.db import DB
from lib.user import User
from lib.terminal_colors import TerminalColors
from lib.system_checks import ConfigurationCheckError
from runner import Runner
import optimization_providers.base


class RunJob(Job):

    def check_job_running(self):
        query = "SELECT id FROM jobs WHERE type = 'run' AND state = 'RUNNING' AND machine_id = %s"
        return DB().fetch_one(query, params=(self._machine_id, ))

    #pylint: disable=arguments-differ
    def _process(self, skip_system_checks=False, docker_prune=False, full_docker_prune=False):

        user = User(self._user_id)

        if not user.can_use_machine(self._machine_id):
            raise RuntimeError(f"Your user does not have the permissions to use the selected machine. Machine ID: {self._machine_id}")

        if not user.has_measurement_quota(self._machine_id):
            raise RuntimeError(f"Your user does not have enough measurement quota to run a job on the selected machine. Machine ID: {self._machine_id}")

        runner = Runner(
            name=self._name,
            uri=self._url,
            uri_type='URL',
            filename=self._filename,
            branch=self._branch,
            skip_unsafe=True,
            skip_system_checks=skip_system_checks,
            full_docker_prune=full_docker_prune,
            docker_prune=docker_prune,
            job_id=self._id,
            user_id=self._user_id,
            measurement_flow_process_duration=user._capabilities['measurement']['settings']['flow-process-duration'],
            measurement_total_duration=user._capabilities['measurement']['settings']['total-duration'],
        )
        try:
            # Start main code. Only URL is allowed for cron jobs
            self._run_id = runner.run()

            # We need to import this here as we need the correct config file
            print(TerminalColors.HEADER, '\nImporting optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.import_reporters()
            print(TerminalColors.HEADER, '\nRunning optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.run_reporters(runner._run_id, runner._tmp_folder, runner.get_optimizations_ignore())

            if self._email:
                Job.insert(
                    'email',
                    user_id=self._user_id,
                    email=self._email,
                    name=f"Measurement Job '{self._name}' successfully processed on Green Metrics Tool Cluster",
                    message=f"Your report is now accessible under the URL: {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={self._run_id}"
                )

        except Exception as exc:
            self._run_id = runner._run_id # might not be set yet, but we try
            if self._email and not isinstance(exc, ConfigurationCheckError): # reduced error message to client, but only if no ConfigurationCheckError

                Job.insert(
                    'email',
                    user_id=self._user_id,
                    email=self._email,
                    name='Measurement Job on Green Metrics Tool Cluster failed',
                    message=f"Run-ID: {self._run_id}\nName: {self._name}\n\nDetails can also be found in the log under: {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={self._run_id}\n\nError message: {exc}\n"
                )
            raise exc
        finally:
            user.deduct_measurement_quota(self._machine_id, int(runner._last_measurement_duration/1_000_000)) # duration in runner is in microseconds. We need seconds
