import unittest
from unittest.mock import Mock, patch
import psycopg
from lib.db import with_db_retry


class TestDbRetry(unittest.TestCase):

    def setUp(self):
        class MockDB:
            def __init__(self):
                self._pool = Mock()

            def _create_pool(self):
                self._pool = Mock()

            @with_db_retry
            def test_method(self):
                return "success"

            @with_db_retry
            def failing_method(self):
                raise psycopg.OperationalError("connection refused")

            @with_db_retry
            def non_retryable_method(self):
                raise psycopg.DatabaseError("syntax error at or near")

        self.mock_db = MockDB()

    def test_success_on_first_attempt(self):
        result = self.mock_db.test_method()
        self.assertEqual(result, "success")

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


if __name__ == '__main__':
    unittest.main()
