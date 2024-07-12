'''There are some values we need to get as root. So there are two scripts one is `hardware_info.py` which is included
in the main program and the `get_values` method is called. Unfortunately there is no way to get root in a safe way. So
we have split out the values we can get without being root and then we call this script from the main program with
sudo. This is why the output is json and not a nice representation as it needs to be machine readable.
'''

import json
import platform
import re
import subprocess
import os

# We can NEVER include non system packages here, as we rely on them all being writeable by root only.
# This will only be true for non-venv pure system packages coming with the python distribution of the OS

REGEX_PARAMS = re.MULTILINE | re.IGNORECASE

def call_function(func, arguments=None, attribute=None):
    if arguments is None:
        arguments = []
    if attribute:
        return getattr(func(*arguments), attribute)
    return func(*arguments)

def read_file_with_regex(file, regex, params=REGEX_PARAMS):
    '''Reads the content of a file and then tries to match the regex and returns the match described by 'o' '''

    try:
        with open(file, 'r', encoding='utf8') as file_ptr:
            file_data = file_ptr.read()
    except FileNotFoundError:
        return 'File not found'

    match = re.search(regex, file_data, params)

    return match.group('o') if match is not None else 'Unknown'


def read_process_with_regex(path, regex, params=REGEX_PARAMS):
    '''Reads the data from a process and then matches the output. The process must terminate and not require user
       input! The matching character for the regex is a 'o'. If the process fails (exit val not 0) an exception
       is thrown.'''
    result = subprocess.run(path, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        shell=True, encoding='UTF-8', check=False)
    if result.returncode != 0:
        return 'Unknown'

    match = re.search(regex, result.stdout, params)

    return match.group('o') if match is not None else 'Unknown'


def read_directory_recursive(directory):
    '''Reads all the files in a directory recursively and adds them to the return dict. We ignore most errors.'''
    output_dic = {}

    dir_path = directory
    for (dir_path, _, file_names) in os.walk(dir_path):
        for filename in file_names:
            try:
                with open(os.path.join(dir_path, filename), 'r', encoding='utf8') as file_ptr:
                    output_dic[os.path.join(dir_path, filename)] = file_ptr.read()
            except (FileNotFoundError, PermissionError, OSError):
                continue
    return output_dic

def get_values(list_of_tasks):
    '''Creates an object with all the data populated'''
    return {x[1]: x[0](*x[2:]) for x in list_of_tasks}


def read_rapl_energy_filtering():
    return read_process_with_regex('rdmsr -d 0xbc', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL)

# Defining shortcuts to make the lines shorter
rfwr = read_file_with_regex
rpwr = read_process_with_regex
rdr = read_directory_recursive
cf = call_function

root_info_list = [
    [rdr, 'Power Limits', '/sys/devices/virtual/powercap/intel-rapl'],
    [rdr, 'CPU Scheduling', '/sys/kernel/debug/sched'],
    [rpwr, 'Hardware Details', 'lshw', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [cf, 'RAPL Energy Filtering', read_rapl_energy_filtering],
]

def get_root_list():
    if platform.system() == 'Darwin':
        return []

    return root_info_list


if __name__ == '__main__':
    if platform.system() == 'Darwin':
        print('{}')
    else:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('--read-rapl-energy-filtering', action='store_true', help='Read RAPL energy filtering')
        args = parser.parse_args()

        if args.read_rapl_energy_filtering is True:
            print(read_rapl_energy_filtering(), end='')
        else:
            print(json.dumps(get_values(get_root_list())))
