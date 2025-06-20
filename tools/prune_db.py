#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.db import DB
from psycopg import errors

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['all', 'failed-runs', 'retention-expired'], default=False, help='Will also remove successful runs if all is used')

    args = parser.parse_args()  # script will exit if arguments not present

    if args.mode == 'all':
        print("This will remove ALL runs, measurement, CI, carbonDB and hog data from the DB. Continue? (y/N)")
        answer = sys.stdin.readline()
        if answer.strip().lower() == 'y':
            tables = ['runs', 'ci_measurements', 'hog_measurements', 'carbondb_data', 'carbondb_data_raw']
            for table in tables:
                try:
                    DB().query(f"TRUNCATE TABLE {table} CASCADE")
                except errors.UndefinedTable:
                    continue
            print("Done")
    elif args.mode == 'failed-runs':
        print("This will remove all runs that have not ended, which includes failed ones, but also possibly running, so be sure no measurement is currently active. Continue? (y/N)")
        answer = sys.stdin.readline()
        if answer.strip().lower() == 'y':
            DB().query('DELETE FROM runs WHERE failed = TRUE OR end_measurement IS NULL')
            print("Done")
