#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib.db import DB

class Machine:

    def __init__(self, machine_id, description):
        if machine_id is None or not isinstance(machine_id, int):
            raise RuntimeError('You must set machine id.')
        if description is None or description == '':
            raise RuntimeError('You must set machine description.')
        self.id = machine_id
        self.description = description

    def register(self):
        DB().query("""
             INSERT INTO machines
                 ("id", "description", "available", "created_at")
             VALUES
                 (%s, %s, TRUE, 'NOW()')
             ON CONFLICT (id) DO
                 UPDATE SET description = %s -- no need to make where clause here for correct row
            """, params=(self.id,
                    self.description,
                    self.description
                )
        )
