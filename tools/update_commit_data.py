#pylint: disable=import-error,wrong-import-position

# This script will update the commit_timestamp field in the database
# for old projects where only the commit_hash field was populated


import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib'))

import subprocess
from datetime import datetime
from db import DB

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
            projects
        WHERE
            uri = %s
            AND commit_hash IS NOT NULL
        """, params=(args.uri,))

    if not data:
        raise RuntimeError(f"No match found in DB for {args.uri}!")

    for row in data:
        project_id = str(row[0])
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
            'UPDATE projects SET commit_timestamp = %s WHERE id = %s',
            params=(parsed_timestamp, project_id)
        )
        print(parsed_timestamp)
