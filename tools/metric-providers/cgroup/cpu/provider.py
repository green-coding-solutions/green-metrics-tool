def import_stats(conn, project_id, containers):
    import pandas as pd
    from io import StringIO

    with open("/tmp/green-metrics-tool/docker_cgroup_read.log", 'r') as f:
        csv_data = f.read()

    csv_data = csv_data[:csv_data.rfind('\n')] # remove the last line from the string

    df = pd.read_csv(StringIO(csv_data), sep=" ", names=["timestamp", "cpu", "container_id"])

    cur = conn.cursor()
    import numpy as np

    for i, row in df.iterrows():
        print(row)
        cur.execute("""
                INSERT INTO stats
                ("project_id", "container_name", "metric", "value", "time")
                VALUES
                (%s, %s, 'cpu', %s, %s)
                """,
                (project_id, containers[row.container_id], float(row.cpu)*10000, row.timestamp)
        )
        conn.commit()
    cur.close()


def read(resolution, containers):
	import subprocess
	import os
	current_dir = os.path.dirname(os.path.abspath(__file__))

	ps = subprocess.Popen(
	    [f"stdbuf -oL {current_dir}/static-binary {resolution} " + " ".join(containers.keys()) + " > /tmp/green-metrics-tool/docker_cgroup_read.log"],
	    shell=True,
	    preexec_fn=os.setsid
	)
	return ps.pid

if __name__ == "__main__":
    import argparse
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../../lib')
    from setup_functions import get_db_connection

    parser = argparse.ArgumentParser()
    parser.add_argument("stats_file", help="Please specify filename where to find the docker stats file. Usually /tmp/green-metrics-tool/docker_stats.log")
    parser.add_argument("project_id", help="Please supply a project_id to attribute the stats to")

    parser.add_argument("mode", help="Please supply a mode. Either cgroup or docker-stats", choices=['cgroup', 'docker-stats'])

    args = parser.parse_args() # script will exit if url is not present

    conn = get_db_connection()

    # Call NOT working atm. TODO
    DockerCgroup.import_stats(conn, args.project_id, containers)


