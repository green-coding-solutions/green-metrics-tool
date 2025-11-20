import pytest

from lib.global_config import GlobalConfig
from lib.db import DB

from tests import test_functions as Tests
from playwright.sync_api import sync_playwright

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
    Tests.import_demo_data_ee()
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

def test_carbondb_display():


    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.locator("#menu").get_by_role("link", name="CarbonDB", exact=True).click()

    carbondb_set_date_to_test_data_date(page)

    page.locator('#carbondb-barchart-carbon-chart canvas').wait_for(timeout=3_000) # will wait for

    total_carbon = page.locator('#total-carbon').text_content()
    assert total_carbon.strip() == '1477.00'

def test_carbondb_manual_add():

    try:
        DB().query('''
            INSERT INTO carbondb_data(id, type,project,machine,source,tags,date,energy_kwh_sum,carbon_kg_sum,carbon_intensity_g_avg,record_count,user_id)
            VALUES
            (3000, 1,1,1,1,ARRAY[]::int[],E'2024-10-10',1.25e3,300,283,7,1);
        ''')


        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        page.locator("#menu").get_by_role("link", name="CarbonDB", exact=True).click()

#        page.screenshot(path="problem.png")

        carbondb_set_date_to_test_data_date(page)

        page.get_by_role("button", name="Refresh").click()

        page.locator('#carbondb-barchart-carbon-chart canvas').wait_for(timeout=3_000) # will wait for

        total_carbon = page.locator('#total-carbon').text_content()
        assert total_carbon.strip() == '1777.00'

    finally:
        DB().query('DELETE FROM carbondb_data WHERE id = 3000;')


def test_carbondb_display_xss_tags():

    try:
        DB().query('''
            INSERT INTO carbondb_tags(id,tag,user_ids)
            VALUES (999,'<script>alert(XSS);</script>','{1}');
            INSERT INTO carbondb_data(id,type,project,machine,source,tags,date,energy_kwh_sum,carbon_kg_sum,carbon_intensity_g_avg,record_count,user_id)
            VALUES
            (3000,1,1,1,1,ARRAY[999],E'2024-10-10',1.25e3,300,283,7,1);
        ''')


        page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
        page.locator("#menu").get_by_role("link", name="CarbonDB", exact=True).click()

        page.locator('#show-filters').click()

        all_tags = page.locator('#tags-include').locator("option").evaluate_all("options => options.map(option => option.textContent)")
        assert '<script>alert(XSS);</script>' not in all_tags
        assert '&lt;script&gt;alert(XSS);&lt;/script&gt;' in all_tags


    finally:
        DB().query('DELETE FROM carbondb_data WHERE id = 3000;')

def test_carbondb_no_display_different_user():
    Tests.insert_user(234, 'NO-CARBONDB')


    page.goto(GlobalConfig().config['cluster']['metrics_url'] + '/index.html')
    page.locator("#menu").get_by_role("link", name="Authentication", exact=True).click()

    page.locator('#authentication-token').fill('NO-CARBONDB')
    page.locator('#save-authentication-token').click()
    page.locator('#token-details-message').wait_for(state='visible')

    page.locator("#menu").get_by_role("link", name="CarbonDB", exact=True).click()

    carbondb_set_date_to_test_data_date(page)

    page.locator('#total-carbon').wait_for(state='hidden')
    assert page.locator('#total-carbon').text_content().strip() == '--' # nothing to show

    page.locator('#no-data-message').wait_for(state='visible')


def carbondb_set_date_to_test_data_date(custom_page):
    custom_page.wait_for_load_state("load") # ALL JS should be done
    custom_page.locator("#show-filters").click()
    custom_page.locator("input[name=range_start]").fill('01.01.2024')
    custom_page.locator("input[name=range_end]").fill('2024-10-31')
    custom_page.get_by_role("button", name="Refresh").click()
    custom_page.wait_for_load_state("load") # ALL JS should be done
