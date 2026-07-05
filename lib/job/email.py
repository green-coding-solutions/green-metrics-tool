#!/usr/bin/env python3

# pylint: disable=cyclic-import
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.db import DB
from lib.job.base import Job
from lib.utils import filter_sensitive_data


class EmailJob(Job):
    # Matches any of the concrete 'email-*' types (email-simple, email-report, ...)
    JOB_TYPE = 'email-%'

    def check_job_running(self):
        query = "SELECT id FROM jobs WHERE type LIKE 'email-%' AND state = 'RUNNING'"
        return DB().fetch_one(query)

    #pylint: disable=arguments-differ
    def _process(self):
        raise NotImplementedError('EmailJob cannot be used directly. Please use child class')

    # Emails are persisted to the DB as the 'message' column of a job before being sent out.
    # Filter here so no credentials or private keys ever reach storage or an outgoing email.
    # Concrete subclasses (EmailSimpleJob, EmailReportJob, ...) set their own JOB_TYPE and
    # inherit this implementation as-is.
    #pylint: disable=arguments-differ
    @classmethod
    def insert(cls, *, user_id, email, name, message=None, run_id=None):
        if cls is EmailJob:
            raise NotImplementedError('EmailJob cannot be used directly. Please use child class')

        return cls._insert_row(
            user_id=user_id,
            email=email,
            name=name,
            run_id=run_id,
            message=filter_sensitive_data(message),
        )
