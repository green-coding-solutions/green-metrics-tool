import os, sys
import subprocess, re

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../tools")
sys.path.append(f"{current_dir}/../../lib")

from runner import Runner
from global_config import GlobalConfig

import utils
from db import DB

example_repo="https://github.com/green-coding-berlin/example-applications"
project_name = "test_" + utils.randomword(12)
downloaded_examples=False

def test_runner_reports(capsys):
    config = GlobalConfig(config_name="test-config.yml").config
  
    uri = os.path.abspath(os.path.join(current_dir, '..', 'stress-application/'))    
    subprocess.run(["docker", "compose", "-f", uri+"/compose.yml", "build"])
    
    project_id = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at") \
                VALUES \
                (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(project_name, uri))[0]

    # Run the application
    runner = Runner()
    runner.run(uri=uri, uri_type="folder", project_id=project_id)

    ## Capture Std.Out and Std.Err and make Assertions
    captured = capsys.readouterr()

    # Check for each metrics provider defined in our test-config.yml
    ## TODO: Currently turned off as the terminal coloring in the output log breaks these regexes
    ##       fix this and re-enable when the time is right

    #metric_providers_keys = config['measurement']['metric-providers'].keys()
    #for m in metric_providers_keys:
        #provider = m.split(".")[-1]
        #match = re.search(rf"Imported\s+(\d+)\s+metrics from \s*{provider}\s*", captured.out)
        #\x1b[95m 170 \x1b[0m    ## Reported in log as terminal coloring for captured output
        # Assert that a match is found for each provider
        #assert match != None
        ## Assert that number of metrics is greater than 0
        #assert (int(match.group(1)) > 0)

    ## Assert that Cleanup has run
    assert re.search("Cleanup gracefully completed", captured.out)
    ## Assert that there is no std.err output
    assert captured.err == ''