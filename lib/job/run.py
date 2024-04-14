#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=cyclic-import
import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.job.base import Job
from lib.global_config import GlobalConfig
from lib.db import DB
from lib.terminal_colors import TerminalColors
from tools.phase_stats import build_and_store_phase_stats
from runner import Runner
import optimization_providers.base


class RunJob(Job):

    def check_job_running(self):
        query = "SELECT id FROM jobs WHERE type = 'run' AND state = 'RUNNING' AND machine_id = %s"
        return DB().fetch_one(query, params=(self._machine_id, ))

    #pylint: disable=arguments-differ
    def _process(self, skip_system_checks=False, docker_prune=False, full_docker_prune=False):

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
        )
        try:
            # Start main code. Only URL is allowed for cron jobs
            self._run_id = runner.run()
            build_and_store_phase_stats(self._run_id, runner._sci)

            # We need to import this here as we need the correct config file
            print(TerminalColors.HEADER, '\nImporting optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.import_reporters()
            print(TerminalColors.HEADER, '\nRunning optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.run_reporters(runner._run_id, runner._tmp_folder, runner.get_optimizations_ignore())

            if self._email:
                Job.insert(
                    'email',
                    email=self._email,
                    name='Measurement Job successfully processed on Green Metrics Tool Cluster',
                    message=f"Your report is now accessible under the URL: {GlobalConfig().config['cluster']['metrics_url']}/stats.html?id={self._run_id}"
                )

        except Exception as exc:
            self._run_id = runner._run_id # might not be set yet, but we try
            raise exc
