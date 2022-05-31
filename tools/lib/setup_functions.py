def get_db_connection(config=None):
    if config is None: config = get_config()

    import psycopg2
    if config['postgresql']['host'] is None: # force domain socket connection
            conn = psycopg2.connect("user=%s dbname=%s password=%s" % (config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))
    else:
            conn = psycopg2.connect("host=%s user=%s dbname=%s password=%s" % (config['postgresql']['host'], config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))
    return conn

def get_config():
    import yaml
    import os
    with open("{path}/../../config.yml".format(path=os.path.dirname(os.path.realpath(__file__)))) as config_file:
        config = yaml.load(config_file,yaml.FullLoader)

    return config