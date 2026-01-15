#!/usr/bin/env python3

# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib import email_helpers
from lib.job.email import EmailJob

class EmailSimpleJob(EmailJob):

    #pylint: disable=arguments-differ
    def _process(self):
        email_helpers.send_email(self._email, self._name, self._message)
