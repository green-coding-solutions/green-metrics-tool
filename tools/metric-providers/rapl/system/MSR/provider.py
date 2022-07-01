import os
import subprocess
import pandas as pd
from io import StringIO
from db import DB

def import_stats(project_id, containers=None): # Containers argument is unused in this function. Just there for interface compatibility

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
    
    DB().copy_from(file=f, table='stats', columns=("time", "value", "container_name", "metric", "project_id"), sep=",")
    
def read(resolution, containers):

    current_dir = os.path.dirname(os.path.abspath(__file__))

    ps = subprocess.Popen(
        [f"sudo {current_dir}/static-binary -i {resolution} > /tmp/green-metrics-tool/rapl-system.log"],
        shell=True,
        preexec_fn=os.setsid,
        encoding="UTF-8"
        # since we are launching the command with shell=True we cannot use ps.terminate() / ps.kill().
        # This would just kill the executing shell, but not it's child and make the process an orphan.
        # therefore we use os.setsid here and later call os.getpgid(pid) to get process group that the shell
        # and the process are running in. These we then can send the signal to and kill them
    )

    return ps.pid
