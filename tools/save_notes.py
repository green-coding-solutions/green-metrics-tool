import sys, os
from db import DB
import numpy as np

def save_notes(project_id, notes):

    for note in notes:
        if note['container_name'] == "[SYSTEM]":
            DB().query("""
                INSERT INTO stats
                ("project_id", "container_name", "time")
                VALUES
                (%s, %s, %s)
                """,
                params=(project_id, "[SYSTEM]", note['timestamp'])
            )
            stat_line_time = note['timestamp']
        else:
            stat_line_time = DB().fetch_one("""
            SELECT time FROM stats 
            WHERE time < %s 
            AND project_id = %s
            AND container_name = %s
            ORDER BY time DESC LIMIT 1;
            """,
            params=(note['timestamp'], project_id, note['container_name']))[0]

        DB().query("""
                INSERT INTO notes
                ("project_id", "container_name", "note", "time", "created_at")
                VALUES
                (%s, %s, %s, %s, NOW())
                """,
                params=(project_id, note['container_name'], note['note'], stat_line_time)
        )

if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser()
    parser.add_argument("project_id", help="Please supply a project_id to attribute the stats to")

    args = parser.parse_args() # script will exit if arguments not present

    save_notes(args.project_id, [{"note": "This is my note", "timestamp": time.time_ns(), "container_name": "Arnes_ Container"}])


