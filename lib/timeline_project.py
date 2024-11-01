#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.db import DB

class TimelineProject():
    #pylint:disable=redefined-outer-name
    @classmethod
    def insert(cls, *, name, url, branch, filename, machine_id, user_id, schedule_mode, last_marker):
        # Timeline projects never insert / use emails as they are always premium and made by admin
        # So they need no notification on success / add
        insert_query = """
                INSERT INTO
                    timeline_projects (name, url, branch, filename, machine_id, last_marker, user_id, schedule_mode, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, NOW()) RETURNING id;
                """
        params = (name, url, branch, filename, machine_id, last_marker, user_id, schedule_mode,)
        return DB().fetch_one(insert_query, params=params)[0]
