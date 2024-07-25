'''This module takes a list of system configurations to read and puts them in an dict. This file only gets the
things we don't need to be root to get. Please look into the hardware_info_root.py for everything that needs
root.
'''
import re
import os
import platform
import pprint
import psutil
import sys
from lib.hardware_info_root_original import rdr, rpwr, rfwr, cf, get_values

REGEX_PARAMS = re.MULTILINE | re.IGNORECASE

CURRENT_PATH = os.path.dirname(__file__)

# pylint: disable=unnecessary-lambda-assignment
# read_process_with_regex with duplicates removed (single)
# this can also be used to remove a \n at the end of single line
rpwrs = lambda *x: ''.join(set(rpwr(*x).split('\n')))

# For the matching the match group needs to be called 'o'
linux_info_list = [
    [platform.system, 'Platform'],
    [rfwr, 'Cpu Info', '/proc/cpuinfo', r'model name.*:\s(?P<o>.*)'],
    [rfwr, 'Memory Total', '/proc/meminfo', r'MemTotal:\s*(?P<o>.*)'],
    [rpwr, 'Linux Version', '/usr/bin/hostnamectl', r'Kernel:\s*(?P<o>.*)'],
    [rpwr, 'Operating System', '/usr/bin/hostnamectl', r'Operating System:\s*(?P<o>.*)'],
    [rpwr, 'Architecture', '/usr/bin/hostnamectl', r'Architecture:\s*(?P<o>.*)'],
    [cf, 'CPU Utilization', psutil.cpu_percent, [0.1]],
    [cf, 'Free Memory', psutil.virtual_memory, [], 'available'],
    [cf, 'Disk Usage', psutil.disk_usage, ['/'], 'free'],
    [rpwr, 'Uptime', '/usr/bin/uptime', r'(?P<o>.*)'],
    [rpwr, 'Hardware Vendor', '/usr/bin/hostnamectl', r'Hardware Vendor:\s*(?P<o>.*)'],
    [rpwr, 'Hardware Model', '/usr/bin/hostnamectl', r'Hardware Model:\s*(?P<o>.*)'],
    [rpwr, 'Docker Info', 'docker info', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [rpwr, 'Docker Version', 'docker version', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [rpwr, 'Docker Containers', 'docker ps -a', r'(?P<o>.*)'],
    [rpwr, 'Installed System Packages', 'if [ -f /etc/lsb-release ]; then dpkg -l ; elif [ -f /etc/redhat-release ]; then dnf list installed ; fi', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [rpwr, 'Installed Python Packages', f"{sys.executable} -m pip freeze", r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [rpwr, 'Processes', '/usr/bin/ps -aux', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [
        rpwrs,
        'Scaling Governor',
        '/usr/bin/cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor',
        r'(?P<o>.*)',
        re.IGNORECASE | re.DOTALL,
    ],
    [rfwr, 'Hyper Threading', '/sys/devices/system/cpu/smt/active', r'(?P<o>.*)'],
    [rdr, 'CPU Complete Dump', '/sys/devices/system/cpu/'],
    # This is also listed in the complete dump but we include it here again so it is more visible in the listing

    # Note that this information is only accurate if intel_pstate is in active mode
    # /sys/devices/system/cpu/intel_pstate/status -> active
    # If another scaling driver is used the info will be in /sys/devices/system/cpu/cpufreq/boost
    # See https://wiki.archlinux.org/title/CPU_frequency_scaling
    # See further: https://www.kernel.org/doc/html/v5.17/admin-guide/pm/intel_pstate.html#user-space-interface-in-sysfs
    [rfwr, 'Turbo Boost', '/sys/devices/system/cpu/intel_pstate/no_turbo', r'(?P<o>.*)'],
    [rfwr, 'Turbo Boost (Legacy non intel_pstate)', '/sys/devices/system/cpu/cpufreq/boost', r'(?P<o>.*)'],
    [rfwr, 'Virtualization', '/proc/cpuinfo', r'(?P<o>hypervisor)'],
    [rpwrs, 'SGX', f"{os.path.join(CURRENT_PATH, '../tools/sgx_enable')} -s", r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [rfwr, 'IO Scheduling', '/sys/block/sda/queue/scheduler', r'(?P<o>.*)'],
    [rpwr, 'Network Interfaces', 'ip addr | grep ether -B 1', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [rfwr, 'Current Clocksource', '/sys/devices/system/clocksource/clocksource0/current_clocksource', r'(?P<o>.*)'],

]

# This is a very slimmed down version in comparison to the linux list. This is because we will not be using this
# for debugging or benchmarks runs. So it is just a nice to have and not really critical
mac_info_list = [
    [platform.system, 'Platform'],
    [rpwr, 'Cpu Info', 'sysctl -n machdep.cpu.brand_string', r'(?P<o>.*)'],
    [rpwr, 'Memory Total', 'sysctl -n hw.memsize', r'(?P<o>.*)'],
    [rpwr, 'Mac Version', 'sw_vers -productVersion', r'(?P<o>.*)'],
    [rpwr, 'Build Version', 'sw_vers -buildVersion', r'(?P<o>.*)'],
    [rpwr, 'Uname', 'uname -a', r'(?P<o>.*)'],
    [cf, 'CPU Utilization', psutil.cpu_percent, [0.1]],
    [cf, 'Free Memory', psutil.virtual_memory, [], 'available'],
    [cf, 'Disk Usage', psutil.disk_usage, ['/'], 'free'],
    [rpwr, 'Uptime', '/usr/bin/uptime', r'(?P<o>.*)'],
    [rpwr, 'Docker Info', 'docker info', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [rpwr, 'Docker Version', 'docker version', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [rpwr, 'Docker Containers', 'docker ps -a', r'(?P<o>.*)'],
    [rpwr, 'Processes', '/bin/ps -ax', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],
    [rpwr, 'Network Interfaces', 'ifconfig | grep -E "flags|ether"', r'(?P<o>.*)', re.IGNORECASE | re.DOTALL],

]

def get_list():
    if platform.system() == 'Darwin':
        return mac_info_list

    return linux_info_list

def get_default_values():
    return get_values(get_list())

if __name__ == '__main__':
    pp = pprint.PrettyPrinter(indent=4)
    pp.pprint(get_default_values())
