import os
import re
import orjson
from typing import Annotated
from xml.sax.saxutils import escape as xml_escape
from datetime import date, datetime, timedelta
import pprint

from fastapi import APIRouter, Response, Depends, HTTPException, Request
import anybadge

from api.object_specifications import Software, JobChange, WatchlistChange, RunChange, ArtifactType
from api.api_helpers import (CustomORJSONResponse, ORJSONResponseObjKeep, add_phase_stats_statistics,
                         determine_comparison_case,get_comparison_details, get_common_info,
                         get_phase_stats, get_phase_stats_object, check_run_failed,
                         is_valid_uuid, convert_value, get_timeline_query,
                         get_run_info, get_machine_list, get_artifact, store_artifact,
                         authenticate, check_int_field_api)

from lib.global_config import GlobalConfig
from lib.db import DB
from lib.diff import get_diffable_rows, diff_rows
from lib.job.run import RunJob
from lib.job.email_simple import EmailSimpleJob
from lib.user import User
from lib.watchlist import Watchlist
from lib import utils
from lib import error_helpers
from lib.encryption import EncryptionConfigurationError


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

router = APIRouter()

MAX_PAGE_LIMIT = 100 # maximum amount of rows that can be requested in one call for paginated list endpoints

def check_offset_field_api(offset):
    if not isinstance(offset, int) or offset < 0:
        raise HTTPException(status_code=422, detail='offset must be integer >= 0')
    return True

def paginated_response(data, total, with_count):
    if data is None or data == []:
        if with_count and total: # offset is beyond the last page, but the filter in general matches rows
            return CustomORJSONResponse({'success': True, 'data': [], 'total': total})
        return Response(status_code=204) # No-Content

    if with_count:
        return CustomORJSONResponse({'success': True, 'data': data, 'total': total})
    return CustomORJSONResponse({'success': True, 'data': data})

def parse_usage_scenario_variables(request: Request, usage_scenario_variables: str | None = None) -> dict[str, str] | str | None:
    usage_scenario_variables_pairs = {}

    for key, value in request.query_params.multi_items():
        if key.startswith('usage_scenario_variables[') and key.endswith(']'):
            variable_key = key[25:-1]
            if variable_key.strip() == '':
                raise HTTPException(status_code=422, detail='Usage Scenario Variables key must not be empty')
            usage_scenario_variables_pairs[variable_key] = value

    if usage_scenario_variables_pairs:
        return usage_scenario_variables_pairs

    if usage_scenario_variables is None or usage_scenario_variables.strip() == '':
        return None

    if usage_scenario_variables.strip() == 'false':
        return 'false'

    raise HTTPException(status_code=422, detail='Usage Scenario Variables must be usage_scenario_variables[KEY]=VALUE pairs or the string false')


# Return a list of all known machines in the cluster
@router.get('/v1/machines')
async def get_machines(
    # Endpoint without user restriction on DB. But authenticate() must be present to check if route is allowed in general
    user: User = Depends(authenticate), # pylint: disable=unused-argument
    ):

    data = get_machine_list()
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return CustomORJSONResponse({'success': True, 'data': data})

@router.get('/v1/jobs', deprecated=True)
def old_v1_jobs_endpoint():
    return CustomORJSONResponse({'success': False, 'err': 'This endpoint is deprecated. Please migrate to /v2/jobs'}, status_code=410)


@router.get('/v2/jobs')
async def get_jobs(
    machine_id: int | None = None,
    state: str | None = None,
    job_id: int | None = None,
    user: User = Depends(authenticate),
    ):

    params = [user.is_super_user(), user.visible_users()]
    machine_id_condition = ''
    state_condition = ''
    job_id_condition = ''

    if machine_id and check_int_field_api(machine_id, 'machine_id', 1024):
        machine_id_condition = 'AND j.machine_id = %s'
        params.append(machine_id)

    if state is not None and state != '':
        state_condition = 'AND j.state = %s'
        params.append(state)

    if job_id is not None:
        job_id_condition = 'AND j.id = %s'
        params.append(job_id)


    query = f"""
        SELECT j.id, r.id as run_id, j.name, j.url, j.filename, j.usage_scenario_variables, j.branch, m.description, j.state, j.updated_at, j.created_at, j.category_ids
        FROM jobs as j
        LEFT JOIN machines as m on m.id = j.machine_id
        LEFT JOIN runs as r on r.job_id = j.id
        WHERE
            (TRUE = %s OR j.user_id = ANY(%s::int[]))
            AND j.type = 'run'
            {machine_id_condition}
            {state_condition}
            {job_id_condition}
        ORDER BY j.updated_at DESC, j.created_at ASC
    """
    data = DB().fetch_all(query, params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    # jobs.url is kept unredacted in the DB as the cluster worker needs the real
    # credentials to clone the repo. Redact it here as it is never needed by the client.
    data = [(*row[:3], utils.filter_sensitive_data(row[3]), *row[4:]) for row in data]

    return CustomORJSONResponse({'success': True, 'data': data})

@router.put('/v1/job')
async def update_job(
    job: JobChange,
    user: User = Depends(authenticate),
    ):

    params = [user.is_super_user(), user._id, job.job_id]

    query = '''
        SELECT state
        FROM jobs as j
        WHERE
            (TRUE = %s OR j.user_id = %s)
            AND j.type = 'run'
            AND j.id = %s
    '''

    job_state = DB().fetch_one(query, params)
    if job_state is None or job_state == []:
        raise HTTPException(status_code=422, detail='The job you wanted to change does not exist in the database or is not assigned to your user_id.')

    if job_state[0] == 'RUNNING':
        raise HTTPException(status_code=422, detail='The job you are trying to change is already running and cannot be cancelled anymore.')

    if job_state[0] == 'CANCELLED':
        raise HTTPException(status_code=422, detail='The job you are trying to change is already cancelled.')

    if job_state[0] != 'WAITING':
        raise HTTPException(status_code=422, detail='The job you are trying to change is not in the waiting state anymore and thus cannot be cancelled.')

    if job.action != 'cancel':
        raise HTTPException(status_code=422, detail=f"You are trying to make an unsupported action: {job.action}")

    query = '''
        UPDATE jobs
        SET state = 'CANCELLED'
        WHERE
            (TRUE = %s OR user_id = %s)
            AND type = 'run'
            AND id = %s
    '''

    status_message = DB().query(query, params)
    if status_message == 'UPDATE 1':
        return Response(status_code=202) # Accepted - Further processing happening internally. Not technically correct, but processing in frontend easier.
    else:
        error_helpers.log_error('Job update did return unexpected result', params=params, status_message=status_message)
        raise RuntimeError('Could not update job due to database error')

# A route for deleting watchlist entries
@router.put('/v1/watchlist')
async def update_watchlist(
    change: WatchlistChange,
    user: User = Depends(authenticate),  # consistent with jobs
    ):

    if change.action != 'delete':
        raise HTTPException(status_code=422, detail=f"Unsupported action: {change.action}")

    query = """
        DELETE FROM watchlist
        WHERE id = %s
          AND (TRUE = %s OR user_id = %s)
        RETURNING id
    """
    params = (change.watchlist_id, user.is_super_user(), user._id)
    deleted = DB().fetch_one(query, params=params)

    if not deleted:
        raise HTTPException(status_code=404, detail='Watchlist entry not found or not owned by user')

    return CustomORJSONResponse({'success': True, 'deleted_id': deleted[0]}, status_code=202)

# A route to return all of the available entries in our catalog.
@router.get('/v1/notes/{run_id}')
async def get_notes(run_id, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise HTTPException(status_code=422, detail='Run ID is not a valid UUID or empty')

    query = '''
            SELECT
                n.run_id, n.detail_name, n.note, n.time,
                (-( n.time - LEAD(n.time) OVER (ORDER BY n.time)) / 1_000_000.0)::DOUBLE PRECISION AS duration
            FROM notes as n
            JOIN runs as r on n.run_id = r.id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]) OR r.public = TRUE)
                AND n.run_id = %s
            ORDER BY n.time ASC;
            '''

    params = (user.is_super_user(), user.visible_users(), run_id)
    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponseObjKeep({'success': True, 'data': data})


@router.get('/v1/logs/{run_id}')
async def get_logs(run_id, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise HTTPException(status_code=422, detail='Run ID is not a valid UUID or empty')

    query = '''
            SELECT logs
            FROM runs
            WHERE
                (TRUE = %s OR user_id = ANY(%s::int[]) OR public = TRUE)
                AND id = %s
            '''

    params = (user.is_super_user(), user.visible_users(), run_id)
    data = DB().fetch_one(query, params=params)
    if data is None or not data[0]: # no access or the run did not produce any logs
        return Response(status_code=204) # No-Content

    return ORJSONResponseObjKeep({'success': True, 'data': data[0]})


@router.get('/v1/warnings/{run_id}')
async def get_warnings(run_id, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise HTTPException(status_code=422, detail='Run ID is not a valid UUID or empty')

    query = '''
            SELECT w.run_id, w.message, w.created_at
            FROM warnings as w
            JOIN runs as r on w.run_id = r.id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]) OR r.public = TRUE)
                AND w.run_id = %s
            ORDER BY w.created_at DESC
            '''

    params = (user.is_super_user(), user.visible_users(), run_id)
    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204)

    return ORJSONResponseObjKeep({'success': True, 'data': data})


@router.get('/v1/network/{run_id}')
async def get_network(run_id: str, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        return ORJSONResponseObjKeep({'success': False, 'err': 'Run ID is not a valid UUID or empty'}, status_code=422)

    run = DB().fetch_one(
        '''
            SELECT measurement_config->'configured_metric_providers'
            FROM runs
            WHERE
                (TRUE = %s OR user_id = ANY(%s::int[]) OR public = TRUE)
                AND id = %s
        ''',
        params=(user.is_super_user(), user.visible_users(), run_id)
    )
    if not run:
        return ORJSONResponseObjKeep({'success': False, 'err': 'Run not found'}, status_code=404)

    # 204 must only mean "provider was active, but no connections were made". If the provider was not active
    # we cannot make any statement about network connections and must tell the client.
    # Legacy runs stored the provider under its full module path instead of the metric name
    configured_metric_providers = run[0] or {}
    if not any(
        provider == 'network_connections_proxy_container' or provider.endswith('.NetworkConnectionsProxyContainerProvider')
        for provider in configured_metric_providers
    ):
        # Expected case, so returned directly instead of raising HTTPException, which would log an error
        return ORJSONResponseObjKeep({'success': False, 'err': 'Network connections metric provider was not active for this run'}, status_code=422)

    query = '''
            SELECT ni.*
            FROM network_intercepts as ni
            JOIN runs as r on r.id = ni.run_id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]) OR r.public = TRUE)
                AND ni.run_id = %s
            ORDER BY ni.time
        '''
    params = (user.is_super_user(), user.visible_users(), run_id)
    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponseObjKeep({'success': True, 'data': data})


@router.get('/v1/repositories')
async def get_repositories(
    uri: str | None = None,
    branch: str | None = None,
    machine_id: int | None = None,
    machine: str | None = None,
    filename: str | None = None,
    sort_by: str = 'name',
    show_archived: bool | None = None,
    show_other_users: bool | None = None,
    user: User = Depends(authenticate),
    ):

    query = '''
            SELECT
                r.uri,
                MAX(r.created_at) as last_run
            FROM runs as r
            LEFT JOIN machines as m on r.machine_id = m.id
            WHERE
    '''
    params = []

    # same visibility semantics as /v2/runs, so a repository is only listed if it has runs that /v2/runs would return
    if show_other_users is False:
        query = f"{query} r.user_id = %s  \n"
        params.append(user._id)
    else:
        query = f"{query} (TRUE = %s OR r.user_id = ANY(%s::int[]) OR r.public = TRUE) \n"
        params.append(user.is_super_user())
        params.append(user.visible_users())

    if show_archived is not True:
        query = f"{query} AND r.archived = False \n"

    if uri:
        query = f"{query} AND r.uri LIKE %s  \n"
        params.append(f"%{uri}%")

    if branch:
        query = f"{query} AND r.branch LIKE %s  \n"
        params.append(f"%{branch}%")

    if filename:
        query = f"{query} AND r.filename LIKE %s  \n"
        params.append(f"%{filename}%")

    if machine_id and check_int_field_api(machine_id, 'machine_id', 1024):
        query = f"{query} AND m.id = %s \n"
        params.append(machine_id)

    if machine:
        query = f"{query} AND m.description LIKE %s \n"
        params.append(f"%{machine}%")

    query = f"{query} GROUP BY r.uri\n"

    if sort_by == 'name':
        query = f"{query} ORDER BY r.uri ASC"
    else:
        query = f"{query} ORDER BY last_run DESC"

    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return CustomORJSONResponse({'success': True, 'data': data})


@router.get('/v1/runs', deprecated=True)
def old_v1_runs_endpoint():
    return CustomORJSONResponse({'success': False, 'err': 'This endpoint is deprecated. Please migrate to /v2/runs'}, status_code=410)

# A route to return all of the available entries in our catalog.
@router.get('/v2/runs')
async def get_runs(
    name: str | None = None,
    uri: str | None = None,
    branch: str | None = None,
    machine_id: int | None = None,
    machine: str | None = None,
    filename: str | None = None,
    usage_scenario_variables: str | None = None,
    job_id: int | None = None,
    failed: bool | None = None,
    show_archived: bool | None = None,
    show_other_users: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    with_count: bool = False,
    search: str | None = None,
    order_by: str = 'created_at',
    order_dir: str = 'desc',
    uri_mode = 'none',
    start_date: date | None = None,
    end_date: date | None = None,
    user: User = Depends(authenticate)
    ):

    check_int_field_api(limit, 'limit', MAX_PAGE_LIMIT)
    check_offset_field_api(offset)

    order_columns = {
        'created_at': 'r.created_at',
        'name': 'r.name',
        'uri': 'r.uri',
        'branch': 'r.branch',
        'filename': 'r.filename',
        'machine': 'm.description',
        'commit_hash': 'r.commit_hash',
    }
    if order_by not in order_columns:
        raise HTTPException(status_code=422, detail=f"order_by must be one of {', '.join(order_columns)}")
    if order_dir not in ('asc', 'desc'):
        raise HTTPException(status_code=422, detail='order_dir must be asc or desc')

    where = 'WHERE'
    params = []

    if show_other_users is False:
        where = f"{where} r.user_id = %s  \n"
        params.append(user._id)
    else:
        where = f"{where} (TRUE = %s OR r.user_id = ANY(%s::int[]) or r.public = TRUE) \n"
        params.append(user.is_super_user())
        params.append(user.visible_users())

    if name:
        where = f"{where} AND r.name ILIKE %s  \n"
        params.append(f"%{name}%")

    if uri:
        if uri_mode == 'exact':
            where = f"{where} AND r.uri = %s  \n"
            params.append(uri)
        else:
            where = f"{where} AND r.uri ILIKE %s  \n"
            params.append(f"%{uri}%")

    if branch:
        where = f"{where} AND r.branch ILIKE %s  \n"
        params.append(f"%{branch}%")

    if filename:
        where = f"{where} AND r.filename ILIKE %s  \n"
        params.append(f"%{filename}%")

    if machine_id and check_int_field_api(machine_id, 'machine_id', 1024):
        where = f"{where} AND m.id = %s \n"
        params.append(machine_id)

    if machine:
        where = f"{where} AND m.description ILIKE %s \n"
        params.append(f"%{machine}%")

    if usage_scenario_variables:
        # This query cannot use an index because of the cast
        # at the moment the column has no index, so it must anyway be scanned.
        # But potential target for optimizations if schema changes
        where = f"{where} AND r.usage_scenario_variables::text ILIKE %s \n"
        params.append(f"%{usage_scenario_variables}%")

    if job_id:
        where = f"{where} AND r.job_id = %s \n"
        params.append(job_id)

    if failed is not None:
        where = f"{where} AND r.failed = %s \n"
        params.append(bool(failed))

    if show_archived is not True:
        where = f"{where} AND r.archived = False \n"

    if start_date is not None:
        where = f"{where} AND DATE(r.created_at) >= %s"
        params.append(start_date)

    if end_date is not None:
        where = f"{where} AND DATE(r.created_at) <= %s"
        params.append(end_date)

    if search:
        where = f"""{where} AND (
                r.name ILIKE %s
                OR r.uri ILIKE %s
                OR r.branch ILIKE %s
                OR r.filename ILIKE %s
                OR r.commit_hash ILIKE %s
                OR m.description ILIKE %s
                OR r.usage_scenario_variables::text ILIKE %s
            ) \n"""
        params.extend([f"%{search}%"] * 7)

    query = f'''
            SELECT r.id, r.name, r.uri, r.branch, r.created_at,
            (SELECT COUNT(id) FROM warnings as w WHERE w.run_id = r.id) as warnings,
            r.filename, r.usage_scenario_variables, m.description, r.commit_hash, r.end_measurement, r.failed, r.machine_id, r.relations
            FROM runs as r
            LEFT JOIN machines as m on r.machine_id = m.id
            {where}
            ORDER BY {order_columns[order_by]} {order_dir.upper()}, r.created_at DESC, r.id ASC
            LIMIT %s OFFSET %s
    '''

    data = DB().fetch_all(query, params=[*params, limit, offset])

    total = None
    if with_count:
        count_query = f'''
            SELECT COUNT(*)
            FROM runs as r
            LEFT JOIN machines as m on r.machine_id = m.id
            {where}
        '''
        total = DB().fetch_one(count_query, params=params)[0]

    return paginated_response(data, total, with_count)

# Just copy and paste if we want to deprecate URLs
# @router.get('/v1/measurements/uri', deprecated=True) # Here you can see, that URL is nevertheless accessible as variable
# later if supplied. Also deprecation shall be used once we move to v2 for all v1 routesthrough

@router.get('/v1/compare')
async def compare_in_repo(ids: str, force_mode:str | None = None, user: User = Depends(authenticate)):
    if ids is None or not ids.strip():
        raise HTTPException(status_code=422, detail='run_id is empty')

    ids = ids.split(',')
    if not all(is_valid_uuid(id) for id in ids):
        raise HTTPException(status_code=422, detail='One of Run IDs is not a valid UUID or empty')


    if not force_mode: # force_mode must always get fresh data
        if artifact := get_artifact(ArtifactType.COMPARE, f"{user._id}_{str(ids)}"):
            return CustomORJSONResponse({'success': True, 'data': orjson.loads(artifact)}) # pylint: disable=no-member

    try:
        case, comparison_db_key = determine_comparison_case(user, ids, force_mode=force_mode)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if case == 'Table':
        return Response(
            content='Compare endpoint cannot handle this set of IDs directly. Please redirect to compare-simple.html',
            status_code=409,
            media_type="text/plain",
        )

    comparison_details = get_comparison_details(user, ids, comparison_db_key)

    # check if a run failed

    if check_run_failed(user, ids) >= 1:
        raise HTTPException(status_code=422, detail='At least one run in your runs to compare failed. Comparsion for failed runs is not supported.')


    if not (phase_stats := get_phase_stats(user, ids)):
        return Response(status_code=204) # No-Content

    try:
        phase_stats_object = get_phase_stats_object(phase_stats, case, comparison_details)
        phase_stats_object = add_phase_stats_statistics(phase_stats_object)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    phase_stats_object['common_info'] = get_common_info(user, ids, case)

    if not force_mode: # force_mode must never store data
        store_artifact(ArtifactType.COMPARE, f"{user._id}_{str(ids)}", orjson.dumps(phase_stats_object)) # pylint: disable=no-member


    return CustomORJSONResponse({'success': True, 'data': phase_stats_object})


@router.get('/v1/phase_stats/single/{run_id}')
async def get_phase_stats_single(run_id: str, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise HTTPException(status_code=422, detail='Run ID is not a valid UUID or empty')

    if artifact := get_artifact(ArtifactType.STATS, f"{user._id}_{str(run_id)}"):
        return CustomORJSONResponse({'success': True, 'data': orjson.loads(artifact)}) # pylint: disable=no-member

    if not (phase_stats := get_phase_stats(user, [run_id])):
        return Response(status_code=204) # No-Content

    try:
        phase_stats_object = get_phase_stats_object(phase_stats, None, None, [run_id])
        phase_stats_object = add_phase_stats_statistics(phase_stats_object)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    store_artifact(ArtifactType.STATS, f"{user._id}_{str(run_id)}", orjson.dumps(phase_stats_object)) # pylint: disable=no-member

    return ORJSONResponseObjKeep({'success': True, 'data': phase_stats_object})


# This route gets the measurements to be displayed in a timeline chart
@router.get('/v1/measurements/single/{run_id}')
async def get_measurements_single(run_id: str, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise HTTPException(status_code=422, detail='Run ID is not a valid UUID or empty')

    query = '''
            SELECT
                mm.detail_name, mv.time, mm.metric,
                   mv.value, mm.unit
            FROM measurement_metrics as mm
            JOIN measurement_values as mv ON mv.measurement_metric_id = mm.id
            JOIN runs as r ON mm.run_id = r.id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]) or r.public = TRUE)
                AND mm.run_id = %s
    '''

    params = (user.is_super_user(), user.visible_users(), run_id)

    # extremely important to order here, cause the charting library in JS cannot do that automatically!
    # Furthermore we do time-lag caclulations and need the order of metric first and then time in stats.js:179... . Please do not change
    query = f"{query} ORDER BY mm.metric ASC, mm.detail_name ASC, mv.time ASC"

    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponseObjKeep({'success': True, 'data': data})

@router.get('/v1/timeline', deprecated=True)
async def get_timeline_stats(
    uri: str, machine_id: int, branch: str | None = None, filename: str | None = None,
    metric: str | None = None, phase: str | None = None,
    show_archived: bool | None = None,
    start_date: date | None = None, end_date: date | None = None,  sorting: str | None = None,
    usage_scenario_variables: Annotated[dict[str, str] | str | None, Depends(parse_usage_scenario_variables)] = None,
    user: User = Depends(authenticate)
    ):

    if uri is None or uri.strip() == '':
        raise HTTPException(status_code=422, detail='URI is empty')

    if phase is None or phase.strip() == '':
        raise HTTPException(status_code=422, detail='Phase is empty')

    check_int_field_api(machine_id, 'machine_id', 1024) # can cause exception
    query, params = get_timeline_query(user, uri, filename, usage_scenario_variables, machine_id, branch, metric, phase, start_date=start_date, end_date=end_date, sorting=sorting, show_archived=show_archived)

    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return CustomORJSONResponse({'success': True, 'data': data})

@router.get('/v2/timeline')
async def get_timeline_stats_v2(
    uri: str, machine_id: int, branch: str | None = None, filename: str | None = None,
    metric: str | None = None, phase: str | None = None,
    show_archived: bool | None = None,
    start_date: date | None = None, end_date: date | None = None,  sorting: str | None = None,
    usage_scenario_variables: Annotated[dict[str, str] | str | None, Depends(parse_usage_scenario_variables)] = None,
    user: User = Depends(authenticate)
    ):

    if uri is None or uri.strip() == '':
        raise HTTPException(status_code=422, detail='URI is empty')

    if phase is None or phase.strip() == '':
        raise HTTPException(status_code=422, detail='Phase is empty')

    check_int_field_api(machine_id, 'machine_id', 1024) # can cause exception
    query, params = get_timeline_query(user, uri, filename, usage_scenario_variables, machine_id, branch, metric, phase, start_date=start_date, end_date=end_date, sorting=sorting, show_archived=show_archived, include_usage_scenario_variables=True)

    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return CustomORJSONResponse({'success': True, 'data': data})

# Show the timeline badges with regression trend
## A complex case to allow public visibility of the badge but restricting everything else would be to have
## User 1 restricted to only this route but a fully populated 'visible_users' array
##
## Technically we allow detail_name to not be mandatory. But a regression over two CPU cores where one is not used and one is increasing in use can lead to
## an unexpected result because they occur at same timepoints but the trend assumes them to be at sequential timepoints.
## You might get unexpected results, but generally it is desireable to have a regression of all CPU cores for instance forthe cpu energy reporter
@router.get('/v1/badge/timeline')
async def get_timeline_badge(
    metric: str, uri: str,
    unit: str = 'watt-hours',
    detail_name: str | None = None, machine_id: int | None = None, branch: str | None = None, filename: str | None = None,
    show_archived: bool | None = None,
    usage_scenario_variables: Annotated[dict[str, str] | str | None, Depends(parse_usage_scenario_variables)] = None,
    user: User = Depends(authenticate),
    ):

    if uri is None or uri.strip() == '':
        raise HTTPException(status_code=422, detail='URI is empty')

    if metric is None or metric.strip() == '':
        raise HTTPException(status_code=422, detail='Metric is mandatory')

    if machine_id is not None:
        check_int_field_api(machine_id, 'machine_id', 1024) # can cause exception


    if unit not in ('watt-hours', 'joules'):
        raise HTTPException(status_code=422, detail='Requested unit is not in allow list: watt-hours, joules')
    # we believe that there is no injection possible to the artifact store and any string can be constructured here ...
    if artifact := get_artifact(ArtifactType.BADGE, f"{user._id}_{uri}_{filename}_{machine_id}_{branch}_{metric}_{detail_name}_{unit}"):
        return Response(content=str(artifact), media_type="image/svg+xml")

    date_30_days_ago = datetime.now() - timedelta(days=30)

    query, params = get_timeline_query(user, uri, filename, usage_scenario_variables, machine_id, branch, metric, '[RUNTIME]', detail_name=detail_name, start_date=date_30_days_ago.strftime('%Y-%m-%d'), end_date=datetime.now(), show_archived=show_archived)
    # query already contains user access check. No need to have it in aggregate query too
    query = f"""
        WITH trend_data AS (
            {query}
        ) SELECT
          MAX(row_num::float),
          regr_slope(value, row_num::float) AS trend_slope,
          regr_intercept(value, row_num::float) AS trend_intercept,
          MAX(unit), -- this is a hack to infert the unit from an unknown metric. We prevent mixing by requiring metric and detail_name
          COUNT (DISTINCT(unit)) -- our safeguard
        FROM trend_data;
    """

    data = DB().fetch_one(query, params=params)

    if data is None or data == [] or data[1] is None: # special check for data[1] as this is aggregate query which always returns result
        return Response(status_code=204) # No-Content

    if data[4] != 1:
        error_helpers.log_error('Your request tried to request metrics over different units. This is not allowed. Please apply more metric and detail_name filters.', query=query, params=params)
        return Response('Your request tried to request metrics over different units. This is not allowed. Please apply more metric and detail_name filters.', status_code=422) # manual Response as we log error separately

    cost = data[1]
    display_in_joules = (unit == 'joules') #pylint: disable=superfluous-parens
    [rescaled_cost, rescaled_unit] = convert_value(cost, data[3], display_in_joules)
    rescaled_cost = f"+{rescaled_cost:.2f}" if abs(cost) == cost else f"{rescaled_cost:.2f}"

    badge = anybadge.Badge(
        label=xml_escape('Run Trend'),
        value=xml_escape(f"{rescaled_cost} {rescaled_unit} per run"),
        num_value_padding_chars=1,
        default_color='orange')

    badge_str = str(badge)

    store_artifact(ArtifactType.BADGE, f"{user._id}_{uri}_{filename}_{machine_id}_{branch}_{metric}_{detail_name}_{unit}", badge_str, ex=60*60*12) # 12 hour storage

    return Response(content=badge_str, media_type="image/svg+xml")


# Return a badge for a single metric of a single run
## A complex case to allow public visibility of the badge but restricting everything else would be to have
## User 1 restricted to only this route but a fully populated 'visible_users' array
@router.get('/v1/badge/single/{run_id}')
async def get_badge_single(run_id: str, metric: str = 'cpu_energy_rapl_msr_component', unit: str = 'watt-hours', phase: str | None = None, user: User = Depends(authenticate)):

    if run_id is None or not is_valid_uuid(run_id):
        raise HTTPException(status_code=422, detail='Run ID is not a valid UUID or empty')

    if unit not in ('watt-hours', 'joules'):
        raise HTTPException(status_code=422, detail='Requested unit is not in allow list: watt-hours, joules')

    if phase:
        phase_label = phase
        phase = f"%_{phase}"
    else:
        phase_label = None
        phase = '%_[RUNTIME]'

    # we believe that there is no injection possible to the artifact store and any string can be constructured here ...
    if artifact := get_artifact(ArtifactType.BADGE, f"{user._id}_{run_id}_{metric}_{unit}_{phase}"):
        return Response(content=str(artifact), media_type="image/svg+xml")

    query = '''
        SELECT
            SUM(ps.value), MAX(ps.unit), MAX(ps.type), COUNT (DISTINCT(ps.unit))
        FROM
            phase_stats as ps
        JOIN
            runs as r ON ps.run_id = r.id
        WHERE
            (TRUE = %s OR r.user_id = ANY(%s::int[]) OR r.public = TRUE)
            AND ps.run_id = %s
            AND ps.metric = %s
            AND ps.phase LIKE %s
    '''

    params = [user.is_super_user(), user.visible_users(), run_id, metric, phase]

    data = DB().fetch_one(query, params=params)

    if data is None or data == [] or data[1] is None: # special check for data[1] as this is aggregate query which always returns result
        return Response(status_code=204) # No-Content
    else:
        if data[2] != 'TOTAL':
            error_helpers.log_error('Your request tried to request a metric that is averaged. Only metrics that can be totaled (like energy, network, carbon etc.) can be requested. Please select a different metric.', query=query, params=params)
            return Response('Your request tried to request a metric that is averaged. Only metrics that can be totaled (like energy, network, carbon etc.) can be requested. Please select a different metric.', status_code=422) # manual Response as we log error separately

        if data[3] != 1:
            error_helpers.log_error('Your request tried to request metrics over different units. This is not allowed. Please apply more metric and detail_name filters.', query=query, params=params)
            return Response('Your request tried to request metrics over different units. This is not allowed. Please apply more metric and detail_name filters.', status_code=422) # manual Response as we log error separately

        display_in_joules = (unit == 'joules') #pylint: disable=superfluous-parens
        [metric_value, energy_unit] = convert_value(data[0], data[1], display_in_joules)
        badge_value= f"{metric_value:.2f} {energy_unit}"

    # now we capture the nice name from a javascript file!!

    with open(f"{CURRENT_DIR}/../frontend/js/helpers/config.js", 'r', encoding='utf-8') as file:
        content = file.read()

    matches = re.findall(r"METRIC_MAPPINGS\s*=\s*(\{.*\}) \/\/ PLEASE DO NOT REMOVE THIS COMMENT -- END METRIC_MAPPINGS", content, re.DOTALL)

    nice_name_dict = orjson.loads(matches[0]).get(metric, None) # pylint: disable=no-member
    if nice_name_dict:
        nice_name = nice_name_dict.get('clean_name', metric)
    else:
        nice_name = metric

    if phase_label:
        nice_name = f"{nice_name} {{{phase_label}}}"

    if '_energy_' in metric:
        color = 'cornflowerblue'
    elif '_carbon_' in metric:
        color = 'black'
    elif '_power_' in metric:
        color = 'orange'
    else:
        color = 'teal'

    badge = anybadge.Badge(
        label=xml_escape(nice_name),
        value=xml_escape(badge_value),
        num_value_padding_chars=1,
        default_color=color)

    badge_str = str(badge)

    store_artifact(ArtifactType.BADGE, f"{user._id}_{run_id}_{metric}_{unit}_{phase}", badge_str)

    return Response(content=badge_str, media_type="image/svg+xml")


@router.get('/v1/watchlist')
async def get_watchlist(user: User = Depends(authenticate)):
    # Do not get the email jobs as they do not need to be display in the frontend atm
    # Also do not get the email field for privacy
    query = '''
        SELECT
            tp.id, tp.name, tp.image_url, tp.repo_url,
            (
                SELECT STRING_AGG(t.name, ', ' )
                FROM unnest(tp.category_ids) as elements
                LEFT JOIN categories as t on t.id = elements
            ) as categories,
            tp.branch, tp.filename, tp.machine_id, m.description, tp.schedule_mode, tp.last_scheduled, tp.created_at, tp.updated_at,
            (
                SELECT created_at
                FROM runs as r
                WHERE
                    tp.repo_url = r.uri
                    AND tp.branch = r.branch
                    AND tp.filename = r.filename
                    AND tp.machine_id = r.machine_id
                    AND tp.usage_scenario_variables = r.usage_scenario_variables
                ORDER BY r.created_at DESC
                LIMIT 1
            ) as "last_run",
            tp.usage_scenario_variables
        FROM watchlist as tp
        LEFT JOIN machines as m ON m.id = tp.machine_id
        WHERE
            (TRUE = %s OR tp.user_id = ANY(%s::int[]))
        ORDER BY tp.repo_url ASC;
    '''
    params = (user.is_super_user(), user.visible_users(),)
    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return CustomORJSONResponse({'success': True, 'data': data})


@router.post('/v1/runs/add')
async def runs_add(software: Software, no_url_check: bool = False, user: User = Depends(authenticate)):

    if software.name is None or software.name.strip() == '':
        raise HTTPException(status_code=422, detail='Name is empty')

    # Note that we use uri as the general identifier, however when adding through web interface we only allow urls
    if software.repo_url is None or software.repo_url.strip() == '':
        raise HTTPException(status_code=422, detail='URL is empty')

    if software.image_url is None:
        software.image_url = ''

    if software.email is not None and software.email.strip() == '':
        software.email = None

    if software.branch is None or software.branch.strip() == '':
        software.branch = 'main'

    if software.commit_hash is not None and software.commit_hash.strip() == '':
        software.commit_hash = None

    if software.filename is None or software.filename.strip() == '':
        software.filename = 'usage_scenario.yml'

    if software.usage_scenario_variables is None:
        software.usage_scenario_variables = {}

    unique_category_ids = None
    if software.category_ids:
        result = DB().fetch_one("SELECT array_agg(id) FROM categories WHERE id = ANY(%s)", (software.category_ids,))[0]
        if not result:
            raise HTTPException(status_code=422, detail=f"Categories not known: {software.category_ids}")

        existing_ids = set(result)
        unique_category_ids = set(software.category_ids) # deduplicate
        unknown_ids = unique_category_ids - existing_ids
        if unknown_ids:
            raise HTTPException(status_code=422, detail=f"Categories not known: {unknown_ids}")
        unique_category_ids = list(unique_category_ids) # transform back to list so we can insert it. psycopg does not understand sets

    if not DB().fetch_one('SELECT id FROM machines WHERE id=%s AND available=TRUE', params=(software.machine_id,)):
        raise HTTPException(status_code=422, detail='Machine does not exist')

    if not user.can_use_machine(software.machine_id):
        raise HTTPException(status_code=422, detail='Your user does not have the permissions to use that machine.')

    if software.schedule_mode not in ['one-off', 'daily', 'weekly', 'commit', 'commit-variance', 'tag', 'tag-variance', 'variance', 'statistical-significance']:
        raise HTTPException(status_code=422, detail=f"Please select a valid measurement interval. ({software.schedule_mode}) is unknown.")

    if not user.can_schedule_job(software.schedule_mode):
        raise HTTPException(status_code=422, detail='Your user does not have the permissions to use that schedule mode.')

    if not no_url_check:
        try:
            utils.check_repo(software.repo_url, software.branch) # if it exists through the git api
        except Exception as exc:
            raise HTTPException(status_code=422, detail=utils.filter_sensitive_data(str(exc))) from exc

    unencrypted_repo_url = software.repo_url
    try:
        software.repo_url = utils.encrypt_uri_credentials(software.repo_url)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=422, detail='Cannot store URL credentials: encryption is not configured on this server') from exc

    try:
        software.usage_scenario_variables = utils.encrypt_secret_usage_scenario_variables(software.usage_scenario_variables)
    except EncryptionConfigurationError as exc:
        raise HTTPException(status_code=422, detail='Cannot store secret usage scenario variables: encryption is not configured on this server') from exc

    if software.schedule_mode in ['daily', 'weekly', 'commit', 'commit-variance', 'tag', 'tag-variance']:

        last_marker = None
        if not no_url_check:
            try:
                if 'tag' in software.schedule_mode:
                    last_marker = utils.get_repo_last_marker(unencrypted_repo_url, 'tags')

                if 'commit' in software.schedule_mode:
                    last_marker = utils.get_repo_last_marker(unencrypted_repo_url, 'commits')
            except RuntimeError as exc:
                raise HTTPException(status_code=422, detail=utils.filter_sensitive_data(str(exc))) from exc

        Watchlist.insert(name=software.name, email=software.email, image_url=software.image_url, repo_url=software.repo_url, branch=software.branch, filename=software.filename, machine_id=software.machine_id, usage_scenario_variables=software.usage_scenario_variables, category_ids=unique_category_ids, carbon_simulation=software.carbon_simulation, user_id=user._id, schedule_mode=software.schedule_mode, last_marker=last_marker)

    job_ids_inserted = []

    if 'variance' in software.schedule_mode:
        amount = 3
    elif software.schedule_mode == 'statistical-significance':
        amount = 10
    else: # even for Watchlist items we do at least one run directly
        amount = 1

    for _ in range(0,amount):
        job_ids_inserted.append(RunJob.insert(user_id=user._id, name=software.name, url=software.repo_url, email=software.email, branch=software.branch, commit_hash=software.commit_hash, filename=software.filename, machine_id=software.machine_id, usage_scenario_variables=software.usage_scenario_variables, category_ids=unique_category_ids, carbon_simulation=software.carbon_simulation))

    # notify admin of new add
    if notification_email := GlobalConfig().config['admin']['notification_email']:
        EmailSimpleJob.insert(user_id=user._id, name='New run added from Web Interface', message=pprint.pformat(software.model_dump(), width=60, indent=2), email=notification_email)

    return CustomORJSONResponse({'success': True, 'data': job_ids_inserted}, status_code=202)

@router.get('/v1/run/{run_id}', deprecated=True)
def old_v1_run_endpoint():
    return CustomORJSONResponse({'success': False, 'err': 'This endpoint is deprecated. Please migrate to /v2/run/{run_id}'}, status_code=410)


@router.get('/v2/run/{run_id}')
async def get_run(run_id: str, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise HTTPException(status_code=422, detail='Run ID is not a valid UUID or empty')
    try:
        data = get_run_info(user, run_id)
    except HTTPException as err:
        return ORJSONResponseObjKeep({'success': False, 'data': err.detail}, status_code=err.status_code)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponseObjKeep({'success': True, 'data': data})

@router.put('/v1/run/{run_id}')
def update_run(
    run_id: str,
    run: RunChange,
    user: User = Depends(authenticate),
    ):

    if run_id is None or not is_valid_uuid(run_id):
        raise HTTPException(status_code=422, detail='Run ID is not a valid UUID or empty')

    columns = []
    params = []

    if run.archived is not None:
        columns.append('archived = %s')
        params.append(run.archived)

    if run.note is not None:
        columns.append('note = %s')
        params.append(run.note.strip())

    if run.public is not None:
        columns.append('public = %s')
        params.append(run.public)

    if not columns:
        raise HTTPException(status_code=422, detail='No data submitted in PUT request to change run with. Please submit data.')

    set_columns = ',\n'.join(columns)
    query = f"""
        UPDATE runs
        SET
            {set_columns}
        WHERE
            (TRUE = %s OR user_id = %s)
            AND id = %s
        RETURNING id;
    """

    params.append(user.is_super_user())
    params.append(user._id)
    params.append(run_id)
    updated = DB().fetch_one(query, params=params)

    if not updated:
        raise HTTPException(status_code=404, detail='Run not found or not owned by user')

    return Response(status_code=202) # No-Content


@router.get('/v1/optimizations/{run_id}')
async def get_optimizations(run_id: str, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise HTTPException(status_code=422, detail='Run ID is not a valid UUID or empty')

    query = '''
            SELECT o.title, o.label, o.criticality, o.reporter, o.icon, o.description, o.link
            FROM optimizations as o
            JOIN runs as r ON o.run_id = r.id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]) OR r.public = TRUE)
                AND o.run_id = %s
    '''

    params = (user.is_super_user(), user.visible_users(), run_id)
    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponseObjKeep({'success': True, 'data': data})



@router.get('/v1/diff')
async def diff(ids: str, user: User = Depends(authenticate)):
    if ids is None or not ids.strip():
        raise HTTPException(status_code=422, detail='run_ids are empty')
    ids = ids.split(',')
    if not all(is_valid_uuid(id) for id in ids):
        raise HTTPException(status_code=422, detail='One of Run IDs is not a valid UUID or empty')
    if len(ids) != 2:
        raise HTTPException(status_code=422, detail='Run IDs != 2. Only exactly 2 Run IDs can be diffed.')

    if artifact := get_artifact(ArtifactType.DIFF, f"{user._id}_{str(ids)}"):
        return CustomORJSONResponse({'success': True, 'data': artifact})

    try:
        diff_runs = diff_rows(get_diffable_rows(user, ids))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    store_artifact(ArtifactType.DIFF, f"{user._id}_{str(ids)}", diff_runs)

    return CustomORJSONResponse({'success': True, 'data': diff_runs})


@router.get('/v1/insights')
async def get_insights(user: User = Depends(authenticate)):

    query = '''
            SELECT COUNT(id), DATE(MIN(created_at))
            FROM runs
            WHERE (TRUE = %s OR user_id = ANY(%s::int[]))
    '''

    params = (user.is_super_user(), user.visible_users())
    data = DB().fetch_one(query, params=params)

    if data is None:
        return Response(status_code=204) # No-Content

    return ORJSONResponseObjKeep({'success': True, 'data': data})
