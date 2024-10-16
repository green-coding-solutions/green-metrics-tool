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

We assume that your green-metrics-tool is already set up to work on your machine, as it will use your local config.yml
file to determine which metric providers can be utilized in the tests.

## First time setup

run:

`python3 setup-test-env.py`

from the test directory. This will create a copy of the `config.yml` and docker `compose.yml` files that will be used in
the test containers. Please make sure that you have compiled all the metric providers and source code in lib. You can do
this automatically by using the `install.sh` command.

You will need to re-run this setup script if new metric providers are added or the config.yml is otherwise changed in a
significant way.

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
