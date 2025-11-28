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
        headless=True, # True is default, set to False to use the browser in headful mode
        # slow_mo=50,
    )
    context = browser.new_context(viewport={"width": 1920, "height": 5600})
    page = context.new_page()
    page.set_default_timeout(3_000)

    page.on("pageerror", handle_page_error)

    yield
    page.close()
    context.close()
    browser.close()

def handle_page_error(exception):
    # we really would love to execute page.screenshot() here, but weirdly this leads to the test passing if page is broken ... even a try/except block does not help ...
    raise RuntimeError("JS error occured on page:", exception)


## Fixture for tests that need demo data
@pytest.fixture()
def use_demo_data():
    """Import demo data for standard frontend tests"""
    Tests.import_demo_data()
    yield
    Tests.reset_db()

@pytest.mark.usefixtures('use_demo_data')
class TestFrontendFunctionality:
    """Functional frontend tests"""

    def test_home(self):
        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        value = page.locator("div.ui.cards.link > div.ui.card:nth-child(1) a.header").text_content()

        assert value== 'ScenarioRunner'

        value = page.locator("#scenario-runner-count").text_content()
        assert value== '6'

        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        value = page.locator("div.ui.cards.link > div.ui.card:nth-child(2) a.header").text_content()

        assert value== 'Eco CI'


    def test_runs(self):
        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/runs.html')
        page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()

        value = page.locator("#runs-and-repos-table > tbody tr:nth-child(3) > td:nth-child(1) > a").text_content()

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

        new_page.wait_for_load_state("networkidle")

        assert new_page.locator("#runtime-hidden-info").is_hidden() is True
        assert new_page.locator("#run-failed").is_hidden() is True
        assert new_page.locator("#run-warnings").is_hidden() is True


        # open details
        new_page.locator('a.step[data-tab="[RUNTIME]"]').click()
        new_page.locator('#runtime-steps phase-metrics .ui.accordion .title > a').first.click()

        machine_energy_value = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="energy"] div.ui.blue.card.machine-energy > div.extra.content span.value.bold').text_content()
        phase_duration = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.teal.card.runtime > div.extra.content span.value.bold').text_content()
        cpu_package_power = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.orange.card.cpu-power > div.extra.content span.value.bold').text_content()
        embodied_carbon = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.teal.card.embodied-carbon > div.extra.content span.value.bold').text_content()
        network_traffic = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.teal.card.network-traffic > div.extra.content span.value.bold').text_content()
        network_data = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.teal.card.network-data > div.extra.content span.value.bold').text_content()

        assert machine_energy_value.strip() == '21.14'
        assert phase_duration.strip() == '5.20'
        assert cpu_package_power.strip() == '8.66'
        assert embodied_carbon.strip() == '0.01'
        assert network_traffic.strip() == '0.37'
        assert network_data.strip() == '0.07'

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


    def test_stats_hidden_run(self):

        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')

        page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()

        with context.expect_page() as new_page_info:
            page.get_by_role("link", name="Hidden Phase Run").click()


        new_page = new_page_info.value
        new_page.set_default_timeout(3_000)

        new_page.wait_for_load_state("networkidle")

        assert new_page.locator("#runtime-hidden-info").is_hidden() is False
        assert new_page.locator("#run-failed").is_hidden() is True
        assert new_page.locator("#run-warnings").is_hidden() is True

        assert new_page.locator('#runtime-sub-phases > .item.runtime-step.hidden-phase-tab[data-tab="I am a hidden phase"]').inner_html() == '<i class="low vision icon"></i> <span class="hidden-phase-name hidden">I am a hidden phase</span>'

        new_page.locator('#runtime-sub-phases > .item.runtime-step.hidden-phase-tab[data-tab="I am a hidden phase"]').click()

        assert new_page.locator('#runtime-sub-phases > .item.runtime-step.hidden-phase-tab[data-tab="I am a hidden phase"]').inner_html() == '<i class="low vision icon"></i> <span class="hidden-phase-name">I am a hidden phase</span>'

        assert new_page.locator('#runtime-hidden-info').is_hidden() is True # bc moved to other tab through click

    def test_compare_with_hidden_phases(self):

        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()

        page.locator('#DataTables_Table_0').wait_for(timeout=3_000) # wait for accordion to fetch XHR and open

        elements = page.query_selector_all("input[type=checkbox]")
        elements[0].click()
        elements[1].click()

        with context.expect_page() as new_page_info:
            page.locator('#compare-button').click() # will do usage-scenario-variables comparison

        new_page = new_page_info.value
        new_page.set_default_timeout(3_000)

        new_page.wait_for_load_state("networkidle")

        assert new_page.locator('#runtime-hidden-info').is_hidden() is False # bc moved to other tab through click

        assert new_page.locator('#runtime-sub-phases > .item.runtime-step.hidden-phase-tab[data-tab="I am a hidden phase"]').inner_html() == '<i class="low vision icon"></i> <span class="hidden-phase-name hidden">I am a hidden phase</span>'

        new_page.locator('#runtime-sub-phases > .item.runtime-step.hidden-phase-tab[data-tab="I am a hidden phase"]').click()

        assert new_page.locator('#runtime-sub-phases > .item.runtime-step.hidden-phase-tab[data-tab="I am a hidden phase"]').inner_html() == '<i class="low vision icon"></i> <span class="hidden-phase-name">I am a hidden phase</span>'

        assert new_page.locator('#runtime-hidden-info').is_hidden() is True # bc moved to other tab through click


    def test_repositories_and_compare_with_diff(self):

        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        page.locator("#menu").get_by_role("link", name="Runs / Repos", exact=True).click()

        page.locator('#DataTables_Table_0').wait_for(timeout=3_000) # wait for accordion to fetch XHR and open

        elements = page.query_selector_all("input[type=checkbox]")
        elements[1].click()
        elements[4].click()

        with context.expect_page() as new_page_info:
            page.locator('#compare-button').click() # will do usage-scenario-variables comparison

        new_page = new_page_info.value
        new_page.set_default_timeout(3_000)

        new_page.locator('#runtime-steps phase-metrics .ui.accordion .title > a').first.click()

        # compare key metrics
        machine_energy_value = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="energy"] div.ui.blue.card.machine-energy > div.extra.content span.value.bold').text_content()
        phase_duration = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.teal.card.runtime > div.extra.content span.value.bold').text_content()
        cpu_package_power = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.orange.card.cpu-power > div.extra.content span.value.bold').text_content()
        embodied_carbon = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.teal.card.embodied-carbon > div.extra.content span.value.bold').text_content()
        network_traffic = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.teal.card.network-traffic > div.extra.content span.value.bold').text_content()
        network_data = new_page.locator('#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.segments div.ui.tab[data-tab="power"] div.ui.teal.card.network-data > div.extra.content span.value.bold').text_content()

        assert machine_energy_value.strip() == '+ 8.19 %'
        assert phase_duration.strip() == '+ 4.80 %'
        assert cpu_package_power.strip() == '+ 4.99 %'
        assert embodied_carbon.strip() == '+ 4.80 %'
        assert network_traffic.strip() == '+ 8.94 %'
        assert network_data.strip() == '+ 4.87 %'

        # compare detailed metrics table
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

        page.get_by_text("/home/arne/Sites/green-coding/example-applications/").click()
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
        elements[1].click()
        elements[2].click()
        elements[3].click()
        elements[5].click()

        with context.expect_page() as new_page_info:
            page.locator('#compare-button').click()

        new_page = new_page_info.value
        new_page.set_default_timeout(3_000)

        assert new_page.locator("#run-data-top > tbody:first-child > tr:first-child > td:nth-child(2)").text_content() == 'Usage Scenario'

        new_page.close()


        page.locator('#unselect-button').click()
        elements = page.query_selector_all("input[type=checkbox]")
        elements[1].click()
        elements[2].click()
        elements[3].click()
        elements[5].click()

        page.locator('#compare-force-mode').select_option("Machines")

        with context.expect_page() as new_page_info:
            page.locator('#compare-button').click()

        new_page = new_page_info.value
        new_page.set_default_timeout(3_000)

        assert new_page.locator("#run-data-top > tbody:first-child > tr > td:nth-child(2)").text_content() == 'Machine'

        assert new_page.locator("#run-data-top > tbody:nth-child(2) > tr > td:first-child").text_content() == 'Number of runs compared'

        assert new_page.locator("#run-data-top > tbody:nth-child(2) > tr > td:nth-child(2)").text_content() == '4'

        assert new_page.locator("#run-data-top > tbody:nth-child(3) > tr > td:nth-child(1)").text_content() == 'Machine'

        assert new_page.locator("#run-data-top > tbody:nth-child(3) > tr > td:nth-child(2)").text_content() == 'Development machine for testing'


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

        assert new_page.locator("#run-data-top > tbody:nth-child(2) > tr > td:nth-child(2)").text_content() == '6'

        table_cell = new_page.locator("#run-data-top > tbody:nth-child(3) > tr > td:nth-child(2)")
        assert "Variable" in table_cell.text_content()  # Should contain table header
        assert "__GMT_VAR_STATUS__" in table_cell.text_content()  # Should contain the variable name
        assert "I love the GMT!" in table_cell.text_content()  # Should contain the value

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
        assert machine_name.strip() == 'Development machine for testing'


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

    def test_xss_protection_of_run_data(self):
        """
        Test that run-related user-provided fields are properly escaped to prevent XSS attacks across multiple pages.
        Tests run name, branch, filename, URI, usage_scenario, usage_scenario_variables, and logs for XSS vulnerabilities
        on runs, stats (including logs view), watchlist, and compare pages.
        This test should FAIL when vulnerabilities exist and PASS when they're fixed.
        """
        base_url = GlobalConfig().config['cluster']['metrics_url']

        # Create malicious payloads using IMG_XSS_EXECUTED approach for all user-provided fields
        xss_payload = '<img src=x onerror="window.IMG_XSS_EXECUTED=true">'
        malicious_name = f'{xss_payload}Safe Name'
        malicious_branch = f'{xss_payload}main'
        malicious_filename = f'{xss_payload}test.yml'
        malicious_uri = f'http://evil.com{xss_payload}'
        malicious_usage_scenario = {
            "name": f"{xss_payload}Scenario",
            "flow": [
                {
                    "name": f"{xss_payload}Malicious Flow"
                }
            ]
        }
        malicious_variables = {
            'var1': f'{xss_payload}value1',
            'var2': f'{xss_payload}value2'
        }
        malicious_logs_json = {
            "malicious-container": [
                {
                    "type": "container_execution",
                    "id": "131377540004848",
                    "cmd": f"docker run -it -d --name malicious-container {xss_payload}",
                    "phase": "[MULTIPLE]",
                    "stdout": f"{xss_payload}Container started with malicious output\nStacktrace here"
                },
                {
                    "type": "flow_command",
                    "id": "131377540003888",
                    "cmd": f"docker exec malicious-container {xss_payload}",
                    "phase": "[RUNTIME]",
                    "stdout": f"{xss_payload}Application executed malicious command\nError output here",
                    "flow": f"{xss_payload}Malicious Flow Scenario"
                }
            ]
        }
        malicious_logs = json.dumps(malicious_logs_json)

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
            json.dumps({'var': 'different_value'}),  # Use different variables for comparison
            malicious_filename,
            1,
            1,
            False,
            malicious_logs
        ))

        # Insert phase_stats for the two runs (needed for the compare view)
        # Include both baseline and flow phases to make the flow visible
        run_query = """
        INSERT INTO phase_stats ("run_id","metric","detail_name","phase","value","type","max_value","min_value","sampling_rate_avg","sampling_rate_max","sampling_rate_95p","unit","created_at","updated_at")
        VALUES
        (%s,E'phase_time_syscall_system',E'[SYSTEM]',E'000_[BASELINE]',5000601,E'TOTAL',NULL,NULL,NULL,NULL,NULL,E'us',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'cpu_energy_rapl_msr_component',E'Package_0',E'000_[BASELINE]',9688000,E'TOTAL',NULL,NULL,99384,99666,99624,E'uJ',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'phase_time_syscall_system',E'[SYSTEM]',E'001_<img src=x onerror="window.IMG_XSS_EXECUTED=true">Malicious Flow',5306934,E'TOTAL',NULL,NULL,NULL,NULL,NULL,E'us',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'cpu_energy_rapl_msr_component',E'Package_0',E'001_<img src=x onerror="window.IMG_XSS_EXECUTED=true">Malicious Flow',3476000,E'TOTAL',NULL,NULL,99120,99132,99131,E'uJ',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'phase_time_syscall_system',E'[SYSTEM]',E'004_[RUNTIME]',5000601,E'TOTAL',NULL,NULL,NULL,NULL,NULL,E'us',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'cpu_energy_rapl_msr_component',E'Package_0',E'000_[RUNTIME]',9688000,E'TOTAL',NULL,NULL,99384,99666,99624,E'uJ',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'phase_time_syscall_system',E'[SYSTEM]',E'000_[BASELINE]',5000601,E'TOTAL',NULL,NULL,NULL,NULL,NULL,E'us',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'cpu_energy_rapl_msr_component',E'Package_0',E'000_[BASELINE]',9688000,E'TOTAL',NULL,NULL,99384,99666,99624,E'uJ',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'phase_time_syscall_system',E'[SYSTEM]',E'001_<img src=x onerror="window.IMG_XSS_EXECUTED=true">Malicious Flow',5306934,E'TOTAL',NULL,NULL,NULL,NULL,NULL,E'us',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'cpu_energy_rapl_msr_component',E'Package_0',E'001_<img src=x onerror="window.IMG_XSS_EXECUTED=true">Malicious Flow',3476000,E'TOTAL',NULL,NULL,99120,99132,99131,E'uJ',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'phase_time_syscall_system',E'[SYSTEM]',E'004_[RUNTIME]',5000601,E'TOTAL',NULL,NULL,NULL,NULL,NULL,E'us',E'2025-01-03 19:40:59.13422+00',NULL),
        (%s,E'cpu_energy_rapl_msr_component',E'Package_0',E'004_[RUNTIME]',9688000,E'TOTAL',NULL,NULL,99384,99666,99624,E'uJ',E'2025-01-03 19:40:59.13422+00',NULL);
        """

        DB().query(run_query, params=(
            run_id,      # 778 - baseline phase_time for run_id
            run_id,      # 779 - baseline cpu_energy for run_id
            run_id,      # 780 - flow phase_time for run_id
            run_id,      # 781 - flow cpu_energy for run_id
            run_id,      # 782 - runtime phase_time for run_id
            run_id,      # 783 - runtime cpu_energy for run_id
            run_id2,     # 784 - baseline phase_time for run_id2
            run_id2,     # 785 - baseline cpu_energy for run_id2
            run_id2,     # 786 - flow phase_time for run_id2
            run_id2,      # 787 - flow cpu_energy for run_id2
            run_id2,     # 788 - runtime phase_time for run_id
            run_id2,     # 789 - runtime cpu_energy for run_id
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

        page.evaluate("window.IMG_XSS_EXECUTED = false")

        # Test 1: Runs page
        page.goto(base_url + '/runs.html')
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_function("() => document.body.innerText.includes('Safe Name')", timeout=10000)

        runs_xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")
        assert runs_xss_executed is not True, "XSS vulnerability detected on runs page: malicious code executed"

        # Test 2: Stats page
        stats_url = f"{base_url}/stats.html?id={run_id}"
        page.goto(stats_url)
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_function("() => document.body.innerText.includes('Safe Name')", timeout=10000)

        stats_xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")
        assert stats_xss_executed is not True, "XSS vulnerability detected on stats page: malicious code executed"

        # Test 3: Watchlist page
        page.goto(base_url + '/watchlist.html')
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_function("() => document.body.innerText.includes('Safe Name')", timeout=10000)

        watchlist_xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")
        assert watchlist_xss_executed is not True, "XSS vulnerability detected on watchlist page: malicious code executed"

        # Test 4: Timeline page
        timeline_url = f"{base_url}/timeline.html?uri={malicious_uri}&branch={malicious_branch}&filename={malicious_filename}&machine_id=1"
        page.goto(timeline_url)
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_function("() => document.querySelector('input[name=\"uri\"]')?.value.includes('evil.com')", timeout=10000)

        timeline_xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")
        assert timeline_xss_executed is not True, "XSS vulnerability detected on timeline page: malicious code executed"

        # Test 5: Compare page (commit hashes comparison view includes repository uri, filename and usage scenario)
        compare_url = f"{base_url}/compare.html?ids={run_id},{run_id2}&force_mode=commit_hashes"
        page.goto(compare_url)
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_function("() => document.body.innerText.includes('deadbeef123456789abcdef')", timeout=10000)

        compare_xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")
        assert compare_xss_executed is not True, "XSS vulnerability detected on compare page: malicious code executed"

        # Test 6: Compare page (usage scenario variables)
        compare_url = f"{base_url}/compare.html?ids={run_id},{run_id2}&force_mode=usage_scenario_variables"

        # Temporarily remove the page error handler for this compare test since there's a JS error due to missing phase_stats data
        page.remove_listener("pageerror", handle_page_error)

        page.goto(compare_url)
        page.wait_for_load_state("networkidle", timeout=10000)
        page.wait_for_function("() => document.body.innerText.includes('different_value')", timeout=10000)

        compare_xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")
        assert compare_xss_executed is not True, "XSS vulnerability detected on compare page with usage scenario variables: malicious code executed"


    @pytest.mark.usefixtures('use_demo_data')
    def test_xss_protection_of_notes(self):
        """
        Test that malicious JavaScript in notes does not execute.
        Verifies XSS protection by checking if malicious script runs.
        ECharts handles XSS protection internally for formatter properties.
        """

        malicious_note = '<img src=x onerror="window.IMG_XSS_EXECUTED=true">Legitimate note content'

        # Get an existing run ID from demo data
        existing_runs = DB().fetch_all("SELECT id FROM runs LIMIT 1")
        assert existing_runs, "No demo data available - test setup failed"

        run_id = existing_runs[0][0]

        # Update an existing note with malicious content for XSS testing
        existing_notes = DB().fetch_all("SELECT id FROM notes WHERE run_id = %s LIMIT 1", params=(run_id,))
        assert existing_notes, f"No existing notes found for run_id {run_id} - demo data incomplete"
        update_notes_query = """
        UPDATE "notes" SET "note" = %s WHERE "id" = %s
        """
        DB().query(update_notes_query, params=(malicious_note, existing_notes[0][0]))


        page.evaluate("window.IMG_XSS_EXECUTED = false")

        base_url = GlobalConfig().config['cluster']['metrics_url']
        stats_url = f"{base_url}/stats.html?id={run_id}"


        page.goto(stats_url)
        page.wait_for_load_state("networkidle")

        fetch_button = page.locator('button#fetch-time-series')

        assert fetch_button.count() > 0, "fetch-time-series button not found - test setup failed"
        fetch_button.click()
        page.wait_for_timeout(3000)

        xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")

        # Verify XSS protection worked - script should NOT execute
        assert xss_executed is not True, "XSS vulnerability detected: malicious script executed"

    def test_xss_protection_of_eco_ci_data(self):
        """
        Test XSS protection on ci-index.html and ci.html pages.
        """
        base_url = GlobalConfig().config['cluster']['metrics_url']
        xss_payload = '<img src=x onerror="window.IMG_XSS_EXECUTED=true">'

        malicious_repo = f'{xss_payload}evil/repo'
        malicious_branch = f'{xss_payload}main'
        malicious_workflow = f'{xss_payload}workflow-456'
        clean_repo = 'clean/repo'
        clean_branch = 'main'
        clean_workflow = 'workflow-789'
        malicious_filter_tags = [f'{xss_payload}tag1', f'{xss_payload}tag2']

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

        # Two entries needed:
        # - malicious repo identifiers test ci-index.html,
        # - clean repo identifiers test ci.html (API requires valid identifiers for queries)
        params_malicious_repo = [
            1000000, malicious_repo, malicious_branch, malicious_workflow,
            f'{xss_payload}run-456', f'{xss_payload}build', 'github',
            f'{xss_payload}intel-cpu', f'{xss_payload}abc123def', 5000000, 85.5,
            f'{xss_payload}Test Workflow', '52.5200', '13.4050', f'{xss_payload}Berlin',
            400, 500000, 'machine.ci', 'CI/CD', 'test-machine'
        ] + malicious_filter_tags + ['127.0.0.1', 1, f'{xss_payload}Test note']

        params_clean_repo = [
            2000000, clean_repo, clean_branch, clean_workflow,
            f'{xss_payload}run-789', f'{xss_payload}deploy', 'github',
            f'{xss_payload}amd-cpu', f'{xss_payload}def456ghi', 7000000, 75.0,
            f'{xss_payload}Deploy Workflow', '52.5200', '13.4050', f'{xss_payload}Munich',
            350, 600000, 'machine.ci', 'CI/CD', 'test-machine'
        ] + [f'{xss_payload}tag3', f'{xss_payload}tag4'] + ['127.0.0.1', 1, f'{xss_payload}Deploy note']

        DB().query(ci_query, params=params_malicious_repo)
        DB().query(ci_query, params=params_clean_repo)

        page.goto(f"{base_url}/ci-index.html")
        page.wait_for_load_state("networkidle")
        page.wait_for_function("() => document.body.innerText.includes('evil/repo')", timeout=10000)

        img_xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")
        assert img_xss_executed is not True, "XSS vulnerability detected on ci-index.html"

        now = datetime.now()
        start_date = (now - timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = now.strftime('%Y-%m-%d')
        ci_url = f"{base_url}/ci.html?repo={clean_repo}&branch={clean_branch}&workflow={clean_workflow}&start_date={start_date}&end_date={end_date}"

        page.goto(ci_url)
        page.reload()
        page.wait_for_load_state("networkidle")

        try:
            page.wait_for_function("() => document.body.innerText.includes('clean/repo')", timeout=10000)
        except PlaywrightTimeoutError:
            page_text = page.evaluate("() => document.body.innerText")
            if 'No data for time frame' in page_text:
                assert False, "CI data not loaded: No data for time frame"
            elif 'error' in page_text.lower():
                assert False, f"CI data not loaded: {page_text[:200]}"
            else:
                assert False, f"CI data not loaded: {page_text[:200]}"

        ci_img_xss_executed = page.evaluate("window.IMG_XSS_EXECUTED")
        assert ci_img_xss_executed is not True, "XSS vulnerability detected on ci.html"

        page_content = page.content()
        assert '<img src=x onerror="window.IMG_XSS_EXECUTED=true">' not in page_content
        assert "data-tooltip='<img src=x onerror=\"window.IMG_XSS_EXECUTED=true\">" not in page_content
        assert '&lt;img src=x onerror=' in page_content
        assert 'onerror=&quot;window.IMG_XSS_EXECUTED=true&quot;' in page_content
