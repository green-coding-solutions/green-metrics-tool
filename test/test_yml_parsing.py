#pylint: disable=import-error,wrong-import-position,protected-access
import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../tools")
sys.path.append(f"{current_dir}/../lib")

from runner import Runner

class TestYML(unittest.TestCase):

    def test_includes(self):
        test_dir = os.path.join(current_dir, 'data/usage_scenarios/')
        test_root_file = 'import_one_root.yml'
        runner = Runner(uri=test_dir, uri_type='folder', pid=1, filename=test_root_file)
        runner.checkout_repository() # We need to do this to setup the file paths correctly

        runner.load_yml_file()
        result_obj = {'name': 'Import Test',
                    'services': {'test-container':
                                    {'type': 'container'}},
                    'flow': [{'name': 'Stress', 'container': 'test-container'}]}

        self.assertEqual(result_obj, runner._usage_scenario)


    def test_invalid_path(self):
        test_dir = os.path.join(current_dir, 'data/usage_scenarios/')
        test_root_file = 'import_error.yml'
        runner = Runner(uri=test_dir, uri_type='folder', pid=1, filename=test_root_file)
        runner.checkout_repository() # We need to do this to setup the file paths correctly
        self.assertRaises(ImportError, runner.load_yml_file)
