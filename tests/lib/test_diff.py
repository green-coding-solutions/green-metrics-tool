from lib.db import DB
from tests import test_functions as Tests

# For the diffing to work as expected it is important that we include a known set of columns
# It might happen that at some point a dev adds a column to the table, but forgets to also add it
# to the diffing. To prevent this, this Unit test checks if the table column signature is unchanged
def test_run_signature():

    expected_signature = 'id,job_id,name,uri,branch,commit_hash,commit_timestamp,category_ids,usage_scenario,usage_scenario_variables,filename,relations,machine_specs,runner_arguments,machine_id,gmt_hash,measurement_config,start_measurement,end_measurement,containers,container_dependencies,phases,logs,failed,archived,note,public,user_id,created_at,updated_at'
    # information_schema.columns is not scoped to one schema by default, so without this filter
    # the query matches the 'runs' table in every schema the connection can see (production,
    # gmt_test, and every worker's own gmt_test_gwNNN schema that's accumulated in the Postgres
    # volume across past pytest-xdist runs) - producing one duplicated block of rows per schema.
    # current_schema() ties this to whichever schema this connection's search_path actually
    # resolves to (see get_test_schema()/PGOPTIONS), matching what the test is really meant to check.
    current_signature = DB().fetch_all("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = 'runs' ORDER BY ordinal_position;")
    current_signature = ",".join([x[0] for x in current_signature])

    assert expected_signature == current_signature, \
        Tests.assertion_info('Current signature of "runs" table does not equal expected_signature. Please update the diffing code to maybe include additional columns.', current_signature)
