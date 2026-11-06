from unittest.mock import patch, call

from cron import backfill_geo

def test_ip_of_row_with_own_coordinates_is_looked_up_without_changing_the_row():
    with patch.object(backfill_geo, 'DB') as db_mock, patch.object(backfill_geo, 'get_geo') as get_geo_mock:
        db_mock.return_value.fetch_all.return_value = [('8.8.8.8',), ('1.1.1.1',)]
        backfill_geo.process_missing_country()

    assert get_geo_mock.call_args_list == [call('8.8.8.8'), call('1.1.1.1')]
    db_mock.return_value.query.assert_not_called() # the coordinates of the client must stay

def test_private_ip_is_skipped():
    with patch.object(backfill_geo, 'DB') as db_mock, patch.object(backfill_geo, 'get_geo') as get_geo_mock:
        db_mock.return_value.fetch_all.return_value = [('192.168.0.1',), ('8.8.8.8',)]
        backfill_geo.process_missing_country()

    assert get_geo_mock.call_args_list == [call('8.8.8.8')]

def test_no_rows_do_no_lookup():
    with patch.object(backfill_geo, 'DB') as db_mock, patch.object(backfill_geo, 'get_geo') as get_geo_mock:
        db_mock.return_value.fetch_all.return_value = None
        backfill_geo.process_missing_country()

    get_geo_mock.assert_not_called()

def test_only_rows_with_own_coordinates_and_no_intensity_or_ip_data_are_selected():
    with patch.object(backfill_geo, 'DB') as db_mock:
        db_mock.return_value.fetch_all.return_value = []
        backfill_geo.fetch_ips_missing_country()

    query = db_mock.return_value.fetch_all.call_args.args[0]
    assert 'from_table.latitude IS NOT NULL' in query
    assert 'from_table.longitude IS NOT NULL' in query
    assert 'from_table.carbon_intensity_g IS NULL' in query
    assert 'NOT EXISTS (SELECT 1 FROM ip_data' in query
