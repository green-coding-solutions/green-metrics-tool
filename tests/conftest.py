import pytest
import os
import shutil
from lib.db import DB

## VERY IMPORTANT to override the config file here
## otherwise it will automatically connect to non-test DB and delete all your real data
from lib.global_config import GlobalConfig
GlobalConfig().override_config(config_name='test-config.yml')

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

def pytest_collection_modifyitems(items):
    for item in items:
        if item.fspath.basename == 'test_functions.py':
            item.add_marker(pytest.mark.skip(reason='Skipping this file'))

def cleanup_tables():
    tables = DB().fetch_all("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    for table in tables:
        table_name = table[0]
        DB().query(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE')

def cleanup_temp_directories():
    tmp_dir = os.path.join(CURRENT_DIR, 'tmp/')
    if os.path.exists(tmp_dir):
        for item in os.listdir(tmp_dir):
            item_path = os.path.join(tmp_dir, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
    if os.path.exists("/tmp/gmt-test-data/"):
        shutil.rmtree("/tmp/gmt-test-data/")

def pytest_sessionfinish(session):
    if not hasattr(session.config, 'workerinput'):
        cleanup_tables()
        cleanup_temp_directories()
