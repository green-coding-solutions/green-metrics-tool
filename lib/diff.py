#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import faulthandler
faulthandler.enable()  # will catch segfaults and write to stderr

from lib.db import DB
from deepdiff import DeepDiff
import json

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

    return DB().fetch_one(query, (uuid, ), fetch_mode='dict')

def diff_rows(row_a,row_b):
    unified_diff = []
    for field in row_a:
        field_a = json.dumps(row_a[field], indent=2, separators=(',', ': ')).replace('\\n', "\n") if isinstance(row_a[field], (dict, list))  else str(row_a[field])
        field_b = json.dumps(row_b[field], indent=2, separators=(',', ': ')).replace('\\n', "\n") if isinstance(row_b[field], (dict, list)) else str(row_b[field])
        diff = DeepDiff(field_a, field_b,
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
        for key, value in diff.items():
            if key == "dictionary_item_added":
                unified_diff.append(f"diff --git a/{field} b/{field}\n---\n+++\n@@ -1 +1 @@")
                for v in value:
                    unified_diff.append(f"+ {key}: {v}")
            elif key == "iterable_item_added":
                unified_diff.append(f"diff --git a/{field} b/{field}\n---\n+++\n@@ -1 +1 @@")
                for k, v in value.items():
                    unified_diff.append(f"+ {k}: {v}")
            elif key == "iterable_item_removed":
                unified_diff.append(f"diff --git a/{field} b/{field}\n---\n+++\n@@ -1 +1 @@")
                for k, v in value.items():
                    unified_diff.append(f"+ {k}: {v}")
            elif key == "dictionary_item_removed":
                unified_diff.append(f"diff --git a/{field} b/{field}\n---\n+++\n@@ -1 +1 @@")
                for v in value:
                    unified_diff.append(f"- {key}: {v}")
            elif key == "values_changed":
                for k, v in value.items():

                    if v.get('diff', False):
                        unified_diff.append(f"diff --git a/{field} b/{field}")
                        unified_diff.append(str(v['diff']))
                    else:
                        unified_diff.append(f"diff --git a/{field} b/{field}\n---\n+++\n@@ -1 +1 @@")
                        unified_diff.append(f"- {k}: {v['old_value']}")
                        unified_diff.append(f"+ {k}: {v['new_value']}")
            else:
                raise RuntimeError(f"Unknown diff mode: {key}")
        unified_diff.append("\n")

    return "\n".join(unified_diff)

if __name__ == '__main__':
    a = get_diffable_row('6f34b31e-f35c-4601-ae0d-6fd04a951aaf')
    b = get_diffable_row('70ed5b3f-fa90-43fe-abcc-d4bf8048786a')
    print(diff_rows(a,b))
