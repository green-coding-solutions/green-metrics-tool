'''There are some values we need to get as root. So there are two scripts one is `hardware_info.py` which is included
in the main program and the `get_values` method is called. Unfortunately there is no way to get root in a safe way. So
we have split out the values we can get without being root and then we call this script from the main program with
sudo. This is why the output is json and not a nice representation as it needs to be machine readable.
'''

import json
import platform
import re
from lib.hardware_info import rdr, rpwr, get_values

root_info_list = [
    [rdr, 'Power Limits', '/sys/devices/virtual/powercap/intel-rapl'],
    [rdr, 'CPU scheduling', '/sys/kernel/debug/sched'],
    [rpwr, 'Hardware Details', 'lshw', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
]

def get_root_list():
    if platform.system() == 'Darwin':
        return []

    return root_info_list


if __name__ == '__main__':
    if platform.system() == 'Darwin':
        print('{}')
    else:
        print(json.dumps(get_values(get_root_list())))
