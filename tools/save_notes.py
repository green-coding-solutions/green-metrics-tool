
def save_notes(conn, project_id, notes):

    cur = conn.cursor()
    import numpy as np

    for note in notes:
        cur.execute("""
                INSERT INTO notes
                ("project_id", "container_name", "note", "time", "created_at")
                VALUES
                (%s, %s, %s, %s, NOW())
                """,
                (project_id, note['container_name'], note['note'], note["timestamp"])
        )
        conn.commit()
    cur.close()

if __name__ == "__main__":
    import argparse
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
    from setup_functions import get_db_connection
    import time

    parser = argparse.ArgumentParser()
    parser.add_argument("project_id", help="Please supply a project_id to attribute the stats to")

    args = parser.parse_args() # script will exit if arguments not present

    conn = get_db_connection()

    save_notes(conn, args.project_id, [{"note": "This is my note", "timestamp": time.time_ns(), "container_name": "Arnes_ Container"}])


