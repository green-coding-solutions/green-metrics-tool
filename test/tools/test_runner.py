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

def test_runner_reports(capsys):
    config = GlobalConfig(config_name="test-config.yml").config

    uri = current_dir + '/../example-applications/stress/'
    subprocess.run(["docker", "compose",   "-f", uri+"compose.yml", "build"])
    
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

def test_runner_with_wordpress_example_app(capsys):
    config = GlobalConfig(config_name="test-config.yml").config

    ## Download example application, insert fake project to be run
    subprocess.run(["rm", "-Rf", "/tmp/example-applications/"])
    subprocess.run(["mkdir", "/tmp/example-applications/"])
    subprocess.run(["git", "clone", example_repo, "/tmp/example-applications/"], check=True, capture_output=True, encoding='UTF-8')

    uri = '/tmp/example-applications/wordpress-official-data/'
    subprocess.run(["docker", "compose",   "-f", uri+"compose.yml", "build"])
    
    project_id = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at") \
                VALUES \
                (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(project_name, uri))[0]

    # Run the application
    runner = Runner(allow_unsafe=True)
    runner.run(uri=uri, uri_type="folder", project_id=project_id)

    ## Capture Std.Out and Std.Err and make Assertions
    captured = capsys.readouterr()

    ## TODO: Add more asserts based on std.out here

    ## Assert that Cleanup has run
    assert re.search("Cleanup gracefully completed", captured.out)

    ## Assert that there is no std.err output
    assert captured.err == ''