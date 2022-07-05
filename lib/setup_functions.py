import yaml
import os

def get_config():
    with open("{path}/../config.yml".format(path=os.path.dirname(os.path.realpath(__file__)))) as config_file:
        config = yaml.load(config_file,yaml.FullLoader)

    return config