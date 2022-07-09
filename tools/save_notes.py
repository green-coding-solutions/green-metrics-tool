import sys, os
from db import DB
import numpy as np

""" In order for the notes to be displayed in a chart they
need to map together with a timestamp of a datapoint.

Therefore we search the metrics table for the nearest timestamp to the one
from the notes we have. Then we map the time of the metrics datapoint to the
one of the note. This diverts a bit from the original datapoint, but still
is reasonable accurate.

Currently no minimun difference in time is enforced.
"""
def save_notes(project_id, notes):

    for note in notes:
        DB().query("""
                INSERT INTO notes
                ("project_id", "container_name", "note", "time", "created_at")
                VALUES
                (%s, %s, %s, %s, NOW())
                """,
                params=(project_id, note['container_name'], note['note'], note['timestamp'])
        )

if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser()
    parser.add_argument("project_id", help="Please supply a project_id to attribute the stats to")

    args = parser.parse_args() # script will exit if arguments not present

    save_notes(args.project_id, [{"note": "This is my note", "timestamp": time.time_ns(), "container_name": "Arnes_ Container"}])


