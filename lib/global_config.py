import os
import yaml
from lib import utils

class GlobalConfig:

    # for unknown reasons pylint needs this argument set, although we don't use it. Only in __init__
    # pylint: disable=unused-argument
    def __new__(cls, config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../config.yml"):
        if not hasattr(cls, 'instance'):
            cls.instance = super(GlobalConfig, cls).__new__(cls)
        return cls.instance

    def __init__(self, config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../config.yml"):
        if not hasattr(self, 'config'):
            with open(config_location, encoding='utf8') as config_file:
                self.config = utils.freeze_dict(yaml.load(config_file, yaml.FullLoader))

    ## add an override function that will always set the config to a new value
    def override_config(self, config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../config.yml"):
        with open(config_location, encoding='utf8') as config_file:
            self.config = utils.freeze_dict(yaml.load(config_file, yaml.FullLoader))

if __name__ == '__main__':
    print(GlobalConfig().config['measurement'])
