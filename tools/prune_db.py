#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.db import DB
from lib.global_config import GlobalConfig

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['all', 'failed-runs', 'retention-expired'], default=False, help='Will also remove successful runs if all is used')

    args = parser.parse_args()  # script will exit if arguments not present

    if args.mode == 'all':
        print("This will remove ALL runs, measurement, CI, carbonDB and hog data from the DB. Continue? (y/N)")
        answer = sys.stdin.readline()
        if answer.strip().lower() == 'y':
            DB().query('TRUNCATE TABLE runs CASCADE')
            DB().query('TRUNCATE TABLE ci_measurements CASCADE')

            if GlobalConfig().config.get('activate_carbon_db', False):
                from ee.tools.prune_db_ee import prune_carbondb #pylint: disable=import-error,no-name-in-module
                prune_carbondb()

            if GlobalConfig().config.get('activate_power_hog', False):
                from ee.tools.prune_db_ee import prune_power_hog #pylint: disable=import-error,no-name-in-module

                prune_power_hog()

            print("Done")
    elif args.mode == 'failed-runs':
        print("This will remove all runs that have not ended, which includes failed ones, but also possibly running, so be sure no measurement is currently active. Continue? (y/N)")
        answer = sys.stdin.readline()
        if answer.strip().lower() == 'y':
            DB().query('DELETE FROM runs WHERE failed = TRUE OR end_measurement IS NULL')
            print("Done")
