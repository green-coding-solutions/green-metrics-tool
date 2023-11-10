import os
import unittest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import utils
from lib.global_config import GlobalConfig
from runner import Runner

GlobalConfig().override_config(config_name='test-config.yml')

class TestYML(unittest.TestCase):

    def test_includes(self):
        test_dir = os.path.join(CURRENT_DIR, 'data/usage_scenarios/')
        test_root_file = 'import_one_root.yml'
        name = 'test_' + utils.randomword(12)

        runner = Runner(name=name, uri=test_dir, uri_type='folder', filename=test_root_file)
        runner.checkout_repository() # We need to do this to setup the file paths correctly

        runner.load_yml_file()
        result_obj = {'name': 'Import Test',
                    'services': {'test-container':
                                    {'type': 'container'}},
                    'flow': [{'name': 'Stress', 'container': 'test-container'}]}

        self.assertEqual(result_obj, runner._usage_scenario)

    def test_(self):
        test_dir = os.path.join(CURRENT_DIR, 'data/usage_scenarios/')
        test_root_file = 'import_two_root.yml'
        name = 'test_' + utils.randomword(12)

        runner = Runner(name=name, uri=test_dir, uri_type='folder', filename=test_root_file)
        runner.checkout_repository() # We need to do this to setup the file paths correctly

        runner.load_yml_file()
        result_obj = {'name': 'my sample flow',
                      'author': 'Arne Tarara',
                      'description': 'test',
                      'services': {'my-database':
                                   {'some-key': 'something',
                                    'setup-commands':
                                    ['cp /tmp/repo/test_1MB.jpg /usr/local/apache2/htdocs/test_1MB.jpg']}}}

        print(f"actual: {runner._usage_scenario}")
        print(f"expect: {result_obj}")
        self.assertEqual(result_obj, runner._usage_scenario)


    def test_invalid_path(self):
        name = 'test_' + utils.randomword(12)
        test_dir = os.path.join(CURRENT_DIR, 'data/usage_scenarios/')
        test_root_file = 'import_error.yml'
        runner = Runner(name=name, uri=test_dir, uri_type='folder', filename=test_root_file)
        runner.checkout_repository() # We need to do this to setup the file paths correctly
        self.assertRaises(ValueError, runner.load_yml_file)
