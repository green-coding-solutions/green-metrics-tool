def import_stats(conn, project_id, containers):
    import pandas as pd
    from io import StringIO

    with open("/tmp/green-metrics-tool/cgroup_cpu.log", 'r') as f:
        csv_data = f.read()

    csv_data = csv_data[:csv_data.rfind('\n')] # remove the last line from the string

    df = pd.read_csv(StringIO(csv_data), 
        sep=" ", 
        names=["timestamp", "cpu", "container_id"], 
        dtype={"timestamp":int, "cpu":float, "container_id":str}
    )
    
    df['cpu'] = (df.cpu)*10000
    df['cpu'] = df.cpu.astype(int)


    df['container_name'] = df.container_id

    for container_id in containers:
        df.loc[df.container_name == container_id, 'container_name'] = containers[container_id]

    df = df.drop('container_id', axis=1)
    df['metric'] = 'cpu'
    df['project_id'] = project_id

    f = StringIO(df.to_csv(index=False, header=False))
    
    cur = conn.cursor()
    cur.copy_from(f, 'stats', columns=("time", "value", "container_name", "metric", "project_id"), sep=",")
    conn.commit()
    cur.close()    

def read(resolution, containers):
    import subprocess
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))

    ps = subprocess.Popen(
        [f"{current_dir}/static-binary {resolution} " + " ".join(containers.keys()) + " > /tmp/green-metrics-tool/cgroup_cpu.log"],
        shell=True,
        preexec_fn=os.setsid
    )
    return ps.pid

if __name__ == "__main__":
    import argparse
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../../../../lib')
    from setup_functions import get_db_connection

    parser = argparse.ArgumentParser()
    parser.add_argument("stats_file", help="Please specify filename where to find the docker stats file. Usually /tmp/green-metrics-tool/docker_stats.log")
    parser.add_argument("project_id", help="Please supply a project_id to attribute the stats to")

    args = parser.parse_args() # script will exit if url is not present

    conn = get_db_connection()

    # Call NOT working atm. TODO
    import_stats(conn, args.project_id, {'7902263ed2a9acbb53e252e446df7935a2f9a608d9829d96193fede53018333e': "Arne_Test"})


