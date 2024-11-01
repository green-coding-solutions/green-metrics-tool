#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

# This script will update the commit_timestamp field in the database
# for old runs where only the commit_hash field was populated
import subprocess
from datetime import datetime

from lib.db import DB

if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('uri', help='URI to search for in DB')
    parser.add_argument('folder', help='Local git folder, where to get commit timestamp from')

    args = parser.parse_args()  # script will exit if arguments not present

    data = DB().fetch_all(
        """
        SELECT
            id, commit_hash
        FROM
            runs
        WHERE
            uri = %s
            AND commit_hash IS NOT NULL
        """, params=(args.uri,))

    if not data:
        raise RuntimeError(f"No match found in DB for {args.uri}!")

    for row in data:
        run_id = str(row[0])
        commit_hash = row[1]
        commit_timestamp = subprocess.run(
            ['git', 'show', '-s', row[1], '--format=%ci'],
            check=True,
            capture_output=True,
            encoding='UTF-8',
            cwd=args.folder
        )
        commit_timestamp = commit_timestamp.stdout.strip("\n")
        parsed_timestamp = datetime.strptime(commit_timestamp, "%Y-%m-%d %H:%M:%S %z")

        DB().query(
            'UPDATE runs SET commit_timestamp = %s WHERE id = %s',
            params=(parsed_timestamp, run_id)
        )
        print(parsed_timestamp)
