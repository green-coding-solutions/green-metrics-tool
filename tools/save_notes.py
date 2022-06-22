
def save_notes(conn, project_id, notes):

    import numpy as np
    cur = conn.cursor()
    

    for note in notes:
        if note['container_name'] == "[SYSTEM]":
            cur.execute("""
                INSERT INTO stats
                ("project_id", "container_name", "time")
                VALUES
                (%s, %s, %s)
                """,
                (project_id, "[SYSTEM]", note['timestamp'])
            )
            conn.commit()
            stat_line_time = note['timestamp']
        else:
            cur.execute("""
            SELECT time FROM stats 
            WHERE time < %s 
            AND project_id = %s
            AND container_name = %s
            ORDER BY time DESC LIMIT 1;
            """,
            (note['timestamp'], project_id, note['container_name']))
            conn.commit()
            stat_line_time = cur.fetchone()[0]
            
        cur.execute("""
                INSERT INTO notes
                ("project_id", "container_name", "note", "time", "created_at")
                VALUES
                (%s, %s, %s, %s, NOW())
                """,
                (project_id, note['container_name'], note['note'], stat_line_time)
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


