import psycopg2.extras
import psycopg2
from global_config import GlobalConfig

class DB:

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(DB, cls).__new__(cls)
        return cls.instance

    def __init__(self):

        if not hasattr(self, '_conn'):
            config = GlobalConfig().config

            # Important note: We are not using cursor_factory = psycopg2.extras.RealDictCursor
            # as an argument, because this would increase the size of a single API request
            # from 50 kB to 100kB.
            # Users are required to use the mask of the API requests to read the data.
            # force domain socket connection by not supplying host
            # pylint: disable=consider-using-f-string
            if config['postgresql']['host'] is None:
                self._conn = psycopg2.connect("user=%s dbname=%s password=%s" % (
                    config['postgresql']['user'],
                    config['postgresql']['dbname'],
                    config['postgresql']['password']))
            else:
                self._conn = psycopg2.connect("host=%s user=%s dbname=%s password=%s" % (
                    config['postgresql']['host'],
                    config['postgresql']['user'],
                    config['postgresql']['dbname'],
                    config['postgresql']['password']))

    def __query(self, query, params=None, return_type=None, cursor_factory=None):

        # None is actually the default cursor factory
        cur = self._conn.cursor(cursor_factory=cursor_factory)
        try:
            cur.execute(query, params)
            self._conn.commit()
            if return_type == 'one':
                ret = cur.fetchone()
            elif return_type == 'all':
                ret = cur.fetchall()
            else:
                ret = True

        except psycopg2.Error as exception:
            self._conn.rollback()
            cur.close()
            raise exception

        cur.close()
        return ret

    def query(self, query, params=None, cursor_factory=None):
        return self.__query(query, params=params, return_type=None, cursor_factory=cursor_factory)

    def fetch_one(self, query, params=None, cursor_factory=None):
        return self.__query(query, params=params, return_type='one', cursor_factory=cursor_factory)

    def fetch_all(self, query, params=None, cursor_factory=None):
        return self.__query(query, params=params, return_type='all', cursor_factory=cursor_factory)

    def copy_from(self, file, table, columns, sep=','):
        try:
            cur = self._conn.cursor()
            cur.copy_from(file, table, columns=columns, sep=sep)
            self._conn.commit()
        except psycopg2.Error as exception:
            self._conn.rollback()
            cur.close()
            raise exception
        cur.close()


if __name__ == '__main__':
    DB()
    DB()
    print(DB().fetch_all('SELECT * FROM projects'))
    # DB().query('SELECT * FROM projects')
    # DB().query('SELECT * FROM projects')
    # DB().query('SELECT * FROM projects')
