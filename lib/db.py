import psycopg2.extras
import psycopg2
import setup_functions

class DB:

    def __new__(cls):
        if not hasattr(cls, 'instance'):
             cls.instance = super(DB, cls).__new__(cls)
        return cls.instance
    def __init__(self):

        if not hasattr(self, "conn"):
            config = setup_functions.get_config()

            # Important note: We are not using cursor_factory = psycopg2.extras.RealDictCursor
            # as an argument, because this would increase the size of a single API request
            # from 50 kB to 100kB.
            # Users are required to use the mask of the API requests to read the data.
            if config['postgresql']['host'] is None: # force domain socket connection by not supplying host
                self.conn = psycopg2.connect("user=%s dbname=%s password=%s" % (config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))
            else:
                self.conn = psycopg2.connect("host=%s user=%s dbname=%s password=%s" % (config['postgresql']['host'], config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))

    def __query(self, query, params=None, return_type=None, cursor_factory=None):

        cur = self.conn.cursor(cursor_factory=cursor_factory) # None is actually the default cursor factory
        try:
            cur.execute(query, params)
            self.conn.commit()
            match return_type:
                case "one":
                    ret = cur.fetchone()
                case "all":
                    ret = cur.fetchall()
                case _:
                    ret = True

        except psycopg2.Error as e:
            self.conn.rollback()
            cur.close()
            raise e

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
            cur = self.conn.cursor()
            cur.copy_from(file, table, columns=columns, sep=sep)
            self.conn.commit()
        except psycopg2.Error as e:
            self.conn.rollback()
            cur.close()
            raise e
        cur.close()

if __name__ == "__main__":
    DB()
    DB()
    print(DB().fetch_all("SELECT * FROM projects"))
    #DB().query("SELECT * FROM projects")
    #DB().query("SELECT * FROM projects")
    #DB().query("SELECT * FROM projects")
