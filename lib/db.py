#pylint: disable=consider-using-enumerate
import os
import time
import random
from functools import wraps
from psycopg_pool import ConnectionPool
import psycopg.rows
import psycopg
import pytest
from lib.global_config import GlobalConfig

def is_pytest_session():
    return "pytest" in os.environ.get('_', '')

def with_db_retry(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        config = GlobalConfig().config
        retry_timeout = config.get('postgresql', {}).get('retry_timeout', 300)
        retry_interval = 1  # Base interval for exponential backoff

        start_time = time.time()
        attempt = 0

        while time.time() - start_time < retry_timeout:
            attempt += 1
            try:
                return func(self, *args, **kwargs)
            except (psycopg.OperationalError, psycopg.DatabaseError) as e:
                # Check if this is a connection-related error that we should retry
                error_str = str(e).lower()
                retryable_errors = [
                    'connection', 'closed', 'terminated', 'timeout', 'network',
                    'server', 'unavailable', 'refused', 'reset', 'broken pipe'
                ]

                is_retryable = any(keyword in error_str for keyword in retryable_errors)

                if not is_retryable:
                    # Non-retryable error (e.g., SQL syntax error)
                    print(f"Database error (non-retryable): {e}")
                    raise

                time_elapsed = time.time() - start_time
                if time_elapsed >= retry_timeout:
                    print(f"Database retry timeout after {attempt} attempts over {time_elapsed:.1f} seconds. Last error: {e}")
                    raise

                # Exponential backoff with jitter
                backoff_time = min(retry_interval * (2 ** (attempt - 1)), 30)  # Cap at 30 seconds
                jitter = random.uniform(0.1, 0.5) * backoff_time
                sleep_time = backoff_time + jitter

                print(f"Database connection error (attempt {attempt}): {e}. Retrying in {sleep_time:.2f} seconds...")

                # Try to recreate the connection pool if it's corrupted
                try:
                    if hasattr(self, '_pool'):
                        self._pool.close()
                        del self._pool
                    self._create_pool()
                except (psycopg.OperationalError, psycopg.DatabaseError, AttributeError) as pool_error:
                    print(f"Failed to recreate connection pool: {pool_error}")

                time.sleep(sleep_time)

        # If we get here, we've exhausted all retries
        raise psycopg.OperationalError(f"Database connection failed after {attempt} attempts over {time.time() - start_time:.1f} seconds")

    return wrapper

class DB:

    def __new__(cls):
        if is_pytest_session() and GlobalConfig().config['postgresql']['host'] != 'test-green-coding-postgres-container':
            pytest.exit(f"You are accessing the live/local database ({GlobalConfig().config['postgresql']['host']}) while running pytest. This might clear the DB. Aborting for security ...", returncode=1)

        if not hasattr(cls, 'instance'):
            cls.instance = super(DB, cls).__new__(cls)
        return cls.instance

    def __init__(self):
        if not hasattr(self, '_pool'):
            self._create_pool()

    def _create_pool(self):
        config = GlobalConfig().config

        # Important note: We are not using cursor_factory = psycopg2.extras.RealDictCursor
        # as an argument, because this would increase the size of a single API request
        # from 50 kB to 100kB.
        # Users are required to use the mask of the API requests to read the data.
        # force domain socket connection by not supplying host
        # pylint: disable=consider-using-f-string

        self._pool = ConnectionPool(
            "user=%s password=%s host=%s port=%s dbname=%s sslmode=require" % (
                config['postgresql']['user'],
                config['postgresql']['password'],
                config['postgresql']['host'],
                config['postgresql']['port'],
                config['postgresql']['dbname'],
            ),
            min_size=1,
            max_size=2,
            open=True,
            # Explicitly disabled (default) to prevent measurement interference
            # from conn.execute("") calls, using @with_db_retry instead
            check=None
        )

    def shutdown(self):
        if hasattr(self, '_pool'):
            self._pool.close()
            del self._pool


    # Query list only supports SELECT queries
    # If we ever need complex queries in the future where we have a transaction that mixes SELECTs and INSERTS
    # then this class needs a refactoring. Until then we can KISS it
    def __query_multi(self, query, params=None):
        with self._pool.connection() as conn:
            conn.autocommit = False # should be default, but we are explicit
            cur = conn.cursor(row_factory=None) # None is actually the default cursor factory
            for i in range(len(query)):
                # In error case the context manager will ROLLBACK the whole transaction
                cur.execute(query[i], params[i])
            conn.commit()

    @with_db_retry
    def __query_single(self, query, params=None, return_type=None, fetch_mode=None):
        ret = False
        row_factory = psycopg.rows.dict_row if fetch_mode == 'dict' else None

        with self._pool.connection() as conn:
            conn.autocommit = False # should be default, but we are explicit
            cur = conn.cursor(row_factory=row_factory) # None is actually the default cursor factory
            cur.execute(query, params)
            conn.commit()
            if return_type == 'one':
                ret = cur.fetchone()
            elif return_type == 'all':
                ret = cur.fetchall()
            else:
                ret = cur.statusmessage

        return ret



    def query(self, query, params=None, fetch_mode=None):
        return self.__query_single(query, params=params, return_type=None, fetch_mode=fetch_mode)

    def query_multi(self, query, params=None):
        return self.__query_multi(query, params=params)

    def fetch_one(self, query, params=None, fetch_mode=None):
        return self.__query_single(query, params=params, return_type='one', fetch_mode=fetch_mode)

    def fetch_all(self, query, params=None, fetch_mode=None):
        return self.__query_single(query, params=params, return_type='all', fetch_mode=fetch_mode)

    @with_db_retry
    def import_csv(self, filename):
        raise NotImplementedError('Code still flakes on ; in data. Please rework')
        # pylint: disable=unreachable
        with self._pool.connection() as conn:
            conn.autocommit = True
            cur = conn.cursor()
            with open(filename, 'r', encoding='utf-8') as sql_file:
                sql_script = sql_file.read()
                for statement in sql_script.split(';'):
                    if statement.strip():
                        cur.execute(statement)
        conn.autocommit = False

    @with_db_retry
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
