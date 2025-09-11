import os
import pytest
import time
import requests
import uuid
import json

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')

from lib.global_config import GlobalConfig
from lib.user import User
from lib.db import DB

from tests import test_functions as Tests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import urllib.parse
from datetime import datetime, timedelta

from api.object_specifications import CI_Measurement


page = None
context = None
playwright = None
browser = None

API_URL = GlobalConfig().config['cluster']['api_url'] # will be pre-loaded with test-config.yml due to conftest.py

## Shared Playwright setup for all tests
@pytest.fixture(autouse=True, scope='module')
def setup_playwright():
    """Start Playwright once for the entire module"""
    # before
    global playwright #pylint: disable=global-statement
    playwright = sync_playwright().start()

    yield

    # after
    playwright.stop()

# Browser setup for each test
@pytest.fixture(autouse=True)
def setup_browser(setup_playwright): #pylint: disable=unused-argument,redefined-outer-name
    """
    Set up browser for each test
    We must close the browser to clear localStorage
    """
    global page #pylint: disable=global-statement
    global context #pylint: disable=global-statement
    global browser #pylint: disable=global-statement

    browser = playwright.firefox.launch(
        headless=True,
        # slow_mo=50,
    )
    context = browser.new_context(viewport={"width": 1920, "height": 5600})
    page = context.new_page()
    page.set_default_timeout(3_000)

    page.on("pageerror", handle_page_error)

    yield
    page.close()
    browser.close()

def handle_page_error(exception):
    raise RuntimeError("JS error occured on page:", exception)

## Fixture for tests that need demo data
@pytest.fixture()
def use_demo_data():
    """Import demo data for standard frontend tests"""
    Tests.import_demo_data()
    yield
    Tests.reset_db()

## Fixture for tests that need clean database
@pytest.fixture()
def use_clean_db():
    """Reset database for test that needs a clean database"""
    Tests.reset_db()
    yield
    Tests.reset_db()
    Tests.import_demo_data()  # Restore demo data after tests

@pytest.mark.usefixtures('use_demo_data')
class TestFrontendFunctionality:
    """Functional frontend tests"""

    def test_home(self):
        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        value = page.locator("div.ui.cards.link > div.ui.card:nth-child(1) a.header").text_content()

        assert value== 'ScenarioRunner'

        value = page.locator("#scenario-runner-count").text_content()
        assert value== '5'

        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        value = page.locator("div.ui.cards.link > div.ui.card:nth-child(2) a.header").text_content()

        assert value== 'Eco CI'


    def test_runs(self):
        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/runs.html')
        page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()

        value = page.locator("#runs-and-repos-table > tbody tr:nth-child(2) > td:nth-child(1) > a").text_content()

        assert value== 'Stress Test #2'


    def test_eco_ci_demo_data(self):
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


    @pytest.mark.usefixtures('use_clean_db')
    def test_eco_ci_adding_data(self):
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


    def test_stats(self):

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

        energy_value = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="energy"] div.ui.blue.card.machine-energy > div.extra.content span.value.bold').text_content()
        phase_duration = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.teal.card.runtime > div.extra.content span.value.bold').text_content()

        assert energy_value.strip() == '21.14'
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

        network_traffic_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(6)")
        assert network_traffic_value.text_content().strip() == '0.37'
        assert network_traffic_value.inner_html().strip() == '<span title="367908">0.37</span>'

        network_traffic_unit = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(7)").text_content()
        assert network_traffic_unit.strip() == 'MB'


        network_traffic_metric = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(13) > td:nth-child(1)").text_content()
        assert network_traffic_metric.strip() == 'Network Transmission CO₂'

        network_traffic_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(13) > td:nth-child(6)").inner_html()
        assert network_traffic_value.strip() == '<span title="425">0.00</span> <span data-tooltip="Value is lower than rounding. Unrounded value is 425 ug" data-position="bottom center" data-inverted=""><i class="question circle icon link"></i></span>'

        network_traffic_unit = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(13) > td:nth-child(7)").text_content()
        assert network_traffic_unit.strip() == 'g'


        # click on baseline
        new_page.locator('a.step[data-tab="[BASELINE]"]').click()
        new_page.locator('div[data-tab="[BASELINE]"] .ui.accordion .title > a').click()

        first_metric = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(1)").text_content()
        assert first_metric.strip() == 'Machine CO₂ (embodied)'

        first_value = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(6)").text_content()
        assert first_value.strip() == '0.01'

        first_unit = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(8) > td:nth-child(7)").text_content()
        assert first_unit.strip() == 'g'

        new_page.close()


    def test_repositories_and_compare_with_diff(self):

        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()

        page.locator('#DataTables_Table_0').wait_for(timeout=3_000) # wait for accordion to fetch XHR and open

        elements = page.query_selector_all("input[type=checkbox]")
        elements[0].click()
        elements[3].click()

        with context.expect_page() as new_page_info:
            page.locator('#compare-button').click() # will do usage-scenario-variables comparison

        new_page = new_page_info.value
        new_page.set_default_timeout(3_000)

        new_page.locator('#runtime-steps phase-metrics .ui.accordion .title > a').first.click()

        first_metric = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(1)")
        assert first_metric.text_content().strip() == 'Phase Duration'
        assert first_metric.inner_html().strip() == '<i class="question circle icon"></i>Phase Duration'

        first_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(6)")
        assert first_value.text_content().strip() == '5.06'
        assert first_value.inner_html().strip() == '<span title="5064843">5.06</span>'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(8)").inner_html().strip() == 's'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(9)").inner_html().strip() == '+ 4.80 %'


        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(9) > td:nth-child(1)").text_content().strip() == 'Machine Energy'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(9) > td:nth-child(6)").text_content().strip() == '20.16'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(9) > td:nth-child(7)").text_content().strip() == '21.81'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(9) > td:nth-child(8)").text_content().strip() == 'mWh'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(9) > td:nth-child(9)").text_content().strip() == '+ 8.19 %'


        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(13) > td:nth-child(1)").text_content().strip() == 'Network Transmission CO₂'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(13) > td:nth-child(6)").inner_html() == '<span title="409">0.00</span> <span data-tooltip="Value is lower than rounding. Unrounded value is 409 ug" data-position="bottom center" data-inverted=""><i class="question circle icon link"></i></span>'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(13) > td:nth-child(7)").inner_html().strip() == '<span title="446">0.00</span> <span data-tooltip="Value is lower than rounding. Unrounded value is 446 ug" data-position="bottom center" data-inverted=""><i class="question circle icon link"></i></span>'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(13) > td:nth-child(8)").inner_html().strip() == 'g'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(13) > td:nth-child(9)").inner_html().strip() == '+ 9.05 %'



        new_page.close()

    def test_repositories_and_compare_repeated_run(self):

        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()
        page.get_by_role("button", name="Switch to repository view").click()

        page.locator('.ui.accordion div.title').click()
        page.locator('#DataTables_Table_0').wait_for(timeout=3_000) # wait for accordion to fetch XHR and open

        elements = page.query_selector_all("input[type=checkbox]")
        elements[0].click()
        elements[1].click()
        elements[2].click()

        with context.expect_page() as new_page_info:
            page.locator('#compare-button').click()

        new_page = new_page_info.value
        new_page.set_default_timeout(3_000)

        comparison_type = new_page.locator('#run-data-top > tbody:nth-child(1) > tr > td:nth-child(2)').text_content()
        assert comparison_type == 'Repeated Run'

        runs_compared = new_page.locator('#run-data-top > tbody:nth-child(2) > tr > td:nth-child(2)').text_content()
        assert runs_compared == '3'

        # open details
        new_page.locator('a.step[data-tab="[RUNTIME]"]').click()
        new_page.locator('#runtime-steps phase-metrics .ui.accordion .title > a').first.click()

        first_metric = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(3) > td:nth-child(1)").text_content()
        assert first_metric.strip() == 'CPU Package Power'

        first_type = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(3) > td:nth-child(5)")
        assert first_type.text_content().strip() == 'MEAN'

        first_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(3) > td:nth-child(6)")
        assert first_value.text_content().strip() == '8.64'
        assert first_value.inner_html().strip() == '<span title="8637">8.64</span>'

        first_unit = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(3) > td:nth-child(7)").text_content()
        assert first_unit.strip() == 'W'

        first_stddev = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(3) > td:nth-child(8)").text_content()
        assert first_stddev.strip() == '± 2.85%'


        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(13) > td:nth-child(6)").inner_html() == '<span title="435.5">0.00</span> <span data-tooltip="Value is lower than rounding. Unrounded value is 435.5 ug" data-position="bottom center" data-inverted=""><i class="question circle icon link"></i></span>'

        assert new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(13) > td:nth-child(8)").inner_html() == '± 3.41%'


        # click on baseline
        new_page.locator('a.step[data-tab="[BASELINE]"]').click()
        new_page.locator('div[data-tab="[BASELINE]"] .ui.accordion a').click()

        first_metric = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(1)").text_content()
        assert first_metric.strip() == 'CPU Package Energy'

        first_value = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(6)").text_content()
        assert first_value.strip() == '2.62'

        first_unit = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(7)").text_content()
        assert first_unit.strip() == 'mWh'

        first_stddev = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(8)").text_content()
        assert first_stddev.strip() == '± 3.89%'

        new_page.close()

    def test_expert_compare_mode(self):

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
        elements[0].click()
        elements[1].click()
        elements[2].click()
        elements[4].click()

        with context.expect_page() as new_page_info:
            page.locator('#compare-button').click()

        new_page = new_page_info.value
        new_page.set_default_timeout(3_000)

        assert new_page.locator("#run-data-top > tbody:first-child > tr:first-child > td:nth-child(2)").text_content() == 'Usage Scenario'

        new_page.close()


        page.locator('#unselect-button').click()
        elements = page.query_selector_all("input[type=checkbox]")
        elements[0].click()
        elements[1].click()
        elements[2].click()
        elements[4].click()

        page.locator('#compare-force-mode').select_option("Machines")

        with context.expect_page() as new_page_info:
            page.locator('#compare-button').click()

        new_page = new_page_info.value
        new_page.set_default_timeout(3_000)

        assert new_page.locator("#run-data-top > tbody:first-child > tr > td:nth-child(2)").text_content() == 'Machine'

        assert new_page.locator("#run-data-top > tbody:nth-child(2) > tr > td:first-child").text_content() == 'Number of runs compared'

        assert new_page.locator("#run-data-top > tbody:nth-child(2) > tr > td:nth-child(2)").text_content() == '4'

        assert new_page.locator("#run-data-top > tbody:nth-child(3) > tr > td:nth-child(1)").text_content() == 'Machine'

        assert new_page.locator("#run-data-top > tbody:nth-child(3) > tr > td:nth-child(2)").text_content() == 'Local machine'


        new_page.close()


    def test_new_usage_scenario_variables_compare_mode(self):
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

        page.locator('#compare-force-mode').select_option("Usage Scenario Variables")


        with context.expect_page() as new_page_info:
            page.locator('#compare-button').click()

        new_page = new_page_info.value
        new_page.set_default_timeout(3_000)

        assert new_page.locator("#run-data-top > tbody:first-child > tr:first-child > td:nth-child(2)").text_content() == 'Usage Scenario Variables'

        assert new_page.locator("#run-data-top > tbody:nth-child(2) > tr > td:first-child").text_content() == 'Number of runs compared'

        assert new_page.locator("#run-data-top > tbody:nth-child(2) > tr > td:nth-child(2)").text_content() == '5'

        assert new_page.locator("#run-data-top > tbody:nth-child(3) > tr > td:nth-child(2)").text_content() == "{} vs. {'__GMT_VAR_STATUS__': 'I love the GMT!'}"


        new_page.close()
    def test_watchlist(self):

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


    def test_status(self):

        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        page.locator("#menu").get_by_role("link", name="Cluster Status", exact=True).click()

        machine_name = page.locator('#machines-table > tbody > tr:nth-child(1) > td:nth-child(2)').text_content()
        assert machine_name.strip() == 'Local machine'


        awaiting_info = page.locator('#machines-table > tbody > tr:nth-child(1) > td:nth-child(10)').text_content()
        assert awaiting_info.strip() == 'awaiting info'




    def test_settings_display(self):

        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        page.locator("#menu").get_by_role("link", name="Settings", exact=True).click()

        page.wait_for_load_state("load") # ALL JS should be done

        energy_display = page.locator('#energy-display').text_content()
        assert energy_display.strip() == 'Currently showing milli-Watt-Hours'


        units_display = page.locator('#units-display').text_content()
        assert units_display.strip() == 'Currently showing imperial units'


        fetch_time_series_display = page.locator('#fetch-time-series-display').text_content()
        assert fetch_time_series_display.strip() == 'Currently not fetching time series by default'


        time_series_avg_display = page.locator('#time-series-avg-display').text_content()
        assert time_series_avg_display.strip() == 'Currently not showing AVG in time series'

    def test_settings_measurement(self):

        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        page.locator("#menu").get_by_role("link", name="Settings", exact=True).click()

        page.wait_for_load_state("load") # ALL JS should be done

        page.locator("a#settings-tab-measurement").click()
        page.wait_for_load_state("load") # ALL JS should be done

        user = User(1)
        # check default values
        assert user._capabilities['measurement']['disabled_metric_providers'] == []
        assert user._capabilities['measurement']['flow_process_duration'] == 86400
        assert user._capabilities['measurement']['total_duration'] == 86400
        assert user._capabilities['measurement']['phase_padding'] is True
        assert user._capabilities['measurement']['dev_no_sleeps'] is False
        assert user._capabilities['measurement']['dev_no_optimizations'] is False
        assert user._capabilities['measurement']['system_check_threshold'] == 3
        assert user._capabilities['measurement']['pre_test_sleep'] == 5
        assert user._capabilities['measurement']['idle_duration'] == 60
        assert user._capabilities['measurement']['baseline_duration'] == 60
        assert user._capabilities['measurement']['post_test_sleep'] == 5
        assert user._capabilities['measurement']['phase_transition_time'] == 1
        assert user._capabilities['measurement']['wait_time_dependencies'] == 60
        assert user._capabilities['measurement']['skip_volume_inspect'] is False


        value = page.locator('#measurement-disabled-metric-providers').input_value()
        providers = [] if value.strip() == '' else [value.strip()]
        assert providers == user._capabilities['measurement']['disabled_metric_providers']

        value = page.locator('#measurement-flow-process-duration').input_value()
        assert int(value.strip()) == user._capabilities['measurement']['flow_process_duration']

        value = page.locator('#measurement-total-duration').input_value()
        assert int(value.strip()) == user._capabilities['measurement']['total_duration']

        value = page.locator('#measurement-phase-padding').is_checked()
        assert value is user._capabilities['measurement']['phase_padding']

        value = page.locator('#measurement-dev-no-sleeps').is_checked()
        assert value is user._capabilities['measurement']['dev_no_sleeps']

        value = page.locator('#measurement-dev-no-optimizations').is_checked()
        assert value is user._capabilities['measurement']['dev_no_optimizations']

        value = page.locator('#measurement-system-check-threshold').input_value()
        assert int(value.strip()) == user._capabilities['measurement']['system_check_threshold']

        value = page.locator('#measurement-pre-test-sleep').input_value()
        assert int(value.strip()) == user._capabilities['measurement']['pre_test_sleep']

        value = page.locator('#measurement-idle-duration').input_value()
        assert int(value.strip()) == user._capabilities['measurement']['idle_duration']

        value = page.locator('#measurement-baseline-duration').input_value()
        assert int(value.strip()) == user._capabilities['measurement']['baseline_duration']

        value = page.locator('#measurement-post-test-sleep').input_value()
        assert int(value.strip()) == user._capabilities['measurement']['post_test_sleep']

        value = page.locator('#measurement-phase-transition-time').input_value()
        assert int(value.strip()) == user._capabilities['measurement']['phase_transition_time']

        value = page.locator('#measurement-wait-time-dependencies').input_value()
        assert int(value.strip()) == user._capabilities['measurement']['wait_time_dependencies']

        value = page.locator('#measurement-skip-volume-inspect').is_checked()
        assert value is user._capabilities['measurement']['skip_volume_inspect']


        page.locator('#measurement-system-check-threshold').fill('2')
        page.evaluate('$("#measurement-disabled-metric-providers").dropdown("set exactly", "NetworkConnectionsProxyContainerProvider");')
        page.locator('#measurement-flow-process-duration').fill('456')
        page.locator('#measurement-total-duration').fill('123')
        page.locator('#measurement-phase-padding').click()
        page.locator('#measurement-pre-test-sleep').fill('100')
        page.locator('#measurement-idle-duration').fill('200')
        page.locator('#measurement-baseline-duration').fill('100')
        page.locator('#measurement-post-test-sleep').fill('100')
        page.locator('#measurement-phase-transition-time').fill('2')
        page.locator('#measurement-wait-time-dependencies').fill('120')
        page.locator('#measurement-dev-no-sleeps').click()
        page.locator('#measurement-dev-no-optimizations').click()
        page.locator('#measurement-skip-volume-inspect').click()

        page.locator('#save-measurement-system-check-threshold').click()
        page.locator('#save-measurement-disabled-metric-providers').click()
        page.locator('#save-measurement-flow-process-duration').click()
        page.locator('#save-measurement-total-duration').click()
        page.locator('#save-measurement-phase-padding').click()
        page.locator('#save-measurement-pre-test-sleep').click()
        page.locator('#save-measurement-idle-duration').click()
        page.locator('#save-measurement-baseline-duration').click()
        page.locator('#save-measurement-post-test-sleep').click()
        page.locator('#save-measurement-phase-transition-time').click()
        page.locator('#save-measurement-wait-time-dependencies').click()
        page.locator('#save-measurement-dev-no-sleeps').click()
        page.locator('#save-measurement-dev-no-optimizations').click()
        page.locator('#save-measurement-skip-volume-inspect').click()

        #page.wait_for_load_state("networkidle") # Network Idle sadly not enough here. The DB seems to take 1-2 seconds
        time.sleep(1)

        user = User(1)
        assert user._capabilities['measurement']['disabled_metric_providers'] == ['NetworkConnectionsProxyContainerProvider']
        assert user._capabilities['measurement']['flow_process_duration'] == 456
        assert user._capabilities['measurement']['total_duration'] == 123
        assert user._capabilities['measurement']['phase_padding'] is False
        assert user._capabilities['measurement']['dev_no_sleeps'] is True
        assert user._capabilities['measurement']['dev_no_optimizations'] is True
        assert user._capabilities['measurement']['system_check_threshold'] == 2
        assert user._capabilities['measurement']['pre_test_sleep'] == 100
        assert user._capabilities['measurement']['idle_duration'] == 200
        assert user._capabilities['measurement']['baseline_duration'] == 100
        assert user._capabilities['measurement']['post_test_sleep'] == 100
        assert user._capabilities['measurement']['phase_transition_time'] == 2
        assert user._capabilities['measurement']['wait_time_dependencies'] == 120
        assert user._capabilities['measurement']['skip_volume_inspect'] is True


class TestXssSecurity:
    """XSS vulnerability tests"""

    @pytest.mark.usefixtures('use_clean_db')
    def test_xss_protection_of_run_data(self):
        """
        Test that run-related user-provided fields are properly escaped to prevent XSS attacks across multiple pages.
        Tests run name, branch, filename, URI, usage_scenario, usage_scenario_variables, and logs for XSS vulnerabilities
        on runs, stats (including logs view), watchlist, and compare pages.
        This test should FAIL when vulnerabilities exist and PASS when they're fixed.
        """
        Tests.reset_db()

        base_url = GlobalConfig().config['cluster']['metrics_url']

        # Create malicious payloads for all user-provided fields
        malicious_name = '<script>alert("XSS_NAME")</script>Safe Name'
        malicious_branch = '<script>alert("XSS_BRANCH")</script>main'
        malicious_filename = '<script>alert("XSS_FILENAME")</script>test.yml'
        malicious_uri = 'http://evil.com<script>alert("XSS_URI")</script>'
        malicious_usage_scenario = {
            "name": "<script>alert(\"XSS_USAGE_SCENARIO\")</script>",
            "flow": [
                {
                    "name": "<script>alert(\"XSS_FLOW_NAME\")</script>Malicious Flow"
                }
            ]
        }
        malicious_variables = {
            'var1': '<script>alert("XSS_VAR1")</script>value1',
            'var2': '<script>alert("XSS_VAR2")</script>value2'
        }
        malicious_logs = '<script>alert("XSS_LOGS")</script>Error in container\nStacktrace here'

        # Insert test data with malicious content in multiple fields
        run_id = str(uuid.uuid4())
        run_id2 = str(uuid.uuid4())

        # Insert malicious run data
        run_query = """
        INSERT INTO "runs"("id","name","uri","branch","commit_hash","commit_timestamp","usage_scenario","usage_scenario_variables","filename","machine_id","user_id","failed","logs","created_at","updated_at")
        VALUES (%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """

        DB().query(run_query, params=(
            run_id,
            malicious_name,
            malicious_uri,
            malicious_branch,
            'deadbeef123456789abcdef',
            json.dumps(malicious_usage_scenario),
            json.dumps(malicious_variables),
            malicious_filename,
            1,
            1,
            False,
            malicious_logs
        ))

        # Insert second run for compare functionality (same params except name and usage scenario variables)
        DB().query(run_query, params=(
            run_id2,
            'Safe Run Name',  # Different name
            malicious_uri,
            malicious_branch,
            'deadbeef123456789abcdef',
            json.dumps(malicious_usage_scenario),
            json.dumps(malicious_variables),
            malicious_filename,
            1,
            1,
            False,
            malicious_logs
        ))

        # Insert phase_stats for the two runs (needed for the compare view)
        # Include both baseline and flow phases to make the flow visible
        run_query = """
        INSERT INTO phase_stats ("id","run_id","metric","detail_name","phase","value","type","max_value","min_value","sampling_rate_avg","sampling_rate_max","sampling_rate_95p","unit","created_at","updated_at")
        VALUES
        (778,%s,E'phase_time_syscall_system',E'[SYSTEM]',E'000_[BASELINE]',5000601,E'TOTAL',NULL,NULL,NULL,NULL,NULL,E'us',E'2025-01-03 19:40:59.13422+00',NULL),
        (779,%s,E'cpu_energy_rapl_msr_component',E'Package_0',E'000_[BASELINE]',9688000,E'TOTAL',NULL,NULL,99384,99666,99624,E'uJ',E'2025-01-03 19:40:59.13422+00',NULL),
        (780,%s,E'phase_time_syscall_system',E'[SYSTEM]',E'001_<script>alert("XSS_FLOW_NAME")</script>Malicious Flow',5306934,E'TOTAL',NULL,NULL,NULL,NULL,NULL,E'us',E'2025-01-03 19:40:59.13422+00',NULL),
        (781,%s,E'cpu_energy_rapl_msr_component',E'Package_0',E'001_<script>alert("XSS_FLOW_NAME")</script>Malicious Flow',3476000,E'TOTAL',NULL,NULL,99120,99132,99131,E'uJ',E'2025-01-03 19:40:59.13422+00',NULL),
        (782,%s,E'phase_time_syscall_system',E'[SYSTEM]',E'000_[BASELINE]',5000601,E'TOTAL',NULL,NULL,NULL,NULL,NULL,E'us',E'2025-01-03 19:40:59.13422+00',NULL),
        (783,%s,E'cpu_energy_rapl_msr_component',E'Package_0',E'000_[BASELINE]',9688000,E'TOTAL',NULL,NULL,99384,99666,99624,E'uJ',E'2025-01-03 19:40:59.13422+00',NULL),
        (784,%s,E'phase_time_syscall_system',E'[SYSTEM]',E'001_<script>alert("XSS_FLOW_NAME")</script>Malicious Flow',5306934,E'TOTAL',NULL,NULL,NULL,NULL,NULL,E'us',E'2025-01-03 19:40:59.13422+00',NULL),
        (785,%s,E'cpu_energy_rapl_msr_component',E'Package_0',E'001_<script>alert("XSS_FLOW_NAME")</script>Malicious Flow',3476000,E'TOTAL',NULL,NULL,99120,99132,99131,E'uJ',E'2025-01-03 19:40:59.13422+00',NULL);
        """

        DB().query(run_query, params=(
            run_id,      # 778 - baseline phase_time for run_id
            run_id,      # 779 - baseline cpu_energy for run_id
            run_id,      # 780 - flow phase_time for run_id
            run_id,      # 781 - flow cpu_energy for run_id
            run_id2,     # 782 - baseline phase_time for run_id2
            run_id2,     # 783 - baseline cpu_energy for run_id2
            run_id2,     # 784 - flow phase_time for run_id2
            run_id2      # 785 - flow cpu_energy for run_id2
        ))

        # Insert malicious watchlist data
        watchlist_query = """
        INSERT INTO "watchlist"("name","image_url","repo_url","branch","filename","usage_scenario_variables","machine_id","schedule_mode","user_id","created_at","updated_at")
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """

        DB().query(watchlist_query, params=(
            malicious_name,
            'http://example.com/image.png',
            malicious_uri,
            malicious_branch,
            malicious_filename,
            json.dumps(malicious_variables),
            1,
            'daily',
            1
        ))

        malicious_scripts = [
            '<script>alert("XSS_NAME")</script>',
            '<script>alert("XSS_BRANCH")</script>',
            '<script>alert("XSS_FILENAME")</script>',
            '<script>alert("XSS_URI")</script>',
            '<script>alert("XSS_USAGE_SCENARIO")</script>',
            '<script>alert("XSS_VAR1")</script>',
            '<script>alert("XSS_VAR2")</script>',
            '<script>alert("XSS_LOGS")</script>',
            '<script>alert("XSS_FLOW_NAME")</script>'
        ]

        # Test 1: Runs page
        page.goto(base_url + '/runs.html')
        page.wait_for_load_state("networkidle")
        page.wait_for_function("() => document.body.innerText.includes('Safe Name')", timeout=10000)

        runs_content = page.content()

        for script in malicious_scripts:
            assert script not in runs_content, \
                f"XSS vulnerability detected on runs page: malicious script '{script}' found unescaped"

        runs_safe_checks = ['XSS_NAME', 'XSS_BRANCH', 'XSS_FILENAME', 'XSS_URI', 'XSS_VAR1', 'XSS_VAR2']
        for content in runs_safe_checks:
            assert content in runs_content, \
                f"Content '{content}' should be visible on runs page (but safely escaped)"

        # Test 2: Stats page
        stats_url = f"{base_url}/stats.html?id={run_id}"
        page.goto(stats_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_function("() => document.body.innerText.includes('Safe Name')", timeout=10000)

        stats_content = page.content()

        for script in malicious_scripts:
            assert script not in stats_content, \
                f"XSS vulnerability detected on stats page: malicious script '{script}' found unescaped"

        stats_safe_checks = ['XSS_NAME', 'XSS_BRANCH', 'XSS_FILENAME', 'XSS_URI', 'XSS_VAR1', 'XSS_VAR2', 'XSS_USAGE_SCENARIO', 'XSS_LOGS', 'XSS_FLOW_NAME']
        for content in stats_safe_checks:
            assert content in stats_content, \
                f"Content '{content}' should be visible on stats page (but safely escaped)"

        # Test 3: Watchlist page
        page.goto(base_url + '/watchlist.html')
        page.wait_for_load_state("networkidle")
        page.wait_for_function("() => document.body.innerText.includes('Safe Name')", timeout=10000)

        watchlist_content = page.content()

        for script in malicious_scripts:
            assert script not in watchlist_content, \
                f"XSS vulnerability detected on watchlist page: malicious script '{script}' found unescaped"

        watchlist_safe_checks = ['XSS_NAME', 'XSS_BRANCH', 'XSS_FILENAME', 'XSS_URI']
        for content in watchlist_safe_checks:
            assert content in watchlist_content, \
                f"Content '{content}' should be visible on watchlist page (but safely escaped)"

        # Test 4: Compare page (repeated runs)
        compare_url = f"{base_url}/compare.html?ids={run_id},{run_id2}"
        page.goto(compare_url)
        page.wait_for_load_state("networkidle")
        page.wait_for_function("() => document.body.innerText.includes('deadbeef123456789abcdef')", timeout=10000)

        compare_content = page.content()

        for script in malicious_scripts:
            assert script not in compare_content, \
                f"XSS vulnerability detected on compare page: malicious script '{script}' found unescaped"

        compare_safe_checks = ['XSS_FILENAME', 'XSS_URI', 'XSS_FLOW_NAME']
        for content in compare_safe_checks:
            assert content in compare_content, \
                f"Content '{content}' should be visible on compare page (but safely escaped)"

    @pytest.mark.usefixtures('use_demo_data')
    def test_xss_protection_of_notes_via_echarts(self):
        """
        Test that malicious JavaScript in notes does not execute.
        Verifies XSS protection by checking if malicious script runs.
        ECharts handles XSS protection internally for formatter properties.
        """

        malicious_note = '<script>window.XSS_EXECUTED = true; alert("XSS_NOTES")</script>Legitimate note content'

        # Get an existing run ID from demo data
        existing_runs = DB().fetch_all("SELECT id FROM runs LIMIT 1")
        assert existing_runs, "No demo data available - test setup failed"

        run_id = existing_runs[0][0]

        # Update an existing note with malicious content for XSS testing
        existing_notes = DB().fetch_all("SELECT id FROM notes WHERE run_id = %s LIMIT 1", params=(run_id,))
        assert existing_notes, f"No existing notes found for run_id {run_id} - demo data incomplete"

        # Update existing note with malicious content
        update_notes_query = """
        UPDATE "notes" SET "note" = %s WHERE "id" = %s
        """
        DB().query(update_notes_query, params=(malicious_note, existing_notes[0][0]))

        # Set up XSS detection
        page.evaluate("window.XSS_EXECUTED = false")

        # Navigate to stats page
        base_url = GlobalConfig().config['cluster']['metrics_url']
        stats_url = f"{base_url}/stats.html?id={run_id}"

        page.goto(stats_url)
        page.wait_for_load_state("networkidle")

        # Click fetch time series to load notes (if button exists)
        fetch_button = page.locator('button#fetch-time-series')
        if fetch_button.count() > 0:
            fetch_button.click()
        # Wait for charts to load
        page.wait_for_timeout(3000)

        # Check if malicious script executed
        xss_executed = page.evaluate("window.XSS_EXECUTED")

        # Verify XSS protection worked - script should NOT execute
        assert xss_executed is not True, "XSS vulnerability detected: malicious script executed"

    @pytest.mark.usefixtures('use_clean_db')
    def test_xss_protection_of_eco_ci_data(self):
        """
        Test that eco-ci related user-provided fields are properly escaped to prevent XSS attacks.
        Tests repository name, branch, workflow, label, and other CI fields for XSS vulnerabilities
        on ci-index.html and ci.html pages.
        This test should FAIL when vulnerabilities exist and PASS when they're fixed.
        """
        Tests.reset_db()

        base_url = GlobalConfig().config['cluster']['metrics_url']

        # Create two test entries to test both pages comprehensively
        xss_payload = '<img src=x onerror="window.IMG_XSS_EXECUTED=true">'

        # Entry 1: Malicious repo identifiers for testing ci-index.html XSS protection
        malicious_repo = f'{xss_payload}evil/repo'
        malicious_branch = f'{xss_payload}main'
        malicious_workflow = f'{xss_payload}workflow-456'

        # Entry 2: Clean repo identifiers for testing ci.html XSS protection
        clean_repo = 'clean/repo'
        clean_branch = 'main'
        clean_workflow = 'workflow-789'

        # Display fields: malicious content where possible, clean only where needed for functionality
        malicious_run_id = f'{xss_payload}run-456'
        malicious_label = f'{xss_payload}build'
        clean_source = 'github'  # Keep clean for URL generation
        malicious_cpu = f'{xss_payload}intel-cpu'
        malicious_commit = f'{xss_payload}abc123def'
        malicious_workflow_name = f'{xss_payload}Test Workflow'
        clean_filter_type = 'machine.ci'  # Keep clean for functionality
        clean_filter_project = 'CI/CD'
        clean_filter_machine = 'test-machine'
        malicious_filter_tags = [f'{xss_payload}tag1', f'{xss_payload}tag2']
        clean_lat = '52.5200'  # Keep clean for functionality
        clean_lon = '13.4050'
        malicious_city = f'{xss_payload}Berlin'
        malicious_note = f'{xss_payload}Test note'

        # Insert two CI measurement entries to test both pages
        filter_tags_sql = f"ARRAY[{','.join(['%s']*len(malicious_filter_tags))}]"
        ci_query = f"""
        INSERT INTO ci_measurements (
            energy_uj, repo, branch, workflow_id, run_id, label, source, cpu, commit_hash,
            duration_us, cpu_util_avg, workflow_name, lat, lon, city, carbon_intensity_g,
            carbon_ug, filter_type, filter_project, filter_machine, filter_tags,
            ip_address, user_id, note, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, {filter_tags_sql}, %s, %s, %s, NOW()
        )
        """

        # Entry 1: Malicious repo identifiers (for ci-index.html XSS testing)
        params_malicious_repo = [
            1000000,  # energy_uj
            malicious_repo,  # repo - contains XSS payload for ci-index.html testing
            malicious_branch,  # branch - contains XSS payload
            malicious_workflow,  # workflow_id - contains XSS payload
            malicious_run_id,  # run_id
            malicious_label,  # label
            clean_source,  # source - keep clean for functionality
            malicious_cpu,  # cpu
            malicious_commit,  # commit_hash
            5000000,  # duration_us
            85.5,  # cpu_util_avg
            malicious_workflow_name,  # workflow_name
            clean_lat,  # lat
            clean_lon,  # lon
            malicious_city,  # city
            400,  # carbon_intensity_g
            500000,  # carbon_ug
            clean_filter_type,  # filter_type
            clean_filter_project,  # filter_project
            clean_filter_machine,  # filter_machine
        ] + malicious_filter_tags + [
            '127.0.0.1',  # ip_address
            1,  # user_id
            malicious_note  # note
        ]

        # Entry 2: Clean repo identifiers (for ci.html XSS testing)
        params_clean_repo = [
            2000000,  # energy_uj (different value)
            clean_repo,  # repo - clean for API queries
            clean_branch,  # branch - clean for API queries
            clean_workflow,  # workflow_id - clean for API queries
            f'{xss_payload}run-789',  # run_id - different malicious content
            f'{xss_payload}deploy',  # label - different malicious content
            clean_source,  # source
            f'{xss_payload}amd-cpu',  # cpu - different malicious content
            f'{xss_payload}def456ghi',  # commit_hash - different malicious content
            7000000,  # duration_us (different value)
            75.0,  # cpu_util_avg (different value)
            f'{xss_payload}Deploy Workflow',  # workflow_name - different malicious content
            clean_lat,  # lat
            clean_lon,  # lon
            f'{xss_payload}Munich',  # city - different malicious content
            350,  # carbon_intensity_g (different value)
            600000,  # carbon_ug (different value)
            clean_filter_type,  # filter_type
            clean_filter_project,  # filter_project
            clean_filter_machine,  # filter_machine
        ] + [f'{xss_payload}tag3', f'{xss_payload}tag4'] + [
            '127.0.0.1',  # ip_address
            1,  # user_id
            f'{xss_payload}Deploy note'  # note - different malicious content
        ]

        DB().query(ci_query, params=params_malicious_repo)
        DB().query(ci_query, params=params_clean_repo)

        # Verify both test entries were inserted correctly
        malicious_verify = "SELECT repo, branch, workflow_id FROM ci_measurements WHERE repo LIKE '%evil/repo%' LIMIT 1"
        malicious_data = DB().fetch_one(malicious_verify)
        assert malicious_data is not None, "Malicious test data was not inserted into database"

        clean_verify = "SELECT repo, branch, workflow_id FROM ci_measurements WHERE repo LIKE '%clean/repo%' LIMIT 1"
        clean_data = DB().fetch_one(clean_verify)
        assert clean_data is not None, "Clean test data was not inserted into database"
        assert clean_data[0] == clean_repo, f"Expected clean repo '{clean_repo}' but got '{clean_data[0]}'"

        # Test ci-index.html page for XSS
        ci_index_url = f"{base_url}/ci-index.html"
        page.goto(ci_index_url)
        page.wait_for_load_state("networkidle")

        # Wait for the malicious repository data to load (contains XSS payload)
        page.wait_for_function("() => document.body.innerText.includes('evil/repo')", timeout=10000)

        # Check if XSS executed via event handler (more reliable than script tags)
        img_xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")

        # Verify XSS vulnerability is fixed - malicious code should NOT execute
        assert img_xss_executed is not True, "XSS vulnerability detected on ci-index.html: malicious code executed via img onerror"

        # Test ci.html page - use clean URL params but malicious data will come from API
        # Use clean URL params that will match our database query identifiers
        # The malicious content will come from the API response data, not URL params

        # Add date parameters to ensure we get recent data
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

        ci_url = f"{base_url}/ci.html?repo={urllib.parse.quote(clean_repo)}&branch={urllib.parse.quote(clean_branch)}&workflow={urllib.parse.quote(clean_workflow)}&start_date={start_date}&end_date={end_date}"
        page.goto(ci_url)
        # Force browser to reload JavaScript by doing a hard refresh
        page.reload()
        page.wait_for_load_state("networkidle")

        # Wait for the clean CI data to load - should find the clean repo name
        try:
            page.wait_for_function("() => document.body.innerText.includes('clean/repo')", timeout=10000)
        except PlaywrightTimeoutError:
            # If data doesn't load, check why and provide meaningful error
            page_text = page.evaluate("() => document.body.innerText")
            if 'No data for time frame' in page_text:
                assert False, "CI data not loaded: API returned 'No data for time frame' - check date range or data insertion"
            elif 'error' in page_text.lower():
                assert False, f"CI data not loaded: Page shows error - {page_text[:200]}"
            else:
                assert False, f"CI data not loaded: Unknown reason - Page content: {page_text[:200]}"

        # Check if XSS executed on ci.html page - the malicious payload should be in the API response but escaped
        ci_img_xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")
        assert ci_img_xss_executed is not True, "XSS vulnerability detected on ci.html: malicious code executed from API data"

        # Verify the malicious content was properly escaped in the page HTML
        page_content = page.content()

        # Check if malicious content is properly escaped
        # Look for dangerous unescaped patterns that could execute
        dangerous_patterns = [
            '<img src=x onerror="window.IMG_XSS_EXECUTED=true">',  # Fully unescaped and executable
            "data-tooltip='<img src=x onerror=\"window.IMG_XSS_EXECUTED=true\">",  # Unescaped in single quotes
            "><img src=x onerror=",  # Breaking out of elements
        ]

        for pattern in dangerous_patterns:
            assert pattern not in page_content, f"XSS vulnerability: dangerous unescaped pattern found: {pattern}"

        # Verify that the content IS present but safely escaped
        assert '&lt;img src=x onerror=' in page_content, "Malicious content should be present but safely escaped"
        assert 'onerror=&quot;window.IMG_XSS_EXECUTED=true&quot;' in page_content, "Quotes should be properly escaped in attributes"
