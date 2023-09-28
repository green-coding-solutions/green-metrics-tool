#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.venv_checker import check_venv
check_venv() # this check must even run before __main__ as imports might not get resolved

from lib.db import DB

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('filename', help='Please supply filename for an SQL file to import into the DB')

    args = parser.parse_args()  # script will exit if arguments not present
    with open(args.filename, encoding='utf-8') as fp:
        data = fp.read()

    DB().query(data)
