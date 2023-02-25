#pylint: disable=import-error,wrong-import-position

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib'))

from db import DB

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help='Please supply filename for an SQL file to import into the DB')

    args = parser.parse_args()  # script will exit if arguments not present
    with open(args.filename, encoding='utf-8') as fp:
        data = fp.read()

    DB().query(data)
