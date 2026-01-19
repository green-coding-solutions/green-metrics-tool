#!/usr/bin/env python3

# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.db import DB
from lib.job.base import Job


class EmailJob(Job):

    def check_job_running(self):
        query = "SELECT id FROM jobs WHERE type LIKE 'email-%' AND state = 'RUNNING'"
        return DB().fetch_one(query)

    #pylint: disable=arguments-differ
    def _process(self):
        raise NotImplementedError('EmailJob cannot be used directly. Please use child class')
