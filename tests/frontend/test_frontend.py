import os
import pytest
import subprocess
import time

GMT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..')

from lib.global_config import GlobalConfig

from tests import test_functions as Tests
from playwright.sync_api import sync_playwright

page = None
context = None

## Reset DB only once after module
#pylint: disable=unused-argument
@pytest.fixture(autouse=True, scope='module')
def setup_and_cleanup_module():
    # before

    global page #pylint: disable=global-statement
    global context #pylint: disable=global-statement
    # start only one browser for whole file
    playwright = sync_playwright().start()
    browser = playwright.firefox.launch()
    context = browser.new_context(viewport={"width": 1920, "height": 10600})
    page = context.new_page()
    page.set_default_timeout(5_000)

    subprocess.run(
        f"docker exec -i --user postgres test-green-coding-postgres-container psql -dtest-green-coding -p9573 < {GMT_DIR}/data/demo_data.sql",
        check=True,
        shell=True,
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        encoding='UTF-8'
    )
    yield

    # after
    browser.close()
    playwright.stop()

    Tests.reset_db()


def test_home():

    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    value = page.locator("#runs-table > tbody > tr:nth-child(2) > td:nth-child(1) > a").text_content()

    assert value== 'Stress Test #4'

def test_ci():
    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.get_by_role("link", name="Eco-CI").click()

    page.locator("#repositories-table > tbody > tr:nth-child(1) > td > div > div.title").click()
    page.locator('#DataTables_Table_0 > tbody > tr > td.sorting_1 > a').click()

    energy_avg_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(2)").text_content()
    assert energy_avg_all_steps.strip() == '14.3 J (± 72.61%)'

    time_avg_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(3)").text_content()
    assert time_avg_all_steps.strip() == '6.4s (± 59.48%)'

    cpu_avg_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(4)").text_content()
    assert cpu_avg_all_steps.strip() == '38.6% (± 36.31%%)'

    grid_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(5)").text_content()
    assert grid_all_steps.strip() == '494.2 gCO2/kWh (± 5.16%)'

    carbon_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(6)").text_content()
    assert carbon_all_steps.strip() == '0.008 gCO2e (± 71.27%)'

    count_all_steps = page.locator("#label-stats-table-avg > tr:nth-child(1) > td:nth-child(7)").text_content()
    assert count_all_steps.strip() == '10'



    energy_avg_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(2)").text_content()
    assert energy_avg_single.strip() == '4.46 J (± 10.96%)'

    time_avg_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(3)").text_content()
    assert time_avg_single.strip() == '2.8s (± 15.97%)'

    cpu_avg_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(4)").text_content()
    assert cpu_avg_single.strip() == '27.6% (± 41.83%%)'

    grid_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(5)").text_content()
    assert grid_single.strip() == '494.2 gCO2/kWh (± 5.47%)'

    carbon_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(6)").text_content()
    assert carbon_single.strip() == '0.0026 gCO2e (± 9.83%)'

    count_single = page.locator("#label-stats-table-avg > tr:nth-child(2) > td:nth-child(7)").text_content()
    assert count_single.strip() == '5'


def test_stats():
    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')

    with context.expect_page() as new_page_info:
        page.get_by_role("link", name="Stress Test #1").click()

    # Get the new page (tab)
    new_page = new_page_info.value
    new_page.set_default_timeout(2_000)

    # open details
    new_page.locator('div[data-tab="[RUNTIME]"] .ui.accordion a').click()
    new_page.locator('a.step[data-tab="[RUNTIME]"]').click()

    energy_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.four.cards.stackable > div.ui.card.machine-energy > div > div.description > div.ui.fluid.mini.statistic > div > span").text_content()
    phase_duration = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.four.cards.stackable > div.ui.card.phase-duration > div > div.description > div.ui.fluid.mini.statistic > div > span").text_content()


    assert energy_value.strip() == '76.10'
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
    assert first_metric.strip() == 'CPU Energy (Package)'

    first_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(6)").text_content()
    assert first_value.strip() == '45.05'

    first_unit = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(7)").text_content()
    assert first_unit.strip() == 'J'


    # click on baseline
    new_page.locator('a.step[data-tab="[BASELINE]"]').click()
    new_page.locator('div[data-tab="[BASELINE]"] .ui.accordion a').click()

    first_metric = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(1)").text_content()
    assert first_metric.strip() == 'CPU Energy (Package)'

    first_value = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(6)").text_content()
    assert first_value.strip() == '9.69'

    first_unit = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(7)").text_content()
    assert first_unit.strip() == 'J'

    new_page.close()


def test_repositories_and_compare():
    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.get_by_role("link", name="Repositories").click()
    page.locator('.ui.accordion div.title').click()
    page.locator('.dataTables_info') # wait for accordion to fetch XHR and open

    elements = page.query_selector_all("input[type=checkbox]")  # Replace with your selector
    for element in elements:
        element.click()
    with context.expect_page() as new_page_info:
        page.locator('#compare-button').click()

    new_page = new_page_info.value
    new_page.set_default_timeout(5_000)

    comparison_type = new_page.locator('#run-data-top > tbody:nth-child(1) > tr > td:nth-child(2)').text_content()
    assert comparison_type == 'Repeated Run'

    runs_compared = new_page.locator('#run-data-top > tbody:nth-child(2) > tr > td:nth-child(2)').text_content()
    assert runs_compared == '5'

    # open details
    new_page.locator('a.step[data-tab="[RUNTIME]"]').click()
    new_page.locator('div[data-tab="[RUNTIME]"] .ui.accordion a').click()



    first_metric = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(1)").text_content()
    assert first_metric.strip() == 'CPU Power (Package)'

    first_value = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(6)").text_content()
    assert first_value.strip() == '8.50'

    first_unit = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(7)").text_content()
    assert first_unit.strip() == 'W'

    first_stddev = new_page.locator("#runtime-steps > div.ui.bottom.attached.active.tab.segment > div.ui.segment.secondary > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(2) > td:nth-child(8)").text_content()
    assert first_stddev.strip() == '± 2.85%'


    # click on baseline
    new_page.locator('a.step[data-tab="[BASELINE]"]').click()
    new_page.locator('div[data-tab="[BASELINE]"] .ui.accordion a').click()

    first_metric = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(1)").text_content()
    assert first_metric.strip() == 'CPU Energy (Package)'

    first_value = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(6)").text_content()
    assert first_value.strip() == '9.21'

    first_unit = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(7)").text_content()
    assert first_unit.strip() == 'J'

    first_stddev = new_page.locator("#main > div.ui.tab.attached.segment.secondary.active > phase-metrics > div.ui.accordion > div.content.active > table > tbody > tr:nth-child(1) > td:nth-child(8)").text_content()
    assert first_stddev.strip() == '± 13.53%'

    new_page.close()


def test_timeline():
    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.get_by_role("link", name="Energy Timeline").click()
    with context.expect_page() as new_page_info:
        page.get_by_role("link", name=" Show Timeline").click()

    new_page = new_page_info.value
    new_page.set_default_timeout(5_000)

    # test before refresh - data missing - Beware that if demo data is updated with new date this might break!
    time.sleep(2)
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
    page.get_by_role("link", name="Status").click()

    machine_name = page.locator('#machines-table > tbody > tr:nth-child(1) > td:nth-child(2)').text_content()
    assert machine_name.strip() == 'Local machine'


    awaiting_info = page.locator('#machines-table > tbody > tr:nth-child(1) > td:nth-child(10)').text_content()
    assert awaiting_info.strip() == 'awaiting info'




def test_settings():
    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.get_by_role("link", name="Settings").click()

    energy_display = page.locator('#energy-display').text_content()
    assert energy_display.strip() == 'Currently showing Joules'


    units_display = page.locator('#units-display').text_content()
    assert units_display.strip() == 'Currently showing imperial units'


    fetch_time_series_display = page.locator('#fetch-time-series-display').text_content()
    assert fetch_time_series_display.strip() == 'Currently not fetching time series by default'


    time_series_avg_display = page.locator('#time-series-avg-display').text_content()
    assert time_series_avg_display.strip() == 'Currently not showing AVG in time series'
