#!/usr/bin/env python3

# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import json
import os
import importlib
from abc import ABC, abstractmethod

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.global_config import GlobalConfig
from lib.db import DB
from lib.configuration_check_error import ConfigurationCheckError

"""
    The jobs.py file is effectively a state machine that can insert a job in the 'WAITING'
    state and then push it through the states 'RUNNING', 'FAILED/FINISHED', 'NOTIFYING'
    and 'NOTIFIED'.

    After 14 days all FAILED and NOTIFIED jobs will be deleted.
"""

class Job(ABC):
    def __init__(self, *, job_id, run_id, state, name, email, url,  branch, filename, usage_scenario_variables, category_ids, carbon_simulation, machine_id, user_id, machine_description, message, created_at):
        self._id = job_id
        self._state = state
        self._name = name
        self._email = email
        self._url = url
        self._branch = branch
        self._filename = filename
        self._usage_scenario_variables = usage_scenario_variables
        self._carbon_simulation = carbon_simulation
        self._category_ids = category_ids
        self._machine_id = machine_id
        self._user_id = user_id
        self._machine_description = machine_description
        self._run_id = run_id
        self._message = message
        self._created_at = created_at

    @abstractmethod
    def check_job_running(self):
        pass

    def update_state(self, state):
        query_update = "UPDATE jobs SET state = %s WHERE id=%s"
        params_update = (state, self._id,)
        DB().query(query_update, params=params_update)

    def process(self, **kwargs):
        try:
            if not self._state == 'WAITING':
                raise RuntimeError(f"Job w/ id {self._id} has unknown state: {self._state}.")

            if data := self.check_job_running():
                raise RuntimeError(f"Measurement-Job was still running: {data}")

            self.update_state('RUNNING')
            self._process(**kwargs) # uses child class function
            self.update_state('FINISHED')
            return

        except ConfigurationCheckError as exc:
            self.update_state('WAITING') # set back to waiting, as not the run itself has failed
            raise exc

        except Exception as exc:
            self.update_state('FAILED')
            raise exc

    @abstractmethod
    def _process(self, **kwargs):
        pass

    @classmethod
    def insert(cls, job_type, *, user_id, run_id=None, name=None, url=None, email=None, branch=None, filename=None, machine_id=None, usage_scenario_variables=None, category_ids=None, carbon_simulation=None, message=None):

        if job_type == 'run' and (not branch or not url or not filename or not machine_id):
            raise RuntimeError('For adding runs branch, url, filename and machine_id must be set')

        if usage_scenario_variables is None:
            usage_scenario_variables = {}

        query = """
                INSERT INTO
                    jobs (run_id, type, name, url, email, branch, filename, usage_scenario_variables, category_ids, carbon_simulation, machine_id, user_id, message, state, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'WAITING', NOW()) RETURNING id;
                """
        params = (run_id, job_type, name, url, email, branch, filename, json.dumps(usage_scenario_variables), category_ids, carbon_simulation, machine_id, user_id, message)

        return DB().fetch_one(query, params=params)[0]

    # A static method to get a job object
    @classmethod
    def get_job(cls, job_type):
        cls.clear_old_jobs()

        query = '''
            SELECT
                j.id, j.run_id, j.type, j.state, j.name, j.email, j.url, j.branch,
                j.filename, j.usage_scenario_variables, j.category_ids, j.carbon_simulation, j.machine_id, j.user_id, m.description, j.message, j.created_at
            FROM jobs as j
            LEFT JOIN machines as m on m.id = j.machine_id
            WHERE
        '''
        params = []
        config = GlobalConfig().config

        if job_type == 'run':
            query = f"{query} j.type = 'run' AND j.state = 'WAITING' AND j.machine_id = %s "
            params.append(config['machine']['id'])
        elif job_type == 'email':
            query = f"{query} j.type LIKE %s AND j.state = 'WAITING'"
            params.append(f"{job_type}-%")
        else:
            query = f"{query} j.type = %s AND j.state = 'WAITING'"
            params.append(job_type)

        if config['cluster']['client']['jobs_processing'] == 'random':
            query = f"{query} ORDER BY RANDOM()"
        else:
            query = f"{query} ORDER BY j.created_at ASC"  # default case == 'fifo'

        query = f"{query} LIMIT 1"

        job = DB().fetch_one(query, params=params, fetch_mode='dict')
        if not job:
            return False

        module = importlib.import_module(f"lib.job.{job['type'].replace('-','_')}")
        capitalized = "".join(word.capitalize() for word in job['type'].split("-"))
        class_name = f"{capitalized}Job"

        return getattr(module, class_name)(
            job_id=job['id'],
            run_id=job['run_id'],
            state=job['state'],
            name=job['name'],
            email=job['email'],
            url=job['url'],
            branch=job['branch'],
            filename=job['filename'],
            usage_scenario_variables=job['usage_scenario_variables'],
            category_ids=job['category_ids'],
            carbon_simulation=job['carbon_simulation'],
            machine_id=job['machine_id'],
            user_id=job['user_id'],
            machine_description=job['description'],
            message=job['message'],
            created_at=job['created_at'],
        )

    @classmethod
    def clear_old_jobs(cls):
        query = '''
            DELETE FROM jobs
            WHERE
                (state = 'FAILED' AND updated_at < NOW() - INTERVAL '14 DAYS')
                OR
                (state = 'FINISHED' AND updated_at < NOW() - INTERVAL '14 DAYS')
                OR
                (state = 'RUNNING' AND type LIKE 'email-%' AND updated_at < NOW() - INTERVAL '5 MINUTES')
            '''
        DB().query(query)
