import io
import os
import subprocess
import re
import pytest
import shutil

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

from contextlib import redirect_stdout, redirect_stderr

from lib.db import DB
from lib import utils
from lib.global_config import GlobalConfig
from tests import test_functions as Tests

run_stderr = None
run_stdout = None

RUN_NAME = 'test_' + utils.randomword(12)

# Runs once per file before any test(
#pylint: disable=expression-not-assigned
def setup_module():
    parallel_id = utils.randomword(12)
    test_case_path=os.path.join(CURRENT_DIR, 'stress-application/')
    tmp_dir_path=os.path.join(CURRENT_DIR, 'tmp', parallel_id)
    shutil.copytree(test_case_path, tmp_dir_path)

    out = io.StringIO()
    err = io.StringIO()
    GlobalConfig(config_name='test-config.yml').config
    with redirect_stdout(out), redirect_stderr(err):
        uri = os.path.abspath(tmp_dir_path)
        subprocess.run(['docker', 'compose', '-f', uri+'/compose.yml', 'build'], check=True)

        # Run the application
        runner = Tests.setup_runner(name=RUN_NAME, uri=uri, uri_type='folder', dev_no_metrics=False, skip_system_checks=False, create_tmp_directory=False, parallel_id=parallel_id)
        runner.run()

    #pylint: disable=global-statement
    global run_stderr, run_stdout
    run_stderr = err.getvalue()
    run_stdout = out.getvalue()

@pytest.mark.xdist_group(name="systems_checks")
def test_no_errors():
    # Assert that there is no std.err output
    assert run_stderr == ''

@pytest.mark.xdist_group(name="systems_checks")
def test_cleanup_success():
    # Assert that Cleanup has run
    assert re.search(
        'MEASUREMENT SUCCESSFULLY COMPLETED', run_stdout)

@pytest.mark.xdist_group(name="systems_checks")
def test_db_rows_are_written_and_presented():
    # for every metric provider, check that there were rows written in the DB with info for that provider
    # also check (in the same test, to save on a DB call) that the output to STD.OUT
    # "Imported XXX metrics from {metric_provider}" displays the same count as in the DB

    run_id = utils.get_run_data(RUN_NAME)['id']
    assert(run_id is not None and run_id != '')
    query = """
            SELECT
                metric, COUNT(*) as count
            FROM
                measurements
            WHERE run_id = %s
            GROUP BY
                metric
            """
    data = DB().fetch_all(query, (run_id,))
    assert(data is not None and data != [])

    config = GlobalConfig(config_name='test-config.yml').config
    metric_providers = utils.get_metric_providers_names(config)

    # The network connection proxy provider writes to a different DB so we need to remove it here
    if 'NetworkConnectionsProxyContainerProvider' in metric_providers:
        metric_providers.remove('NetworkConnectionsProxyContainerProvider')

    if 'PowermetricsProvider' in metric_providers:
        # The problem here is that the powermetrics provider splits up the output of powermetrics and acts like
        # there are loads of providers. This makes a lot easier in showing and processing the data but is
        # not std behavior. That is also why we need to patch the imported check down below.
        pm_additional_list = [
            'cpu_time_powermetrics_vm',
            'disk_io_bytesread_powermetrics_vm',
            'disk_io_byteswritten_powermetrics_vm',
            'energy_impact_powermetrics_vm',
            'cores_energy_powermetrics_component',
            'cpu_energy_powermetrics_component',
            'gpu_energy_powermetrics_component',
            'ane_energy_powermetrics_component',
        ]

        metric_providers.extend([utils.get_pascal_case(i) + 'Provider' for i in pm_additional_list])

    do_check = True

    for d in data:
        d_provider = utils.get_pascal_case(d[0]) + 'Provider'
        d_count = d[1]
        ## Assert the provider in DB matches one of the metric providers in config
        assert d_provider in metric_providers

        ## Assert the number of rows for that provider is at least 1
        assert d_count > 0

        if do_check:
            if 'PowermetricsProvider' in metric_providers:
                ## Assert the information printed to std.out matches what's in the db
                match = re.search(r"Imported \S* (\d+) \S* metrics from  PowermetricsProvider", run_stdout, re.MULTILINE)
                assert match is not None
                do_check = False
            else:
                ## Assert the information printed to std.out matches what's in the db
                match = re.search(rf"Imported \S* (\d+) \S* metrics from\s*{d_provider}", run_stdout)
                assert match is not None
                assert int(match.group(1)) == d_count

            ## Assert that all the providers in the config are represented
            metric_providers.remove(d_provider)

    if not 'PowermetricsProvider' in metric_providers:
        assert len(metric_providers) == 0
