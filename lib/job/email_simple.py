#!/usr/bin/env python3

# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.global_config import GlobalConfig
from lib import email_helpers
from lib.job.email import EmailJob

class EmailSimpleJob(EmailJob):

    #pylint: disable=arguments-differ
    def _process(self):
        message = f"{self._message}\n\n---\n{GlobalConfig().config['cluster']['metrics_url']}"
        email_helpers.send_email(self._email, self._name, message)
