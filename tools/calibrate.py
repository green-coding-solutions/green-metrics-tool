#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#pylint: disable=logging-fstring-interpolation


import argparse
import importlib
import logging
import subprocess
import shutil
import sys
import time
from pathlib import Path
import random

from tqdm import tqdm
import plotext as plt
import pandas as pd
import yaml

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

# Globals
metric_providers= []
timings = {}


def countdown_bar(total_seconds, desc='Countdown'):
    with tqdm(total=total_seconds, desc=desc, bar_format='{l_bar}{bar}| {remaining}') as pbar:
        for _ in range(total_seconds):
            time.sleep(1)
            pbar.update(1)

def load_metric_providers(mp, pt_providers, provider_interval):
    # We pretty much copied this from the runner. Keeping the same flow so we can maintain it easier.
    for metric_provider in pt_providers:
        module_path, class_name = metric_provider.rsplit('.', 1)
        module_path = f"metric_providers.{module_path}"
        conf = mp[metric_provider] or {}

        logging.info(f"Importing {class_name} from {module_path}")

        conf['resolution'] = provider_interval

        module = importlib.import_module(module_path)

        metric_provider_obj = getattr(module, class_name)(**conf)

        metric_providers.append(metric_provider_obj)


def start_metric_providers():
    for metric_provider in metric_providers:
        metric_provider.start_profiling()

    logging.info('Waiting for Metric Providers to boot ...')
    countdown_bar(len(metric_providers) * 2, 'Booting')

    for metric_provider in metric_providers:
        stderr_read = metric_provider.get_stderr()
        logging.debug(f"Stderr check on {metric_provider.__class__.__name__}")
        if stderr_read is not None:
            raise RuntimeError(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

def stop_metric_providers():
    logging.debug('Stopping metric providers and parsing measurements')

    data = {}
    for metric_provider in metric_providers:

        if stderr_read := metric_provider.get_stderr() is not None:
            raise RuntimeError(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

        metric_provider.stop_profiling()

        data[metric_provider.__class__.__name__] = metric_provider.read_metrics(1)
        if data[metric_provider.__class__.__name__] is None or data[metric_provider.__class__.__name__].shape[0] == 0:
            raise RuntimeError(f"No metrics were able to be imported from: {metric_provider.__class__.__name__}")

    return data


def main(idle_time,
         stress_time,
         provider_interval,
         stress_command,
         cooldown_time,
         write_config,
         ):

    # Setup
    shutil.rmtree(TMP_FOLDER, ignore_errors=True)
    Path(TMP_FOLDER).mkdir(parents=True, exist_ok=True)
    logging.debug(f"Temporary folder created: {TMP_FOLDER}")

    # Importing Metric provider
    mp = utils.get_metric_providers(GlobalConfig().config)

    # Do some checks
    def check_provider(mp, criteria):
        providers = [provider for provider in mp if all(criterion in provider for criterion in criteria)]
        return providers[0] if len(providers) == 1 else None

    def one_psu_provider(mp):
        return check_provider(mp, ['.energy', '.machine'])

    def rapl_provider(mp):
        return check_provider(mp, ['cpu', '.energy', '.RAPL'])

    def temp_provider(mp):
        return check_provider(mp, ['lm_sensors', '.temperature'])

    power_provider = one_psu_provider(mp)
    if not power_provider:
        logging.warning('Please configure a psu provider for the best results.')
        power_provider = rapl_provider(mp)
        if power_provider:
            logging.info('Using rapl provider.')
        else:
            logging.error('We need at least one psu/ rapl provider configured!')
            sys.exit(1)

    # Warn and exit if there is no temperature or system energy provider configured
    tmp_provider = temp_provider(mp)
    if not tmp_provider:
        logging.error('We need at least one temperature provider configured!')
        sys.exit(1)

    load_metric_providers(mp, [power_provider, tmp_provider], provider_interval)

    # Start the metrics providers
    start_metric_providers()

    logging.warning('Starting idle measurement timeframe. Please don\'t do anything with the computer!')

    # Wait for n minutes and record data into different files
    timings['start_idle'] = int(time.time() * 1_000_000)
    countdown_bar(idle_time, 'Idle')
    timings['end_idle'] = int(time.time() * 1_000_000)

    data_idle = stop_metric_providers()

    def check_values(data):
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
            std_value = group['value'].std()

            threshold = STD_THRESHOLD_MULTI * std_value

            out_mask = (group['value'] < mean_value - threshold) | (group['value'] > mean_value + threshold)

            outliers = group[out_mask]
            if not outliers.empty:
                logging.error(f'''There are outliers in your data for {name}. It looks like your system is not in a stable state!
                                Please make sure that the are no jobs running in the background. Aborting!''')
                logging.debug('\n%s', group)
                logging.debug('Mean Val: %s', mean_value)
                logging.debug('Std. Dev: %s', std_value)

                sys.exit(4)

            mean_values[name] = mean_value
            std_values[name] = std_value

        return mean_values, std_values

    logging.info('Checking for consistent data')

    power_provider_name = power_provider.rsplit('.', 1)[-1]
    temp_provider_name = tmp_provider.rsplit('.', 1)[-1]

    power_mean, power_std = check_values(data_idle[power_provider_name])
    tmp_mean, tmp_std = check_values(data_idle[temp_provider_name])

    logging.debug('Power mean is %s', power_mean)
    logging.debug('Temperature means are %s', tmp_mean)

    # Step 2
    # Now we have the idle values now let's stress
    start_metric_providers()

    def run_stress(stress_command, stress_time):
        with subprocess.Popen(stress_command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
            countdown_bar(stress_time, 'Stressing')
            return_code = process.wait()
            if return_code != 0:
                logging.error(f"{stress_command} failed with return code: {return_code}")
                sys.exit(2)


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
        # Remove boot and stop values
        data_mask = (data['time'] >= timings['start_cooldown']) & (data['time'] <= timings['end_cooldown'])
        data = data[data_mask]

        grouped = data.groupby('detail_name')

        norm_times = {}
        for name, group in grouped:
            under_checker = group['value'] <= tmp_mean[name] + (tmp_std[name] * STD_THRESHOLD_MULTI)
            consecutive_under = under_checker.rolling(window=RELIABLE_DURATION).sum() == RELIABLE_DURATION

            if consecutive_under.any():
                tmp_id = consecutive_under.idxmax() - RELIABLE_DURATION
                logging.debug(f"Temp normal again at {tmp_id}")
                norm_times[name] = group['time'].loc[tmp_id]
            else:
                logging.error(f"The temperature value never falls below idle mean for {name}.")
                logging.info(data)
                logging.info(f"Mean    : {tmp_mean[name]}")
                logging.info(f"Mean+std: {tmp_mean[name] + (tmp_std[name] * STD_THRESHOLD_MULTI)}")
                logging.info(f"Window  : {RELIABLE_DURATION}")
                sys.exit(3)

        return norm_times

    cooldown_times = get_cooldown_time(data_stress[temp_provider_name])
    biggest_time = max(cooldown_times.values())
    cdt_seconds = round(((biggest_time - timings['start_cooldown']) / 1_000_000))
    logging.info(f"Cool down time is {cdt_seconds} seconds")


    # Offer to set the values in the config.yml
    def save_value():
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
                    'power_mean': [{k: str(v)} for k, v in power_mean.items()],
                    'power_std': [{k: str(v)} for k, v in power_std.items()],
                    'temp_mean': [{k: str(v)} for k, v in tmp_mean.items()],
                    'temp_std': [{k: str(v)} for k, v in tmp_std.items()]
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

    if write_config or input("Do you want to save the values in the config.yml? [Y/n] ").lower() in ('y', ''):
        save_value()

    if input('Do you want to see a summary? [Y/n]').lower() in ('y', ''):

        def plot_data(data_source, xside, yside, label_prefix, mean_values):
            data_mask = (data_source['time'] >= timings['start_idle']) & (data_source['time'] <= timings['end_cooldown'])
            filtered_data = data_source[data_mask]

            for n, g in filtered_data.groupby('detail_name'):
                g = g.iloc[1:]
                chosen_color = random.choice(allowed_colors)
                allowed_colors.remove(chosen_color)

                plt.plot(g['time'].tolist(), g['value'].tolist(), xside=xside, yside=yside, label=f"{label_prefix}: {n}", color=chosen_color)
                plt.hline(mean_values[n], chosen_color)

        allowed_colors = ["red", "green", "yellow", "blue", "magenta", "cyan", "white"]

        tmp_data = pd.concat([data_idle[temp_provider_name], data_stress[temp_provider_name]], ignore_index=True)
        tmp_data = tmp_data.sort_values(by='time')

        pow_data = pd.concat([data_idle[power_provider_name], data_stress[power_provider_name]], ignore_index=True)
        pow_data = pow_data.sort_values(by='time')

        plot_data(tmp_data, "lower", "left", "Temperature (left, bottom)", tmp_mean)
        plot_data(pow_data, "upper", "right", "Power (right, top)", power_mean)

        plt.title("Temperature/ Energy Plot")
        plt.theme('clear')
        plt.show()

    shutil.rmtree(TMP_FOLDER, ignore_errors=True)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description=
                                     '''
                                     A script to establish baseline values for systems that the Green Metrics Tool
                                     should run benchmarks on.
                                     Return codes are:
                                     1 - no psu and temp provider configured
                                     2 - stress command failed
                                     3 - temperature never falls below mean
                                     4 - outliers in idle measurement
                                     ''')

    parser.add_argument('-d', '--dev', action='store_true', help='Enable development mode with reduced timing.')
    parser.add_argument('-w', '--write-config', action='store_true', help='Skips the config write dialog and just writes it.')

    parser.add_argument('-it', '--idle-time', type=int, default=60*5, help='The seconds the system should wait in idle mode. Defaults to 5 minutes')
    parser.add_argument('-st', '--stress-time', type=int, default=60*2, help='The seconds the system should stress the system. Defaults to 2 minutes')
    parser.add_argument('-ct', '--cooldown-time', type=int, default=60*5, help='The seconds the system should wait to be back to normal temperature. Defaults to 5 minutes')

    parser.add_argument('-pi', '--provider-interval', type=int, default=2000, help='The interval in milliseconds for the providers . Defaults to 5000')

    parser.add_argument('-s', '--stress-command', type=str, help='The command to stress the system with. Defaults to stress-ng')

    parser.add_argument('-v', '--log-level', choices=LOG_LEVELS, default='info', help='Logging level (debug, info, warning, error, critical)')
    parser.add_argument('-o', '--output-file', type=str, help='Path to the output log file.')

    args = parser.parse_args()

    if args.dev:
        args.idle_time = 5
        args.stress_time = 1
        args.cooldown_time = 10
        args.provider_interval = 1000
        args.log_level = 'debug'
        RELIABLE_DURATION = 2

    log_level = getattr(logging, args.log_level.upper())

    if args.provider_interval < 1000:
        logging.warning('A too small interval will make it difficult for the system to become stable!')

    if not args.stress_command:
        # Currently we are only interested in how hot the CPU gets so we use the matrix stress
        # In the future we might also want to see how much energy components.
        args.stress_command = f"stress-ng --matrix 0 -t {args.stress_time}s"

    if args.output_file:
        logging.basicConfig(filename=args.output_file, level=log_level, format='[%(levelname)s] %(asctime)s - %(message)s')
    else:
        logging.basicConfig(level=log_level, format='[%(levelname)s] %(asctime)s - %(message)s')

    logging.debug('Calibration script started 🎉')

    main(idle_time = args.idle_time,
         stress_time = args.stress_time,
         provider_interval = args.provider_interval,
         stress_command = args.stress_command,
         cooldown_time = args.cooldown_time,
         write_config = args.write_config,
         )
