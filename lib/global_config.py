import yaml
import os

class GlobalConfig:

    def __new__(cls):
        if not hasattr(cls, 'instance'):
             cls.instance = super(GlobalConfig, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        if not hasattr(self, "config"):
            with open("{path}/../config.yml".format(path=os.path.dirname(os.path.realpath(__file__)))) as config_file:
                self.config = yaml.load(config_file,yaml.FullLoader)

if __name__ == "__main__":
    print(GlobalConfig().config['measurement'])

    #DB().query("SELECT * FROM projects")
    #DB().query("SELECT * FROM projects")
    #DB().query("SELECT * FROM projects")
