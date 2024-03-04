# Tests

## Pre-reqs

Make sure you have venv activated:

```bash
source ../venv/bin/activate
```

Make sure you have the required dev dependencies installed:

```bash
python3 -m pip install -r ../requirements-dev.txt
```

We assume that your green-metrics-tool is already set up to work on your machine, as it will use your local config.yml
file to determine which metric providers can be utilized in the tests.

## First time setup

run:

`python3 setup-test-env.py`

from the test directory. This will create a copy of the docker `compose.yml` file that will be used in
the test containers. Please make sure that you have compiled all the metric providers and source code in lib. You can do
this automatically by using the `install_linux.sh` or `install_mac.sh` command.

## Running

To run the tests, you need to first start the test containers, then run pytest, and afterwards stop the containers.
There are a few scripts to make this easy.

`./start-test-containers.sh` will start the test containers (non-detached mode)
    you can run this with -d flag to start the containers in detached mode:
    `./start-test-containers.sh -d`
`./stop-test-containers.sh` will stop them.
`./run-tests.sh` will do everything - start the containers, run pytest, and then stop the containers.

The recommended workflow is to start the containers with the `./start-test-containers.sh` script, then in another shell
window run the pytest suite using:

`pytest -n auto -m "not serial" --dist loadgroup && pytest -m "serial"`, and then stop the containers when your test run has finished.

Running a subset of tests using pytest is better explained within the documentation here:
 https://docs.pytest.org/en/7.2.x/how-to/usage.html

You can also do everything in one command using the `./run-tests.sh` script.


## Parallelization
We now  support running our test suite with parallelization using xdist. When writing tests it is important to note that not all tests can be parallelized, and the ones that cannot need to be marked accordingly. For parallelization, we use functions in test_functions.py to setup the environment with unique container names, as well as setting up the runner with setup_runner so that its tmp folders are also unique. If you bypass using the setup_runner, you will need need to still use the `parallelize_runner_folders` function to make sure its internal directories are correct.

Any test that cannot be parrallelized should be marked with:
`@pytest.mark.serial`

This includes any test that runs the runner through a subprocess, or otherwise creates a Runner class withhout using either test_functions.setup_runner or test_functions.parallelize_runner_folders

- tests that do not skip_system_checks can be parallelized, but only if they are marked with
`@pytest.mark.xdist_group(name="systems_checks")`

This will make all tests that use group name run sequentially on the same thread (but parallel to the rest of the suite). This is needed because we have a system check which makes sure the metric providers are not already running during setup.