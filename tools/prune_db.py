#pylint: disable=import-error,wrong-import-position

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib'))

from db import DB

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
        print("This will remove all failed runs and measurement data from the DB. Continue? (y/N)")
        answer = sys.stdin.readline()
        if answer.strip().lower() == 'y':
            DB().query('DELETE FROM runs WHERE end_measurement IS NULL')
            print("Done")
