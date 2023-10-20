import os
import yaml

class GlobalConfig:

    # for unknown reasons pylint needs this argument set, although we don't use it. Only in __init__
    # pylint: disable=unused-argument
    def __new__(cls, config_name='config.yml'):
        if not hasattr(cls, 'instance'):
            cls.instance = super(GlobalConfig, cls).__new__(cls)
        return cls.instance

    def __init__(self, config_name='config.yml'):
        if not hasattr(self, 'config'):
            path = os.path.dirname(os.path.realpath(__file__))
            with open(f"{path}/../{config_name}", encoding='utf8') as config_file:
                self.config = yaml.load(config_file, yaml.FullLoader)

    ## add an override function that will always set the config to a new value
    def override_config(self, config_name='config.yml'):
        path = os.path.dirname(os.path.realpath(__file__))
        with open(f"{path}/../{config_name}", encoding='utf8') as config_file:
            self.config = yaml.load(config_file, yaml.FullLoader)


if __name__ == '__main__':
    print(GlobalConfig().config['measurement'])
