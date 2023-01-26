#pylint: disable=fixme,import-error,wrong-import-position, global-statement, unused-argument, invalid-name
# unused-argument because its not happy with 'module', which is unfortunately necessary for pytest
# also disabled invalid-name because its not happy with single word for d in data , for example

import io
import os
import sys
import subprocess
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../tools")
sys.path.append(f"{current_dir}/../../lib")

from contextlib import redirect_stdout, redirect_stderr
from db import DB
import utils
from runner import Runner
from global_config import GlobalConfig

PROJECT_NAME = 'test_' + utils.randomword(12)
config = GlobalConfig(config_name='test-config.yml').config
metric_providers_keys = config['measurement']['metric-providers'].keys()
RUN_STD_ERR = ''
RUN_STD_OUT = ''


# Runs once per file before any test
# This will run the stress-application e2e through the GMT CLI
def setup_module(module):
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        uri = os.path.abspath(os.path.join(
            current_dir, '..', 'stress-application/'))
        subprocess.run(['docker', 'compose', '-f', uri+'/compose.yml', 'build'], check=True)

        project_id = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at") \
                    VALUES \
                    (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(PROJECT_NAME, uri))[0]

        # Run the application
        runner = Runner()
        runner.run(uri=uri, uri_type='folder', project_id=project_id)

    global RUN_STD_ERR, RUN_STD_OUT
    RUN_STD_ERR = err.getvalue()
    RUN_STD_OUT = out.getvalue()

def test_no_errors():
    # Assert that there is no std.err output
    assert RUN_STD_ERR == ''

def test_cleanup_success():
    # Assert that Cleanup has run
    assert re.search(
        '>>>> MEASUREMENT SUCCESSFULLY COMPLETED <<<<<<', RUN_STD_OUT)

def test_db_rows_are_written_and_presented():
    # for every metric provider, check that there were rows written in the DB with info for that provider
    # also check (in the same test, to save on a DB call) that the output to STD.OUT
    # "Imported XXX metrics from {metric_provider}" displays the same count as in the DB

    project_id = utils.get_pid(PROJECT_NAME)
    assert(project_id is not None or project_id != '')
    query = """
            SELECT
                metric, COUNT(*) as count
            FROM
                stats
            WHERE project_id = %s
            GROUP BY
                metric
            """
    data = DB().fetch_all(query, (project_id,))
    assert(data is not None or data != [])

    metric_providers = [(m.split('.')[-1]) for m in metric_providers_keys]

    for d in data:
        d_provider = utils.get_pascal_case(d[0]) + 'Provider'
        d_count = d[1]
        ## Assert the provider in DB matches one of the metric providers in config
        assert d_provider in metric_providers

        ## Assert the number of rows for that provider is at least 1
        assert d_count > 0

        ## Assert the information printed to std.out matches what's in the db
        match = re.search(rf"Imported \S* (\d+) \S* metrics from\s*{d_provider}", RUN_STD_OUT)
        assert match is not None
        assert int(match.group(1)) == d_count

        ## Assert that all the providers in the config are represented
        metric_providers.remove(d_provider)
    assert len(metric_providers) == 0
    
