import unittest
from unittest.mock import Mock, patch
import io
import psycopg
from lib.db import with_db_retry, DB


class TestWithDbRetryDecorator(unittest.TestCase):
    """Test the @with_db_retry decorator using mocks to simulate various error conditions.
    
    These tests verify the retry logic, timeout behavior, and error classification
    without requiring actual database connections.
    """

    def setUp(self):
        class MockDB:
            def __init__(self):
                self._pool = Mock()

            def _create_pool(self):
                self._pool = Mock()

            @with_db_retry
            def failing_method(self):
                raise psycopg.OperationalError("connection refused")

            @with_db_retry
            def non_retryable_method(self):
                raise psycopg.DatabaseError("syntax error at or near")

        self.mock_db = MockDB()

    @patch('time.time')
    @patch('time.sleep')
    def test_retry_on_retryable_errors(self, mock_sleep, mock_time):
        # Mock time progression: start=0, while_loop=1, elapsed_check=2, timeout_while=350, final_msg=350
        mock_time.side_effect = [0, 1, 2, 350, 350]

        with self.assertRaises(psycopg.OperationalError):
            self.mock_db.failing_method()

        # Verify that sleep was called (indicating a retry attempt)
        self.assertTrue(mock_sleep.called)

    def test_non_retryable_errors(self):
        with self.assertRaises(psycopg.DatabaseError) as cm:
            self.mock_db.non_retryable_method()

        self.assertIn("syntax error", str(cm.exception))

    @patch('time.time')
    @patch('time.sleep')
    @patch('builtins.print')
    def test_timeout_behavior(self, mock_print, mock_sleep, mock_time):
        # Mock time: start=0, while_check=1, elapsed_check=350 (timeout)
        mock_time.side_effect = [0, 1, 350]

        with self.assertRaises(psycopg.OperationalError) as cm:
            self.mock_db.failing_method()

        # Original error is raised
        self.assertIn("connection refused", str(cm.exception))

        # But timeout message is printed
        timeout_call = None
        for call in mock_print.call_args_list:
            if "Database retry timeout" in str(call):
                timeout_call = call
                break
        self.assertIsNotNone(timeout_call)

        # Sleep should not be called since timeout occurs before sleep
        self.assertFalse(mock_sleep.called)


class TestDbIntegration(unittest.TestCase):
    """Integration tests for DB class methods using real database connections.
    
    These tests verify actual database operations against a test PostgreSQL database without mocking.
    """

    def setUp(self):
        self.db = DB()
        self.table_name = "test_integration_table"

    def test_basic_query_execution(self):
        result = self.db.query(f"CREATE TABLE {self.table_name} (id INT, name TEXT)")
        self.assertIn("CREATE TABLE", result)

    def test_fetch_one_operation(self):
        self.db.query(f"CREATE TABLE {self.table_name} (id INT, name TEXT)")
        self.db.query(f"INSERT INTO {self.table_name} VALUES (1, 'test')")

        result = self.db.fetch_one(f"SELECT id, name FROM {self.table_name} WHERE id = 1")
        self.assertEqual(result[0], 1)
        self.assertEqual(result[1], 'test')

    def test_fetch_all_operation(self):
        self.db.query(f"CREATE TABLE {self.table_name} (id INT, name TEXT)")
        self.db.query(f"INSERT INTO {self.table_name} VALUES (1, 'test1'), (2, 'test2')")

        results = self.db.fetch_all(f"SELECT id, name FROM {self.table_name} ORDER BY id")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], 1)
        self.assertEqual(results[1][0], 2)

    def test_parameter_binding(self):
        self.db.query(f"CREATE TABLE {self.table_name} (id INT, name TEXT)")

        self.db.query(f"INSERT INTO {self.table_name} VALUES (%s, %s)", (1, 'param_test'))
        result = self.db.fetch_one(f"SELECT name FROM {self.table_name} WHERE id = %s", (1,))
        self.assertEqual(result[0], 'param_test')

    def test_fetch_mode_dict(self):
        self.db.query(f"CREATE TABLE {self.table_name} (id INT, name TEXT)")
        self.db.query(f"INSERT INTO {self.table_name} VALUES (1, 'dict_test')")

        result = self.db.fetch_one(f"SELECT id, name FROM {self.table_name}", fetch_mode='dict')
        self.assertIsInstance(result, dict)
        self.assertEqual(result['id'], 1)
        self.assertEqual(result['name'], 'dict_test')

    def test_error_handling_invalid_sql(self):
        with self.assertRaises(psycopg.DatabaseError):
            self.db.query("INVALID SQL STATEMENT")

    def test_copy_from_csv_data(self):
        self.db.query(f"CREATE TABLE {self.table_name} (id INT, name TEXT, value NUMERIC)")

        csv_data = io.StringIO("1,test1,10.5\n2,test2,20.7\n")
        columns = ['id', 'name', 'value']

        self.db.copy_from(csv_data, self.table_name, columns)

        results = self.db.fetch_all(f"SELECT id, name, value FROM {self.table_name} ORDER BY id")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], 1)
        self.assertEqual(results[0][1], 'test1')
        self.assertEqual(results[1][0], 2)
        self.assertEqual(results[1][1], 'test2')


if __name__ == '__main__':
    unittest.main()
