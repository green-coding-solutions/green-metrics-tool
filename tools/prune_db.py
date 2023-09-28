#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

import sys

from lib.db import DB

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--all', action='store_true', default=False, help='Will also remove successful runs')

    args = parser.parse_args()  # script will exit if arguments not present

    if args.all:
        print("This will remove ALL runs and measurement data from the DB. Continue? (y/N)")
        answer = sys.stdin.readline()
        if answer.strip().lower() == 'y':
            DB().query('DELETE FROM runs')
            print("Done")
    else:
        print("This will remove all runs that have not ended, which includes failed ones, but also possibly running, so be sure no measurement is currently active. Continue? (y/N)")
        answer = sys.stdin.readline()
        if answer.strip().lower() == 'y':
            DB().query('DELETE FROM runs WHERE end_measurement IS NULL')
            print("Done")
