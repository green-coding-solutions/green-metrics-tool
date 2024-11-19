#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.db import DB
from lib.phase_stats import build_and_store_phase_stats

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('run_id', help='Run ID', type=str)

    args = parser.parse_args()  # script will exit if type is not present

    query = '''
        SELECT id, measurement_config
        FROM runs
        WHERE
            end_measurement IS NOT NULL AND phases IS NOT NULL
            AND id = %s

    '''
    data = DB().fetch_one(query, params=(args.run_id, ), fetch_mode='dict')

    build_and_store_phase_stats(args.run_id, data['measurement_config']['sci'])
