#pylint: disable=import-error,wrong-import-position

import os
from re import fullmatch
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib'))

from db import DB

def save_notes(project_id, notes):

    for note in notes:
        try:
            if not fullmatch(r'\d{16}', str(note['timestamp'])):
                raise ValueError
            if not isinstance(note['timestamp'], int):
                note['timestamp'] = int(note['timestamp'])
        except ValueError as e:
            raise ValueError(
                f"Note timestamp did not match expected format: {note['timestamp']}"
            ) from e

        DB().query("""
                INSERT INTO notes
                ("project_id", "detail_name", "note", "time", "created_at")
                VALUES
                (%s, %s, %s, %s, NOW())
                """,
                   params=(project_id, note['detail_name'], note['note'], note['timestamp'])
                   )


if __name__ == '__main__':
    import argparse
    import time

    parser = argparse.ArgumentParser()
    parser.add_argument('project_id', help='Please supply a project_id to attribute the stats to')

    args = parser.parse_args()  # script will exit if arguments not present

    save_notes(args.project_id,
               [{'note': 'This is my note',
                 'timestamp': int(time.time_ns() / 1000),
                 'detail_name': 'Arnes_ Container'}])
