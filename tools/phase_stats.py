#!/usr/bin/env python3

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.db import DB
from lib.phase_stats import build_and_store_phase_stats


def derive_sci_metrics(usage_scenario):
    # Re-derives the sci_metrics list that scenario_runner.py builds live from the usage_scenario
    # yml while running (self.__sci_metrics, see _initial_parse()). It is not persisted anywhere
    # of its own, so on rebuild we recompute it from runs.usage_scenario, which stores the parsed
    # yml (including the custom_metrics section) as it was at run time.
    sci_metrics = []
    for key, custom_metric in (usage_scenario or {}).get('custom_metrics', {}).items():
        if custom_metric.get('sci', False):
            sci_metrics.append(f"custom_{key}")
    return sci_metrics


def derive_custom_metric_types(usage_scenario):
    custom_metric_types = {}
    for key, custom_metric in (usage_scenario or {}).get('custom_metrics', {}).items():
        custom_metric_types[f"custom_{key}"] = custom_metric.get('type', 'TOTAL')
    return custom_metric_types


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('run_id', help='Run ID', type=str)

    args = parser.parse_args()  # script will exit if type is not present

    query = '''
        SELECT id, measurement_config, usage_scenario
        FROM runs
        WHERE
            end_measurement IS NOT NULL AND phases IS NOT NULL
            AND id = %s

    '''
    data = DB().fetch_one(query, params=(args.run_id, ), fetch_mode='dict')

    build_and_store_phase_stats(args.run_id, data['measurement_config']['sci'], derive_sci_metrics(data['usage_scenario']), derive_custom_metric_types(data['usage_scenario']))
