import json

from api import api_helpers


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument(
        'ids', type=str, help='Ids as comma separated list')
    args = parser.parse_args()

    ids = args.ids.split(',')

    case, comparison_db_key = api_helpers.determine_comparison_case(ids)
    comparison_details = api_helpers.get_comparison_details(ids, comparison_db_key)
    phase_stats = api_helpers.get_phase_stats(ids)
    phase_stats_object = api_helpers.get_phase_stats_object(phase_stats, case, comparison_details)
    phase_stats_object = api_helpers.add_phase_stats_statistics(phase_stats_object)

    print(json.dumps(phase_stats_object, indent=4))
