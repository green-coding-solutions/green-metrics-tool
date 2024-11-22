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
            DB().query('DELETE FROM runs WHERE end_measurement IS NULL')
            print("Done")
    elif args.mode == 'retention-expired':
        print("Getting all users on the system ...")
        users = DB().fetch_all('SELECT * FROM users', fetch_mode='dict')
        for user in users:
            print('User:', user['name'])
            print('Retention periods:')
            for table, retention in user['capabilities']['data'].items():
                print("\t-", table, retention['retention'])
                join_condition = 'WHERE'
                if table == 'measurements':
                    join_condition = 'USING runs WHERE measurements.run_id = runs.id AND'
                elif table in 'hog_coalitions':
                    join_condition = 'USING hog_measurements WHERE hog_coalitions.measurement = hog_measurements.id AND'
                elif table in 'hog_tasks':
                    join_condition = 'USING hog_measurements, hog_tasks WHERE hog_coalitions.measurement = hog_measurements.id AND hog_tasks.coalition = hog_coalitions.id AND'
                DB().query(f"DELETE FROM {table} {join_condition} user_id = {user['id']} AND {table}.created_at < NOW() - INTERVAL '{retention['retention']} SECONDS'")
        print("Done")
