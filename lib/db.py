#pylint: disable=consider-using-enumerate

from psycopg_pool import ConnectionPool

from lib.global_config import GlobalConfig
class DB:

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(DB, cls).__new__(cls)
        return cls.instance

    def __init__(self):

        if not hasattr(self, '_pool'):
            config = GlobalConfig().config

            # Important note: We are not using cursor_factory = psycopg2.extras.RealDictCursor
            # as an argument, because this would increase the size of a single API request
            # from 50 kB to 100kB.
            # Users are required to use the mask of the API requests to read the data.
            # force domain socket connection by not supplying host
            # pylint: disable=consider-using-f-string
            if config['postgresql']['host'] is None:
                self._pool = ConnectionPool(
                    "postgresql://%s:%s@localhost:%s/%s" % (
                        config['postgresql']['user'],
                        config['postgresql']['password'],
                        config['postgresql']['port'],
                        config['postgresql']['dbname'],
                    ),
                    min_size=1,
                    max_size=2,
                    open=True
                )
            else:
                self._pool = ConnectionPool(
                    "postgresql://%s:%s@%s:%s/%s" % (
                        config['postgresql']['user'],
                        config['postgresql']['password'],
                        config['postgresql']['host'],
                        config['postgresql']['port'],
                        config['postgresql']['dbname'],
                    ),
                    min_size=1,
                    max_size=2,
                    open=True
                )

    def __query(self, query, params=None, return_type=None, row_factory=None):
        ret = False

        with self._pool.connection() as conn:
            conn.autocommit = False # should be default, but we are explicit
            cur = conn.cursor(row_factory=row_factory) # None is actually the default cursor factory
            if isinstance(query, list) and isinstance(params, list) and len(query) == len(params):
                for i in range(len(query)):
                    # In error case the context manager will ROLLBACK the whole transaction
                    cur.execute(query[i], params[i])
            else:
                cur.execute(query, params)
            conn.commit()
            if return_type == 'one':
                ret = cur.fetchone()
            elif return_type == 'all':
                ret = cur.fetchall()
            else:
                ret = True

        return ret

    def query(self, query, params=None, row_factory=None):
        return self.__query(query, params=params, return_type=None, row_factory=row_factory)

    def fetch_one(self, query, params=None, row_factory=None):
        return self.__query(query, params=params, return_type='one', row_factory=row_factory)

    def fetch_all(self, query, params=None, row_factory=None):
        return self.__query(query, params=params, return_type='all', row_factory=row_factory)

    def copy_from(self, file, table, columns, sep=','):
        with self._pool.connection() as conn:
            conn.autocommit = False # is implicit default
            cur = conn.cursor()
            statement = f"COPY {table}({','.join(list(columns))}) FROM stdin (format csv, delimiter '{sep}')"
            with cur.copy(statement) as copy:
                copy.write(file.read())


if __name__ == '__main__':
    DB()
    DB()
    print(DB().fetch_all('SELECT * FROM runs'))
    # DB().query('SELECT * FROM runs')
    # DB().query('SELECT * FROM runs')
    # DB().query('SELECT * FROM runs')
