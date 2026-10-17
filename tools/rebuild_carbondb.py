#!/usr/bin/env python3

import sys
import os
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

from lib.global_config import GlobalConfig
from lib.db import DB
from cron.carbondb_copy_over_and_remove_duplicates import copy_over_eco_ci, copy_over_scenario_runner, copy_over_power_hog, remove_duplicates
from cron.carbondb_compress import compress_carbondb_raw

if __name__ == '__main__':
    GlobalConfig().override_config(config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../manager-config.yml")

    print('This will remove ALL non-custom data (ScenarioRunner, Eco CI and PowerHOG) from CarbonDB RAW data and will try to rebuild CarbonDB aggregates. If you have deleted ScenarioRunner runs or Eco CI / PowerHOG data it will not be possible to reconstruct it. Continue? (y/N)')
    answer = sys.stdin.readline()
    if answer.strip().lower() == 'y':
        print('Truncating carbondb_data table ...')
        DB().query('TRUNCATE carbondb_data')

        print('Deleting non custom data from carbondb_data_raw ...')
        DB().query("DELETE FROM carbondb_data_raw WHERE source IN ('ScenarioRunner', 'Eco CI', 'Power HOG')")

        print('Copying Eco CI data over to carbondb_data_raw without any lookback date restriction...')
        copy_over_eco_ci(None)
        print('Copying ScenarioRunner data over to carbondb_data_raw without any lookback date restriction...')
        copy_over_scenario_runner(None)
        print('Copying PowerHOG data over to carbondb_data_raw without any lookback date restriction...')
        copy_over_power_hog(None)
        remove_duplicates(None)

        print('Running compress on carbondb ...')
        compress_carbondb_raw(None)

        print('Done')
