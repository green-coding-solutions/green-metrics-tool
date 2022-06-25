def import_stats(conn, project_id, containers = None): # Containers argument is unused in this function. Just there for interface compatibility
    import pandas as pd
    from io import StringIO

    with open('/tmp/green-metrics-tool/rapl-system.log', 'r') as f:
        csv_data = f.read()

    csv_data = csv_data[:csv_data.rfind('\n')] # remove the last line from the string

    df = pd.read_csv(StringIO(csv_data), 
        sep=" ", 
        names=["timestamp", "energy"], 
        dtype={"timestamp":int, "energy":float}
    )
    
    df['energy'] = (df.energy)*1000
    df['energy'] = df.energy.astype(int)
    df['container_name'] = 'RAPL CPU-Package'
    df['metric'] = 'system-energy'
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
        [f"sudo {current_dir}/static-binary -i {resolution} > /tmp/green-metrics-tool/rapl-system.log"],
        shell=True,
        preexec_fn=os.setsid,
        encoding="UTF-8"
    )

    return ps.pid
