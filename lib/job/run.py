#!/usr/bin/env python3

# pylint: disable=cyclic-import

import sys
import faulthandler

faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.job.base import Job
from lib.job.email_report import EmailReportJob
from lib.db import DB
from lib.user import User
from lib.terminal_colors import TerminalColors
from lib.scenario_runner import ScenarioRunner


class RunJob(Job):
    JOB_TYPE = 'run'

    def check_job_running(self):
        query = "SELECT id FROM jobs WHERE type = 'run' AND state = 'RUNNING' AND machine_id = %s"
        return DB().fetch_one(query, params=(self._machine_id, ))

    #pylint: disable=arguments-differ
    @classmethod
    def insert(cls, *, user_id, name, url, branch, filename, machine_id, email=None, commit_hash=None, usage_scenario_variables=None, category_ids=None, carbon_simulation=None):
        if not branch or not url or not filename or not machine_id:
            raise RuntimeError('For adding runs branch, url, filename and machine_id must be set')

        return cls._insert_row(
            user_id=user_id,
            name=name,
            url=url,
            email=email,
            commit_hash=commit_hash,
            branch=branch,
            filename=filename,
            machine_id=machine_id,
            usage_scenario_variables=usage_scenario_variables,
            category_ids=category_ids,
            carbon_simulation=carbon_simulation,
        )

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
            commit_hash=self._commit_hash,
            ssh_private_key=user.get_ssh_private_key(),
            allow_unsafe=False, # cluster runs should never allow this. All should go through individual user permissions,
            skip_unsafe=True, # Always True in cluster as no way to use unsafe rules anyway since we do not expose allow_unsafe atm
            dev_no_system_checks=user._capabilities['measurement']['dev_no_system_checks'],
            skip_volume_inspect=user._capabilities['measurement']['skip_volume_inspect'],
            skip_optimizations=user._capabilities['measurement']['skip_optimizations'],
            full_docker_prune=full_docker_prune, # is no user setting as it can change behaviour of subsequent runs. Thus set by machine / cluster
            docker_prune=docker_prune, # is no user setting as it can change behaviour of subsequent runs. Thus set by machine / cluster
            job_id=self._id,
            user_id=self._user_id,
            usage_scenario_variables=self._usage_scenario_variables,
            category_ids=self._category_ids,
            carbon_simulation=self._carbon_simulation,
            measurement_flow_process_duration=user._capabilities['measurement']['flow_process_duration'],
            measurement_total_duration=user._capabilities['measurement']['total_duration'],
            measurement_system_check_threshold=user._capabilities['measurement']['system_check_threshold'],
            measurement_pre_test_sleep=user._capabilities['measurement']['pre_test_sleep'],
            measurement_idle_duration=user._capabilities['measurement']['idle_duration'],
            measurement_baseline_duration=user._capabilities['measurement']['baseline_duration'],
            measurement_post_test_sleep=user._capabilities['measurement']['post_test_sleep'],
            measurement_phase_transition_time=user._capabilities['measurement']['phase_transition_time'],
            measurement_wait_time_dependencies=user._capabilities['measurement']['wait_time_dependencies'],
            dev_no_sleeps=user._capabilities['measurement']['dev_no_sleeps'],
            disabled_metric_providers=user._capabilities['measurement']['disabled_metric_providers'],
            allowed_run_args=user._capabilities['measurement']['orchestrators']['docker']['allowed_run_args'], # They are specific to the orchestrator. However currently we only have one. As soon as we support more orchestrators we will sub-class Runner with dedicated child classes (DockerRunner, PodmanRunner etc.)
            allowed_volume_mounts=user._capabilities['measurement']['allowed_volume_mounts'],


        )
        try:
            # Start main code. Only URL is allowed for cron jobs
            self._run_id = runner.run()

            # We need to import this here as we need the correct config file, and to avoid a circular
            # import (optimization_providers.base imports api.scenario_runner, which imports RunJob)
            import optimization_providers.base #pylint: disable=import-outside-toplevel
            print(TerminalColors.HEADER, '\nImporting optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.import_reporters()
            print(TerminalColors.HEADER, '\nRunning optimization reporters ...', TerminalColors.ENDC)
            optimization_providers.base.run_reporters(runner._user_id, runner._run_id, runner._tmp_folder, runner.get_optimizations_ignore())


            if self._email:
                EmailReportJob.insert(
                    user_id=self._user_id,
                    email=self._email,
                    name=f"Measurement Job '{self._name}' successfully processed on Green Metrics Tool Cluster",
                    run_id=self._run_id,
                )

        finally:
            # we see no sane reason for keeping tmp files on the cluster after a run.
            # We empty the folder in place rather than removing it (see
            # ScenarioRunner._initialize_folder) so the directory inode stays stable
            # for Docker Desktop's virtiofs cache on macOS.
            runner._initialize_folder(runner._tmp_folder)

            self._run_id = runner._run_id # might not be set yet due to error
            user.deduct_measurement_quota(self._machine_id, int(runner._last_measurement_duration/1_000_000)) # duration in runner is in microseconds. We need seconds
