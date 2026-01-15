#!/usr/bin/env python3

# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import email_helpers
from lib.job.email import EmailJob


class EmailReportJob(EmailJob):

    #pylint: disable=arguments-differ
    def _process(self):
        # create a text message
        # create a html message
        # capture all the vars from the DB
        email_helpers.send_email(self._email, self._name, self._message)
