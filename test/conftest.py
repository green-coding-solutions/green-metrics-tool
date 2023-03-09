#pylint: disable=undefined-variable

def pytest_collection_modifyitems(items):
    for item in items:
        if item.fspath.basename == 'test_functions.py':
            item.add_marker(pytest.mark.skip(reason='Skipping this file'))
