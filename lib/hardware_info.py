"""This module takes a list of system configurations to read and puts them in a json data structure.
"""
import re
import os
import subprocess
import pprint

REGEX_PARAMS = re.MULTILINE | re.IGNORECASE


def read_file_with_regex(file, regex, params=REGEX_PARAMS):
    """Reads the content of a file and then tries to match the regex and returns the match described by 'o'"""

    try:
        with open(file, "r", encoding="utf8") as file_ptr:
            file_data = file_ptr.read()
    except FileNotFoundError:
        return "File not found"

    match = re.search(regex, file_data, params)

    return match.group("o") if match is not None else "Unknown"


def read_process_with_regex(path, regex, params=REGEX_PARAMS):
    """Reads the data from a process and then matches the output. The process must terminate and not require user
       input! The matching character for the regex is a 'o'. If the process fails (exit val not 0) an exception
       is thrown."""
    result = subprocess.run(path, stdout=subprocess.PIPE, shell=True, check=True)
    std_data = result.stdout.decode("utf-8")

    match = re.search(regex, std_data, params)

    return match.group("o") if match is not None else "Unknown"


def read_directory_recursive(directory):
    """Reads all the files in a directory recursively and adds them to the return dict. We ignore most errors."""
    # pylint: disable=unused-variable
    output_dic = {}

    dir_path = directory
    for (dir_path, dir_names, file_names) in os.walk(dir_path):
        for filename in file_names:
            try:
                with open(os.path.join(dir_path, filename), "r", encoding="utf8") as file_ptr:
                    output_dic[os.path.join(dir_path, filename)] = file_ptr.read()
            except (FileNotFoundError, PermissionError, OSError):
                continue
    return output_dic


# Defining shortcuts to make the lines shorter
rfwr = read_file_with_regex
rpwr = read_process_with_regex
rdr = read_directory_recursive

# pylint: disable=unnecessary-lambda-assignment
# read_process_with_regex with duplicates removed (single)
# this can also be used to remove a \n at the end of single line
rpwrs = lambda *x: "".join(set(rpwr(*x).split('\n')))

# For the matching the match group needs to be called 'o'
info_list = [
    [rfwr, "Cpu Info", "/proc/cpuinfo", r"model name.*:\s(?P<o>.*)"],
    [rfwr, "Memory Total", "/proc/meminfo", r"MemTotal:\s*(?P<o>.*)"],
    [rpwr, "Linux Version", "/usr/bin/hostnamectl", r"Kernel:\s*(?P<o>.*)"],
    [
        rpwr,
        "Operating System",
        "/usr/bin/hostnamectl",
        r"Operating System:\s*(?P<o>.*)",
    ],
    [rpwr, "Architecture", "/usr/bin/hostnamectl", r"Architecture:\s*(?P<o>.*)"],
    [rpwr, "Hardware Vendor", "/usr/bin/hostnamectl", r"Hardware Vendor:\s*(?P<o>.*)"],
    [rpwr, "Hardware Model", "/usr/bin/hostnamectl", r"Hardware Model:\s*(?P<o>.*)"],
    [
        rpwr,
        "Processes",
        ["/usr/bin/ps", "-ef"],
        r"(?P<o>.*)",
        re.IGNORECASE | re.DOTALL,
    ],
    [
        rpwrs,
        "Scaling Governor",
        ["/usr/bin/cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"],
        r"(?P<o>.*)",
        re.IGNORECASE | re.DOTALL,
    ],
    [rfwr, "Hyper Threading", "/sys/devices/system/cpu/smt/active", r"(?P<o>.*)"],
    [rdr, "CPU complete dump", "/sys/devices/system/cpu/"],
    # This is also listed in the complete dump but we include it here again so it is more visible in the listing
    [
        rfwr,
        "Turbo Boost",
        "/sys/devices/system/cpu/intel_pstate/no_turbo",
        r"(?P<o>.*)",
    ],
    [rfwr, "Virtualization", "/proc/cpuinfo", r"(?P<o>hypervisor)"],
    [rpwrs, "SGX", ["./sgx_enable", "-s"], r"(?P<o>.*)", re.IGNORECASE | re.DOTALL],
    [rdr, "CPU scheduling", "/sys/kernel/debug/sched"],
]


def get_values():
    """Creates an object with all the data populated"""
    return {x[1]: x[0](*x[2:]) for x in info_list}


if __name__ == "__main__":
    os.setuid(0)
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(get_values())
