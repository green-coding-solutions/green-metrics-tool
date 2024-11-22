#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB
from lib import email_helpers
from lib.job.base import Job


class EmailJob(Job):

    def check_job_running(self):
        query = "SELECT id FROM jobs WHERE type = 'email' AND state = 'RUNNING'"
        return DB().fetch_one(query)

    #pylint: disable=arguments-differ
    def _process(self):
        if self._created_at:
            self._message = f"{self._message}\n\nOriginal date and time: {self._created_at} - This error was transported via E-Mail"
        email_helpers.send_email(self._email, self._name, self._message)
