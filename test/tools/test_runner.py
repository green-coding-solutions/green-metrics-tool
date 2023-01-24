#pylint: disable=fixme,import-error,wrong-import-position
import os
import sys
import subprocess
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../tools")
sys.path.append(f"{current_dir}/../../lib")

from db import DB
import utils
from runner import Runner

PROJECT_NAME = 'test_' + utils.randomword(12)

def test_runner_reports(capsys):

    uri = os.path.abspath(os.path.join(
        current_dir, '..', 'stress-application/'))
    subprocess.run(['docker', 'compose', '-f', uri+'/compose.yml', 'build'], check=True)

    project_id = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at") \
                VALUES \
                (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(PROJECT_NAME, uri))[0]

    # Run the application
    runner = Runner()
    runner.run(uri=uri, uri_type='folder', project_id=project_id)

    # Capture Std.Out and Std.Err and make Assertions
    captured = capsys.readouterr()

    # Check for each metrics provider defined in our test-config.yml
    # TODO: Currently turned off as the terminal coloring in the output log breaks these regexes
    # fix this and re-enable when the time is right

    # metric_providers_keys = config['measurement']['metric-providers'].keys()
    # for m in metric_providers_keys:
    # provider = m.split('.')[-1]
    # match = re.search(rf"Imported\s+(\d+)\s+metrics from \s*{provider}\s*", captured.out)
    # \x1b[95m 170 \x1b[0m    ## Reported in log as terminal coloring for captured output
    # Assert that a match is found for each provider
    # assert match != None
    # Assert that number of metrics is greater than 0
    # assert (int(match.group(1)) > 0)

    # Assert that Cleanup has run
    assert re.search(
        '>>>> MEASUREMENT SUCCESSFULLY COMPLETED <<<<', captured.out)
    # Assert that there is no std.err output
    assert captured.err == ''
