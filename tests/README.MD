# Tests

## Pre-reqs

Make sure you have venv activated:

```bash
source ../venv/bin/activate
```

Make sure you have the required dev dependencies installed:

```bash
python3 -m pip install -r ../requirements-dev.txt
playwright install --with-deps firefox
```

playwrite might fail with `BEWARE: your OS is not officially supported by Playwright; installing dependencies for ubuntu20.04-x64 as a fallback.
` under non Ubuntu distros like Fedora as some libs are not installed. In this case remove the `-with-deps` and ignore the following warning as we only use firefox which should work.

We assume that your green-metrics-tool is already set up to work on your machine.

Tests will always run for *ScenarioRunner* and *Eco CI* even if you have this deactivated in your GMT installation.

## First time setup

run:

`python3 setup-test-env.py`

from the test directory. This will create a copy of the `config.yml`, `test-config.yml` and docker `compose.yml` files that will be used in
the test containers. Please make sure that you have compiled all the metric providers and source code in lib. You can do
this automatically by using the `install-linux.sh`/`install-mac.sh` command.

If you have an enterprise / premium license please append `--ee` to the `python3 setup-test-env.py` call.

You will need to re-run this setup script if you updated GMT.

## Running

To run the tests, you need to first start the test containers, then run pytest, and afterwards stop the containers.
There are a few scripts to make this easy.

`./start-test-containers.sh` will start the test containers (non-detached mode)
    you can run this with -d flag to start the containers in detached mode:
    `./start-test-containers.sh -d`
`./stop-test-containers.sh` will stop them.
`./run-tests.sh` will do everything - start the containers, run pytest, and then stop the containers.

The recommended workflow is to start the containers with the `./start-test-containers.sh` script, then in another shell
window run the pytest suite using `pytest`, and then stop the containers when your test run has finished.

Running a subset of tests using pytest is better explained within the documentation here:
 https://docs.pytest.org/en/7.2.x/how-to/usage.html

You can also do everything in one command using the `./run-tests.sh` script.
