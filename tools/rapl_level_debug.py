#!/usr/bin/env python3

'''
RAPL level debug tool

Some machines report the RAPL package energy on one of two (or more) fixed levels although the power
drawn at the wall is the same. Which level is active can change with temperature and from boot to boot.
The level is not visible at idle. It only shows under load.

This tool makes one record per invocation and stores it as JSON. A record contains:
  - a snapshot of the machine (boot id, uptime, off time before boot, kernel, microcode, BIOS, cpuidle setup)
  - a scan of all readable MSRs of the first CPU. The scan is taken twice, so that the values which stay
    constant during the run are known
  - all hwmon sensors and, if FreeIPMI is installed, all BMC sensors (board and regulator temperatures)
  - a short load probe (idle, 1 core busy, all but one core busy, idle) sampled once per second with
    package, core (PP0) and DRAM energy, core voltage, frequency, C0 share and temperatures
    and, if the MCP wall meter is enabled in the config.yml of GMT, the AC power

With --compare all stored records are put side by side. The records are split into a lower and an upper
level by the package power of the load phase. Then every MSR, sensor and derived value is tested whether
it separates the two groups. Such a value would be a direct indicator of the level.

The tool only reads MSRs. It never writes one. It needs root because of /dev/cpu/*/msr.
It is stand-alone on purpose (standard library only), so it runs with the system python under sudo.

Do not run it while GMT is measuring. On a cluster machine stop the client first:
    systemctl --user stop green-coding-client
    sudo python3 tools/rapl_level_debug.py --note "what is special about this run"
    systemctl --user start green-coding-client

Examples:
    sudo python3 tools/rapl_level_debug.py                       # full record, about 3 minutes
    sudo python3 tools/rapl_level_debug.py --load-seconds 600    # longer load phase to watch a slow drift
    sudo python3 tools/rapl_level_debug.py --no-load             # snapshot, MSR scan and sensors only
    python3 tools/rapl_level_debug.py --compare                  # compare all stored records (no root needed)
'''

import argparse
import fcntl
import glob
import json
import multiprocessing
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

VERSION = 1
DEFAULT_OUT_DIR = '/var/log/gmt-rapl-level-debug' # not /tmp. That is a tmpfs on the cluster machines and is lost on power off
GMT_ROOT_DIR = Path(__file__).resolve().parent.parent
MCP_BINARY = GMT_ROOT_DIR / 'metric_providers/psu/energy/ac/mcp/machine/metric-provider-binary'

MSR_SCAN_RANGE = (0x0, 0x1000)
SETTLE_SECONDS = 2   # skipped at the start of every phase before the phase average is taken
EDGE_SECONDS = 20    # length of the "first" and "last" window of the long load phase
PROGRESS_EVERY = 5   # print a progress line every N samples

IA32_TSC = 0x10
IA32_MPERF = 0xE7
IA32_APERF = 0xE8
IA32_PERF_STATUS = 0x198
IA32_THERM_STATUS = 0x19C
MSR_TEMPERATURE_TARGET = 0x1A2
IA32_PACKAGE_THERM_STATUS = 0x1B1
MSR_RAPL_POWER_UNIT = 0x606
MSR_PKG_ENERGY_STATUS = 0x611
MSR_DRAM_ENERGY_STATUS = 0x619
MSR_UNCORE_PERF_STATUS = 0x621
MSR_PP0_ENERGY_STATUS = 0x639
MSR_PLATFORM_ENERGY_STATUS = 0x64D
IA32_MISC_PACKAGE_CTLS = 0xBC

# Only used to label the output. The scan itself reads every address in MSR_SCAN_RANGE.
MSR_NAMES = {
    0x17: 'IA32_PLATFORM_ID', 0x8B: 'IA32_BIOS_SIGN_ID (microcode)', 0xBC: 'IA32_MISC_PACKAGE_CTLS (energy filtering)',
    0xCE: 'MSR_PLATFORM_INFO', 0xE2: 'MSR_PKG_CST_CONFIG_CONTROL', 0x10A: 'IA32_ARCH_CAPABILITIES',
    0x198: 'IA32_PERF_STATUS (ratio and core voltage)', 0x199: 'IA32_PERF_CTL', 0x19A: 'IA32_CLOCK_MODULATION',
    0x19B: 'IA32_THERM_INTERRUPT', 0x19C: 'IA32_THERM_STATUS', 0x1A0: 'IA32_MISC_ENABLE',
    0x1A2: 'MSR_TEMPERATURE_TARGET', 0x1AA: 'MSR_MISC_PWR_MGMT', 0x1AD: 'MSR_TURBO_RATIO_LIMIT',
    0x1B0: 'IA32_ENERGY_PERF_BIAS', 0x1B1: 'IA32_PACKAGE_THERM_STATUS', 0x1B2: 'IA32_PACKAGE_THERM_INTERRUPT',
    0x1FC: 'MSR_POWER_CTL', 0x3F8: 'MSR_PKG_C3_RESIDENCY', 0x3F9: 'MSR_PKG_C6_RESIDENCY', 0x3FA: 'MSR_PKG_C7_RESIDENCY',
    0x3FC: 'MSR_CORE_C3_RESIDENCY', 0x3FD: 'MSR_CORE_C6_RESIDENCY', 0x3FE: 'MSR_CORE_C7_RESIDENCY',
    0x601: 'MSR_VR_CURRENT_CONFIG', 0x603: 'MSR_VR_MISC_CONFIG', 0x606: 'MSR_RAPL_POWER_UNIT',
    0x60A: 'MSR_PKGC3_IRTL', 0x60B: 'MSR_PKGC6_IRTL', 0x60C: 'MSR_PKGC7_IRTL', 0x60D: 'MSR_PKG_C2_RESIDENCY',
    0x610: 'MSR_PKG_POWER_LIMIT', 0x611: 'MSR_PKG_ENERGY_STATUS', 0x613: 'MSR_PKG_PERF_STATUS',
    0x614: 'MSR_PKG_POWER_INFO', 0x618: 'MSR_DRAM_POWER_LIMIT', 0x619: 'MSR_DRAM_ENERGY_STATUS',
    0x61B: 'MSR_DRAM_PERF_STATUS', 0x61C: 'MSR_DRAM_POWER_INFO', 0x620: 'MSR_UNCORE_RATIO_LIMIT',
    0x621: 'MSR_UNCORE_PERF_STATUS', 0x630: 'MSR_PKG_C8_RESIDENCY', 0x631: 'MSR_PKG_C9_RESIDENCY',
    0x632: 'MSR_PKG_C10_RESIDENCY', 0x638: 'MSR_PP0_POWER_LIMIT', 0x639: 'MSR_PP0_ENERGY_STATUS',
    0x63A: 'MSR_PP0_POLICY', 0x63B: 'MSR_PP0_PERF_STATUS', 0x640: 'MSR_PP1_POWER_LIMIT',
    0x641: 'MSR_PP1_ENERGY_STATUS', 0x642: 'MSR_PP1_POLICY', 0x648: 'MSR_CONFIG_TDP_NOMINAL',
    0x649: 'MSR_CONFIG_TDP_LEVEL_1', 0x64A: 'MSR_CONFIG_TDP_LEVEL_2', 0x64B: 'MSR_CONFIG_TDP_CONTROL',
    0x64C: 'MSR_TURBO_ACTIVATION_RATIO', 0x64D: 'MSR_PLATFORM_ENERGY_STATUS', 0x64F: 'MSR_CORE_PERF_LIMIT_REASONS',
    0x65C: 'MSR_PLATFORM_POWER_LIMIT', 0x690: 'MSR_CORE_PERF_LIMIT_REASONS (older)', 0x6B0: 'MSR_GFX_PERF_LIMIT_REASONS',
    0x6B1: 'MSR_RING_PERF_LIMIT_REASONS', 0x770: 'IA32_PM_ENABLE (HWP)', 0x771: 'IA32_HWP_CAPABILITIES',
    0x774: 'IA32_HWP_REQUEST', 0x777: 'IA32_HWP_STATUS',
}


class MsrReader:
    def __init__(self, cpus):
        self._fds = {cpu: os.open(f"/dev/cpu/{cpu}/msr", os.O_RDONLY) for cpu in cpus}

    def read(self, cpu, reg):
        try:
            return struct.unpack('<Q', os.pread(self._fds[cpu], 8, reg))[0]
        except OSError: # the MSR does not exist on this CPU
            return None

    def close(self):
        for fd in self._fds.values():
            os.close(fd)


################### Machine snapshot ###################

def read_text(path, default=None):
    try:
        return Path(path).read_text(encoding='UTF-8', errors='replace').strip()
    except OSError:
        return default

def run_command(cmd, timeout=60):
    try:
        ps = subprocess.run(cmd, check=False, capture_output=True, encoding='UTF-8', errors='replace', timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return ps.stdout if ps.returncode == 0 else None

def cpu_info():
    info = {}
    for line in (read_text('/proc/cpuinfo', '')).split('\n'):
        if not line.strip(): # only the first processor block
            break
        key, _, value = line.partition(':')
        if key.strip() in ('vendor_id', 'cpu family', 'model', 'model name', 'stepping', 'microcode'):
            info[key.strip()] = value.strip()
    return info

def boot_info():
    info = {'boot_id': read_text('/proc/sys/kernel/random/boot_id'), 'uptime_s': None, 'off_before_boot_s': None}
    uptime = read_text('/proc/uptime')
    if uptime:
        info['uptime_s'] = float(uptime.split()[0])

    # The time the machine was off before this boot tells if the board was still warm when it was powered on
    boots = run_command(['journalctl', '--list-boots', '--no-pager', '-o', 'json'], timeout=30)
    try:
        boots = sorted(json.loads(boots), key=lambda x: x['index'])
        if len(boots) >= 2:
            info['off_before_boot_s'] = (int(boots[-1]['first_entry']) - int(boots[-2]['last_entry'])) / 1e6
        info['boot_count_in_journal'] = len(boots)
    except (TypeError, ValueError, KeyError):
        raw = run_command(['journalctl', '--list-boots', '--no-pager'], timeout=30)
        info['journal_boots_raw'] = raw.strip().split('\n')[-3:] if raw else None
    return info

def cpuidle_info(cpu):
    states = []
    for state in sorted(glob.glob(f"/sys/devices/system/cpu/cpu{cpu}/cpuidle/state*")):
        states.append(f"{read_text(f'{state}/name')}{' (disabled)' if read_text(f'{state}/disable') == '1' else ''}")
    return {
        'driver': read_text('/sys/devices/system/cpu/cpuidle/current_driver'),
        'governor': read_text('/sys/devices/system/cpu/cpuidle/current_governor'),
        'states': states,
    }

def system_snapshot(cpus):
    return {
        'hostname': socket.gethostname(),
        'kernel': os.uname().release,
        'cmdline': read_text('/proc/cmdline'),
        'cpu': cpu_info(),
        'cpus': cpus,
        'bios_version': read_text('/sys/class/dmi/id/bios_version'),
        'bios_date': read_text('/sys/class/dmi/id/bios_date'),
        'board_name': read_text('/sys/class/dmi/id/board_name'),
        'product_name': read_text('/sys/class/dmi/id/product_name'),
        'cpuidle': cpuidle_info(cpus[0]),
        'scaling_driver': read_text(f"/sys/devices/system/cpu/cpu{cpus[0]}/cpufreq/scaling_driver"),
        'loadavg': read_text('/proc/loadavg'),
        'boot': boot_info(),
    }

def gmt_processes():
    found = []
    for path in glob.glob('/proc/[0-9]*/cmdline'):
        cmdline = read_text(path, '').replace('\0', ' ')
        if 'metric-provider-binary' in cmdline or 'runner.py' in cmdline:
            found.append(cmdline.strip()[:120])
    return found


################### Sensors ###################

HWMON_SCALE = {'temp': 1000, 'power': 1_000_000, 'in': 1000, 'curr': 1000, 'fan': 1}

def discover_hwmon():
    sensors = []
    for hwmon in sorted(glob.glob('/sys/class/hwmon/hwmon*')):
        chip = read_text(f"{hwmon}/name", 'unknown')
        # hwmonX numbers can change between boots. The device name (for instance the I2C address) does not.
        device = os.path.basename(os.path.realpath(f"{hwmon}/device")) if os.path.exists(f"{hwmon}/device") else ''
        for path in sorted(glob.glob(f"{hwmon}/*_input") + glob.glob(f"{hwmon}/*_average")):
            attribute = os.path.basename(path).rsplit('_', 1)[0]
            kind = attribute.rstrip('0123456789')
            if kind not in HWMON_SCALE:
                continue
            label = read_text(f"{hwmon}/{attribute}_label")
            name = f"{chip}{'@' + device if device else ''}/{attribute}{' ' + label if label else ''}"
            sensors.append((name, path, HWMON_SCALE[kind]))
    return sensors

def read_hwmon(sensors):
    values = {}
    for name, path, scale in sensors:
        try:
            values[name] = int(read_text(path)) / scale
        except (TypeError, ValueError):
            pass
    return values

def read_ipmi():
    if not shutil.which('ipmi-sensors'):
        return None
    out = run_command(['ipmi-sensors', '--comma-separated-output', '--no-header-output', '--ignore-not-available-sensors'], timeout=120)
    if out is None:
        return None
    values = {}
    for line in out.strip().split('\n'):
        fields = line.split(',') # ID,Name,Type,Reading,Units,Event
        if len(fields) < 5:
            continue
        try:
            values[f"{fields[1]} [{fields[4]}]"] = float(fields[3])
        except ValueError:
            pass
    return values


################### MSR helpers ###################

def scan_msrs(msr, cpu):
    values = {}
    for reg in range(*MSR_SCAN_RANGE):
        value = msr.read(cpu, reg)
        if value is not None:
            values[f"0x{reg:03X}"] = f"0x{value:X}"
    return values

def decode_units(raw):
    return {
        'power_w': 1 / (1 << (raw & 0xF)),
        'energy_j': 1 / (1 << ((raw >> 8) & 0x1F)),
        'time_s': 1 / (1 << ((raw >> 16) & 0xF)),
    }

def decode_vcore(perf_status):
    if not perf_status:
        return None
    return ((perf_status >> 32) & 0xFFFF) / 8192 or None

def decode_temp(therm_status, tjmax):
    if therm_status is None or not therm_status & (1 << 31): # reading valid bit
        return None
    return tjmax - ((therm_status >> 16) & 0x7F)

def take_sample(msr, cpus, hwmon_sensors):
    first = cpus[0]
    sample = {
        't': time.time(),
        'pkg': msr.read(first, MSR_PKG_ENERGY_STATUS),
        'pp0': msr.read(first, MSR_PP0_ENERGY_STATUS),
        'dram': msr.read(first, MSR_DRAM_ENERGY_STATUS),
        'psys': msr.read(first, MSR_PLATFORM_ENERGY_STATUS),
        'pkg_therm': msr.read(first, IA32_PACKAGE_THERM_STATUS),
        'uncore': msr.read(first, MSR_UNCORE_PERF_STATUS),
        'cpu': {},
    }
    for cpu in cpus:
        sample['cpu'][str(cpu)] = [msr.read(cpu, reg) for reg in (IA32_TSC, IA32_APERF, IA32_MPERF, IA32_PERF_STATUS, IA32_THERM_STATUS)]
    sample['hwmon'] = read_hwmon(hwmon_sensors)
    return sample


################### Wall meter (optional) ###################

def mcp_enabled_in_config():
    # The MCP binary configures and reads whatever is connected to /dev/ttyACM0. So the meter is only used if the
    # provider is switched on in the config.yml of GMT. A provider entry is followed by its sampling_rate.
    # The same name also appears in the control workload metrics, where a threshold follows.
    lines = [line.strip() for line in read_text(GMT_ROOT_DIR / 'config.yml', '').split('\n') if line.strip()]
    for line, following in zip(lines, lines[1:]):
        if line.startswith('psu_energy_ac_mcp_machine') and following.startswith('sampling_rate'):
            return True
    return False

class WallMeter:
    # Reads the AC power from the MCP39F511N with the metric provider binary of GMT. Output is "<time in us> <power in uW>"
    def __init__(self, binary):
        self.samples = [] # (time in s, power in W)
        self._buffer = b''
        self._ps = None
        if not binary or not os.access(binary, os.X_OK):
            return
        try:
            self._ps = subprocess.Popen([str(binary), '-i', '200'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) # pylint: disable=consider-using-with
        except OSError:
            return
        flags = fcntl.fcntl(self._ps.stdout, fcntl.F_GETFL)
        fcntl.fcntl(self._ps.stdout, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        time.sleep(1.5)
        self.drain()
        if not self.samples: # no meter connected or the device is busy
            self.stop()
            self._ps = None

    @property
    def available(self):
        return self._ps is not None

    def drain(self):
        if self._ps is None:
            return
        try:
            while chunk := os.read(self._ps.stdout.fileno(), 65536):
                self._buffer += chunk
        except BlockingIOError:
            pass
        *lines, self._buffer = self._buffer.split(b'\n')
        for line in lines:
            try:
                timestamp, value = line.split()
                self.samples.append((int(timestamp) / 1e6, int(value) / 1e6))
            except ValueError:
                pass

    def stop(self):
        if self._ps is not None and self._ps.poll() is None:
            self._ps.terminate()
            try:
                self._ps.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ps.kill()


################### Load probe ###################

def burn(cpu, stop, counter):
    # Fixed integer workload. The same code runs on every invocation, so the power levels are comparable between runs.
    os.sched_setaffinity(0, {cpu})
    x = 1
    chunks = 0
    while not stop.is_set():
        for _ in range(200_000):
            x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        chunks += 1
        counter.value = chunks

def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None

def counter_delta(a, b, bits):
    return (b - a) & ((1 << bits) - 1)

def window_stats(samples, wall_samples, t_start, t_end, cpus, context):
    window = [s for s in samples if t_start <= s['t'] <= t_end]
    if len(window) < 2:
        return None
    first, last = window[0], window[-1]
    duration = last['t'] - first['t']
    stats = {'seconds': round(duration, 3)}

    for key in ('pkg', 'pp0', 'dram', 'psys'):
        stats[f"{key}_w"] = None
        if first[key] is not None and last[key] is not None:
            stats[f"{key}_w"] = counter_delta(first[key], last[key], 32) * context['energy_unit_j'] / duration
    if stats['psys_w'] == 0: # domain exists but is not wired up on this board
        stats['psys_w'] = None
    stats['rest_w'] = stats['pkg_w'] - stats['pp0_w'] if stats['pkg_w'] is not None and stats['pp0_w'] is not None else None

    wall = [w for t, w in wall_samples if first['t'] <= t <= last['t']]
    stats['wall_w'] = mean(wall)
    stats['wall_samples'] = len(wall)

    freqs, c0s, vcores, temps = [], [], [], []
    for cpu in cpus:
        tsc_a, aperf_a, mperf_a, _, _ = first['cpu'][str(cpu)]
        tsc_b, aperf_b, mperf_b, _, _ = last['cpu'][str(cpu)]
        if None not in (tsc_a, aperf_a, mperf_a, tsc_b, aperf_b, mperf_b):
            d_tsc, d_aperf, d_mperf = counter_delta(tsc_a, tsc_b, 64), counter_delta(aperf_a, aperf_b, 64), counter_delta(mperf_a, mperf_b, 64)
            if d_mperf > 0 and d_tsc > 0:
                # MPERF counts at the TSC rate while the CPU is in C0. The TSC rate is taken from the samples themselves
                freqs.append(d_tsc / duration / 1e6 * d_aperf / d_mperf)
                c0s.append(100 * d_mperf / d_tsc)
        for s in window:
            vcores.append(decode_vcore(s['cpu'][str(cpu)][3]))
            temps.append(decode_temp(s['cpu'][str(cpu)][4], context['tjmax']))
    stats['freq_mhz'] = mean(freqs)
    stats['c0_pct'] = mean(c0s)
    stats['vcore_v'] = mean(vcores)
    stats['temp_core_c'] = mean(temps)
    stats['temp_pkg_c'] = mean([decode_temp(s['pkg_therm'], context['tjmax']) for s in window])
    stats['uncore_ratio'] = mean([s['uncore'] & 0x7F for s in window if s['uncore'] is not None])
    stats['hwmon'] = {name: mean([s['hwmon'].get(name) for s in window]) for name in first['hwmon']}
    return stats

def fmt(value, digits=2, width=0):
    text = '-' if value is None else f"{value:.{digits}f}"
    return text.rjust(width)

def format_cpus(cpus):
    # [1, 2, 3, 5] -> "1-3,5"
    if not cpus:
        return '-'
    ranges, start, previous = [], cpus[0], cpus[0]
    for cpu in cpus[1:] + [None]:
        if cpu is None or cpu != previous + 1:
            ranges.append(str(start) if start == previous else f"{start}-{previous}")
            start = cpu
        previous = cpu
    return ','.join(ranges)

def run_phase(name, seconds, busy_cpus, state):
    ctx = multiprocessing.get_context('fork')
    stop = ctx.Event()
    counters = [ctx.Value('Q', 0, lock=False) for _ in busy_cpus]
    workers = [ctx.Process(target=burn, args=(cpu, stop, counter), daemon=True) for cpu, counter in zip(busy_cpus, counters)]
    for worker in workers:
        worker.start()

    samples, wall, interval = state['samples'], state['wall'], state['interval']
    start = time.time()
    samples.append(take_sample(state['msr'], state['cpus'], state['hwmon_sensors']))
    next_tick, end, count = start + interval, start + seconds, 0
    while time.time() < end:
        time.sleep(max(0, min(next_tick, end) - time.time()))
        samples.append(take_sample(state['msr'], state['cpus'], state['hwmon_sensors']))
        wall.drain()
        next_tick += interval
        count += 1
        if count % PROGRESS_EVERY == 0:
            live = window_stats(samples, wall.samples, samples[-PROGRESS_EVERY-1]['t'], samples[-1]['t'], busy_cpus or state['cpus'], state['context'])
            print(f"  {name:<11} {samples[-1]['t'] - start:5.0f}s  pkg {fmt(live['pkg_w'], 2, 6)} W  cores {fmt(live['pp0_w'], 2, 6)} W  "
                  f"wall {fmt(live['wall_w'], 2, 6)} W  vcore {fmt(live['vcore_v'], 4)} V  {fmt(live['temp_pkg_c'], 0)} C", flush=True)
    end = samples[-1]['t']

    stop.set()
    for worker in workers:
        worker.join(timeout=5)
        if worker.is_alive():
            worker.terminate()

    cpus = busy_cpus or state['cpus'] # voltage, frequency and C0 share are reported for the busy CPUs
    settle = SETTLE_SECONDS if seconds >= 5 * SETTLE_SECONDS else 0
    phase = {'name': name, 'start': start, 'end': end, 'busy_cpus': busy_cpus}
    phase.update(window_stats(samples, wall.samples, start + settle, end, cpus, state['context']) or {})
    phase['work_per_s'] = sum(counter.value for counter in counters) / (end - start) if counters else None
    if end - start >= 3 * EDGE_SECONDS: # shows if the level moves during the phase
        phase['first'] = window_stats(samples, wall.samples, start + settle, start + settle + EDGE_SECONDS, cpus, state['context'])
        phase['last'] = window_stats(samples, wall.samples, end - EDGE_SECONDS, end, cpus, state['context'])
    return phase

def print_phases(phases):
    print(f"\n{'phase':<12}{'sec':>6}{'cpus':>8}{'pkg W':>9}{'cores W':>9}{'rest W':>8}{'dram W':>8}{'wall W':>8}{'vcore V':>9}{'pkg C':>7}{'MHz':>7}{'C0 %':>7}{'work/s':>8}")
    for phase in phases:
        rows = [(phase['name'], phase)]
        rows += [(f"  {edge} {EDGE_SECONDS}s", phase[edge]) for edge in ('first', 'last') if phase.get(edge)]
        for name, row in rows:
            print(f"{name:<12}{fmt(row.get('seconds'), 0, 6)}{format_cpus(phase['busy_cpus']):>8}{fmt(row.get('pkg_w'), 3, 9)}"
                  f"{fmt(row.get('pp0_w'), 3, 9)}{fmt(row.get('rest_w'), 3, 8)}{fmt(row.get('dram_w'), 3, 8)}{fmt(row.get('wall_w'), 2, 8)}"
                  f"{fmt(row.get('vcore_v'), 4, 9)}{fmt(row.get('temp_pkg_c'), 1, 7)}{fmt(row.get('freq_mhz'), 0, 7)}{fmt(row.get('c0_pct'), 1, 7)}"
                  f"{fmt(row.get('work_per_s'), 1, 8)}")

def record_run(args):
    if os.geteuid() != 0:
        sys.exit('This tool reads MSRs and must run as root. Use sudo. Only --compare works without root.')
    if cpu_info().get('vendor_id') != 'GenuineIntel':
        sys.exit('This tool only knows the Intel RAPL MSRs.')
    if not args.force and (found := gmt_processes()):
        sys.exit('GMT seems to be measuring right now. Stop it first or use --force.\n  ' + '\n  '.join(found))

    cpus = sorted(os.sched_getaffinity(0))
    if not os.path.exists(f"/dev/cpu/{cpus[0]}/msr"):
        print('Loading the msr kernel module ...')
        subprocess.run(['modprobe', 'msr'], check=True)
    msr = MsrReader(cpus)

    units_raw = msr.read(cpus[0], MSR_RAPL_POWER_UNIT)
    if units_raw is None or msr.read(cpus[0], MSR_PKG_ENERGY_STATUS) is None:
        sys.exit('Could not read the RAPL MSRs. RAPL is not available on this machine.')
    target = msr.read(cpus[0], MSR_TEMPERATURE_TARGET)
    filtering = msr.read(cpus[0], IA32_MISC_PACKAGE_CTLS)
    context = {
        'energy_unit_j': decode_units(units_raw)['energy_j'], # DRAM uses a different fixed unit on some server CPUs. Treat dram_w with care there
        'tjmax': ((target >> 16) & 0xFF) if target and (target >> 16) & 0xFF else 100,
        'energy_filtering': bool(filtering & 1) if filtering is not None else None,
    }

    record = {
        'version': VERSION,
        'started': datetime.now().astimezone().isoformat(timespec='seconds'),
        'note': args.note,
        'args': {k: v for k, v in vars(args).items() if k != 'compare'},
        'system': system_snapshot(cpus),
        'context': context,
    }
    boot = record['system']['boot']
    print(f"{record['system']['hostname']}  {record['system']['cpu'].get('model name')}  microcode {record['system']['cpu'].get('microcode')}  BIOS {record['system']['bios_version']}")
    print(f"boot {boot['boot_id']}  up {fmt(boot['uptime_s'], 0)} s  off before boot {fmt(boot['off_before_boot_s'], 0)} s  energy filtering {context['energy_filtering']}")
    if context['energy_filtering']:
        print('WARNING: RAPL energy filtering is on. The energy values contain random noise.')

    hwmon_sensors = discover_hwmon()
    record['hwmon_start'] = read_hwmon(hwmon_sensors)
    if not args.no_ipmi:
        print('Reading BMC sensors ...')
        record['ipmi_start'] = read_ipmi()
    if not args.no_scan:
        record['msr_scan'] = scan_msrs(msr, cpus[0])

    if not args.no_load:
        # The sampler and the wall meter reader stay on the first CPU. The load runs on the others, as GMT containers do.
        os.sched_setaffinity(0, {cpus[0]})
        load_cpus = cpus[1:] or cpus
        use_wall = args.wall == 'on' or (args.wall == 'auto' and mcp_enabled_in_config())
        wall = WallMeter(args.mcp_binary if use_wall else None)
        wall_state = 'connected' if wall.available else ('not available' if use_wall else 'not used (MCP provider is not enabled in config.yml)')
        print(f"Wall meter: {wall_state}. Load CPUs: {format_cpus(load_cpus)}. Sampler CPU: {cpus[0]}")
        state = {'msr': msr, 'cpus': cpus, 'hwmon_sensors': hwmon_sensors, 'samples': [], 'wall': wall, 'interval': args.interval, 'context': context}
        try:
            record['phases'] = [
                run_phase('idle_before', args.idle_seconds, [], state),
                run_phase('load_single', args.single_seconds, load_cpus[:1], state),
                run_phase('load_multi', args.load_seconds, load_cpus, state),
                run_phase('idle_after', args.idle_seconds, [], state),
            ]
        finally:
            wall.stop()
        os.sched_setaffinity(0, set(cpus))
        record['samples'] = state['samples']
        record['wall_samples'] = wall.samples
        print_phases(record['phases'])

    if not args.no_scan:
        # Only values that did not change during the run can be compared between runs
        second_scan = scan_msrs(msr, cpus[0])
        record['msr_static'] = {reg: value for reg, value in record.pop('msr_scan').items() if second_scan.get(reg) == value}
        record['msr_volatile'] = sorted(reg for reg in second_scan if reg not in record['msr_static'])
    if not args.no_ipmi:
        record['ipmi_end'] = read_ipmi()
    record['hwmon_end'] = read_hwmon(hwmon_sensors)
    msr.close()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"rapl_level_{record['system']['hostname']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps(record), encoding='UTF-8')
    out_file.chmod(0o644)
    print(f"\nRecord saved to {out_file}")
    return out_dir


################### Compare ###################

def level_power(record):
    for phase in record.get('phases') or []:
        if phase['name'] == 'load_multi':
            return (phase.get('last') or phase).get('pkg_w')
    return None

def phase_of(record, name):
    for phase in record.get('phases') or []:
        if phase['name'] == name:
            return phase
    return {}

def numeric_features(record):
    idle, single, multi = phase_of(record, 'idle_before'), phase_of(record, 'load_single'), phase_of(record, 'load_multi')
    last = multi.get('last') or multi
    features = {
        'uptime at start [s]': record['system']['boot'].get('uptime_s'),
        'off time before boot [s]': record['system']['boot'].get('off_before_boot_s'),
        'idle: pkg [W]': idle.get('pkg_w'), 'idle: cores [W]': idle.get('pp0_w'), 'idle: wall [W]': idle.get('wall_w'),
        'idle: vcore [V]': idle.get('vcore_v'), 'idle: pkg temp [C]': idle.get('temp_pkg_c'),
        'single: vcore [V]': single.get('vcore_v'),
        'load: cores [W]': last.get('pp0_w'), 'load: pkg minus cores [W]': last.get('rest_w'), 'load: dram [W]': last.get('dram_w'),
        'load: wall [W]': last.get('wall_w'), 'load: vcore [V]': last.get('vcore_v'), 'load: pkg temp [C]': last.get('temp_pkg_c'),
        'load: frequency [MHz]': last.get('freq_mhz'), 'load: uncore ratio': last.get('uncore_ratio'), 'load: work per s': multi.get('work_per_s'),
    }
    for source in ('hwmon_start', 'ipmi_start'):
        for name, value in (record.get(source) or {}).items():
            features[f"{source.split('_', maxsplit=1)[0]}: {name}"] = value
    return {name: value for name, value in features.items() if value is not None}

def compare(files, level_gap):
    records = []
    for file in sorted(files):
        try:
            record = json.loads(Path(file).read_text(encoding='UTF-8'))
        except (OSError, ValueError) as exc:
            print(f"Skipping {file}: {exc}")
            continue
        record['file'] = os.path.basename(file)
        records.append(record)
    if not records:
        sys.exit('No records found.')
    records.sort(key=lambda r: r['started'])

    probed = [r for r in records if level_power(r) is not None]
    threshold = None
    if len(probed) >= 2:
        powers = sorted(level_power(r) for r in probed)
        gap, index = max((powers[i+1] - powers[i], i) for i in range(len(powers) - 1))
        if gap >= level_gap:
            threshold = (powers[index] + powers[index+1]) / 2
    def level(record):
        if level_power(record) is None or threshold is None:
            return '-'
        return 'upper' if level_power(record) > threshold else 'lower'

    print(f"{'started':<21}{'boot':<10}{'up s':>8}{'off s':>8}{'idle C':>8}{'idle W':>8}{'single W':>10}{'load W':>9}{'first':>9}{'last':>9}"
          f"{'cores W':>9}{'rest W':>8}{'wall W':>8}{'vcore V':>9}  {'level':<7}note")
    for record in records:
        boot = record['system']['boot']
        idle, single, multi = phase_of(record, 'idle_before'), phase_of(record, 'load_single'), phase_of(record, 'load_multi')
        last = multi.get('last') or multi
        print(f"{record['started'][:19]:<21}{(boot.get('boot_id') or '')[:8]:<10}{fmt(boot.get('uptime_s'), 0, 8)}{fmt(boot.get('off_before_boot_s'), 0, 8)}"
              f"{fmt(idle.get('temp_pkg_c'), 1, 8)}{fmt(idle.get('pkg_w'), 3, 8)}{fmt(single.get('pkg_w'), 3, 10)}{fmt(multi.get('pkg_w'), 3, 9)}"
              f"{fmt((multi.get('first') or {}).get('pkg_w'), 3, 9)}{fmt((multi.get('last') or {}).get('pkg_w'), 3, 9)}{fmt(last.get('pp0_w'), 3, 9)}"
              f"{fmt(last.get('rest_w'), 3, 8)}{fmt(last.get('wall_w'), 2, 8)}{fmt(last.get('vcore_v'), 4, 9)}  {level(record):<7}{record.get('note') or ''}")

    if threshold is None:
        if len(probed) >= 2:
            print(f"\nAll {len(probed)} probed records are on one level so far. Spread of the load power: {powers[-1] - powers[0]:.3f} W (level gap is {level_gap} W).")
        else:
            print('\nAt least two records with a load probe are needed to look for levels.')
        return

    lower, upper = [r for r in probed if level(r) == 'lower'], [r for r in probed if level(r) == 'upper']
    print(f"\nTwo levels found. Split at {threshold:.3f} W of package power under load. {len(lower)} lower and {len(upper)} upper records.")
    if min(len(lower), len(upper)) < 3:
        print('NOTE: With fewer than 3 records per level a value can separate the levels by pure chance. Collect more records.')

    print('\nMSRs that are constant within each level and differ between the levels (direct indicators):')
    found = False
    regs = set().union(*[set(r.get('msr_static') or {}) for r in probed])
    for reg in sorted(regs, key=lambda x: int(x, 16)):
        if any(reg not in (r.get('msr_static') or {}) for r in probed): # volatile or missing in at least one record
            continue
        low_values, up_values = {r['msr_static'][reg] for r in lower}, {r['msr_static'][reg] for r in upper}
        if len(low_values) == 1 and len(up_values) == 1 and low_values != up_values:
            found = True
            print(f"  {reg} {MSR_NAMES.get(int(reg, 16), ''):<45} lower {low_values.pop()}  upper {up_values.pop()}")
    if not found:
        print('  none')

    print('\nMeasured values whose ranges do not overlap between the levels (sorted by how clear the separation is):')
    rows = []
    low_features, up_features = [numeric_features(r) for r in lower], [numeric_features(r) for r in upper]
    for name in sorted(set().union(*low_features, *up_features)):
        low_values, up_values = [f[name] for f in low_features if name in f], [f[name] for f in up_features if name in f]
        if not low_values or not up_values:
            continue
        gap = max(min(up_values) - max(low_values), min(low_values) - max(up_values))
        if gap > 0:
            spread = (max(low_values) - min(low_values)) + (max(up_values) - min(up_values))
            rows.append((gap / (spread + 1e-9), name, low_values, up_values))
    for _, name, low_values, up_values in sorted(rows, reverse=True)[:25]:
        print(f"  {name:<48} lower {min(low_values):.4f} to {max(low_values):.4f}   upper {min(up_values):.4f} to {max(up_values):.4f}")
    if not rows:
        print('  none')
    print('\n"load: cores" and "load: pkg minus cores" tell in which power plane the offset sits. "load: wall" should NOT separate the levels.')


################### Main ###################

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Records and compares everything that could explain different RAPL levels on a machine.')
    parser.add_argument('--compare', nargs='*', metavar='FILE', default=None, help='Compare stored records. Without files all records in --out-dir are used')
    parser.add_argument('--out-dir', default=DEFAULT_OUT_DIR, help=f"Folder for the records. Default: {DEFAULT_OUT_DIR}")
    parser.add_argument('--note', default='', help='Free text that is stored with the record, for instance "cold boot after a night off"')
    parser.add_argument('--idle-seconds', type=float, default=20, help='Length of the idle phase before and after the load')
    parser.add_argument('--single-seconds', type=float, default=20, help='Length of the phase with one busy core')
    parser.add_argument('--load-seconds', type=float, default=90, help='Length of the phase with all but one core busy')
    parser.add_argument('--interval', type=float, default=1.0, help='Sampling interval in seconds')
    parser.add_argument('--level-gap', type=float, default=0.15, help='Minimum gap in W of package power under load to call it two levels')
    parser.add_argument('--mcp-binary', default=str(MCP_BINARY), help='Path to the MCP wall meter binary of GMT')
    parser.add_argument('--no-load', action='store_true', help='Skip the load probe')
    parser.add_argument('--no-scan', action='store_true', help='Skip the MSR scan')
    parser.add_argument('--no-ipmi', action='store_true', help='Skip the BMC sensors')
    parser.add_argument('--wall', choices=['auto', 'on', 'off'], default='auto', help='Use the MCP wall meter. auto: only if the MCP provider is enabled in the config.yml of GMT')
    parser.add_argument('--force', action='store_true', help='Run even if GMT seems to be measuring')
    cli_args = parser.parse_args()

    if cli_args.compare is None:
        record_dir = record_run(cli_args)
        print('\n################### All records so far ###################\n')
        compare(glob.glob(f"{record_dir}/rapl_level_*.json"), cli_args.level_gap)
    else:
        compare(cli_args.compare or glob.glob(f"{cli_args.out_dir}/rapl_level_*.json"), cli_args.level_gap)
