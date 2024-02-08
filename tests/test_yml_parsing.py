import os
import unittest

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from lib import utils
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

GlobalConfig().override_config(config_name='test-config.yml')

class TestYML(unittest.TestCase):

    def test_includes(self):
        test_root_file = 'import_one_root.yml'
        name = 'test_' + utils.randomword(12)

        runner = Tests.setup_runner(usage_scenario=test_root_file, name=name, uri_type='folder')
        runner.checkout_repository() # We need to do this to setup the file paths correctly

        runner.load_yml_file()
        result_obj = {'name': 'Import Test',
                    'services': {'test-container':
                                    {'type': 'container'}},
                    'flow': [{'name': 'Stress', 'container': 'test-container'}]}

        self.assertEqual(result_obj, runner._usage_scenario)

    def test_(self):
        test_root_file = 'import_two_root.yml'
        name = 'test_' + utils.randomword(12)

        runner = Tests.setup_runner(usage_scenario=test_root_file, name=name, uri_type='folder')
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
        test_root_file = 'import_error.yml'
        runner = Tests.setup_runner(usage_scenario=test_root_file, name=name, uri_type='folder')
        runner.checkout_repository() # We need to do this to setup the file paths correctly
        self.assertRaises(ValueError, runner.load_yml_file)
