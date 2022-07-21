import os, sys
import subprocess

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(f"{current_dir}/../../tools")
sys.path.append(f"{current_dir}/../../lib")

from runner import Runner
import utils
from db import DB



example_repo="https://github.com/green-coding-berlin/example-applications"
project_name = "test_" + utils.randomword(12)

def test_runner_reports():
    runner = Runner()

    subprocess.run(["rm", "-Rf", "/tmp/example-applications/"])
    subprocess.run(["mkdir", "/tmp/example-applications/"])

    subprocess.run(["git", "clone", example_repo, "/tmp/example-applications/"], check=True, capture_output=True, encoding='UTF-8')
    uri = '/tmp/example-applications/stress/'

    project_id = DB().fetch_one('INSERT INTO "projects" ("name","uri","email","last_run","created_at") \
                VALUES \
                (%s,%s,\'manual\',NULL,NOW()) RETURNING id;', params=(project_name, uri))[0]


    runner.run(uri=uri, uri_type="folder", project_id=project_id)

    # assert here that stderr does not have anything
    # assert that data in DB exists