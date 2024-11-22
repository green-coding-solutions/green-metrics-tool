from lib.db import DB
from tests import test_functions as Tests

# For the diffing to work as expected it is important that we include a known set of columns
# It might happen that at some point a dev adds a column to the table, but forgets to also add it
# to the diffing. To prevent this, this Unit test checks if the table column signature is unchanged
def test_run_signature():

    expected_signature = 'id,job_id,name,uri,branch,commit_hash,commit_timestamp,email,categories,usage_scenario,filename,machine_specs,runner_arguments,machine_id,gmt_hash,measurement_config,start_measurement,end_measurement,phases,logs,invalid_run,failed,user_id,created_at,updated_at'
    current_signature = DB().fetch_all("SELECT column_name FROM information_schema.columns WHERE table_name = 'runs' ORDER BY ordinal_position;")
    current_signature = ",".join([x[0] for x in current_signature])

    assert expected_signature == current_signature, \
        Tests.assertion_info('Current signature of "runs" table does not equal expected_signature. Please update the diffing code to maybe include additional columns.', current_signature)
