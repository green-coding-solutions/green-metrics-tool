#pylint: disable=import-error,wrong-import-position

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'lib'))

from db import DB

def save_notes(project_id, notes):

    for note in notes:
        if len(str(note['timestamp'])) != 16:
            raise ValueError('Timestamp too short')
        if not isinstance(note['timestamp'], int):
            try:
                note['timestamp'] = int(note['timestamp'])
            except ValueError:
                raise ValueError(f"Note timestamp did not match expected format: {note['timestamp']}")

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
                 'timestamp': time.time_ns(),
                 'detail_name': 'Arnes_ Container'}])
