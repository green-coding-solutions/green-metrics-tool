## Pre-reqs
Make sure you have `pytest` and `pydantic` installed:
`pip install pytest pydantic`

We assume that your green-metrics-tool is already set up to work on your machine, as it will use your local config.yml file to determine which metric providers can be utilized in the tests.

## First time setup
run:

`./setup-test-env.sh`

from the test directory. This will create a copy of the `config.yml` and docker compose.yml` files that will be used in the test containers.

You will need to re-run this setup script if new metric providers are added or the config.yml is otherwise changed in a significant way.

## Running
To run the tests, you need to first start the test containers, then run pytest, and afterwards stop the containers. There are a few scripts to make this easy.

`./start-test-containers.sh` will start the test containers (non-detached mode)
`./stop-test-containers.sh` will stop them.
`./run-tests.sh` will do everything - start the containers, run pytest, and then stop the containers.

The recommended workflow is to start the containers with the `./start-test-containers.sh` script, then in another shell window run the pytest suite using `pytest`, and then stop the containers when your test run has finished. 

Running a subset of tests using pytest is better explained within the documentation here: https://docs.pytest.org/en/7.2.x/how-to/usage.html

You can also do everything in one command using the `./run-tests.sh` script.