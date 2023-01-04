'''There are some values we need to get as root. So there are two scripts one is `hardware_info.py` which is included
in the main program and the `get_values` method is called. Unfortunately there is no way to get root in a safe way. So
we have split out the values we can get without being root and then we call this script from the main program with
sudo. This is why the output is json and not a nice representation as it needs to be machine readable.
'''

import json
from hardware_info import rdr, get_values

root_info_list = [
    [rdr, 'CPU scheduling', '/sys/kernel/debug/sched'],
]

if __name__ == '__main__':
    print(json.dumps(get_values(root_info_list)))
