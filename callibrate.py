import argparse
import importlib
import logging
import subprocess
import shutil
import sys
import time
from pathlib import Path

from tqdm import tqdm

from lib.global_config import GlobalConfig
from lib import utils

# Todo only CPU Stress

TMP_FOLDER = '/tmp/green-metrics-tool'
LOG_LEVELS = ['debug', 'info', 'warning', 'error', 'critical']

config = GlobalConfig().config
metric_providers= []
timings = {}

def check_one_psu_provider(mp):
    return True
    energy_machine_providers = [provider for provider in metric_providers if ".energy" in provider and ".machine" in provider]
    return len(energy_machine_providers) <= 1

def check_temp_provider(mp):
    return True

def countdown_bar(minutes):
    total_seconds = minutes * 60
    with tqdm(total=total_seconds, desc="Countdown", bar_format="{l_bar}{bar}| {remaining}") as pbar:
        for _ in range(total_seconds):
            time.sleep(1)
            pbar.update(1)

def start_metric_providers():
    for metric_provider in metric_providers:
        stderr_read = metric_provider.get_stderr()
        logging.debug(f"Stderr check on {metric_provider.__class__.__name__}")
        if stderr_read is not None:
            raise RuntimeError(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")
    logging.info('Waiting for Metric Providers to boot ...')
    time.sleep(2)

def stop_metric_providers():
    logging.debug('Stopping metric providers and parsing measurements')

    data = {}
    errors = []
    for metric_provider in metric_providers:
        if not metric_provider.has_started():
            continue

        stderr_read = metric_provider.get_stderr()
        if stderr_read is not None:
            errors.append(f"Stderr on {metric_provider.__class__.__name__} was NOT empty: {stderr_read}")

        metric_provider.stop_profiling()

        data[metric_provider.__class__.__name__] = metric_provider.read_metrics(1)
        if data[metric_provider.__class__.__name__] is None or data[metric_provider.__class__.__name__].shape[0] == 0:
            errors.append(f"No metrics were able to be imported from: {metric_provider.__class__.__name__}")

    if errors:
        raise RuntimeError("\n".join(errors))

    return data

def main(idle_time, provider_interval):

    # Setup
    shutil.rmtree(TMP_FOLDER, ignore_errors=True)
    Path(TMP_FOLDER).mkdir(parents=True, exist_ok=True)
    logging.debug(f"Temporary folder created: {TMP_FOLDER}")

    # Importing Metric provider
    mp = utils.get_metric_providers(config)

    # Warn and exit if there is no temperature or system energy provider configured
    if not (check_one_psu_provider(mp) and  (mp)):
        logging.error('We need at least one psu provider and one temperature provider')
        sys.exit(1)

    # Stop metrics provider that are not used


    # We pretty much copied this from the runner. Keeping the same flow so we can maintain it easier.
    for metric_provider in mp:
        module_path, class_name = metric_provider.rsplit('.', 1)
        module_path = f"metric_providers.{module_path}"
        conf = mp[metric_provider] or {}

        logging.info(f"Importing {class_name} from {module_path}")

        conf['resolution'] = provider_interval

        module = importlib.import_module(module_path)

        metric_provider_obj = getattr(module, class_name)(**conf)

        metric_providers.append(metric_provider_obj)

    # Start the metrics providers configured in the config.yml
    start_metric_providers()

    logging.warning('Starting idle measurement timeframe. Please don\'t do anything with the computer!')

    # Wait for 5 minutes and record data into different files
    timings['start_idle'] = time.time()
    countdown_bar(idle_time)
    timings['start_idle'] = time.time()

    # Stop metrics providers
    data_idle = stop_metric_providers()

    # calculate the average and save this as the baseline

    # make sure that there are no massive peaks in standard deviation. If so exit with notification

    # Start metrics providers
    start_metric_providers()

    # Now stress the computer for 2 minutes on all cores
    # Download a huge file
    # create loads of disk io

    # Wait till temperature is back to baseline and save time delta

    # Offer to set the values in the config.yml

    # Create a little report

    logging.info('Removing temporary files')
    shutil.rmtree(TMP_FOLDER, ignore_errors=True)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description=
                                     '''
                                     A script to establish baseline values for systems that the Green Metrics Tool
                                     should run benchmarks on.
                                     Return codes are:
                                     1 -  no psu and temp provider configured
                                     ''')
    parser.add_argument('-d', '--dev', action='store_true', help='Enable development mode with reduced timing.')
    parser.add_argument('-it', '--idle-time', type=int, default=60*5, help='The seconds the system should wait in idle mode. Defaults to 5 minutes')
    parser.add_argument('-st', '--stress-time', type=int, default=60*2, help='The seconds the system should stress the system. Defaults to 2 minutes')
    parser.add_argument('-pi', '--provider-interval', type=int, default=5000, help='The interval in milliseconds for the providers . Defaults to 5000')

    parser.add_argument('-v', '--log-level', choices=LOG_LEVELS, default='info', help='Logging level (debug, info, warning, error, critical)')
    parser.add_argument('-o', '--output-file', type=str, help='Path to the output log file.')

    args = parser.parse_args()

    if args.dev:
        args.idle_time = 60
        args.stress_time = 30
        args.log_level = 'debug'

    log_level = getattr(logging, args.log_level.upper())


    if args.output_file:
        logging.basicConfig(filename=args.output_file, level=log_level, format='[%(levelname)s] %(asctime)s - %(message)s')
    else:
        logging.basicConfig(level=log_level, format='[%(levelname)s] %(asctime)s - %(message)s')

    logging.debug('Calibration script started 🎉')

    main(idle_time=args.idle_time, provider_interval=args.provider_interval)