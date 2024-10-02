#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.phase_stats import build_and_store_phase_stats

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('run_id', help='Run ID', type=str)

    args = parser.parse_args()  # script will exit if type is not present

    build_and_store_phase_stats(args.run_id)
