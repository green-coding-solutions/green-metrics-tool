#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pylint: disable=cyclic-import
import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import email_helpers
from lib.job.base import Job

class EmailJob(Job):

    #pylint: disable=arguments-differ
    def _process(self):
        email_helpers.send_email(self._email, self._name, self._message)
