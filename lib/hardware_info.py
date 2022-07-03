import re

def get_cpu():
    with open("/proc/cpuinfo", "r")  as f:
        info = f.readlines()

    cpuinfo = [x.strip().split(": ")[1] for x in info if "model name"  in x]
    if not cpuinfo:
        return 'Unknown'
    else:
        return cpuinfo[0]

    #print(memtotal.group())

    #lshw_output = subprocess.check_output(["lshw", "-C", "display"])
    #gpuinfo = re.search(r"product: (.*)$", lshw_output.decode("UTF-8"))
    #print(gpuinfo.group())

def get_mem():
    with open("/proc/meminfo", "r") as f:
        lines = f.readlines()
    memtotal = re.search(r"\d+", lines[0].strip())
    return memtotal.group()
    #print(memtotal.group())

    #lshw_output = subprocess.check_output(["lshw", "-C", "display"])
    #gpuinfo = re.search(r"product: (.*)$", lshw_output.decode("UTF-8"))
    #print(gpuinfo.group())

