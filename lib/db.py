import psycopg2.extras
import psycopg2
from error_helpers import log_error
from setup_functions import get_config
import sys

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

def __call(query, params, return_type=None, conn=None):
    if conn is None: conn = get_db_connection()

    cur = conn.cursor()
    try:
        cur.execute(query, params)
        conn.commit()
        match return_type:
            case "one":
                ret = cur.fetchone()
            case "all":
                ret = cur.fetchall()
            case None:
                ret = True

    # Still need to figure out what the real exception is
    except psycopg2.Error as e:
        conn.rollback()
        log_error(e)
        ret = False
    cur.close()
    return ret

def call(query, params=None, conn=None):
    return __call(query, params, None, conn)

def fetch_one(query, params=None, conn=None):
    return __call(query, params, "one", conn)

def fetch_all(query, params=None, conn=None):
    return __call(query, params, "all", conn)