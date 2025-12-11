#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.db import DB
from deepdiff import DeepDiff
import json

def get_diffable_rows(user, uuids):
    query = """SELECT
        uri,
        branch,
        commit_hash,
        phases,
        machine_id,
        filename,
        gmt_hash,
        commit_timestamp,
        usage_scenario,
        usage_scenario_variables,
        containers,
        container_dependencies,
        measurement_config,
        runner_arguments,
        machine_specs -- most complex. Should come last
        FROM runs
        WHERE
            (TRUE = %s OR user_id = ANY(%s::int[]))
            AND id = ANY(%s::uuid[])
    """

    params = (user.is_super_user(), user.visible_users(), uuids)
    return DB().fetch_all(query, params, fetch_mode='dict')

def diff_rows(rows):
    if len(rows) < 2:
        raise ValueError(f"Diffing currently only supported for exaclty 2 runs. Please add at least one more run to the diff. This error might also happen if one of the runs supplied has no data yet and is still running or failed. Amount of groups supplied: {len(rows)}.")
    if len(rows) > 2:
        raise ValueError(f"Diffing currently only supported for exaclty 2 runs. Please try to reduce your amount of runs diffed to only two and drill down separately with others. Amount of groups supplied: {len(rows)}.")



    row_a = rows[0]
    row_b = rows[1]

    # expand machine_specs into root level
    row_a_machine_specs = row_a.pop('machine_specs')
    row_a.update({f"machine_specs.{k}": v for k, v in row_a_machine_specs.items()})

    row_b_machine_specs = row_b.pop('machine_specs')
    row_b.update({f"machine_specs.{k}": v for k, v in row_b_machine_specs.items()})

    unified_diff = []
    for field in row_a:
        field_a = json.dumps(row_a[field], indent=2, separators=(',', ': ')).replace('\\n', "\n") if isinstance(row_a[field], (dict, list))  else str(row_a[field])
        field_b = json.dumps(row_b[field], indent=2, separators=(',', ': ')).replace('\\n', "\n") if isinstance(row_b[field], (dict, list)) else str(row_b[field])

        # although not strictly needed we use DeepDiff as this is WAY faster than difflib suprisingly
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
    from lib.user import User
    diffable_rows = get_diffable_rows(User(1), ['6f34b31e-f35c-4601-ae0d-6fd04a951aaf', '70ed5b3f-fa90-43fe-abcc-d4bf8048786a'])
    print(diff_rows(diffable_rows))
