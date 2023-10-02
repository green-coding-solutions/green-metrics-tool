#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import sys

from tools.phase_stats import build_and_store_phase_stats

from lib.db import DB

if __name__ == '__main__':
    print('This will remove ALL phase_stats and completely rebuild them. No data will get lost, but it will take some time. Continue? (y/N)')
    answer = sys.stdin.readline()
    if answer.strip().lower() == 'y':
        print('Deleting old phase_stats ...')
        DB().query('DELETE FROM phase_stats')
        print('Fetching runs ...')
        query = '''
            SELECT id
            FROM runs
            WHERE
                end_measurement IS NOT NULL AND phases IS NOT NULL
        '''
        runs = DB().fetch_all(query)

        print(f"Fetched {len(runs)} runs. Commencing ...")
        for idx, run_id in enumerate(runs):

            print(f"Rebuilding phase_stats for run #{idx} {run_id[0]}")
            build_and_store_phase_stats(run_id[0])
        print('Done')
