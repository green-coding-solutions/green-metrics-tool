def get_db_connection(config=None):
    if config is None: config = get_config()

    import psycopg2

    # Important note: We are not using cursor_factory = psycopg2.extras.RealDictCursor
    # as an argument, because this would increase the size of a single API request
    # from 50 kB to 100kB.
    # Users are required to use the mask of the API requests to read the data.
    if config['postgresql']['host'] is None: # force domain socket connection by not supplying host
            conn = psycopg2.connect("user=%s dbname=%s password=%s" % (config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))
    else:
            conn = psycopg2.connect("host=%s user=%s dbname=%s password=%s" % (config['postgresql']['host'], config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))
    return conn

def get_config():
    import yaml
    import os
    with open("{path}/../config.yml".format(path=os.path.dirname(os.path.realpath(__file__)))) as config_file:
        config = yaml.load(config_file,yaml.FullLoader)

    return config