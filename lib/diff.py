#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.db import DB
from deepdiff import DeepDiff
from psycopg.rows import dict_row as psycopg_rows_dict_row


def get_diffable_row(uuid):
    query = """SELECT
        uri,
        branch,
        invalid_run,
        commit_hash,
        phases,
        machine_id,
        filename,
        gmt_hash,
        commit_timestamp,
        machine_specs,
        usage_scenario,
        measurement_config,
        runner_arguments
        FROM runs WHERE id = %s
    """

    return DB().fetch_one(query, (uuid, ), row_factory=psycopg_rows_dict_row)

def diff_rows(row_a,row_b):
    diff_string = []
    for field in row_a:
        diff = DeepDiff(row_a[field], row_b[field],
            exclude_paths=[
                "root['job_id']",
                "root['Processes']",
                "root['CPU scheduling']",
            ],
            exclude_regex_paths=[
                r"root\[\d+\]\['end'\]",
                r"root\[\d+\]\['start'\]",
                r"root\['CPU complete dump'\]\['/sys/devices/system/cpu/cpu\d+/cpuidle/state\d+/(above|below|usage|time)']",
                r"root\['CPU complete dump'\]\['/sys/devices/system/cpu/cpufreq/policy\d+/scaling_cur_freq']"
            ]
        )
        for diff_type in diff:
            diff_string.append('\n\n')
            diff_string.append(str(field))
            diff_string.append(' -> ')
            diff_string.append(str(diff_type))
            diff_string.append('\n###########################################\n')

            if diff_type == 'dictionary_item_removed':
                for el in diff[diff_type]:
                    diff_string.append('-')
                    diff_string.append(str(el))
                    diff_string.append('\n')
            elif diff_type == 'dictionary_item_added':
                for el in diff[diff_type]:
                    diff_string.append('+')
                    diff_string.append(str(el))
                    diff_string.append('\n')
            else:
                for inner_el in diff[diff_type]:
                    diff_string.append('----------')
                    diff_string.append(str(inner_el))
                    diff_string.append('-----------------------------\n')
                    if diff[diff_type][inner_el].get('diff', False):
                        diff_string.append(str(diff[diff_type][inner_el]['diff']))
                    else:
                        diff_string.append(str(diff[diff_type][inner_el]))
                    diff_string.append('\n\n')
    return "".join(diff_string)

if __name__ == '__main__':
    a = get_diffable_row('f814b51e-e953-4984-932c-1e537dcf8cc0')
    b = get_diffable_row('709fe691-1813-4006-8bb3-781582f9dc6c')
    print(diff_rows(a,b))
