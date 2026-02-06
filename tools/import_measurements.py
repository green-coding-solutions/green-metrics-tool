#!/usr/bin/env python3

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import argparse
import importlib

from lib.global_config import GlobalConfig
from lib import metric_importer


config = GlobalConfig().config

def import_metric_provider(metric_provider):

    module_path, class_name = metric_provider.rsplit('.', 1)
    module_path = f"metric_providers.{module_path}"

    print(f"Importing {class_name} from {module_path}")

    module = importlib.import_module(module_path)

    stub_config = { 'sampling_rate' : 99, 'skip_check': True}

    return getattr(module, class_name)(**stub_config)


if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('run_id', type=str, help='Run-ID (UUID)')
    parser.add_argument('metric_provider', type=str, help='Metric Provider (ex. cpu.utilization.mach.system.provider.CpuUtilizationMachSystemProvider)')
    parser.add_argument('filename', type=str, help='Filename')


    args = parser.parse_args()

    metric_provider_obj = import_metric_provider(args.metric_provider)

    # patch the object
    metric_provider_obj._tmp_folder = '/non_existent_folder_which_should_never_be_accessed'
    metric_provider_obj._filename = args.filename

    df = metric_provider_obj.read_metrics()

    if isinstance(df, list):
        for i, dfi in enumerate(df):
            if dfi is None or dfi.shape[0] == 0:
                print(f"No metrics were able to be imported from: {args.filename}")
            metric_importer.import_measurements(dfi, metric_provider_obj._sub_metrics_name[i], args.run_id)
    else:
        if df is None or df.shape[0] == 0:
            print(f"No metrics were able to be imported from: {args.filename}")
        metric_importer.import_measurements(df, metric_provider_obj._metric_name, args.run_id)
