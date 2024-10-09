import os
import yaml

class FrozenDict(dict):
    def __setattr__(self, key, value):
        raise TypeError("GlobalConfig is immutable once loaded! (__setattr__)")

    def __setitem__(self, key, value):
        raise TypeError("GlobalConfig is immutable once loaded! (__setitem__)")

    def __delitem__(self, key):
        raise TypeError("GlobalConfig is immutable once loaded! (__delitem__)")

    def update(self, *args, **kwargs):
        raise TypeError("GlobalConfig is immutable once loaded! (update)")

    def setdefault(self, *args, **kwargs):
        raise TypeError("GlobalConfig is immutable once loaded! (setdefault)")

# Function to recursively freeze nested dictionaries
def freeze_dict(d):
    if isinstance(d, dict):
        # Convert nested dicts to FrozenDict
        return FrozenDict({k: freeze_dict(v) for k, v in d.items()})
    if isinstance(d, list):
        # Convert lists to tuples (to make them immutable)
        return tuple(freeze_dict(item) for item in d)
    if not hasattr(d, '__class__') and isinstance(d, object): # hasattr __class__ separates actual defined classes from builtins like str
        raise RuntimeError(f"GlobalConfig received object of type {type(d)} in it's config initalization. This is not expected and leads to issues as it cannot be made immutable!")

    # Return the object itself if not a dict or list
    return d

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
                self.config = freeze_dict(yaml.load(config_file, yaml.FullLoader))


    ## add an override function that will always set the config to a new value
    def override_config(self, config_location=f"{os.path.dirname(os.path.realpath(__file__))}/../config.yml"):
        with open(config_location, encoding='utf8') as config_file:
            self.config = freeze_dict(yaml.load(config_file, yaml.FullLoader))


if __name__ == '__main__':
    print(GlobalConfig().config['measurement'])
