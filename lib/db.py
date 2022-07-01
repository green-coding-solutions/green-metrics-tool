import psycopg2.extras
import psycopg2
import error_helpers
import setup_functions
import sys


class DB:
    __conn = None
    def __new__(cls):
        if not hasattr(cls, 'instance'):
             cls.instance = super(DB, cls).__new__(cls)
             print("Creating new instance")
        else:
            print("Returning cached instance")
        return cls.instance
    def __init__(self):
        print("Instance is called")

        if self.__conn is None:
            config = setup_functions.get_config()

            # Important note: We are not using cursor_factory = psycopg2.extras.RealDictCursor
            # as an argument, because this would increase the size of a single API request
            # from 50 kB to 100kB.
            # Users are required to use the mask of the API requests to read the data.
            if config['postgresql']['host'] is None: # force domain socket connection by not supplying host
                    self.__conn = psycopg2.connect("user=%s dbname=%s password=%s" % (config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))
            else:
                    self.__conn = psycopg2.connect("host=%s user=%s dbname=%s password=%s" % (config['postgresql']['host'], config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))

    def __query(self, query, params=None, return_type=None, cursor_factory=None):

        cur = self.__conn.cursor(cursor_factory=cursor_factory) # None is actually the default cursor factory
        try:
            cur.execute(query, params)
            self.__conn.commit()
            match return_type:
                case "one":
                    ret = cur.fetchone()
                case "all":
                    ret = cur.fetchall()
                case _:
                    ret = True

        except psycopg2.Error as e:
            self.__conn.rollback()
            error_helpers.email_and_log_error(e)
            ret = False
        cur.close()
        return ret

    def query(self, query, params=None, cursor_factory=None):
        return self.__query(query, params=params, return_type=None, cursor_factory=cursor_factory)

    def fetch_one(self, query, params=None, cursor_factory = None):
        return self.__query(query, params=params, return_type="one", cursor_factory=cursor_factory)

    def fetch_all(self, query, params=None, cursor_factory=None):
        return self.__query(query, params=params, return_type="all", cursor_factory=cursor_factory)

    def copy_from(self, file, table, columns, sep=','):
        try:
            cur = self.__conn.cursor()
            cur.copy_from(file, table, columns=columns, sep=sep)
            self.__conn.commit()
        except psycopg2.Error as e:
            self.__conn.rollback()
            error_helpers.email_and_log_error(e)
        cur.close()

if __name__ == "__main__":
    DB()
    DB()
    print(DB().fetch_all("SELECT * FROM projects"))
    #DB().query("SELECT * FROM projects")
    #DB().query("SELECT * FROM projects")
    #DB().query("SELECT * FROM projects")
