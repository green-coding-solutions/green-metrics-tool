import math

from tests import test_functions as Tests
from lib.db import DB

def test_import_cpu_utilization():

    run_id = Tests.insert_run()
    measurement_lines = Tests.import_cpu_utilization(run_id)

    results = DB().fetch_all('SELECT COUNT(*), AVG(value), MAX(resolution_avg), MAX(resolution_max), MAX(resolution_95p) FROM measurements GROUP BY metric, detail_name, unit')

    assert len(results) == 2, 'Too many entries in table'



    result = results[0]
    assert result[0] == len(measurement_lines)/2 # since we group, length mus be divided by groups
    assert math.isclose(result[1], 3958.59401, rel_tol=1e-5), 'AVG value not in expected range'
    assert math.isclose(result[2], 99373.57636, rel_tol=1e-5), 'Resolution was not in expected range'
    assert math.isclose(result[3], 100688.0, rel_tol=1e-5), 'MAX resolution was not in expected range'
    assert math.isclose(result[4],  99696.0, rel_tol=1e-5), '95p resolution was not in expected range'

    result = results[1]
    assert result[0] == len(measurement_lines)/2 # since we group, length mus be divided by groups
    assert math.isclose(result[1], 1985.44716, rel_tol=1e-5), 'AVG value not in expected range'
    assert math.isclose(result[2], 99373.57636, rel_tol=1e-5), 'Resolution was not in expected range'
    assert math.isclose(result[3], 100688.0, rel_tol=1e-5), 'MAX resolution was not in expected range'
    assert math.isclose(result[4],  99696.0, rel_tol=1e-5), '95p resolution was not in expected range'

def test_import_machine_energy():

    run_id = Tests.insert_run()
    measurement_lines = Tests.import_machine_energy(run_id)

    results = DB().fetch_all('SELECT COUNT(*), AVG(value), MAX(resolution_avg), MAX(resolution_max), MAX(resolution_95p) FROM measurements GROUP BY metric, detail_name, unit')

    assert len(results) == 1, 'Too many entries in table'
    result = results[0]

    assert result[0] == len(measurement_lines)
    assert math.isclose(result[1], 2921.3863, rel_tol=1e-5), 'AVG value not in expected range'
    assert math.isclose(result[2], 101673.76957, rel_tol=1e-5), 'Resolution was not in expected range'
    assert math.isclose(result[3], 107613.0, rel_tol=1e-5), 'MAX resolution was not in expected range'
    assert math.isclose(result[4], 104670.55, rel_tol=1e-5), '95p resolution was not in expected range'

def test_import_cpu_energy():

    run_id = Tests.insert_run()
    measurement_lines = Tests.import_cpu_energy(run_id)

    results = DB().fetch_all('SELECT COUNT(*), AVG(value), MAX(resolution_avg), MAX(resolution_max), MAX(resolution_95p) FROM measurements GROUP BY metric, detail_name, unit')

    assert len(results) == 1, 'Too many entries in table'
    result = results[0]

    assert result[0] == len(measurement_lines)
    assert math.isclose(result[1], 1194.5976, rel_tol=1e-5), 'AVG value not in expected range'
    assert math.isclose(result[2], 99216.78038, rel_tol=1e-5), 'Resolution was not in expected range'
    assert math.isclose(result[3], 107827.0, rel_tol=1e-5), 'MAX resolution was not in expected range'
    assert math.isclose(result[4], 99486.0, rel_tol=1e-5), '95p resolution was not in expected range'
