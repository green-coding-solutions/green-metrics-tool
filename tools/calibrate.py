#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#pylint: disable=logging-fstring-interpolation, broad-exception-caught,global-statement

import argparse
import importlib
import logging
import subprocess
import shutil
import time
from pathlib import Path
import random
import traceback
import sys

from tqdm import tqdm
import plotext as plt
import pandas as pd
import yaml
import docker

from lib.global_config import GlobalConfig
from lib import utils

# Todo only CPU Stress

# The multiplier for the deviation
STD_THRESHOLD_MULTI = 4

# How many values does the temp need to be under mean consecutively
RELIABLE_DURATION = 4

# You should never need to change in the usual case
TMP_FOLDER = '/tmp/green-metrics-tool'
LOG_LEVELS = ['debug', 'info', 'warning', 'error', 'critical']
CONF_FILE = '../config.yml'

RED="\x1b[31m"
YELLOW="\x1b[33m"
MAGENTA="\x1b[35m"
GREEN="\x1b[32m"
NC="\x1b[0m" # No Color

# Globals
metric_providers = []
timings = {}
docker_sleeper = None

def countdown_bar(total_seconds, desc='Countdown'):
    with tqdm(total=total_seconds, desc=desc, bar_format='{l_bar}{bar}| {remaining}') as pbar:
        for _ in range(total_seconds):
            time.sleep(1)
            pbar.update(1)

# This also checks if the temp is actually increasing. The problem is that depending on what sensors are being monitored
# not all temperatures increase or with quite a delay. Also it takes some time for the CPU to get hot. (quite dependent
# on the make actually). Another problem is that the CPU cools down again when the fans go to full blast.
# So instead of doing a rolling window analysis or something clever we just wait 10 seconds and
# check if at least one temp provider has increased for "temp_increase" degrees at some stage.
def check_temperature_increase(total_seconds, desc, temp_mean, temp_std, temp_provider, temp_increase=1000):
    with tqdm(total=total_seconds, desc=desc, bar_format='{l_bar}{bar}| {remaining}') as pbar:
        for i in range(total_seconds):
            time.sleep(1)
            pbar.update(1)
            if i == 10:
                data = temp_provider.read_metrics(1)
                grouped = data.groupby('detail_name')
                logging.info('Checking for temperature increase!')
                if len(grouped) < 1:
                    raise SystemExit(f"Not enough values could be collected for temperature check increase. Is the time too small ({total_seconds} seconds)? ")

                for name, group in grouped:
                    if not any(group['value'] > temp_mean[name] + temp_std[name] + temp_increase):
                        logging.error(f"Temperature hasn\'t increased for at least {temp_increase/100}° during {total_seconds} seconds")
                        raise SystemExit(5)
                    logging.info(f"Temperature increase ok for {name}. Saw a {max(group['value'])/100}° increase during {total_seconds} seconds")



def load_metric_providers(mp, pt_providers, provider_interval_override=None):
    global metric_providers
    metric_providers = [] # reset

    # We pretty much copied this from the runner. Keeping the same flow so we can maintain it easier.
    for metric_provider in pt_providers:
        module_path, class_name = metric_provider.rsplit('.', 1)
        module_path = f"metric_providers.{module_path}"
        conf = mp[metric_provider] or {}

        logging.info(f"Importing {class_name} from {module_path}")

        if provider_interval_override:
            conf['resolution'] = provider_interval_override


        module = importlib.import_module(module_path)

        metric_provider_obj = getattr(module, class_name)(**conf)

        metric_providers.append(metric_provider_obj)


def start_metric_providers(containers=None):
    for metric_provider in metric_providers:
        metric_provider.start_profiling(containers)

    logging.debug('Waiting for Metric Providers to boot ...')
    countdown_bar(5, 'Booting Metric Providers')

    for metric_provider in metric_providers:
        stderr_read = metric_provider.get_stderr()
        logging.debug(f"Stderr check on {metric_provider.__class__.__name__}")
        if stderr_read is not None:
            raise RuntimeError(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")


def stop_metric_providers(force=False, containers=None):
    logging.debug('Stopping metric providers and parsing measurements')

    data = {}
    for metric_provider in metric_providers:
        if metric_provider.has_started() is False:
            continue

        if force is False:
            if stderr_read := metric_provider.get_stderr() is not None:
                raise RuntimeError(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

        metric_provider.stop_profiling()

        if force is False:
            data[metric_provider.__class__.__name__] = metric_provider.read_metrics(1, containers=containers)
            if isinstance(data[metric_provider.__class__.__name__], int):
                # If df returns an int the data has already been committed to the db
                continue
            if data[metric_provider.__class__.__name__] is None or data[metric_provider.__class__.__name__].shape[0] == 0:
                raise RuntimeError(f"No metrics were able to be imported from: {metric_provider.__class__.__name__}")

    return data


def check_minimum_provider_configuration(mp):
    # Do some checks
    def check_provider(mp, criteria):
        providers = [provider for provider in mp if all(criterion in provider for criterion in criteria)]
        return providers[0] if len(providers) == 1 else None

    def one_psu_provider(mp):
        return check_provider(mp, ['.energy', '.machine'])

    def rapl_provider(mp):
        return check_provider(mp, ['cpu', '.energy', '.rapl'])

    def temp_provider(mp):
        return check_provider(mp, ['lmsensors', '.temperature'])

    energy_provider = one_psu_provider(mp)
    if not energy_provider:
        logging.warning('Please configure a PSU provider for the best results.')
        energy_provider = rapl_provider(mp)
        if energy_provider:
            logging.info('Using rapl provider.')
        else:
            logging.error('We need at least one PSU / RAPL provider configured!')
            raise SystemExit(1)

    # Warn and exit if there is no temperature or system energy provider configured
    temp_provider = temp_provider(mp)
    if not temp_provider:
        logging.error('We need at least one temperature provider configured!')
        raise SystemExit(1)
    return (energy_provider, temp_provider)


#####
# This block is to check the load the metric providers create on an idle system.
# We currently only look at energy
#####
def determine_baseline_energy(mp, energy_provider, idle_time, provider_interval):
    # global timings # we just read

    # Load only the energy provider with a benchmarking provider_interval
    load_metric_providers(mp, [energy_provider,], provider_interval)

    start_metric_providers()
    timings['start_energy_idle'] = int(time.time() * 1_000_000)
    countdown_bar(idle_time, 'Baseline Measurement')
    timings['end_energy_idle'] = int(time.time() * 1_000_000)

    data_energy_idle = stop_metric_providers()

    if len(data_energy_idle.keys()) != 1:
        raise ValueError("data_energy_idle should have only one key")

    energy_provider_key = next(iter(data_energy_idle))
    data_energy_idle = data_energy_idle[energy_provider_key]

    return check_energy_values(data_energy_idle, timings['start_energy_idle'], timings['end_energy_idle'], provider_interval, 'Baseline')


def check_energy_values(data, timing_start, timing_end, provider_interval, mode):
    # global timings # we just read

    # Remove boot and stop values
    data_mask = (data['time'] >= timing_start) & (data['time'] <= timing_end)
    data = data[data_mask]

    # Remove first values as RAPL is an aggregate value and the first is not representative.
    data = data.iloc[2:]


    # make sure that there are no massive peaks in standard deviation. If so exit with notification
    mean_value = data['value'].mean()
    std_value = data['value'].std()

    if len(data['value']) < 3:
        raise SystemExit(f"Not enough data points for idle time calculation (amount: {len(data['value'])}; Std: {round(std_value,2)} mJ). Please extend the idle time duration. {data}")

    threshold = STD_THRESHOLD_MULTI * std_value

    out_mask = (data['value'] < mean_value - threshold) | (data['value'] > mean_value + threshold)

    outliers = data[out_mask]
    if not outliers.empty or (std_value / mean_value) > 0.03:
        logging.error(f"""here are outliers in your {mode} data or the StdDev is > 3%. It looks like your system is not in a stable state!
                        Please make sure that the are no jobs running in the background. Aborting!""")
        logging.info('\n%s', data)
        logging.info('Mean Energy: %s mJ', round(mean_value,2))
        logging.info('Mean Power: %s W', round(mean_value/provider_interval,2))
        logging.info('Std. Dev: %s mJ', round(std_value,2))
        logging.info('Std. Dev (rel): %s %%', round((std_value / mean_value) * 100,2))
        logging.info('Allowed threshold: %s', threshold)
        logging.info('Outliers: %s', outliers)

        if input("System is not stable, do you still want to continue?? [Y/n] ").lower() not in ('y', ''):
            raise SystemExit('System not stable.')

    logging.info(f"{GREEN}System {mode} measurement successful{NC}")
    logging.info('Mean Energy: %s mJ', round(mean_value,2))
    logging.info('Mean Power: %s W', round(mean_value/provider_interval,2))
    logging.info('Std. Dev: %s mJ', round(std_value,2))
    logging.info('Std. Dev (rel): %s %%', round((std_value / mean_value) * 100,2))
    logging.info('----------------------------------------------------------')

    return mean_value, std_value

def check_configured_provider_energy_overhead(mp, energy_provider_key, idle_time, energy_baseline_mean_value, provider_interval):
    # global timings # we just read
    global docker_sleeper

    client = docker.from_env()

    load_metric_providers(mp, mp, None)

    # We need to start at least one container that just idles so we can also run the container providers

    logging.info('Starting and pulling docker container.')
    docker_sleeper = client.containers.run('alpine', 'sleep 2147483647',
                                    detach=True, auto_remove=True, name='calibrate_sleeper', remove=True)

    gmt_container_obj = {docker_sleeper.id: {'name': docker_sleeper.name}}

    start_metric_providers(containers=gmt_container_obj)
    timings['start_all_idle'] = int(time.time() * 1_000_000)
    countdown_bar(idle_time, 'Idle')
    timings['end_all_idle'] = int(time.time() * 1_000_000)

    data_all_idle = stop_metric_providers(containers=gmt_container_obj)

    logging.info('Stopping and removing docker container.')
    docker_sleeper.stop()
    docker_sleeper = None

    data_energy_idle = data_all_idle[energy_provider_key]

    energy_all_mean_value, energy_all_std_value = check_energy_values(data_energy_idle, timings['start_all_idle'], timings['end_all_idle'], provider_interval, 'Idle')

    logging.info(f"{GREEN}Provider idle energy overhead measurement successful.{NC}")

    logging.info(f"Idle Energy overhead is: {energy_all_mean_value - energy_baseline_mean_value} mJ")
    logging.info(f"Idle Energy overhead (rel.): {((energy_all_mean_value - energy_baseline_mean_value) / energy_baseline_mean_value) * 100} %")
    logging.info(f"Idle Power overhead is: {(energy_all_mean_value - energy_baseline_mean_value) / provider_interval} W")
    logging.info('-----------------------------------------------------------------------------------------')

    return energy_all_mean_value, energy_all_std_value

def check_values(data):
    # global timings # we just read

    # Remove boot and stop values
    data_mask = (data['time'] >= timings['start_idle']) & (data['time'] <= timings['end_idle'])
    data = data[data_mask]

    grouped = data.groupby('detail_name')

    mean_values = {}
    std_values = {}

    for name, group in grouped:

        # Remove first values as RAPL is an aggregate value and the first is not representative.
        group = group.iloc[2:]
        # make sure that there are no massive peaks in standard deviation. If so exit with notification
        mean_value = group['value'].mean()
        max_value = group['value'].max()
        std_value = group['value'].std()

        if group.iloc[0]['unit'] == 'centi°C':
            display_unit = '°C'
            display_value = mean_value / 100
            display_max = max_value / 100
            display_std = std_value / 100
        elif group.iloc[0]['unit'] == 'mJ':
            display_unit = group.iloc[0]['unit']
            display_value = mean_value
            display_max = max_value
            display_std = std_value
        else:
            raise SystemExit(f"Unknown unit detected for {name}: {group.iloc[0]['unit']}; Only expecting mJ and centi°C.")


        threshold = STD_THRESHOLD_MULTI * std_value

        out_mask = (group['value'] < mean_value - threshold) | (group['value'] > mean_value + threshold)

        outliers = group[out_mask]
        if not outliers.empty or (std_value / mean_value) > 0.03:
            logging.error(f'''There are outliers in your data for {name} or the StdDev is > 3%. It looks like your system is not in a stable state!
                            Please make sure that the are no jobs running in the background. Aborting!''')
            logging.info('\n%s', group)
            logging.info('Mean Value: %s %s', round(display_value,2), display_unit)
            logging.info('Max Value: %s %s', round(display_max,2), display_unit)
            logging.info('Std. Dev: %s %s', round(display_std,2), display_unit)
            logging.info('Std. Dev (rel): %s %%', round(display_std / display_value, 2)) # /100 * 100 = 1, therefore omitted
            logging.info('Allowed threshold: %s', threshold)
            logging.info('Outliers: %s', outliers)

            if input("System is not stable, do you still want to continue?? [Y/n] ").lower() not in ('y', ''):
                raise SystemExit(4)

        logging.info(f"Measurement for {name} completed")
        logging.info('Mean Value: %s %s', round(display_value,2), display_unit)
        logging.info('Max Value: %s %s', round(display_max,2), display_unit)
        logging.info('Std. Dev: %s %s', round(display_std,2), display_unit)
        logging.info('Std. Dev (rel): %s %%', round(display_std / display_value, 2)) # /100 * 100 = 1, therefore omitted
        logging.info('----------------------------------------------------------')


        mean_values[name] = mean_value
        std_values[name] = std_value

    return mean_values, std_values


def determine_idle_energy_and_temp(mp, energy_provider, temp_provider, idle_time, provider_interval):
    # global timings # we just read

    load_metric_providers(mp, [energy_provider, temp_provider], provider_interval)

    # Start the metrics providers
    start_metric_providers()

    # Wait for n minutes and record data into different files
    timings['start_idle'] = int(time.time() * 1_000_000)
    countdown_bar(idle_time, 'Idle')
    timings['end_idle'] = int(time.time() * 1_000_000)

    data_idle = stop_metric_providers()

    logging.debug('Checking for consistent data')

    energy_provider_name = energy_provider.rsplit('.', 1)[-1]
    temp_provider_name = temp_provider.rsplit('.', 1)[-1]

    energy_mean, energy_std = check_values(data_idle[energy_provider_name])
    temp_mean, temp_std = check_values(data_idle[temp_provider_name])

    return data_idle, energy_mean, energy_std, temp_mean, temp_std, energy_provider_name, temp_provider_name

def stress_system(stress_command, stress_time, cooldown_time, temp_mean, temp_std, temp_provider, temperature_increase, energy_provider_name, energy_baseline_mean_value, energy_all_mean_value, provider_interval):
    # global metric_providers # we just read
    # global timings # we just read

    temp_provider_name = temp_provider.rsplit('.', 1)[-1]

    start_metric_providers()

    temp_provider = next(x for x in metric_providers if temp_provider_name == x.__class__.__name__)

    def run_stress(stress_command, stress_time):
        with subprocess.Popen(stress_command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
            check_temperature_increase(stress_time, 'Stressing', temp_mean, temp_std, temp_provider, temperature_increase)
            return_code = process.wait()
            if return_code != 0:
                logging.error(f"{stress_command} failed with return code: {return_code}")
                raise SystemExit(2)


    logging.info('Starting stress')
    timings['start_stress'] = int(time.time() * 1_000_000)
    run_stress(stress_command, stress_time)
    timings['end_stress'] = int(time.time() * 1_000_000)

    logging.info('Starting cool down')
    timings['start_cooldown'] = int(time.time() * 1_000_000)
    countdown_bar(cooldown_time, 'Cooldown')
    timings['end_cooldown'] = int(time.time() * 1_000_000)


    data_stress = stop_metric_providers()

    def get_cooldown_time(data):
        # global timings # we just read

        # Remove boot and stop values
        data_mask = (data['time'] >= timings['start_cooldown']) & (data['time'] <= timings['end_cooldown'])
        data = data[data_mask]

        grouped = data.groupby('detail_name')

        norm_times = {}
        for name, group in grouped:
            under_checker = group['value'] <= temp_mean[name] + (temp_std[name] * STD_THRESHOLD_MULTI)
            consecutive_under = under_checker.rolling(window=RELIABLE_DURATION).sum() == RELIABLE_DURATION

            if consecutive_under.any():
                temp_id = consecutive_under.idxmax()
                norm_times[name] = group['time'].loc[temp_id]
                logging.debug(f"Temp normal again at ID {temp_id} with time {(norm_times[name] - timings['start_cooldown']) / 1_000_000}")
            else:
                logging.error(f"The temperature of {name} never falls below the idle value ({round(temp_mean[name]/100,2)}°) for more than {RELIABLE_DURATION} consecutive data points.")
                logging.error(f"System is still hot after evaluation timeframe ({round((temp_mean[name] + (temp_std[name] * STD_THRESHOLD_MULTI))/100,2)}).")
                logging.error('You can either increase the cooldown wait time for the script, or install a fan :)')
                logging.info('Data from cooldown:')
                logging.info(f"\n{group}")
                logging.info(f"Mean from from idle: {round(temp_mean[name]/100,2)}°")
                logging.info(f"Mean+std from idle : {round((temp_mean[name] + (temp_std[name] * STD_THRESHOLD_MULTI)/100),2)}°")
                if input("System is still to hot. No meaningful data could be derived. Do you want to continue?? [Y/n] ").lower() not in ('y', ''):
                    raise SystemExit(3)

        return norm_times

    cooldown_times = get_cooldown_time(data_stress[temp_provider_name])
    biggest_time = max(cooldown_times.values())

    data_energy_stress = data_stress[energy_provider_name]
    energy_stress_mean_value, _ = check_energy_values(data_energy_stress, timings['start_stress'], timings['end_stress'], provider_interval, 'Load')

    logging.info(f"{GREEN}Provider effective energy overhead measurement successful.{NC}")

    logging.info(f"Peak system energy is: {energy_stress_mean_value} mJ")
    logging.info(f"Peak system power is: {energy_stress_mean_value / provider_interval} W")

    logging.info(f"Effective energy overhead (rel.) is: {((energy_all_mean_value - energy_baseline_mean_value) / (energy_stress_mean_value - energy_baseline_mean_value)) * 100} %")
    logging.info('-----------------------------------------------------------------------------------------')

    return data_stress, round(((biggest_time - timings['start_cooldown']) / 1_000_000),2) + 30 # We add 30 secs just to be sure

def save_value(energy_mean, energy_std, temp_mean, temp_std, energy_baseline_mean_value, energy_baseline_std_value, energy_all_mean_value, energy_all_std_value, cdt_seconds):
    def modify_sleep_time_in_client_section(lines, new_value):
        inside_client_section = False
        modified_lines = []
        modified = False

        for line in lines:
            # Once we have made the replacement we just add the lines without doing anything more
            if not modified:
                stripped_line = line.strip().lower()

                if stripped_line == "client:":
                    inside_client_section = True

                if inside_client_section and "sleep_time_after_job:" in stripped_line:
                    leading_spaces = len(line) - len(line.lstrip())
                    line = " " * leading_spaces + f"sleep_time_after_job: {new_value}\n"
                    logging.debug('Setting value')
                    modified = True

            modified_lines.append(line)

        return modified_lines

    def add_calibration(modified_lines):
        lines_to_add = []
        yml_data = {
            'calibration': {
                'energy_stress_mean': [{k: str(v)} for k, v in energy_mean.items()],
                'energy_stress_std': [{k: str(v)} for k, v in energy_std.items()],
                'temp_mean': [{k: str(v)} for k, v in temp_mean.items()],
                'temp_std': [{k: str(v)} for k, v in temp_std.items()],
                'energy_baseline_mean': energy_baseline_mean_value,
                'energy_baseline_std': energy_baseline_std_value,
                'energy_baseline_all_mean': energy_all_mean_value,
                'energy_baseline_all_std': energy_all_std_value,

            }
        }

        yml_string = yaml.dump(yml_data).split('\n')
        lines_to_add.extend(['', '', '#This was written by the calibrate.py script'])
        lines_to_add.extend(yml_string)
        lines_to_add = [f"{i}\n" for i in lines_to_add]
        modified_lines.extend(lines_to_add)
        return modified_lines

    with open(CONF_FILE, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    modified_lines = modify_sleep_time_in_client_section(lines, cdt_seconds)
    modified_lines = add_calibration(modified_lines)

    with open(CONF_FILE, 'w', encoding='utf-8') as file:
        logging.debug('Writing config file')
        file.writelines(modified_lines)

def show_summary(data_idle, data_stress, temp_provider_name, energy_provider_name, temp_mean, energy_mean):
    def plot_data(data_source, xside, yside, label_prefix, mean_values):
        # global timings # we just read

        data_mask = (data_source['time'] >= timings['start_idle']) & (data_source['time'] <= timings['end_cooldown'])
        filtered_data = data_source[data_mask]

        for n, g in filtered_data.groupby('detail_name'):
            g = g.iloc[1:]
            chosen_color = random.choice(allowed_colors)
            allowed_colors.remove(chosen_color)

            plt.plot(g['time'].tolist(), g['value'].tolist(), xside=xside, yside=yside, label=f"{label_prefix}: {n}", color=chosen_color)
            plt.hline(mean_values[n], chosen_color)

    allowed_colors = ["red", "green", "yellow", "blue", "magenta", "cyan", "white"]

    temp_data = pd.concat([data_idle[temp_provider_name], data_stress[temp_provider_name]], ignore_index=True)
    temp_data = temp_data.sort_values(by='time')

    pow_data = pd.concat([data_idle[energy_provider_name], data_stress[energy_provider_name]], ignore_index=True)
    pow_data = pow_data.sort_values(by='time')

    plot_data(temp_data, "lower", "left", "Temperature (left, bottom)", temp_mean)
    plot_data(pow_data, "upper", "right", "Energy (right, top)", energy_mean)

    plt.title("Temperature/ Energy Plot")
    plt.theme('clear')
    plt.show()


def cleanup():
    # global docker_sleeper # we just execute

    logging.debug('Cleaning everything up for exit')
    stop_metric_providers(force=True)
    shutil.rmtree(TMP_FOLDER, ignore_errors=True)
    if docker_sleeper:
        docker_sleeper.kill()


def main(idle_time,
         stress_time,
         provider_interval,
         stress_command,
         cooldown_time,
         write_config,
         temperature_increase
         ):
    # global docker_sleeper # we just read

    # Setup and importing
    logging.warning('Starting calibration. Please don\'t do anything with the computer!')

    logging.info(f"{MAGENTA}Setting up environment and metric providers for initial baseline measurement ...{NC}")
    shutil.rmtree(TMP_FOLDER, ignore_errors=True)
    Path(TMP_FOLDER).mkdir(parents=True, exist_ok=True)
    logging.debug(f"Temporary folder created: {TMP_FOLDER}")

    mp = utils.get_metric_providers(GlobalConfig().config)
    energy_provider, temp_provider = check_minimum_provider_configuration(mp)

    logging.info(f"{MAGENTA}Determining baseline of system with no load ...{NC}")
    energy_baseline_mean_value, energy_baseline_std_value = determine_baseline_energy(mp, energy_provider, idle_time, provider_interval)
    energy_provider_key = energy_provider.rsplit('.', 1)[1]

    logging.info(f"{MAGENTA}Determining provider overhead for GMT when running configured set of providers ...{NC}")
    energy_all_mean_value, energy_all_std_value = check_configured_provider_energy_overhead(mp, energy_provider_key, idle_time, energy_baseline_mean_value, provider_interval)

    logging.info(f"{MAGENTA}Determining idle values for energy and temperature to caclulate cooldown calibration settings ...{NC}")
    data_idle, energy_mean, energy_std, temp_mean, temp_std, energy_provider_name, temp_provider_name = determine_idle_energy_and_temp(mp, energy_provider, temp_provider, idle_time, provider_interval)

    logging.info(f"{MAGENTA}Stressing system to determine max. system temperature under load ...{NC}")
    data_stress, cdt_seconds = stress_system(stress_command, stress_time, cooldown_time, temp_mean, temp_std, temp_provider, temperature_increase, energy_provider_name, energy_baseline_mean_value, energy_all_mean_value, provider_interval)

    logging.info(f"{MAGENTA}Your calculated cooldown time is {cdt_seconds} seconds.{NC}")

    if write_config or input("Do you want to save the values in the config.yml? [Y/n] ").lower() in ('y', ''):
        save_value(energy_mean, energy_std, temp_mean, temp_std, energy_baseline_mean_value, energy_baseline_std_value, energy_all_mean_value, energy_all_std_value, cdt_seconds)

    if input('Do you want to see a summary? [Y/n]').lower() in ('y', ''):
        show_summary(data_idle, data_stress, temp_provider_name, energy_provider_name, temp_mean, energy_mean)

    cleanup()

# Custom formatter for logging
class MyFormatter(logging.Formatter):

    my_format = '[%(levelname)s] %(asctime)s - %(message)s'

    FORMATS = {
        logging.DEBUG: my_format,
        logging.INFO: my_format,
        logging.WARNING: YELLOW + my_format + NC,
        logging.ERROR: RED + my_format + NC,
        logging.CRITICAL: RED + my_format + NC
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description=
                                     '''
                                     A script to establish baseline values for systems that the Green Metrics Tool
                                     should run benchmarks on.
                                     Return codes are:
                                     1 - no PSU and temp provider configured
                                     2 - stress command failed
                                     3 - temperature never falls below mean
                                     4 - outliers in idle measurement
                                     5 - temperature is not raising under stress
                                     ''')

    parser.add_argument('-d', '--dev', action='store_true', help='Enable development mode with reduced timing.')
    parser.add_argument('-w', '--write-config', action='store_true', help='Skips the config write dialog and just writes it.')

    parser.add_argument('-it', '--idle-time', type=int, default=60*5, help='The seconds the system should wait in idle mode. Defaults to 5 minutes')
    parser.add_argument('-st', '--stress-time', type=int, default=60*2, help='The seconds the system should stress the system. Defaults to 2 minutes')
    parser.add_argument('-ct', '--cooldown-time', type=int, default=60*5, help='The seconds the system should wait to be back to normal temperature. Defaults to 5 minutes')

    parser.add_argument('-pi', '--provider-interval', type=int, default=2000, help='The interval in milliseconds for the providers . Defaults to 5000')
    parser.add_argument('-ti', '--temperature-increase', type=int, default=1000, help='The delta the temperature must increase. Defaults to 1000')

    parser.add_argument('-s', '--stress-command', type=str, help='The command to stress the system with. Defaults to stress-ng')

    parser.add_argument('-v', '--log-level', choices=LOG_LEVELS, default='info', help='Logging level (debug, info, warning, error, critical)')
    parser.add_argument('-o', '--output-file', type=str, help='Path to the output log file.')

    args = parser.parse_args()

    if args.dev:
        args.idle_time = 15
        args.stress_time = 15
        args.cooldown_time = 30
        args.provider_interval = 1000
        args.log_level = 'debug'
        RELIABLE_DURATION = 2

    log_level = getattr(logging, args.log_level.upper())

    if not args.stress_command:
        # Currently we are only interested in how hot the CPU gets so we use the matrix stress
        # In the future we might also want to see how much energy components.
        args.stress_command = f"stress-ng --matrix 0 -t {args.stress_time}s"



    if args.output_file:
        logging.basicConfig(filename=args.output_file, level=log_level, format='[%(levelname)s] %(asctime)s - %(message)s')
    else:
        handler_sh = logging.StreamHandler(sys.stdout)
        handler_sh.setFormatter(MyFormatter())
        logging.basicConfig(level=log_level, handlers=[handler_sh], format='[%(levelname)s] %(asctime)s - %(message)s')

    if args.provider_interval < 1000:
        logging.warning('A too small interval will make it difficult for the system to become stable!')

    logging.debug('Calibration script started 🎉')

    try:
        main(idle_time = args.idle_time,
            stress_time = args.stress_time,
            provider_interval = args.provider_interval,
            stress_command = args.stress_command,
            cooldown_time = args.cooldown_time,
            write_config = args.write_config,
            temperature_increase = args.temperature_increase
        )
    except Exception as e:
        error_message = f"An error occurred: {e}\n"
        error_message += traceback.format_exc()
        logging.error(error_message)
    finally:
        cleanup()
