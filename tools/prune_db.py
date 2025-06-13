#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.db import DB

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['all', 'failed-runs', 'retention-expired'], default=False, help='Will also remove successful runs if all is used')

    args = parser.parse_args()  # script will exit if arguments not present

    if args.mode == 'all':
        print("This will remove ALL runs, measurement, CI, carbonDB and hog data from the DB. Continue? (y/N)")
        answer = sys.stdin.readline()
        if answer.strip().lower() == 'y':
            DB().query('TRUNCATE runs CASCADE')
            DB().query('TRUNCATE ci_measurements CASCADE')
            DB().query('TRUNCATE hog_measurements CASCADE')
            DB().query('TRUNCATE carbondb_energy_data CASCADE')
            DB().query('TRUNCATE carbondb_energy_data_day CASCADE')
            print("Done")
    elif args.mode == 'failed-runs':
        print("This will remove all runs that have not ended, which includes failed ones, but also possibly running, so be sure no measurement is currently active. Continue? (y/N)")
        answer = sys.stdin.readline()
        if answer.strip().lower() == 'y':
            DB().query('DELETE FROM runs WHERE failed = TRUE')
            print("Done")
