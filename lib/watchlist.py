#!/usr/bin/env python3

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import json
from lib.db import DB

class Watchlist():
    #pylint:disable=redefined-outer-name
    @classmethod
    def insert(cls, *, name, image_url, repo_url, branch, filename, usage_scenario_variables, machine_id, user_id, schedule_mode, last_marker):
        # Watchlist items never insert / use emails as they are always premium and made by admin
        # So they need no notification on success / add
        insert_query = """
                INSERT INTO
                    watchlist (name, image_url, repo_url, branch, filename, usage_scenario_variables, machine_id, last_marker, user_id, schedule_mode, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()) RETURNING id;
                """
        params = (name, image_url, repo_url, branch, filename, json.dumps(usage_scenario_variables), machine_id, last_marker, user_id, schedule_mode,)
        return DB().fetch_one(insert_query, params=params)[0]
