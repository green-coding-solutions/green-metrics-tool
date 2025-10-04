#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os
import argparse

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import error_helpers

"""
    This file schedules new Watchlist items by inserting jobs in the jobs table
"""

def check_queue(hours=6):
    query = """
        SELECT id, name
        FROM jobs
        WHERE type = 'run' AND state = 'WAITING' AND created_at <= CURRENT_TIMESTAMP - make_interval(hours => %s)
       """
    data = DB().fetch_all(query, params=(hours, ))

    errors = []
    for [job_id, name] in data:
        errors.append(f"Name {name}; ID: {job_id}")

    if errors:
        error_helpers.log_error(f"Jobs in queue are waiting for longer than {hours} hours", errors=errors)
    else:
        print('All good. Nothing to alert ...')


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('hours', type=int, help='Amount of hours for waiting jobs from which an alert shall be issued')

        args = parser.parse_args()  # script will exit if arguments not present

        check_queue(args.hours)

    except Exception as exc: # pylint: disable=broad-except
        error_helpers.log_error(f'Processing in {__file__} failed.', exception=exc, machine=GlobalConfig().config['machine']['description'])
