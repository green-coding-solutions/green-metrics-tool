import os
import re
import yaml

if __name__ == '__main__':
    import argparse

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser()

    # add an arguement --categories which takes a list of strings
    parser.add_argument(
        '--categories', type=str, nargs='+', help='The categories to disable the metric providers for')

    parser.add_argument(
        '--providers', type=str, nargs='+', help='the specific providers to turn off')

    args = parser.parse_args()

    # as seperate in case you don't want to override/ for debug purposes
    config_path = f"{current_dir}/config.yml"

    with open(config_path, 'r', encoding='utf8') as f:
        data = f.readlines()

    INSIDE_METRIC_PROVIDERS = False

    # first uncomment out all the metric providers
    for i, line in enumerate(data):
        if re.match(r'\s*#--- Architecture - Linux Only\s*', line):
            INSIDE_METRIC_PROVIDERS = True
        elif re.match(r'\s*#--- END\s*', line):
            INSIDE_METRIC_PROVIDERS = False
        elif INSIDE_METRIC_PROVIDERS and not re.match(r'\s*#--', line):
            data[i] = re.sub(r"^#(.*)", r"\1", line)

    # then comment out all the categories
    if args.categories:
        CATEGORY_FOUND = False
        for category in args.categories:
            print("turning off: " + category)
            for i, line in enumerate(data):
                line_stripped = line.strip()
                if line_stripped.startswith('#---') and category in line:
                    CATEGORY_FOUND = True
                elif line_stripped.startswith('#---'):
                    CATEGORY_FOUND = False
                if CATEGORY_FOUND and not line_stripped.startswith('#'):
                    data[i] = '# ' + line
    # write to file
    with open(config_path, "w", encoding='utf8') as f:
        f.writelines(data)

    # if there are individual files, load again, as a yaml this time, and remove them
    if args.providers:
        with open(config_path, 'r', encoding='utf8') as f:
            data = yaml.load(f, Loader=yaml.FullLoader)

        for provider_to_turn_off in args.providers:
            for arch in data['measurement']['metric-providers']:
                for provider in list(data['measurement']['metric-providers'][arch].keys()):
                    if provider_to_turn_off in provider:
                        del data['measurement']['metric-providers'][arch][provider]
                        print("turning off: " + provider)

        with open(config_path, 'w', encoding='utf8') as f:
            yaml.dump(data, f)

    print("disabled metric providers and categories")
