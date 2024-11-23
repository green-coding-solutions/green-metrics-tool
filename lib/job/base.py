#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

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
    def __init__(self, *, state, name, email, url,  branch, filename, machine_id, user_id, run_id, job_id, machine_description, message, created_at = None):
        self._id = job_id
        self._state = state
        self._name = name
        self._email = email
        self._url = url
        self._branch = branch
        self._filename = filename
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
    def insert(cls, job_type, *, user_id, name=None, url=None, email=None, branch=None, filename=None, machine_id=None, message=None):

        if job_type == 'run' and (not branch or not url or not filename or not machine_id):
            raise RuntimeError('For adding runs branch, url, filename and machine_id must be set')

        query = """
                INSERT INTO
                    jobs (type, name, url, email, branch, filename, machine_id, user_id, message, state, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'WAITING', NOW()) RETURNING id;
                """
        params = (job_type, name, url, email, branch, filename, machine_id, user_id, message)
        return DB().fetch_one(query, params=params)[0]

    # A static method to get a job object
    @classmethod
    def get_job(cls, job_type):
        cls.clear_old_jobs()

        query = '''
            SELECT
                j.id, j.state, j.name, j.email, j.url, j.branch,
                j.filename, j.machine_id, j.user_id, m.description, j.message, r.id as run_id, j.created_at

            FROM jobs as j
            LEFT JOIN machines as m on m.id = j.machine_id
            LEFT JOIN runs as r on r.job_id = j.id
            WHERE
        '''
        params = []
        config = GlobalConfig().config

        if job_type == 'run':
            query = f"{query} j.type = 'run' AND j.state = 'WAITING' AND j.machine_id = %s "
            params.append(config['machine']['id'])
        else:
            query = f"{query} j.type = %s AND j.state = 'WAITING'"
            params.append(job_type)

        if config['cluster']['client']['jobs_processing'] == 'random':
            query = f"{query} ORDER BY RANDOM()"
        else:
            query = f"{query} ORDER BY j.created_at ASC"  # default case == 'fifo'

        query = f"{query} LIMIT 1"

        job = DB().fetch_one(query, params=params)
        if not job:
            return False

        module = importlib.import_module(f"lib.job.{job_type}")
        class_name = f"{job_type.capitalize()}Job"

        return getattr(module, class_name)(
            job_id=job[0],
            state=job[1],
            name=job[2],
            email=job[3],
            url=job[4],
            branch=job[5],
            filename=job[6],
            machine_id=job[7],
            user_id=job[8],
            machine_description=job[9],
            message=job[10],
            run_id=job[11],
            created_at=job[12],
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
                (state = 'RUNNING' AND type = 'email' AND updated_at < NOW() - INTERVAL '5 MINUTES')
            '''
        DB().query(query)
