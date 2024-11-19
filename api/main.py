# It seems like FastAPI already enables faulthandler as it shows stacktrace on SEGFAULT
# Is the redundant call problematic?
import sys
import faulthandler
faulthandler.enable(file=sys.__stderr__)  # will catch segfaults and write to stderr

import zlib
import base64
import orjson
from typing import List
from xml.sax.saxutils import escape as xml_escape
from urllib.parse import urlparse
from datetime import date

from fastapi import FastAPI, Request, Response, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from starlette.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.datastructures import Headers as StarletteHeaders

from pydantic import ValidationError

import anybadge

from api.object_specifications import Measurement, CI_Measurement_Old, CI_Measurement, HogMeasurement, Software, EnergyData
from api.api_helpers import (ORJSONResponseObjKeep, add_phase_stats_statistics, carbondb_add, determine_comparison_case,
                         html_escape_multi, get_phase_stats, get_phase_stats_object,
                         is_valid_uuid, rescale_energy_value, get_timeline_query,
                         get_run_info, get_machine_list, get_artifact, store_artifact, get_connecting_ip,
                         validate_hog_measurement_data, replace_nan_with_zero)

from lib.global_config import GlobalConfig
from lib.db import DB
from lib.diff import get_diffable_row, diff_rows
from lib import error_helpers
from lib.job.base import Job
from lib.user import User, UserAuthenticationError
from lib.secure_variable import SecureVariable
from lib.timeline_project import TimelineProject
from lib import utils

from enum import Enum
ArtifactType = Enum('ArtifactType', ['DIFF', 'COMPARE', 'STATS', 'BADGE'])


app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_helpers.log_error(
        'Error in API call - validation_exception_handler',
        url=request.url,
        query_params=request.query_params,
        client=request.client,
        headers=obfuscate_authentication_token(request.headers),
        body=exc.body,
        details=exc.errors(),
        exception=exc
    )
    return ORJSONResponse(
        status_code=422, # HTTP_422_UNPROCESSABLE_ENTITY
        content=jsonable_encoder({'success': False, 'err': exc.errors(), 'body': exc.body}),
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    body = await request.body()
    error_helpers.log_error(
        'Error in API call - http_exception_handler',
        url=request.url,
        query_params=request.query_params,
        client=request.client,
        headers=obfuscate_authentication_token(request.headers),
        body=body,
        details=exc.detail,
        exception=exc
    )
    return ORJSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({'success': False, 'err': exc.detail}),
    )

async def catch_exceptions_middleware(request: Request, call_next):
    #pylint: disable=broad-except
    body = None

    try:
        body = await request.body()
        return await call_next(request)
    except Exception as exc:
        error_helpers.log_error(
            'Error in API call - catch_exceptions_middleware',
            url=request.url,
            query_params=request.query_params,
            client=request.client,
            headers=obfuscate_authentication_token(request.headers),
            body=body,
            exception=exc
        )
        return ORJSONResponse(
            content={
                'success': False,
                'err': 'Technical error with getting data from the API - Please contact us: info@green-coding.io',
            },
            status_code=500,
        )

# Binding the Exception middleware must confusingly come BEFORE the CORS middleware.
# Otherwise CORS will not be sent in response
app.middleware('http')(catch_exceptions_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=GlobalConfig().config['cluster']['cors_allowed_origins'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

header_scheme = APIKeyHeader(
    name='X-Authentication',
    scheme_name='Header',
    description='Authentication key - See https://docs.green-coding.io/authentication',
    auto_error=False
)

def obfuscate_authentication_token(headers: StarletteHeaders):
    headers_mut = headers.mutablecopy()
    if 'X-Authentication' in headers_mut:
        headers_mut['X-Authentication'] = '****OBFUSCATED****'
    return headers_mut

def authenticate(authentication_token=Depends(header_scheme), request: Request = None):
    parsed_url = urlparse(str(request.url))
    try:
        if not authentication_token or authentication_token.strip() == '': # Note that if no token is supplied this will authenticate as the DEFAULT user, which in FOSS systems has full capabilities
            authentication_token = 'DEFAULT'

        user = User.authenticate(SecureVariable(authentication_token))

        if not user.can_use_route(parsed_url.path):
            raise HTTPException(status_code=401, detail="Route not allowed") from UserAuthenticationError

        if not user.has_api_quota(parsed_url.path):
            raise HTTPException(status_code=401, detail="Quota exceeded") from UserAuthenticationError

        user.deduct_api_quota(parsed_url.path, 1)

    except UserAuthenticationError:
        raise HTTPException(status_code=401, detail="Invalid token") from UserAuthenticationError
    return user


@app.get('/')
async def home():
    return RedirectResponse(url='/docs')


# A route to return all of the available entries in our catalog.
@app.get('/v1/notes/{run_id}')
async def get_notes(run_id):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    query = """
            SELECT run_id, detail_name, note, time
            FROM notes
            WHERE run_id = %s
            ORDER BY created_at DESC  -- important to order here, the charting library in JS cannot do that automatically!
            """
    data = DB().fetch_all(query, (run_id,))
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    escaped_data = [html_escape_multi(note) for note in data]
    return ORJSONResponseObjKeep({'success': True, 'data': escaped_data})

@app.get('/v1/network/{run_id}')
async def get_network(run_id):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    query = """
            SELECT *
            FROM network_intercepts
            WHERE run_id = %s
            ORDER BY time
            """
    data = DB().fetch_all(query, (run_id,))

    escaped_data = html_escape_multi(data)
    return ORJSONResponseObjKeep({'success': True, 'data': escaped_data})


# return a list of all possible registered machines
@app.get('/v1/machines')
async def get_machines():

    data = get_machine_list()
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/v1/repositories')
async def get_repositories(uri: str | None = None, branch: str | None = None, machine_id: int | None = None, machine: str | None = None, filename: str | None = None, sort_by: str = 'name'):
    query = """
            SELECT
                r.uri,
                MAX(r.created_at) as last_run
            FROM runs as r
            LEFT JOIN machines as m on r.machine_id = m.id
            WHERE 1=1
            """
    params = []

    if uri:
        query = f"{query} AND r.uri LIKE %s  \n"
        params.append(f"%{uri}%")

    if branch:
        query = f"{query} AND r.branch LIKE %s  \n"
        params.append(f"%{branch}%")

    if filename:
        query = f"{query} AND r.filename LIKE %s  \n"
        params.append(f"%{filename}%")

    if machine_id:
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

    data = DB().fetch_all(query, params=tuple(params))
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    escaped_data = [html_escape_multi(run) for run in data]

    return ORJSONResponse({'success': True, 'data': escaped_data})


# A route to return all of the available entries in our catalog.
@app.get('/v1/runs')
async def get_runs(uri: str | None = None, branch: str | None = None, machine_id: int | None = None, machine: str | None = None, filename: str | None = None, limit: int | None = None, uri_mode = 'none'):

    query = """
            SELECT r.id, r.name, r.uri, r.branch, r.created_at, r.invalid_run, r.filename, m.description, r.commit_hash, r.end_measurement, r.failed, r.machine_id
            FROM runs as r
            LEFT JOIN machines as m on r.machine_id = m.id
            WHERE 1=1
            """
    params = []

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

    if machine_id:
        query = f"{query} AND m.id = %s \n"
        params.append(machine_id)

    if machine:
        query = f"{query} AND m.description LIKE %s \n"
        params.append(f"%{machine}%")

    query = f"{query} ORDER BY r.created_at DESC"

    if limit:
        query = f"{query} LIMIT %s"
        params.append(limit)


    data = DB().fetch_all(query, params=tuple(params))
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    escaped_data = [html_escape_multi(run) for run in data]

    return ORJSONResponse({'success': True, 'data': escaped_data})


# Just copy and paste if we want to deprecate URLs
# @app.get('/v1/measurements/uri', deprecated=True) # Here you can see, that URL is nevertheless accessible as variable
# later if supplied. Also deprecation shall be used once we move to v2 for all v1 routesthrough

@app.get('/v1/compare')
async def compare_in_repo(ids: str):
    if ids is None or not ids.strip():
        raise RequestValidationError('run_id is empty')
    ids = ids.split(',')
    if not all(is_valid_uuid(id) for id in ids):
        raise RequestValidationError('One of Run IDs is not a valid UUID or empty')


    if artifact := get_artifact(ArtifactType.COMPARE, str(ids)):
        return ORJSONResponse({'success': True, 'data': orjson.loads(artifact)}) # pylint: disable=no-member

    try:
        case = determine_comparison_case(ids)
    except RuntimeError as err:
        raise RequestValidationError(str(err)) from err

    if not (phase_stats := get_phase_stats(ids)):
        return Response(status_code=204) # No-Content

    phase_stats_object = get_phase_stats_object(phase_stats, case)
    phase_stats_object = add_phase_stats_statistics(phase_stats_object)
    phase_stats_object['common_info'] = {}

    try:
        run_info = get_run_info(ids[0])

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

    store_artifact(ArtifactType.COMPARE, str(ids), orjson.dumps(phase_stats_object)) # pylint: disable=no-member


    return ORJSONResponse({'success': True, 'data': phase_stats_object})


@app.get('/v1/phase_stats/single/{run_id}')
async def get_phase_stats_single(run_id: str):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    if artifact := get_artifact(ArtifactType.STATS, str(run_id)):
        return ORJSONResponse({'success': True, 'data': orjson.loads(artifact)}) # pylint: disable=no-member

    if not (phase_stats := get_phase_stats([run_id])):
        return Response(status_code=204) # No-Content

    phase_stats_object = get_phase_stats_object(phase_stats, None)
    phase_stats_object = add_phase_stats_statistics(phase_stats_object)

    store_artifact(ArtifactType.STATS, str(run_id), orjson.dumps(phase_stats_object)) # pylint: disable=no-member

    return ORJSONResponseObjKeep({'success': True, 'data': phase_stats_object})


# This route gets the measurements to be displayed in a timeline chart
@app.get('/v1/measurements/single/{run_id}')
async def get_measurements_single(run_id: str):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    query = """
            SELECT measurements.detail_name, measurements.time, measurements.metric,
                   measurements.value, measurements.unit
            FROM measurements
            WHERE measurements.run_id = %s
            """

    # extremely important to order here, cause the charting library in JS cannot do that automatically!

    query = f"{query} ORDER BY measurements.metric ASC, measurements.detail_name ASC, measurements.time ASC"

    data = DB().fetch_all(query, params=(run_id, ))

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponseObjKeep({'success': True, 'data': data})

@app.get('/v1/timeline')
async def get_timeline_stats(uri: str, machine_id: int, branch: str | None = None, filename: str | None = None, start_date: date | None = None, end_date: date | None = None, metrics: str | None = None, phase: str | None = None, sorting: str | None = None,):
    if uri is None or uri.strip() == '':
        raise RequestValidationError('URI is empty')

    if phase is None or phase.strip() == '':
        raise RequestValidationError('Phase is empty')

    query, params = get_timeline_query(uri,filename,machine_id, branch, metrics, phase, start_date=start_date, end_date=end_date, sorting=sorting)

    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/v1/badge/timeline')
async def get_timeline_badge(detail_name: str, uri: str, machine_id: int, branch: str | None = None, filename: str | None = None, metrics: str | None = None):
    if uri is None or uri.strip() == '':
        raise RequestValidationError('URI is empty')

    if detail_name is None or detail_name.strip() == '':
        raise RequestValidationError('Detail Name is mandatory')

    if artifact := get_artifact(ArtifactType.BADGE, f"{uri}_{filename}_{machine_id}_{branch}_{metrics}_{detail_name}"):
        return Response(content=str(artifact), media_type="image/svg+xml")


    query, params = get_timeline_query(uri,filename,machine_id, branch, metrics, '[RUNTIME]', detail_name=detail_name, limit_365=True)

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
    cost = f"+{round(float(cost), 2)}" if abs(cost) == cost else f"{round(float(cost), 2)}"

    badge = anybadge.Badge(
        label=xml_escape('Run Trend'),
        value=xml_escape(f"{cost} {data[3]} per day"),
        num_value_padding_chars=1,
        default_color='orange')

    badge_str = str(badge)

    store_artifact(ArtifactType.BADGE, f"{uri}_{filename}_{machine_id}_{branch}_{metrics}_{detail_name}", badge_str, ex=60*60*12) # 12 hour storage

    return Response(content=badge_str, media_type="image/svg+xml")


# A route to return all of the available entries in our catalog.
@app.get('/v1/badge/single/{run_id}')
async def get_badge_single(run_id: str, metric: str = 'ml-estimated'):

    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    if artifact := get_artifact(ArtifactType.BADGE, f"{run_id}_{metric}"):
        return Response(content=str(artifact), media_type="image/svg+xml")

    query = '''
        SELECT
            SUM(value), MAX(unit)
        FROM
            phase_stats
        WHERE
            run_id = %s
            AND metric LIKE %s
            AND phase LIKE '%%_[RUNTIME]'
    '''

    value = None
    label = 'Energy Cost'
    via = ''
    if metric == 'ml-estimated':
        value = 'psu_energy_ac_xgboost_machine'
        via = 'via XGBoost ML'
    elif metric == 'RAPL':
        value = '%_energy_rapl_%'
        via = 'via RAPL'
    elif metric == 'AC':
        value = 'psu_energy_ac_%'
        via = 'via PSU (AC)'
    elif metric == 'SCI':
        label = 'SCI'
        value = 'software_carbon_intensity_global'
    else:
        raise RequestValidationError(f"Unknown metric '{metric}' submitted")

    params = (run_id, value)
    data = DB().fetch_one(query, params=params)

    if data is None or data == [] or data[1] is None: # special check for data[1] as this is aggregate query which always returns result
        badge_value = 'No energy data yet'
    else:
        [energy_value, energy_unit] = rescale_energy_value(data[0], data[1])
        badge_value= f"{energy_value:.2f} {energy_unit} {via}"

    badge = anybadge.Badge(
        label=xml_escape(label),
        value=xml_escape(badge_value),
        num_value_padding_chars=1,
        default_color='cornflowerblue')

    badge_str = str(badge)

    store_artifact(ArtifactType.BADGE, f"{run_id}_{metric}", badge_str)

    return Response(content=badge_str, media_type="image/svg+xml")


@app.get('/v1/timeline-projects')
async def get_timeline_projects():
    # Do not get the email jobs as they do not need to be display in the frontend atm
    # Also do not get the email field for privacy
    query = """
        SELECT
            p.id, p.name, p.url,
            (
                SELECT STRING_AGG(t.name, ', ' )
                FROM unnest(p.categories) as elements
                LEFT JOIN categories as t on t.id = elements
            ) as categories,
            p.branch, p.filename, p.machine_id, m.description, p.schedule_mode, p.last_scheduled, p.created_at, p.updated_at,
            (
                SELECT created_at
                FROM runs as r
                WHERE
                    p.url = r.uri
                    AND p.branch = r.branch
                    AND p.filename = r.filename
                    AND p.machine_id = r.machine_id
                ORDER BY r.created_at DESC
                LIMIT 1
            ) as "last_run"
        FROM timeline_projects as p
        LEFT JOIN machines as m ON m.id = p.machine_id
        ORDER BY p.url ASC;
    """
    data = DB().fetch_all(query)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})


@app.get('/v1/jobs')
async def get_jobs(machine_id: int | None = None, state: str | None = None):

    params = []
    machine_id_condition = ''
    state_condition = ''

    if machine_id is not None:
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
            j.type = 'run'
            {machine_id_condition}
            {state_condition}
        ORDER BY j.updated_at DESC, j.created_at ASC
    """
    data = DB().fetch_all(query, params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})



@app.post('/v1/hog/add')
async def hog_add(
    measurements: List[HogMeasurement],
    user: User = Depends(authenticate), # pylint: disable=unused-argument
    ):

    for measurement in measurements:
        decoded_data = base64.b64decode(measurement.data)
        decompressed_data = zlib.decompress(decoded_data)
        measurement_data = orjson.loads(decompressed_data.decode()) # pylint: disable=no-member

        # For some reason we sometimes get NaN in the data.
        measurement_data = replace_nan_with_zero(measurement_data)

        #Check if the data is valid, if not this will throw an exception and converted into a request by the middleware
        try:
            _ = Measurement(**measurement_data)
        except (ValidationError, RequestValidationError) as exc:
            print('Caught Exception in Measurement()', exc.__class__.__name__, exc)
            print('Hog parsing error. Missing expected, but non critical key', str(exc))
            # Output is extremely verbose. Please only turn on if debugging manually
            # print(f"Errors are: {exc.errors()}")


        try:
            validate_hog_measurement_data(measurement_data)
        except ValueError as exc:
            print(f"Caught Exception in validate_hog_measurement_data() {exc.__class__.__name__} {exc}")
            raise exc

        coalitions = []
        for coalition in measurement_data['coalitions']:
            if coalition['name'] == 'com.googlecode.iterm2' or \
                coalition['name'] == 'com.apple.Terminal' or \
                coalition['name'] == 'com.vix.cron' or \
                coalition['name'].strip() == '':
                tmp = coalition['tasks']
                for tmp_el in tmp:
                    tmp_el['tasks'] = []
                coalitions.extend(tmp)
            else:
                coalitions.append(coalition)

        # We remove the coalitions as we don't want to save all the data in hog_measurements
        del measurement_data['coalitions']
        del measurement.data

        cpu_energy_data = {}
        energy_impact = round(measurement_data['all_tasks'].get('energy_impact_per_s') * measurement_data['elapsed_ns'] / 1_000_000_000)
        if 'ane_energy' in measurement_data['processor']:
            cpu_energy_data = {
                'combined_energy': round(measurement_data['processor'].get('combined_power', 0) * measurement_data['elapsed_ns'] / 1_000_000_000.0),
                'cpu_energy': round(measurement_data['processor'].get('cpu_energy', 0)),
                'gpu_energy': round(measurement_data['processor'].get('gpu_energy', 0)),
                'ane_energy': round(measurement_data['processor'].get('ane_energy', 0)),
                'energy_impact': energy_impact,
            }
        elif 'package_joules' in measurement_data['processor']:
            # Intel processors report in joules/ watts and not mJ
            cpu_energy_data = {
                'combined_energy': round(measurement_data['processor'].get('package_joules', 0) * 1_000),
                'cpu_energy': round(measurement_data['processor'].get('cpu_joules', 0) * 1_000),
                'gpu_energy': round(measurement_data['processor'].get('igpu_watts', 0) * measurement_data['elapsed_ns'] / 1_000_000_000.0 * 1_000),
                'ane_energy': 0,
                'energy_impact': energy_impact,
            }
        else:
            raise RequestValidationError("input not valid")

        query = """
            INSERT INTO
                hog_measurements (
                    time,
                    machine_uuid,
                    elapsed_ns,
                    combined_energy,
                    cpu_energy,
                    gpu_energy,
                    ane_energy,
                    energy_impact,
                    thermal_pressure,
                    settings,
                    user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """
        params = (
            measurement.time,
            measurement.machine_uuid,
            measurement_data['elapsed_ns'],
            cpu_energy_data['combined_energy'],
            cpu_energy_data['cpu_energy'],
            cpu_energy_data['gpu_energy'],
            cpu_energy_data['ane_energy'],
            cpu_energy_data['energy_impact'],
            measurement_data['thermal_pressure'],
            measurement.settings,
            user._id,
        )

        measurement_db_id = DB().fetch_one(query=query, params=params)[0]


        # Save hog_measurements
        for coalition in coalitions:

            if coalition['energy_impact'] < 1.0:
                # If the energy_impact is too small we just skip the coalition.
                continue

            c_tasks = coalition['tasks'].copy()
            del coalition['tasks']

            c_energy_impact = round((coalition['energy_impact_per_s'] / 1_000_000_000) * measurement_data['elapsed_ns'])
            c_cputime_ns = ((coalition['cputime_ms_per_s'] * 1_000_000)  / 1_000_000_000) * measurement_data['elapsed_ns']

            query = """
                INSERT INTO
                    hog_coalitions (
                        measurement,
                        name,
                        cputime_ns,
                        cputime_per,
                        energy_impact,
                        diskio_bytesread,
                        diskio_byteswritten,
                        intr_wakeups,
                        idle_wakeups)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """
            params = (
                measurement_db_id,
                coalition['name'],
                c_cputime_ns,
                int(c_cputime_ns / measurement_data['elapsed_ns'] * 100),
                c_energy_impact,
                coalition['diskio_bytesread'],
                coalition['diskio_byteswritten'],
                coalition['intr_wakeups'],
                coalition['idle_wakeups'],
            )

            coaltion_db_id = DB().fetch_one(query=query, params=params)[0]

            for task in c_tasks:
                t_energy_impact = round((task['energy_impact_per_s'] / 1_000_000_000) * measurement_data['elapsed_ns'])
                t_cputime_ns = ((task['cputime_ms_per_s'] * 1_000_000)  / 1_000_000_000) * measurement_data['elapsed_ns']

                query = """
                    INSERT INTO
                        hog_tasks (
                            coalition,
                            name,
                            cputime_ns,
                            cputime_per,
                            energy_impact,
                            bytes_received,
                            bytes_sent,
                            diskio_bytesread,
                            diskio_byteswritten,
                            intr_wakeups,
                            idle_wakeups)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """
                params = (
                    coaltion_db_id,
                    task['name'],
                    t_cputime_ns,
                    int(t_cputime_ns / measurement_data['elapsed_ns'] * 100),
                    t_energy_impact,
                    task.get('bytes_received', 0),
                    task.get('bytes_sent', 0),
                    task.get('diskio_bytesread', 0),
                    task.get('diskio_byteswritten', 0),
                    task.get('intr_wakeups', 0),
                    task.get('idle_wakeups', 0),
                )
                DB().fetch_one(query=query, params=params)

    return Response(status_code=204) # No-Content


@app.get('/v1/hog/top_processes')
async def hog_get_top_processes():
    query = """
        SELECT
            name,
            (SUM(energy_impact)::bigint) AS total_energy_impact
        FROM
            hog_coalitions
        GROUP BY
            name
        ORDER BY
            total_energy_impact DESC
        LIMIT 100;
    """
    data = DB().fetch_all(query)

    if data is None:
        data = []

    query = """
        SELECT COUNT(DISTINCT machine_uuid) FROM hog_measurements;
    """

    machine_count = DB().fetch_one(query)[0]

    return ORJSONResponse({'success': True, 'process_data': data, 'machine_count': machine_count})


@app.get('/v1/hog/machine_details/{machine_uuid}')
async def hog_get_machine_details(machine_uuid: str):

    if machine_uuid is None or not is_valid_uuid(machine_uuid):
        return ORJSONResponse({'success': False, 'err': 'machine_uuid is empty or malformed'}, status_code=422)

    query = """
        SELECT
            time,
            combined_energy,
            cpu_energy,
            gpu_energy,
            ane_energy,
            energy_impact::bigint,
            id
        FROM
            hog_measurements
        WHERE
            machine_uuid = %s
        ORDER BY
            time
    """

    data = DB().fetch_all(query, (machine_uuid,))

    return ORJSONResponse({'success': True, 'data': data})


@app.get('/v1/hog/coalitions_tasks/{machine_uuid}/{measurements_id_start}/{measurements_id_end}')
async def hog_get_coalitions_tasks(machine_uuid: str, measurements_id_start: int, measurements_id_end: int):

    if machine_uuid is None or not is_valid_uuid(machine_uuid):
        return ORJSONResponse({'success': False, 'err': 'machine_uuid is empty'}, status_code=422)

    if measurements_id_start is None:
        return ORJSONResponse({'success': False, 'err': 'measurements_id_start is empty'}, status_code=422)

    if measurements_id_end is None:
        return ORJSONResponse({'success': False, 'err': 'measurements_id_end is empty'}, status_code=422)


    coalitions_query = """
        SELECT
            name,
            (SUM(hc.energy_impact)::bigint) AS total_energy_impact,
            (SUM(hc.diskio_bytesread)::bigint) AS total_diskio_bytesread,
            (SUM(hc.diskio_byteswritten)::bigint) AS total_diskio_byteswritten,
            (SUM(hc.intr_wakeups)::bigint) AS total_intr_wakeups,
            (SUM(hc.idle_wakeups)::bigint) AS total_idle_wakeups,
            (AVG(hc.cputime_per)::integer) AS avg_cpu_per
        FROM
            hog_coalitions AS hc
        JOIN
            hog_measurements AS hm ON hc.measurement = hm.id
        WHERE
            hc.measurement BETWEEN %s AND %s
            AND hm.machine_uuid = %s
        GROUP BY
            name
        ORDER BY
            total_energy_impact DESC
        LIMIT 100;
    """

    measurements_query = """
        SELECT
            (SUM(combined_energy)::bigint) AS total_combined_energy,
            (SUM(cpu_energy)::bigint) AS total_cpu_energy,
            (SUM(gpu_energy)::bigint) AS total_gpu_energy,
            (SUM(ane_energy)::bigint) AS total_ane_energy,
            (SUM(energy_impact)::bigint) AS total_energy_impact
        FROM
            hog_measurements
        WHERE
            id BETWEEN %s AND %s
            AND machine_uuid = %s

    """

    coalitions_data = DB().fetch_all(coalitions_query, (measurements_id_start, measurements_id_end, machine_uuid))

    energy_data = DB().fetch_one(measurements_query, (measurements_id_start, measurements_id_end, machine_uuid))

    return ORJSONResponse({'success': True, 'data': coalitions_data, 'energy_data': energy_data})

@app.get('/v1/hog/tasks_details/{machine_uuid}/{measurements_id_start}/{measurements_id_end}/{coalition_name}')
async def hog_get_task_details(machine_uuid: str, measurements_id_start: int, measurements_id_end: int, coalition_name: str):

    if machine_uuid is None or not is_valid_uuid(machine_uuid):
        return ORJSONResponse({'success': False, 'err': 'machine_uuid is empty'}, status_code=422)

    if measurements_id_start is None:
        return ORJSONResponse({'success': False, 'err': 'measurements_id_start is empty'}, status_code=422)

    if measurements_id_end is None:
        return ORJSONResponse({'success': False, 'err': 'measurements_id_end is empty'}, status_code=422)

    if coalition_name is None or not coalition_name.strip():
        return ORJSONResponse({'success': False, 'err': 'coalition_name is empty'}, status_code=422)

    tasks_query = """
        SELECT
            t.name,
            COUNT(t.id)::bigint AS number_of_tasks,
            SUM(t.energy_impact)::bigint AS total_energy_impact,
            SUM(t.cputime_ns)::bigint AS total_cputime_ns,
            SUM(t.bytes_received)::bigint AS total_bytes_received,
            SUM(t.bytes_sent)::bigint AS total_bytes_sent,
            SUM(t.diskio_bytesread)::bigint AS total_diskio_bytesread,
            SUM(t.diskio_byteswritten)::bigint AS total_diskio_byteswritten,
            SUM(t.intr_wakeups)::bigint AS total_intr_wakeups,
            SUM(t.idle_wakeups)::bigint AS total_idle_wakeups
        FROM
            hog_tasks t
        JOIN hog_coalitions c ON t.coalition = c.id
        JOIN hog_measurements m ON c.measurement = m.id
        WHERE
            c.name = %s
            AND c.measurement BETWEEN %s AND %s
            AND m.machine_uuid = %s
        GROUP BY
            t.name
        ORDER BY
            total_energy_impact DESC;
    """

    coalitions_query = """
        SELECT
            c.name,
            (SUM(c.energy_impact)::bigint) AS total_energy_impact,
            (SUM(c.diskio_bytesread)::bigint) AS total_diskio_bytesread,
            (SUM(c.diskio_byteswritten)::bigint) AS total_diskio_byteswritten,
            (SUM(c.intr_wakeups)::bigint) AS total_intr_wakeups,
            (SUM(c.idle_wakeups)::bigint) AS total_idle_wakeups
        FROM
            hog_coalitions c
        JOIN hog_measurements m ON c.measurement = m.id
        WHERE
            c.name = %s
            AND c.measurement BETWEEN %s AND %s
            AND m.machine_uuid = %s
        GROUP BY
            c.name
        ORDER BY
            total_energy_impact DESC
        LIMIT 100;
    """

    tasks_data = DB().fetch_all(tasks_query, (coalition_name, measurements_id_start,measurements_id_end, machine_uuid))
    coalitions_data = DB().fetch_one(coalitions_query, (coalition_name, measurements_id_start, measurements_id_end, machine_uuid))

    return ORJSONResponse({'success': True, 'tasks_data': tasks_data, 'coalitions_data': coalitions_data})



@app.post('/v1/software/add')
async def software_add(software: Software, user: User = Depends(authenticate)):

    software = html_escape_multi(software)

    if software.name is None or software.name.strip() == '':
        raise RequestValidationError('Name is empty')

    # Note that we use uri as the general identifier, however when adding through web interface we only allow urls
    if software.url is None or software.url.strip() == '':
        raise RequestValidationError('URL is empty')

    if software.name is None or software.name.strip() == '':
        raise RequestValidationError('Name is empty')

    if software.email is None or software.email.strip() == '':
        raise RequestValidationError('E-mail is empty')

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

        TimelineProject.insert(name=software.name, url=software.url, branch=software.branch, filename=software.filename, machine_id=software.machine_id, user_id=user._id, schedule_mode=software.schedule_mode, last_marker=last_marker)

    # even for timeline projects we do at least one run directly
    amount = 3 if 'variance' in software.schedule_mode else 1
    for _ in range(0,amount):
        Job.insert('run', user_id=user._id, name=software.name, url=software.url, email=software.email, branch=software.branch, filename=software.filename, machine_id=software.machine_id)

    # notify admin of new add
    if notification_email := GlobalConfig().config['admin']['notification_email']:
        Job.insert('email', user_id=user._id, name='New run added from Web Interface', message=str(software), email=notification_email)

    return ORJSONResponse({'success': True}, status_code=202)


@app.get('/v1/run/{run_id}')
async def get_run(run_id: str):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    data = get_run_info(run_id)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    data = html_escape_multi(data)

    return ORJSONResponseObjKeep({'success': True, 'data': data})

@app.get('/v1/optimizations/{run_id}')
async def get_optimizations(run_id: str):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    query = """
            SELECT title, label, criticality, reporter, icon, description, link
            FROM optimizations
            WHERE optimizations.run_id = %s
            """

    data = DB().fetch_all(query, params=(run_id, ))

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponseObjKeep({'success': True, 'data': data})



@app.get('/v1/diff')
async def diff(ids: str):
    if ids is None or not ids.strip():
        raise RequestValidationError('run_ids are empty')
    ids = ids.split(',')
    if not all(is_valid_uuid(id) for id in ids):
        raise RequestValidationError('One of Run IDs is not a valid UUID or empty')
    if len(ids) != 2:
        raise RequestValidationError('Run IDs != 2. Only exactly 2 Run IDs can be diffed.')

    if artifact := get_artifact(ArtifactType.DIFF, str(ids)):
        return ORJSONResponse({'success': True, 'data': artifact})

    a = get_diffable_row(ids[0])
    b = get_diffable_row(ids[1])
    diff_runs = diff_rows(a,b)

    store_artifact(ArtifactType.DIFF, str(ids), diff_runs)

    return ORJSONResponse({'success': True, 'data': diff_runs})


@app.get('/robots.txt')
async def robots_txt():
    data =  "User-agent: *\n"
    data += "Disallow: /"

    return Response(content=data, media_type='text/plain')


@app.post('/v1/ci/measurement/add')
async def post_ci_measurement_add_deprecated(
    request: Request,
    measurement: CI_Measurement_Old,
    user: User = Depends(authenticate) # pylint: disable=unused-argument
    ):

    measurement = html_escape_multi(measurement)

    used_client_ip = get_connecting_ip(request)

    co2i_transformed = int(measurement.co2i) if measurement.co2i else None

    co2eq_transformed = int(float(measurement.co2eq)*1000000) if measurement.co2eq else None

    query = '''
        INSERT INTO
            ci_measurements (energy_uj,
                            repo,
                            branch,
                            workflow_id,
                            run_id,
                            label,
                            source,
                            cpu,
                            commit_hash,
                            duration_us,
                            cpu_util_avg,
                            workflow_name,
                            lat,
                            lon,
                            city,
                            carbon_intensity_g,
                            carbon_ug,
                            filter_type,
                            filter_project,
                            filter_machine,
                            filter_tags,
                            user_id,
                            ip_address
                            )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        '''

    params = ( measurement.energy_value*1000, measurement.repo, measurement.branch,
            measurement.workflow, measurement.run_id, measurement.label, measurement.source, measurement.cpu,
            measurement.commit_hash, measurement.duration*1000000, measurement.cpu_util_avg, measurement.workflow_name,
            measurement.lat, measurement.lon, measurement.city, co2i_transformed, co2eq_transformed,
            'machine.ci', 'CI/CD', 'unknown', [],
            user._id, used_client_ip)


    DB().query(query=query, params=params)

    if measurement.energy_value <= 1 or (measurement.co2eq and co2eq_transformed <= 1):
        error_helpers.log_error(
            'Extremely small energy budget was submitted to old Eco-CI API',
            measurement=measurement
        )

    return Response(status_code=204)


@app.post('/v2/ci/measurement/add')
async def post_ci_measurement_add(
    request: Request,
    measurement: CI_Measurement,
    user: User = Depends(authenticate) # pylint: disable=unused-argument
    ):

    measurement = html_escape_multi(measurement)

    params = [measurement.energy_uj, measurement.repo, measurement.branch,
            measurement.workflow, measurement.run_id, measurement.label, measurement.source, measurement.cpu,
            measurement.commit_hash, measurement.duration_us, measurement.cpu_util_avg, measurement.workflow_name,
            measurement.lat, measurement.lon, measurement.city, measurement.carbon_intensity_g, measurement.carbon_ug,
            measurement.filter_type, measurement.filter_project, measurement.filter_machine]

    tags_replacer = ' ARRAY[]::text[] '
    if measurement.filter_tags:
        tags_replacer = f" ARRAY[{','.join(['%s']*len(measurement.filter_tags))}] "
        params = params + measurement.filter_tags

    used_client_ip = measurement.ip # If an ip has been given with the data. We prioritize that
    if used_client_ip is None:
        used_client_ip = get_connecting_ip(request)

    params.append(used_client_ip)
    params.append(user._id)

    query = f"""
        INSERT INTO
            ci_measurements (energy_uj,
                            repo,
                            branch,
                            workflow_id,
                            run_id,
                            label,
                            source,
                            cpu,
                            commit_hash,
                            duration_us,
                            cpu_util_avg,
                            workflow_name,
                            lat,
                            lon,
                            city,
                            carbon_intensity_g,
                            carbon_ug,
                            filter_type,
                            filter_project,
                            filter_machine,
                            filter_tags,
                            ip_address,
                            user_id
                            )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                {tags_replacer},
                %s, %s)

        """

    DB().query(query=query, params=params)

    if measurement.energy_uj <= 1 or (measurement.carbon_ug and measurement.carbon_ug <= 1):
        error_helpers.log_error(
            'Extremely small energy budget was submitted to Eco-CI API',
            measurement=measurement
        )

    return Response(status_code=204)

@app.get('/v1/ci/measurements')
async def get_ci_measurements(repo: str, branch: str, workflow: str, start_date: date, end_date: date):

    query = """
        SELECT energy_uj, run_id, created_at, label, cpu, commit_hash, duration_us, source, cpu_util_avg,
               (SELECT workflow_name FROM ci_measurements AS latest_workflow
                WHERE latest_workflow.repo = ci_measurements.repo
                AND latest_workflow.branch = ci_measurements.branch
                AND latest_workflow.workflow_id = ci_measurements.workflow_id
                ORDER BY latest_workflow.created_at DESC
                LIMIT 1) AS workflow_name,
               lat, lon, city, carbon_intensity_g, carbon_ug
        FROM ci_measurements
        WHERE
            repo = %s AND branch = %s AND workflow_id = %s
            AND DATE(created_at) >= TO_DATE(%s, 'YYYY-MM-DD')
            AND DATE(created_at) <= TO_DATE(%s, 'YYYY-MM-DD')
        ORDER BY run_id ASC, created_at ASC
    """
    params = (repo, branch, workflow, str(start_date), str(end_date))
    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204)  # No-Content

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/v1/ci/repositories')
async def get_ci_repositories(repo: str | None = None, sort_by: str = 'name'):

    params = []
    query = """
        SELECT repo, source, MAX(created_at) as last_run
        FROM ci_measurements
        WHERE 1=1
    """

    if repo: # filter is currently not used, but may be a feature in the future
        query = f"{query} AND ci_measurements.repo = %s  \n"
        params.append(repo)

    query = f"{query} GROUP BY repo, source"

    if sort_by == 'date':
        query = f"{query} ORDER BY last_run DESC"
    else:
        query = f"{query} ORDER BY repo ASC"

    data = DB().fetch_all(query, params=tuple(params))
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data}) # no escaping needed, as it happend on ingest


@app.get('/v1/ci/runs')
async def get_ci_runs(repo: str, sort_by: str = 'name'):

    params = []
    query = """
        SELECT repo, branch, workflow_id, source, MAX(created_at) as last_run,
                (SELECT workflow_name FROM ci_measurements AS latest_workflow
                WHERE latest_workflow.repo = ci_measurements.repo
                AND latest_workflow.branch = ci_measurements.branch
                AND latest_workflow.workflow_id = ci_measurements.workflow_id
                ORDER BY latest_workflow.created_at DESC
                LIMIT 1) AS workflow_name
        FROM ci_measurements
        WHERE 1=1
    """

    query = f"{query} AND ci_measurements.repo = %s  \n"
    params.append(repo)
    query = f"{query} GROUP BY repo, branch, workflow_id, source"

    if sort_by == 'date':
        query = f"{query} ORDER BY last_run DESC"
    else:
        query = f"{query} ORDER BY repo ASC"

    data = DB().fetch_all(query, params=tuple(params))
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data}) # no escaping needed, as it happend on ingest

@app.get('/v1/ci/badge/get')
async def get_ci_badge_get(repo: str, branch: str, workflow:str):
    query = """
        SELECT SUM(energy_uj), MAX(run_id)
        FROM ci_measurements
        WHERE repo = %s AND branch = %s AND workflow_id = %s
        GROUP BY run_id
        ORDER BY MAX(created_at) DESC
        LIMIT 1
    """

    params = (repo, branch, workflow)
    data = DB().fetch_one(query, params=params)

    if data is None or data == [] or data[1] is None: # special check for data[1] as this is aggregate query which always returns result
        return Response(status_code=204) # No-Content

    energy_value = data[0]

    [energy_value, energy_unit] = rescale_energy_value(energy_value, 'uJ')
    badge_value= f"{energy_value:.2f} {energy_unit}"

    badge = anybadge.Badge(
        label='Energy Used',
        value=xml_escape(badge_value),
        num_value_padding_chars=1,
        default_color='green')
    return Response(content=str(badge), media_type="image/svg+xml")


@app.post('/v1/carbondb/add')
async def add_carbondb_deprecated():
    return Response("This endpoint is not supported anymore. Please migrate to /v2/carbondb/add !", status_code=410)

@app.post('/v2/carbondb/add')
async def add_carbondb(
    request: Request,
    energydata: EnergyData,
    user: User = Depends(authenticate) # pylint: disable=unused-argument
    ):

    try:
        carbondb_add(get_connecting_ip(request), energydata.dict(), 'CUSTOM', user._id)
    except ValueError as exc:
        raise RequestValidationError(str(exc)) from exc

    return Response(status_code=204)


@app.get('/v1/carbondb/')
async def get_carbondb_deprecated():
    return Response("This endpoint is not supported anymore. Please migrate to /v2/carbondb/ !", status_code=410)

@app.get('/v2/carbondb')
async def carbondb_get(
    user: User = Depends(authenticate),
    start_date: date | None = None, end_date: date | None = None,
    tags_include: str | None = None, tags_exclude: str | None = None,
    types_include: str | None = None, types_exclude: str | None = None,
    projects_include: str | None = None, projects_exclude: str | None = None,
    machines_include: str | None = None, machines_exclude: str | None = None,
    sources_include: str | None = None, sources_exclude: str | None = None
    ):

    params = [user._id,]

    start_date_condition = ''
    if start_date is not None:
        start_date_condition =  "AND DATE(cedd.date) >= %s"
        params.append(start_date)

    end_date_condition = ''
    if end_date is not None:
        end_date_condition =  "AND DATE(cedd.date) <= %s"
        params.append(end_date)

    tags_include_condition = ''
    if tags_include:
        tags_include_list = tags_include.split(',')
        tags_include_condition = f" AND cedd.tags @> ARRAY[{','.join(['%s::integer']*len(tags_include_list))}]"
        params = params + tags_include_list

    tags_exclude_condition = ''
    if tags_exclude:
        tags_exclude_list = tags_exclude.split(',')
        tags_exclude_condition = f" AND cedd.tags NOT @> ARRAY[{','.join(['%s::integer']*len(tags_exclude_list))}]"
        params = params + tags_exclude_list

    machines_include_condition = ''
    if machines_include:
        machines_include_list = machines_include.split(',')
        machines_include_condition = f" AND cedd.machine IN ({','.join(['%s']*len(machines_include_list))})"
        params = params + machines_include_list

    machines_exclude_condition = ''
    if machines_exclude:
        machines_exclude_list = machines_exclude.split(',')
        machines_exclude_condition = f" AND cedd.machine NOT IN ({','.join(['%s']*len(machines_exclude_list))})"
        params = params + machines_exclude_list

    types_include_condition = ''
    if types_include:
        types_include_list = types_include.split(',')
        types_include_condition = f" AND cedd.type IN ({','.join(['%s']*len(types_include_list))})"
        params = params + types_include_list

    types_exclude_condition = ''
    if types_exclude:
        types_exclude_list = types_exclude.split(',')
        types_exclude_condition = f" AND cedd.type NOT IN ({','.join(['%s']*len(types_exclude_list))})"
        params = params + types_exclude_list

    projects_include_condition = ''
    if projects_include:
        projects_include_list = projects_include.split(',')
        projects_include_condition = f" AND cedd.project IN ({','.join(['%s']*len(projects_include_list))})"
        params = params + projects_include_list

    projects_exclude_condition = ''
    if projects_exclude:
        projects_exclude_list = projects_exclude.split(',')
        projects_exclude_condition = f" AND cedd.project NOT IN ({','.join(['%s']*len(projects_exclude_list))})"
        params = params + projects_exclude_list

    sources_include_condition = ''
    if sources_include:
        sources_include_list = sources_include.split(',')
        sources_include_condition = f" AND cedd.source IN ({','.join(['%s']*len(sources_include_list))})"
        params = params + sources_include_list

    sources_exclude_condition = ''
    if sources_exclude:
        sources_exclude_list = sources_exclude.split(',')
        sources_exclude_condition = f" AND cedd.source NOT IN ({','.join(['%s']*len(sources_exclude_list))})"
        params = params + sources_exclude_list

    query = f"""
        SELECT
            type, project, machine, source, tags, date, energy_kwh_sum, carbon_kg_sum, carbon_intensity_g_avg, record_count
        FROM
            carbondb_data as cedd
        WHERE
            user_id = %s
            {start_date_condition}
            {end_date_condition}
            {tags_include_condition}
            {tags_exclude_condition}
            {machines_include_condition}
            {machines_exclude_condition}
            {types_include_condition}
            {types_exclude_condition}
            {projects_include_condition}
            {projects_exclude_condition}
            {sources_include_condition}
            {sources_exclude_condition}

        ORDER BY
            date ASC
        ;
    """
    data = DB().fetch_all(query, params)

    return ORJSONResponse({'success': True, 'data': data})


@app.get('/v2/carbondb/filters')
async def carbondb_get_filters(
    user: User = Depends(authenticate)
    ):

    query = 'SELECT jsonb_object_agg(id, type) FROM carbondb_types WHERE user_id = %s'
    carbondb_types = DB().fetch_one(query, (user._id, ))[0]

    query = 'SELECT jsonb_object_agg(id, tag) FROM carbondb_tags WHERE user_id = %s'
    carbondb_tags = DB().fetch_one(query, (user._id, ))[0]

    query = 'SELECT jsonb_object_agg(id, machine) FROM carbondb_machines WHERE user_id = %s'
    carbondb_machines = DB().fetch_one(query, (user._id, ))[0]

    query = 'SELECT jsonb_object_agg(id, project) FROM carbondb_projects WHERE user_id = %s'
    carbondb_projects = DB().fetch_one(query, (user._id, ))[0]

    query = 'SELECT jsonb_object_agg(id, source) FROM carbondb_sources WHERE user_id = %s'
    carbondb_sources = DB().fetch_one(query, (user._id, ))[0]

    return ORJSONResponse({'success': True, 'data': {'types': carbondb_types, 'tags': carbondb_tags, 'machines': carbondb_machines, 'projects': carbondb_projects, 'sources': carbondb_sources}})


# @app.get('/v1/authentication/new')
# This will fail if the DB insert fails but still report 'success': True
# Must be reworked if we want to allow API based token generation
# async def get_authentication_token(name: str = None):
#     if name is not None and name.strip() == '':
#         name = None
#     return ORJSONResponse({'success': True, 'data': User.get_new(name)})

@app.get('/v1/authentication/data')
async def read_authentication_token(user: User = Depends(authenticate)):
    return ORJSONResponse({'success': True, 'data': user.to_dict()})

if __name__ == '__main__':
    app.run() # pylint: disable=no-member
