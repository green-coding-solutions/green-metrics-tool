
import orjson
from xml.sax.saxutils import escape as xml_escape
from datetime import date

from fastapi import APIRouter, Response, Depends
from fastapi.responses import ORJSONResponse
from fastapi.exceptions import RequestValidationError

import anybadge

from api.object_specifications import Software
from api.api_helpers import (ORJSONResponseObjKeep, add_phase_stats_statistics,
                         determine_comparison_case,get_comparison_details,
                         html_escape_multi, get_phase_stats, get_phase_stats_object,
                         is_valid_uuid, convert_value, get_timeline_query,
                         get_run_info, get_machine_list, get_artifact, store_artifact,
                         authenticate, check_int_field_api)

from lib.global_config import GlobalConfig
from lib.db import DB
from lib.diff import get_diffable_rows, diff_rows
from lib.job.base import Job
from lib.user import User
from lib.watchlist import Watchlist
from lib import utils

from enum import Enum
ArtifactType = Enum('ArtifactType', ['DIFF', 'COMPARE', 'STATS', 'BADGE'])


router = APIRouter()


# Return a list of all known machines in the cluster
@router.get('/v1/machines')
async def get_machines(
    user: User = Depends(authenticate), # pylint: disable=unused-argument
    ):

    data = get_machine_list()
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})

@router.get('/v1/jobs')
async def get_jobs(
    machine_id: int | None = None,
    state: str | None = None,
    user: User = Depends(authenticate), # pylint: disable=unused-argument
    ):

    params = [user.is_super_user(), user.visible_users()]
    machine_id_condition = ''
    state_condition = ''

    if machine_id and check_int_field_api(machine_id, 'machine_id', 1024):
        machine_id_condition = 'AND j.machine_id = %s'
        params.append(machine_id)

    if state is not None and state != '':
        state_condition = 'AND j.state = %s'
        params.append(state)

    query = f"""
        SELECT j.id, r.id as run_id, j.name, j.url, j.filename, j.branch, m.description, j.state, j.updated_at, j.created_at
        FROM jobs as j
        LEFT JOIN machines as m on m.id = j.machine_id
        LEFT JOIN runs as r on r.job_id = j.id
        WHERE
            (TRUE = %s OR j.user_id = ANY(%s::int[]))
            AND j.type = 'run'
            {machine_id_condition}
            {state_condition}
        ORDER BY j.updated_at DESC, j.created_at ASC
    """
    data = DB().fetch_all(query, params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})

# A route to return all of the available entries in our catalog.
@router.get('/v1/notes/{run_id}')
async def get_notes(run_id, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    query = '''
            SELECT n.run_id, n.detail_name, n.note, n.time
            FROM notes as n
            JOIN runs as r on n.run_id = r.id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]))
                AND n.run_id = %s
            ORDER BY n.created_at DESC  -- important to order here, the charting library in JS cannot do that automatically!
            '''

    params = (user.is_super_user(), user.visible_users(), run_id)
    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    escaped_data = [html_escape_multi(note) for note in data]
    return ORJSONResponseObjKeep({'success': True, 'data': escaped_data})


@router.get('/v1/network/{run_id}')
async def get_network(run_id, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    query = '''
            SELECT ni.*
            FROM network_intercepts as ni
            JOIN runs as r on r.id = ni.run_id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]))
                AND ni.run_id = %s
            ORDER BY ni.time
    '''
    params = (user.is_super_user(), user.visible_users(), run_id)
    data = DB().fetch_all(query, params=params)

    escaped_data = html_escape_multi(data)
    return ORJSONResponseObjKeep({'success': True, 'data': escaped_data})


@router.get('/v1/repositories')
async def get_repositories(uri: str | None = None, branch: str | None = None, machine_id: int | None = None, machine: str | None = None, filename: str | None = None, sort_by: str = 'name', user: User = Depends(authenticate)):
    query = '''
            SELECT
                r.uri,
                MAX(r.created_at) as last_run
            FROM runs as r
            LEFT JOIN machines as m on r.machine_id = m.id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]))
    '''

    params = [user.is_super_user(), user.visible_users()]

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

    escaped_data = [html_escape_multi(run) for run in data]

    return ORJSONResponse({'success': True, 'data': escaped_data})


# A route to return all of the available entries in our catalog.
@router.get('/v1/runs')
async def get_runs(uri: str | None = None, branch: str | None = None, machine_id: int | None = None, machine: str | None = None, filename: str | None = None, limit: int = 5, uri_mode = 'none', user: User = Depends(authenticate)):

    query = '''
            SELECT r.id, r.name, r.uri, r.branch, r.created_at, r.invalid_run, r.filename, m.description, r.commit_hash, r.end_measurement, r.failed, r.machine_id
            FROM runs as r
            LEFT JOIN machines as m on r.machine_id = m.id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]))
    '''
    params = [user.is_super_user(), user.visible_users()]

    if uri:
        if uri_mode == 'exact':
            query = f"{query} AND r.uri = %s  \n"
            params.append(uri)
        else:
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

    query = f"{query} ORDER BY r.created_at DESC"

    check_int_field_api(limit, 'limit', 50)
    query = f"{query} LIMIT %s"
    params.append(limit)


    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    escaped_data = [html_escape_multi(run) for run in data]

    return ORJSONResponse({'success': True, 'data': escaped_data})


# Just copy and paste if we want to deprecate URLs
# @router.get('/v1/measurements/uri', deprecated=True) # Here you can see, that URL is nevertheless accessible as variable
# later if supplied. Also deprecation shall be used once we move to v2 for all v1 routesthrough

@router.get('/v1/compare')
async def compare_in_repo(ids: str, user: User = Depends(authenticate)):
    if ids is None or not ids.strip():
        raise RequestValidationError('run_id is empty')
    ids = ids.split(',')
    if not all(is_valid_uuid(id) for id in ids):
        raise RequestValidationError('One of Run IDs is not a valid UUID or empty')


    if artifact := get_artifact(ArtifactType.COMPARE, f"{user._id}_{str(ids)}"):
        return ORJSONResponse({'success': True, 'data': orjson.loads(artifact)}) # pylint: disable=no-member

    try:
        case, comparison_db_key = determine_comparison_case(user, ids)
    except RuntimeError as exc:
        raise RequestValidationError(str(exc)) from exc

    comparison_details = get_comparison_details(user, ids, comparison_db_key)

    if not (phase_stats := get_phase_stats(user, ids)):
        return Response(status_code=204) # No-Content

    try:
        phase_stats_object = get_phase_stats_object(phase_stats, case, comparison_details)
        phase_stats_object = add_phase_stats_statistics(phase_stats_object)
    except ValueError as exc:
        raise RequestValidationError(str(exc)) from exc

    phase_stats_object['common_info'] = {}

    try:
        run_info = get_run_info(user, ids[0])

        machine_list = get_machine_list()
        machines = {machine[0]: machine[1] for machine in machine_list}

        machine = machines[run_info['machine_id']]
        uri = run_info['uri']
        usage_scenario = run_info['usage_scenario']['name']
        branch = run_info['branch']
        commit = run_info['commit_hash']
        filename = run_info['filename']

        match case:
            case 'Repeated Run':
                # same repo, same usage scenarios, same machines, same branches, same commit hashes
                phase_stats_object['common_info']['Repository'] = uri
                phase_stats_object['common_info']['Filename'] = filename
                phase_stats_object['common_info']['Usage Scenario'] = usage_scenario
                phase_stats_object['common_info']['Machine'] = machine
                phase_stats_object['common_info']['Branch'] = branch
                phase_stats_object['common_info']['Commit'] = commit
            case 'Usage Scenario':
                # same repo, diff usage scenarios, same machines, same branches, same commit hashes
                phase_stats_object['common_info']['Repository'] = uri
                phase_stats_object['common_info']['Machine'] = machine
                phase_stats_object['common_info']['Branch'] = branch
                phase_stats_object['common_info']['Commit'] = commit
            case 'Machine':
                # same repo, same usage scenarios, diff machines, same branches, same commit hashes
                phase_stats_object['common_info']['Repository'] = uri
                phase_stats_object['common_info']['Filename'] = filename
                phase_stats_object['common_info']['Usage Scenario'] = usage_scenario
                phase_stats_object['common_info']['Branch'] = branch
                phase_stats_object['common_info']['Commit'] = commit
            case 'Commit':
                # same repo, same usage scenarios, same machines, diff commit hashes
                phase_stats_object['common_info']['Repository'] = uri
                phase_stats_object['common_info']['Filename'] = filename
                phase_stats_object['common_info']['Usage Scenario'] = usage_scenario
                phase_stats_object['common_info']['Machine'] = machine
            case 'Repository':
                # diff repo, diff usage scenarios, same machine,  same branches, diff/same commits_hashes
                phase_stats_object['common_info']['Machine'] = machine
                phase_stats_object['common_info']['Branch'] = branch
            case 'Branch':
                # same repo, same usage scenarios, same machines, diff branch
                phase_stats_object['common_info']['Repository'] = uri
                phase_stats_object['common_info']['Filename'] = filename
                phase_stats_object['common_info']['Usage Scenario'] = usage_scenario
                phase_stats_object['common_info']['Machine'] = machine

    except RuntimeError as err:
        raise RequestValidationError(str(err)) from err

    store_artifact(ArtifactType.COMPARE, f"{user._id}_{str(ids)}", orjson.dumps(phase_stats_object)) # pylint: disable=no-member


    return ORJSONResponse({'success': True, 'data': phase_stats_object})


@router.get('/v1/phase_stats/single/{run_id}')
async def get_phase_stats_single(run_id: str, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    if artifact := get_artifact(ArtifactType.STATS, f"{user._id}_{str(run_id)}"):
        return ORJSONResponse({'success': True, 'data': orjson.loads(artifact)}) # pylint: disable=no-member

    if not (phase_stats := get_phase_stats(user, [run_id])):
        return Response(status_code=204) # No-Content

    try:
        phase_stats_object = get_phase_stats_object(phase_stats, None, None, [run_id])
        phase_stats_object = add_phase_stats_statistics(phase_stats_object)
    except ValueError as exc:
        raise RequestValidationError(str(exc)) from exc

    store_artifact(ArtifactType.STATS, f"{user._id}_{str(run_id)}", orjson.dumps(phase_stats_object)) # pylint: disable=no-member

    return ORJSONResponseObjKeep({'success': True, 'data': phase_stats_object})


# This route gets the measurements to be displayed in a timeline chart
@router.get('/v1/measurements/single/{run_id}')
async def get_measurements_single(run_id: str, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    query = '''
            SELECT
                mm.detail_name, mv.time, mm.metric,
                   mv.value, mm.unit
            FROM measurement_metrics as mm
            JOIN measurement_values as mv ON mv.measurement_metric_id = mm.id
            JOIN runs as r ON mm.run_id = r.id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]))
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

@router.get('/v1/timeline')
async def get_timeline_stats(uri: str, machine_id: int, branch: str | None = None, filename: str | None = None, start_date: date | None = None, end_date: date | None = None, metrics: str | None = None, phase: str | None = None, sorting: str | None = None, user: User = Depends(authenticate)):
    if uri is None or uri.strip() == '':
        raise RequestValidationError('URI is empty')

    if phase is None or phase.strip() == '':
        raise RequestValidationError('Phase is empty')

    query, params = get_timeline_query(user, uri, filename, machine_id, branch, metrics, phase, start_date=start_date, end_date=end_date, sorting=sorting)

    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})

# Show the timeline badges with regression trend
## A complex case to allow public visibility of the badge but restricting everything else would be to have
## User 1 restricted to only this route but a fully populated 'visible_users' array
@router.get('/v1/badge/timeline')
async def get_timeline_badge(detail_name: str, uri: str, machine_id: int, branch: str | None = None, filename: str | None = None, metrics: str | None = None, unit: str = 'watt-hours', user: User = Depends(authenticate)):
    if uri is None or uri.strip() == '':
        raise RequestValidationError('URI is empty')

    if detail_name is None or detail_name.strip() == '':
        raise RequestValidationError('Detail Name is mandatory')

    if unit not in ('watt-hours', 'joules'):
        raise RequestValidationError('Requested unit is not in allow list: watt-hours, joules')

    # we believe that there is no injection possible to the artifact store and any string can be constructured here ...
    if artifact := get_artifact(ArtifactType.BADGE, f"{user._id}_{uri}_{filename}_{machine_id}_{branch}_{metrics}_{detail_name}_{unit}"):
        return Response(content=str(artifact), media_type="image/svg+xml")

    query, params = get_timeline_query(user, uri,filename,machine_id, branch, metrics, '[RUNTIME]', detail_name=detail_name, limit_365=True)

    # query already contains user access check. No need to have it in aggregate query too
    query = f"""
        WITH trend_data AS (
            {query}
        ) SELECT
          MAX(row_num::float),
          regr_slope(value, row_num::float) AS trend_slope,
          regr_intercept(value, row_num::float) AS trend_intercept,
          MAX(unit)
        FROM trend_data;
    """

    data = DB().fetch_one(query, params=params)

    if data is None or data == [] or data[1] is None: # special check for data[1] as this is aggregate query which always returns result
        return Response(status_code=204) # No-Content

    cost = data[1]/data[0]
    display_in_watthours = True if unit == 'watt-hours' else False # pylint: disable=simplifiable-if-expression
    [rescaled_cost, rescaled_unit] = convert_value(cost, data[3], display_in_watthours)
    rescaled_cost = f"+{rescaled_cost:.2f}" if abs(cost) == cost else f"{rescaled_cost:.2f}"

    badge = anybadge.Badge(
        label=xml_escape('Run Trend'),
        value=xml_escape(f"{rescaled_cost} {rescaled_unit} per day"),
        num_value_padding_chars=1,
        default_color='orange')

    badge_str = str(badge)

    store_artifact(ArtifactType.BADGE, f"{user._id}_{uri}_{filename}_{machine_id}_{branch}_{metrics}_{detail_name}_{unit}", badge_str, ex=60*60*12) # 12 hour storage

    return Response(content=badge_str, media_type="image/svg+xml")


# Return a badge for a single metric of a single run
## A complex case to allow public visibility of the badge but restricting everything else would be to have
## User 1 restricted to only this route but a fully populated 'visible_users' array
@router.get('/v1/badge/single/{run_id}')
async def get_badge_single(run_id: str, metric: str = 'ml-estimated', unit: str = 'watt-hours', user: User = Depends(authenticate)):

    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    if unit not in ('watt-hours', 'joules'):
        raise RequestValidationError('Requested unit is not in allow list: watt-hours, joules')

    # we believe that there is no injection possible to the artifact store and any string can be constructured here ...
    if artifact := get_artifact(ArtifactType.BADGE, f"{user._id}_{run_id}_{metric}_{unit}"):
        return Response(content=str(artifact), media_type="image/svg+xml")

    query = '''
        SELECT
            SUM(ps.value), MAX(ps.unit)
        FROM
            phase_stats as ps
        JOIN
            runs as r ON ps.run_id = r.id
        WHERE
            (TRUE = %s OR r.user_id = ANY(%s::int[]))
            AND ps.run_id = %s
            AND ps.metric LIKE %s
            AND ps.phase LIKE '%%_[RUNTIME]'
    '''

    params = [user.is_super_user(), user.visible_users(), run_id]

    label = 'Energy Cost'
    via = ''
    if metric == 'ml-estimated':
        params.append('psu_energy_ac_xgboost_machine')
        via = 'via XGBoost ML'
    elif metric == 'RAPL':
        params.append('%_energy_rapl_%')
        via = 'via RAPL'
    elif metric == 'AC':
        params.append('psu_energy_ac_%')
        via = 'via PSU (AC)'
    elif metric == 'SCI':
        label = 'SCI'
        params.append('software_carbon_intensity_global')
    else:
        raise RequestValidationError(f"Unknown metric '{metric}' submitted")

    data = DB().fetch_one(query, params=params)

    if data is None or data == [] or data[1] is None: # special check for data[1] as this is aggregate query which always returns result
        badge_value = 'No metric data yet'
    else:
        display_in_watthours = True if unit == 'watt-hours' else False # pylint: disable=simplifiable-if-expression
        [metric_value, energy_unit] = convert_value(data[0], data[1], display_in_watthours)
        badge_value= f"{metric_value:.2f} {energy_unit} {via}"

    badge = anybadge.Badge(
        label=xml_escape(label),
        value=xml_escape(badge_value),
        num_value_padding_chars=1,
        default_color='cornflowerblue')

    badge_str = str(badge)

    if badge_value != 'No metric data yet':
        store_artifact(ArtifactType.BADGE, f"{user._id}_{run_id}_{metric}_{unit}", badge_str)

    return Response(content=badge_str, media_type="image/svg+xml")


@router.get('/v1/watchlist')
async def get_watchlist(user: User = Depends(authenticate)):
    # Do not get the email jobs as they do not need to be display in the frontend atm
    # Also do not get the email field for privacy
    query = '''
        SELECT
            tp.id, tp.name, tp.url,
            (
                SELECT STRING_AGG(t.name, ', ' )
                FROM unnest(tp.categories) as elements
                LEFT JOIN categories as t on t.id = elements
            ) as categories,
            tp.branch, tp.filename, tp.machine_id, m.description, tp.schedule_mode, tp.last_scheduled, tp.created_at, tp.updated_at,
            (
                SELECT created_at
                FROM runs as r
                WHERE
                    tp.url = r.uri
                    AND tp.branch = r.branch
                    AND tp.filename = r.filename
                    AND tp.machine_id = r.machine_id
                ORDER BY r.created_at DESC
                LIMIT 1
            ) as "last_run"
        FROM watchlist as tp
        LEFT JOIN machines as m ON m.id = tp.machine_id
        WHERE
            (TRUE = %s OR tp.user_id = ANY(%s::int[]))
        ORDER BY tp.url ASC;
    '''
    params = (user.is_super_user(), user.visible_users(),)
    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})


@router.post('/v1/software/add')
async def software_add(software: Software, user: User = Depends(authenticate)):

    software = html_escape_multi(software)

    if software.name is None or software.name.strip() == '':
        raise RequestValidationError('Name is empty')

    # Note that we use uri as the general identifier, however when adding through web interface we only allow urls
    if software.url is None or software.url.strip() == '':
        raise RequestValidationError('URL is empty')

    if software.email is not None and software.email.strip() == '':
        software.email = None

    if software.branch is None or software.branch.strip() == '':
        software.branch = 'main'

    if software.filename is None or software.filename.strip() == '':
        software.filename = 'usage_scenario.yml'

    if not DB().fetch_one('SELECT id FROM machines WHERE id=%s AND available=TRUE', params=(software.machine_id,)):
        raise RequestValidationError('Machine does not exist')

    if not user.can_use_machine(software.machine_id):
        raise RequestValidationError('Your user does not have the permissions to use that machine.')

    if software.schedule_mode not in ['one-off', 'daily', 'weekly', 'commit', 'commit-variance', 'tag', 'tag-variance', 'variance']:
        raise RequestValidationError(f"Please select a valid measurement interval. ({software.schedule_mode}) is unknown.")

    if not user.can_schedule_job(software.schedule_mode):
        raise RequestValidationError('Your user does not have the permissions to use that schedule mode.')

    utils.check_repo(software.url, software.branch) # if it exists through the git api

    if software.schedule_mode in ['daily', 'weekly', 'commit', 'commit-variance', 'tag', 'tag-variance']:

        last_marker = None
        if 'tag' in software.schedule_mode:
            last_marker = utils.get_repo_last_marker(software.url, 'tags')

        if 'commit' in software.schedule_mode:
            last_marker = utils.get_repo_last_marker(software.url, 'commits')

        Watchlist.insert(name=software.name, url=software.url, branch=software.branch, filename=software.filename, machine_id=software.machine_id, user_id=user._id, schedule_mode=software.schedule_mode, last_marker=last_marker)

    # even for Watchlist items we do at least one run directly
    amount = 3 if 'variance' in software.schedule_mode else 1
    for _ in range(0,amount):
        Job.insert('run', user_id=user._id, name=software.name, url=software.url, email=software.email, branch=software.branch, filename=software.filename, machine_id=software.machine_id)

    # notify admin of new add
    if notification_email := GlobalConfig().config['admin']['notification_email']:
        Job.insert('email', user_id=user._id, name='New run added from Web Interface', message=str(software), email=notification_email)

    return ORJSONResponse({'success': True}, status_code=202)


@router.get('/v1/run/{run_id}')
async def get_run(run_id: str, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    data = get_run_info(user, run_id)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    data = html_escape_multi(data)

    return ORJSONResponseObjKeep({'success': True, 'data': data})

@router.get('/v1/optimizations/{run_id}')
async def get_optimizations(run_id: str, user: User = Depends(authenticate)):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    query = '''
            SELECT o.title, o.label, o.criticality, o.reporter, o.icon, o.description, o.link
            FROM optimizations as o
            JOIN runs as r ON o.run_id = r.id
            WHERE
                (TRUE = %s OR r.user_id = ANY(%s::int[]))
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
        raise RequestValidationError('run_ids are empty')
    ids = ids.split(',')
    if not all(is_valid_uuid(id) for id in ids):
        raise RequestValidationError('One of Run IDs is not a valid UUID or empty')
    if len(ids) != 2:
        raise RequestValidationError('Run IDs != 2. Only exactly 2 Run IDs can be diffed.')

    if artifact := get_artifact(ArtifactType.DIFF, f"{user._id}_{str(ids)}"):
        return ORJSONResponse({'success': True, 'data': artifact})

    try:
        diff_runs = diff_rows(get_diffable_rows(user, ids))
    except ValueError as exc:
        raise RequestValidationError(str(exc)) from exc

    store_artifact(ArtifactType.DIFF, f"{user._id}_{str(ids)}", diff_runs)

    return ORJSONResponse({'success': True, 'data': diff_runs})


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
