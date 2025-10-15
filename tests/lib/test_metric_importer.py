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
    assert math.isclose(result[1], 539.3809, rel_tol=1e-5), 'AVG value not in expected range'

    result = results[1]
    assert result[0] == len(measurement_lines)/2 # since we group, length must be divided by groups
    assert math.isclose(result[1], 39.8095, rel_tol=1e-5), 'AVG value not in expected range'

def test_import_machine_energy():

    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    measurement_lines = Tests.import_machine_energy(run_id)

    results = DB().fetch_all('SELECT COUNT(mm.id), AVG(mv.value) FROM measurement_metrics as mm JOIN measurement_values as mv ON mv.measurement_metric_id = mm.id GROUP BY metric, detail_name, unit')

    assert len(results) == 1, 'Too many entries in table'
    result = results[0]

    assert result[0] == len(measurement_lines)
    assert math.isclose(result[1], 877086510.4527, rel_tol=1e-5), 'AVG value not in expected range'


def test_import_cpu_energy():

    run_id = Tests.insert_run(Tests.TEST_MEASUREMENT_PHASES)
    measurement_lines = Tests.import_cpu_energy(run_id)

    results = DB().fetch_all('SELECT COUNT(mm.id), AVG(mv.value) FROM measurement_metrics as mm JOIN measurement_values as mv ON mv.measurement_metric_id = mm.id GROUP BY metric, detail_name, unit')

    assert len(results) == 1, 'Too many entries in table'
    result = results[0]

    assert result[0] == len(measurement_lines)
    assert math.isclose(result[1], 446780.2100, rel_tol=1e-5), 'AVG value not in expected range'
