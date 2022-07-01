sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
import re
from db import DB
def insert_hw_info(project_id):
    with open("/proc/cpuinfo", "r")  as f:
        info = f.readlines()

    cpuinfo = [x.strip().split(": ")[1] for x in info if "model name"  in x]
    if not cpuinfo:
        cpuinfo = 'Unknown'
    else:
        cpuinfo = cpuinfo[0]

    with open("/proc/meminfo", "r") as f:
        lines = f.readlines()
    memtotal = re.search(r"\d+", lines[0].strip())
    #print(memtotal.group())

    #lshw_output = subprocess.check_output(["lshw", "-C", "display"])
    #gpuinfo = re.search(r"product: (.*)$", lshw_output.decode("UTF-8"))
    #print(gpuinfo.group())

    DB().query("""UPDATE projects
        SET cpu=%s, memtotal=%s
        WHERE id = %s
        """, params=(cpuinfo, memtotal.group(), project_id))
