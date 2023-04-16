import sys, os
import json
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{CURRENT_DIR}/lib")

from db import DB
from global_config import GlobalConfig

from api.api_helpers import *


if __name__ == '__main__':
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()

    parser.add_argument(
        'ids', type=str, help='Ids as comma separated list')
    args = parser.parse_args()

    ids = args.ids.split(',')

    case = determine_comparison_case(ids)
    phase_stats = get_phase_stats(ids)
    phase_stats_object = get_phase_stats_object(phase_stats, case)
    phase_stats_object = add_phase_stats_statistics(phase_stats_object)

    print(json.dumps(phase_stats_object, indent=4))
