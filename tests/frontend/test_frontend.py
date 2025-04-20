import os
import pytest
import time
import requests

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')

from lib.global_config import GlobalConfig
from lib.user import User

from tests import test_functions as Tests
from playwright.sync_api import sync_playwright

from api.object_specifications import CI_Measurement


page = None
context = None
playwright = None
browser = None

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

## Reset DB only once after module
#pylint: disable=unused-argument
@pytest.fixture(autouse=True, scope='module')
def setup_and_cleanup_module():
    # before

    global playwright #pylint: disable=global-statement
    # start only one browser for whole file
    playwright = sync_playwright().start()

    Tests.import_demo_data()
    yield

    # after
    playwright.stop()

    Tests.reset_db()

# will run after every test.
# We must close the browser to clear localStorage
@pytest.fixture(autouse=True)
def setup_and_cleanup_test():
    global page #pylint: disable=global-statement
    global context #pylint: disable=global-statement
    global browser #pylint: disable=global-statement

    browser = playwright.firefox.launch()
    context = browser.new_context(viewport={"width": 1920, "height": 5600})
    page = context.new_page()
    page.set_default_timeout(3_000)
    yield
    page.close()
    browser.close()


def test_home():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    value = page.locator("div.ui.cards.link > div.ui.card:nth-child(1) a.header").text_content()

    assert value== 'ScenarioRunner'

    value = page.locator("#scenario-runner-count").text_content()
    assert value== '5'

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    value = page.locator("div.ui.cards.link > div.ui.card:nth-child(2) a.header").text_content()

    assert value== 'Eco CI'


def test_runs():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/runs.html')
    page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()

    value = page.locator("#runs-and-repos-table > tbody tr:nth-child(2) > td:nth-child(1) > a").text_content()

    assert value== 'Stress Test #2'


def test_eco_ci_demo_data():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.locator("#menu").get_by_role("link", name="Eco CI", exact=True).click()

    page.wait_for_load_state("load") # ALL JS should be done

    page.locator("#ci-repositories-table > tbody > tr:nth-child(1) > td > div > div.title").click()
    page.locator('#DataTables_Table_0 > tbody > tr  > td:first-child > a').click()

    page.wait_for_load_state("load") # ALL JS should be done

    page.locator("input[name=range_start]").fill('2024-09-11')
    page.locator("input[name=range_end]").fill('2024-10-11')
    page.get_by_role("button", name="Refresh").click()

    time.sleep(2) # wait for new data to render

    energy_avg_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(2)").text_content()
    assert energy_avg_all_steps.strip() == '28.60 J (± 3.30%)'

    time_avg_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(3)").text_content()
    assert time_avg_all_steps.strip() == '12.80 s (± 3.49%)'

    cpu_avg_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(4)").text_content()
    assert cpu_avg_all_steps.strip() == '44.73% (± 10.65%%)'

    grid_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(5)").text_content()
    assert grid_all_steps.strip() == '494.20 gCO2/kWh (± 5.47%)'

    carbon_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(6)").text_content()
    assert carbon_all_steps.strip() == '0.016 gCO2e (± 5.71%)'

    count_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(7)").text_content()
    assert count_all_steps.strip() == '5'



    energy_avg_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(2)").text_content()
    assert energy_avg_single.strip() == '24.14 J (± 1.88%)'

    time_avg_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(3)").text_content()
    assert time_avg_single.strip() == '10.00 s (± 0.00%)'

    cpu_avg_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(4)").text_content()
    assert cpu_avg_single.strip() == '49.60% (± 5.06%%)'

    grid_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(5)").text_content()
    assert grid_single.strip() == '494.20 gCO2/kWh (± 5.47%)'

    carbon_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(6)").text_content()
    assert carbon_single.strip() == '0.0134 gCO2e (± 5.27%)'

    count_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(7)").text_content()
    assert count_single.strip() == '5'


def test_eco_ci_adding_data():

    Tests.reset_db()

    try:

        for index in range(1,4):
            measurement = CI_Measurement(energy_uj=(13_000_000*index),
                        repo='testRepo',
                        branch='testBranch',
                        cpu='testCPU',
                        cpu_util_avg=50,
                        commit_hash='1234asdf',
                        workflow='testWorkflow',
                        run_id='testRunID',
                        source='testSource',
                        label='testLabel',
                        duration_us=35323,
                        workflow_name='testWorkflowName',
                        lat="18.2972",
                        lon="77.2793",
                        city="Nine Mile",
                        carbon_intensity_g=100,
                        carbon_ug=323456
            )
            response = requests.post(f"{API_URL}/v2/ci/measurement/add", json=measurement.model_dump(), timeout=15)
            assert response.status_code == 204, Tests.assertion_info('success', response.text)


        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        page.locator("#menu").get_by_role("link", name="Eco CI", exact=True).click()

        page.locator("#ci-repositories-table > tbody > tr:nth-child(1) > td > div > div.title").click()
        page.locator('#DataTables_Table_0 > tbody > tr  > td:first-child > a').click()

        page.wait_for_load_state("load") # ALL JS should be done

        energy_avg_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(2)").text_content()
        assert energy_avg_all_steps.strip() == '78.00 J (± 0.00%)'

        carbon_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(6)").text_content()
        assert carbon_all_steps.strip() == '0.9704 gCO2e (± 0.00%)'

        carbon_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(3)").text_content()
        assert carbon_all_steps.strip() == '0.11 s (± 0.00%)'


    finally: # reset state to expectation of this file
        Tests.reset_db()
        Tests.import_demo_data()


def test_stats():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')

    page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()

    with context.expect_page() as new_page_info:
        page.get_by_role("link", name="Stress Test #1").click()

    # Get the new page (tab)
    new_page = new_page_info.value
    new_page.set_default_timeout(3_000)

    # open details
    new_page.locator('a.step[data-tab="[RUNTIME]"]').click()
    new_page.locator('#runtime-steps phase-metrics .ui.accordion .title > a').first.click()

    energy_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.four.cards.stackable > div.ui.card.machine-energy > div > div.description > div.ui.fluid.mini.statistic > div > span").text_content()
    phase_duration = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.four.cards.stackable > div.ui.card.phase-duration > div > div.description > div.ui.fluid.mini.statistic > div > span").text_content()


    assert energy_value.strip() == '0.02'
    assert phase_duration.strip() == '5.20'

    # fetch time series
    new_page.locator('button#fetch-time-series').click()

    # expand charts
    new_page.locator('div#chart-container .statistics-chart-card button.toggle-width')
    for el in new_page.locator('div#chart-container .statistics-chart-card button.toggle-width').all():
        el.click()

    chart_label = new_page.locator("#chart-container > div:nth-child(3) > div > div.ui.left.floated.chart-title").text_content()
    assert chart_label.strip() == 'CPU % via procfs'


    first_metric = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(1)").text_content()
    assert first_metric.strip() == 'Phase Duration'

    first_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(6)").text_content()
    assert first_value.strip() == '5.20'

    first_unit = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(7)").text_content()
    assert first_unit.strip() == 's'

    first_sr = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(10)").text_content().replace(" ","")
    assert first_sr.strip() == '-/\n-/\n-ms'

    machine_power_metric = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(10) > td:nth-child(1)").text_content()
    assert machine_power_metric.strip() == 'Machine Power'

    machine_power_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(10) > td:nth-child(6)").text_content()
    assert machine_power_value.strip() == '14.62'

    machine_power_unit = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(10) > td:nth-child(7)").text_content()
    assert machine_power_unit.strip() == 'W'

    machine_power_sr = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(10) > td:nth-child(10)").text_content().replace(" ","")
    assert machine_power_sr.strip() == '99/\n100/\n101ms'

    network_io_metric = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(7) > td:nth-child(1)").text_content()
    assert network_io_metric.strip() == 'Network I/O'

    network_io_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(7) > td:nth-child(6)").text_content()
    assert network_io_value.strip() == '0.07'

    network_io_unit = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(7) > td:nth-child(7)").text_content()
    assert network_io_unit.strip() == 'MB/s'

    network_traffic_metric = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(1)").text_content()
    assert network_traffic_metric.strip() == 'Network Traffic'

    network_traffic_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(6)").text_content()
    assert network_traffic_value.strip() == '0.37'

    network_traffic_unit = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(7)").text_content()
    assert network_traffic_unit.strip() == 'MB'


    # click on baseline
    new_page.locator('a.step[data-tab="[BASELINE]"]').click()
    new_page.locator('div[data-tab="[BASELINE]"] .ui.accordion .title > a').click()

    first_metric = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(1)").text_content()
    assert first_metric.strip() == 'Embodied Carbon'

    first_value = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(6)").text_content()
    assert first_value.strip() == '0.01'

    first_unit = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(7)").text_content()
    assert first_unit.strip() == 'g'

    new_page.close()


def test_repositories_and_compare():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()
    page.get_by_role("button", name="Switch to repository view").click()

    page.locator('.ui.accordion div.title').click()
    page.locator('#DataTables_Table_0').wait_for(timeout=3_000) # wait for accordion to fetch XHR and open

    elements = page.query_selector_all("input[type=checkbox]")
    for element in elements:
        element.click()

    page.locator("#DataTables_Table_0 tr:last-child input[type=checkbox]").click() # uncheck last box with different scenario

    with context.expect_page() as new_page_info:
        page.locator('#compare-button').click()

    new_page = new_page_info.value
    new_page.set_default_timeout(3_000)

    comparison_type = new_page.locator('#run-data-top > tbody:nth-child(1) > tr > td:nth-child(2)').text_content()
    assert comparison_type == 'Repeated Run'

    runs_compared = new_page.locator('#run-data-top > tbody:nth-child(2) > tr > td:nth-child(2)').text_content()
    assert runs_compared == '4'

    # open details
    new_page.locator('a.step[data-tab="[RUNTIME]"]').click()
    new_page.locator('#runtime-steps phase-metrics .ui.accordion .title > a').first.click()

    first_metric = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(3) > td:nth-child(1)").text_content()
    assert first_metric.strip() == 'CPU Power (Package)'

    first_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(3) > td:nth-child(6)").text_content()
    assert first_value.strip() == '8.56'

    first_unit = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(3) > td:nth-child(7)").text_content()
    assert first_unit.strip() == 'W'

    first_stddev = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(3) > td:nth-child(8)").text_content()
    assert first_stddev.strip() == '± 2.62%'


    # click on baseline
    new_page.locator('a.step[data-tab="[BASELINE]"]').click()
    new_page.locator('div[data-tab="[BASELINE]"] .ui.accordion a').click()

    first_metric = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(1)").text_content()
    assert first_metric.strip() == 'CPU Energy (Package)'

    first_value = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(6)").text_content()
    assert first_value.strip() == '0.00'

    first_unit = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(7)").text_content()
    assert first_unit.strip() == 'Wh'

    first_stddev = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(8)").text_content()
    assert first_stddev.strip() == '± 15.63%'

    new_page.close()

def test_expert_compare_mode():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.locator("#menu").get_by_role("link", name="Settings", exact=True).click()
    page.wait_for_load_state("load")  # wait JS
    assert page.locator("#expert-compare-mode").text_content() == 'Expert compare mode is off'

    page.locator('#toggle-expert-compare-mode').click()

    page.wait_for_load_state("load") # wait JS
    assert page.locator("#expert-compare-mode").text_content() == 'Expert compare mode is on'

    page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()

    page.locator('#DataTables_Table_0').wait_for(timeout=3_000) # wait for accordion to fetch XHR and open

    elements = page.query_selector_all("input[type=checkbox]")
    for element in elements:
        element.click()

    with context.expect_page() as new_page_info:
        page.locator('#compare-button').click()

    new_page = new_page_info.value
    new_page.set_default_timeout(3_000)

    assert new_page.locator("#run-data-top > tbody:first-child > tr:first-child > td:nth-child(2)").text_content() == 'Usage Scenario'

    new_page.close()


    page.locator('#unselect-button').click()
    elements = page.query_selector_all("input[type=checkbox]")
    for element in elements:
        element.click()
    page.locator('#compare-force-mode').select_option("Machines")

    with context.expect_page() as new_page_info:
        page.locator('#compare-button').click()

    new_page = new_page_info.value
    new_page.set_default_timeout(3_000)

    assert new_page.locator("#run-data-top > tbody:first-child > tr > td:nth-child(2)").text_content() == 'Machine'

    assert new_page.locator("#run-data-top > tbody:nth-child(2) > tr > td:first-child").text_content() == 'Number of runs compared'

    assert new_page.locator("#run-data-top > tbody:nth-child(2) > tr > td:nth-child(2)").text_content() == '5'

    assert new_page.locator("#run-data-top > tbody:nth-child(3) > tr > td:nth-child(1)").text_content() == 'Machine'

    assert new_page.locator("#run-data-top > tbody:nth-child(3) > tr > td:nth-child(2)").text_content() == 'Local machine'


    new_page.close()



def test_watchlist():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.locator("#menu").get_by_role("link", name="Watchlist", exact=True).click()
    with context.expect_page() as new_page_info:
        page.get_by_role("link", name="Show Timeline").click()

    new_page = new_page_info.value
    new_page.set_default_timeout(3_000)

    # test before refresh - data missing - Beware that if demo data is updated with new date this might break!
    new_page.wait_for_load_state("load") # ALL JS should be done
    new_page.locator('.ui.active.dimmer') # will be removed after

    new_page.locator("a.item[data-tab=two]").click()
    new_page.locator("input[name=start_date]").fill('01.01.2024')
    new_page.get_by_role("button", name="Refresh Charts & Badges").click()

    # test after refresh
    chart_label = new_page.locator('#chart-container > div:nth-child(2) > div > div.ui.left.floated.chart-title').text_content()
    assert chart_label.strip() == 'Network Transmission via Formula - [FORMULA]'

    assert 0 == new_page.locator('.ui.active.dimmer').count() # must be removed now

    new_page.close()


def test_status():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.locator("#menu").get_by_role("link", name="Cluster Status", exact=True).click()

    machine_name = page.locator('#machines-table > tbody > tr:nth-child(1) > td:nth-child(2)').text_content()
    assert machine_name.strip() == 'Local machine'


    awaiting_info = page.locator('#machines-table > tbody > tr:nth-child(1) > td:nth-child(10)').text_content()
    assert awaiting_info.strip() == 'awaiting info'




def test_settings_display():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.locator("#menu").get_by_role("link", name="Settings", exact=True).click()

    page.wait_for_load_state("load") # ALL JS should be done

    energy_display = page.locator('#energy-display').text_content()
    assert energy_display.strip() == 'Currently showing Watt-Hours'


    units_display = page.locator('#units-display').text_content()
    assert units_display.strip() == 'Currently showing imperial units'


    fetch_time_series_display = page.locator('#fetch-time-series-display').text_content()
    assert fetch_time_series_display.strip() == 'Currently not fetching time series by default'


    time_series_avg_display = page.locator('#time-series-avg-display').text_content()
    assert time_series_avg_display.strip() == 'Currently not showing AVG in time series'

def test_settings_measurement():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.locator("#menu").get_by_role("link", name="Settings", exact=True).click()

    page.wait_for_load_state("load") # ALL JS should be done

    page.locator("a#settings-tab-measurement").click()
    page.wait_for_load_state("load") # ALL JS should be done

    user = User(1)

    value = page.locator('#measurement-total-duration').input_value()
    assert int(value.strip()) == user._capabilities['measurement']['total_duration']


    value = page.locator('#measurement-flow-process-duration').input_value()
    assert int(value.strip()) == user._capabilities['measurement']['flow_process_duration']

    value = page.locator('#measurement-disabled-metric-providers').input_value()
    providers = [] if value.strip() == '' else [value.strip()]
    assert providers == user._capabilities['measurement']['disabled_metric_providers']

    page.locator('#measurement-total-duration').fill('123')
    page.locator('#measurement-flow-process-duration').fill('456')
    page.evaluate('$("#measurement-disabled-metric-providers").dropdown("set exactly", "NetworkConnectionsProxyContainerProvider");')

    page.locator('#save-measurement-total-duration').click()
    page.locator('#save-measurement-flow-process-duration').click()
    page.locator('#save-measurement-disabled-metric-providers').click()

    page.wait_for_load_state("networkidle") # ALL AJAX should be done

    user = User(1)
    assert user._capabilities['measurement']['total_duration'] == 123
    assert user._capabilities['measurement']['flow_process_duration'] == 456
    assert user._capabilities['measurement']['disabled_metric_providers'] == ['NetworkConnectionsProxyContainerProvider']
