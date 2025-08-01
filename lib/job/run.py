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
from lib.scenario_runner import ScenarioRunner
import optimization_providers.base


class RunJob(Job):

    def check_job_running(self):
        query = "SELECT id FROM jobs WHERE type = 'run' AND state = 'RUNNING' AND machine_id = %s"
        return DB().fetch_one(query, params=(self._machine_id, ))

    #pylint: disable=arguments-differ
    def _process(self, docker_prune=False, full_docker_prune=False):

        user = User(self._user_id)

        if not user.can_use_machine(self._machine_id):
            raise RuntimeError(f"Your user does not have the permissions to use the selected machine. Machine ID: {self._machine_id}")

        if not user.has_measurement_quota(self._machine_id):
            raise RuntimeError(f"Your user does not have enough measurement quota to run a job on the selected machine. Machine ID: {self._machine_id}")

        runner = ScenarioRunner(
            name=self._name,
            uri=self._url,
            uri_type='URL',
            filename=self._filename,
            branch=self._branch,
            skip_unsafe=user._capabilities['measurement'].get('skip_unsafe', True),
            allow_unsafe=user._capabilities['measurement'].get('allow_unsafe', False),
            skip_system_checks=skip_system_checks,
            skip_volume_inspect=user._capabilities['measurement'].get('skip_volume_inspect', False),
            full_docker_prune=full_docker_prune,
            docker_prune=docker_prune,
            job_id=self._id,
            user_id=self._user_id,
            usage_scenario_variables=self._usage_scenario_variables,
            measurement_flow_process_duration=user._capabilities['measurement']['flow_process_duration'],
            dev_no_sleeps=user._capabilities['measurement'].get('dev_no_sleeps', False),
            dev_no_optimizations=user._capabilities['measurement'].get('dev_no_optimizations', False),
            measurement_total_duration=user._capabilities['measurement']['total_duration'],
            disabled_metric_providers=user._capabilities['measurement']['disabled_metric_providers'],
            allowed_run_args=user._capabilities['measurement']['orchestrators']['docker']['allowed_run_args'], # They are specific to the orchestrator. However currently we only have one. As soon as we support more orchestrators we will sub-class Runner with dedicated child classes (DockerRunner, PodmanRunner etc.)
        )
        try:
            # Start main code. Only URL is allowed for cron jobs
            self._run_id = runner.run()

            # We need to import this here as we need the correct config file
            print(TerminalColors.HEADER, '\nImporting optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.import_reporters()
            print(TerminalColors.HEADER, '\nRunning optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.run_reporters(runner._user_id, runner._run_id, runner._tmp_folder, runner.get_optimizations_ignore())

            if self._email:
                Job.insert(
                    'email',
                    user_id=self._user_id,
                    email=self._email,
                    name=f"Measurement Job '{self._name}' successfully processed on Green Metrics Tool Cluster",
                    message=f"Your report is now accessible under the URL: {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={self._run_id}"
                )
        finally:
            self._run_id = runner._run_id # might not be set yet, but we try
            user.deduct_measurement_quota(self._machine_id, int(runner._last_measurement_duration/1_000_000)) # duration in runner is in microseconds. We need seconds
