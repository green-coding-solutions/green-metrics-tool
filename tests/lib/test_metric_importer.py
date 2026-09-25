import math

from tests import test_functions as Tests
from lib.db import DB

def test_import_cpu_utilization_container():

    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    measurement_lines = Tests.import_cpu_utilization_container(run_id)

    results = DB().fetch_all('SELECT COUNT(mm.id), AVG(mv.value) FROM measurement_metrics as mm JOIN measurement_values as mv ON mv.measurement_metric_id = mm.id GROUP BY metric, detail_name, unit')

    assert len(results) == 2, 'Too many entries in table'

    result = results[0]
    assert result[0] == len(measurement_lines)/2 # since we group, length must be divided by groups
    assert math.isclose(result[1], 539.3809, abs_tol=1e-3), 'AVG value not in expected range'

    result = results[1]
    assert result[0] == len(measurement_lines)/2 # since we group, length must be divided by groups
    assert math.isclose(result[1], 39.8095, abs_tol=1e-3), 'AVG value not in expected range'

def test_import_machine_energy():

    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    measurement_lines = Tests.import_machine_energy(run_id)

    results = DB().fetch_all('SELECT COUNT(mm.id), AVG(mv.value) FROM measurement_metrics as mm JOIN measurement_values as mv ON mv.measurement_metric_id = mm.id GROUP BY metric, detail_name, unit')

    assert len(results) == 1, 'Too many entries in table'
    result = results[0]

    assert result[0] == len(measurement_lines)
    assert math.isclose(result[1], 877086855.184, abs_tol=1e-3), 'AVG value not in expected range'

def test_import_cpu_energy():

    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    measurement_lines = Tests.import_cpu_energy(run_id)

    results = DB().fetch_all('SELECT COUNT(mm.id), AVG(mv.value) FROM measurement_metrics as mm JOIN measurement_values as mv ON mv.measurement_metric_id = mm.id GROUP BY metric, detail_name, unit')

    assert len(results) == 1, 'Too many entries in table'
    result = results[0]

    assert result[0] == len(measurement_lines)
    assert math.isclose(result[1], 446780.2100, abs_tol=1e-3), 'AVG value not in expected range'

def test_import_tcpdump_system():

    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    Tests.import_tcpdump_system(run_id)

    results = DB().fetch_all('SELECT run_id, detail_name, metric, stats FROM network_connections_tcpdump WHERE run_id = %s', params=(run_id,))

    assert len(results) == 1, 'system provider must write exactly one row, for the [SYSTEM] group'
    assert results[0][1] == '[SYSTEM]'
    assert results[0][2] == 'network_connections_tcpdump_system'
    assert 'IP: 5.75.242.14' in results[0][3]

    # runs.logs must no longer receive a network_stats entry for this metric
    logs = DB().fetch_one('SELECT logs FROM runs WHERE id = %s', params=(run_id,))[0]
    assert not logs, 'runs.logs must stay empty - tcpdump stats now go to network_connections_tcpdump instead'

def test_import_tcpdump_container():

    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    Tests.import_tcpdump_container(run_id)

    results = DB().fetch_all('SELECT run_id, detail_name, metric, stats FROM network_connections_tcpdump WHERE run_id = %s ORDER BY detail_name', params=(run_id,))

    assert len(results) == 2, 'container provider must write one row per container'
    assert [row[1] for row in results] == ['container-a', 'container-b']
    assert all(row[2] == 'network_connections_tcpdump_container' for row in results)
    assert 'IP: 5.75.242.14' in results[0][3]
    assert 'IP: 10.0.0.5' in results[1][3]
