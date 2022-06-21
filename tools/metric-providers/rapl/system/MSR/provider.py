def import_stats(conn, project_id, containers = None): # Containers argument is unused in this function. Just there for interface compatibility
    import pandas as pd
    from io import StringIO

    with open('/tmp/green-metrics-tool/rapl-system.log', 'r') as f:
        csv_data = f.read()

    csv_data = csv_data[:csv_data.rfind('\n')] # remove the last line from the string

    df = pd.read_csv(StringIO(csv_data), sep=" ", names=["timestamp", "energy"])

    cur = conn.cursor()
    import numpy as np

    for i, row in df.iterrows():
        print(row)
        cur.execute("""
                INSERT INTO stats
                ("project_id", "container_name", "energy", "time")
                VALUES
                (%s, %s, %s, %s)
                """,
                (project_id, "RAPL CPU-Package", float(row.energy)*1000, row.timestamp)
        )
        conn.commit()
    cur.close()

def read(resolution, containers):
    import subprocess
    import os

    current_dir = os.path.dirname(os.path.abspath(__file__))

    ps = subprocess.Popen(
        [f"sudo /usr/bin/stdbuf -oL {current_dir}/static-binary -i {resolution} > /tmp/green-metrics-tool/rapl-system.log &"],
        shell=True,
        preexec_fn=os.setsid,
        encoding="UTF-8"
    )

    return ps.pid
