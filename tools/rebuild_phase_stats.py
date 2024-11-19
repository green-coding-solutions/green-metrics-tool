#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.db import DB
from tools.phase_stats import build_and_store_phase_stats

if __name__ == '__main__':
    print('This will remove ALL phase_stats and completely rebuild them. Not data will get lost, but it will take some time. Continue? (y/N)')
    answer = sys.stdin.readline()
    if answer.strip().lower() == 'y':
        print('Deleting old phase_stats ...')
        DB().query('DELETE FROM phase_stats')
        print('Fetching runs ...')
        query = '''
            SELECT id, measurement_config
            FROM runs
            WHERE end_measurement IS NOT NULL AND phases IS NOT NULL

        '''
        runs = DB().fetch_all(query, fetch_mode='dict')


        print(f"Fetched {len(runs)} runs. Commencing ...")
        for idx, data in enumerate(runs):
            print(f"Rebuilding phase_stats for run #{idx} {data['id']}")
            build_and_store_phase_stats(data['id'], data['measurement_config']['sci'])
        print('Done')
