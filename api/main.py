import faulthandler
import time

# It seems like FastAPI already enables faulthandler as it shows stacktrace on SEGFAULT
# Is the redundant call problematic
faulthandler.enable()  # will catch segfaults and write to STDERR

import zlib
import base64
import orjson
from typing import List
from xml.sax.saxutils import escape as xml_escape
import math
from fastapi import FastAPI, Request, Response
from fastapi.responses import ORJSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from datetime import date

from starlette.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from pydantic import BaseModel, ValidationError, field_validator
from typing import Optional
from uuid import UUID

import anybadge

from api.object_specifications import Measurement
from api.api_helpers import (ORJSONResponseObjKeep, add_phase_stats_statistics, carbondb_add, determine_comparison_case,
                         html_escape_multi, get_phase_stats, get_phase_stats_object,
                         is_valid_uuid, rescale_energy_value, get_timeline_query,
                         get_run_info, get_machine_list, get_artifact, store_artifact)

from lib.global_config import GlobalConfig
from lib.db import DB
from lib.diff import get_diffable_row, diff_rows
from lib import error_helpers
from lib.job.base import Job
from tools.timeline_projects import TimelineProject

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
        headers=request.headers,
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
        headers=request.headers,
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
            headers=request.headers,
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
            GROUP BY r.uri
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
            SELECT r.id, r.name, r.uri, r.branch, r.created_at, r.invalid_run, r.filename, m.description, r.commit_hash, r.end_measurement, r.failed
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
    try:
        phase_stats = get_phase_stats(ids)
    except RuntimeError:
        return Response(status_code=204) # No-Content
    try:
        phase_stats_object = get_phase_stats_object(phase_stats, case)
        phase_stats_object = add_phase_stats_statistics(phase_stats_object)
        phase_stats_object['common_info'] = {}

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

    try:
        phase_stats = get_phase_stats([run_id])
        phase_stats_object = get_phase_stats_object(phase_stats, None)
        phase_stats_object = add_phase_stats_statistics(phase_stats_object)

    except RuntimeError:
        return Response(status_code=204) # No-Content

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

####

class HogMeasurement(BaseModel):
    time: int
    data: str
    settings: str
    machine_uuid: str

def replace_nan_with_zero(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                replace_nan_with_zero(v)
            elif isinstance(v, float) and math.isnan(v):
                obj[k] = 0
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, (dict, list)):
                replace_nan_with_zero(item)
            elif isinstance(item, float) and math.isnan(item):
                obj[i] = 0
    return obj


def validate_measurement_data(data):
    required_top_level_fields = [
        'coalitions', 'all_tasks', 'elapsed_ns', 'processor', 'thermal_pressure'
    ]
    for field in required_top_level_fields:
        if field not in data:
            raise ValueError(f"Missing required field: {field}")

    # Validate 'coalitions' structure
    if not isinstance(data['coalitions'], list):
        raise ValueError("Expected 'coalitions' to be a list")

    for coalition in data['coalitions']:
        required_coalition_fields = [
            'name', 'tasks', 'energy_impact_per_s', 'cputime_ms_per_s',
            'diskio_bytesread', 'diskio_byteswritten', 'intr_wakeups', 'idle_wakeups'
        ]
        for field in required_coalition_fields:
            if field not in coalition:
                raise ValueError(f"Missing required coalition field: {field}")
            if field == 'tasks' and not isinstance(coalition['tasks'], list):
                raise ValueError(f"Expected 'tasks' to be a list in coalition: {coalition['name']}")

    # Validate 'all_tasks' structure
    if 'energy_impact_per_s' not in data['all_tasks']:
        raise ValueError("Missing 'energy_impact_per_s' in 'all_tasks'")

    # Validate 'processor' structure based on the processor type
    processor_fields = data['processor'].keys()
    if 'ane_energy' in processor_fields:
        required_processor_fields = ['combined_power', 'cpu_energy', 'gpu_energy', 'ane_energy']
    elif 'package_joules' in processor_fields:
        required_processor_fields = ['package_joules', 'cpu_joules', 'igpu_watts']
    else:
        raise ValueError("Unknown processor type")

    for field in required_processor_fields:
        if field not in processor_fields:
            raise ValueError(f"Missing required processor field: {field}")

    # All checks passed
    return True

@app.post('/v1/hog/add')
async def hog_add(measurements: List[HogMeasurement]):

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
            validate_measurement_data(measurement_data)
        except ValueError as exc:
            print(f"Caught Exception in validate_measurement_data() {exc.__class__.__name__} {exc}")
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
                    settings)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        return ORJSONResponse({'success': False, 'err': 'machine_uuid is empty or malformed'}, status_code=400)

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
        return ORJSONResponse({'success': False, 'err': 'machine_uuid is empty'}, status_code=400)

    if measurements_id_start is None:
        return ORJSONResponse({'success': False, 'err': 'measurements_id_start is empty'}, status_code=400)

    if measurements_id_end is None:
        return ORJSONResponse({'success': False, 'err': 'measurements_id_end is empty'}, status_code=400)


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
        return ORJSONResponse({'success': False, 'err': 'machine_uuid is empty'}, status_code=400)

    if measurements_id_start is None:
        return ORJSONResponse({'success': False, 'err': 'measurements_id_start is empty'}, status_code=400)

    if measurements_id_end is None:
        return ORJSONResponse({'success': False, 'err': 'measurements_id_end is empty'}, status_code=400)

    if coalition_name is None or not coalition_name.strip():
        return ORJSONResponse({'success': False, 'err': 'coalition_name is empty'}, status_code=400)

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



####

class Software(BaseModel):
    name: str
    url: str
    email: str
    filename: str
    branch: str
    machine_id: int
    schedule_mode: str

@app.post('/v1/software/add')
async def software_add(software: Software):

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


    if software.schedule_mode not in ['one-off', 'daily', 'weekly', 'commit', 'variance']:
        raise RequestValidationError(f"Please select a valid measurement interval. ({software.schedule_mode}) is unknown.")

    # notify admin of new add
    if notification_email := GlobalConfig().config['admin']['notification_email']:
        Job.insert('email', name='New run added from Web Interface', message=str(software), email=notification_email)


    if software.schedule_mode in ['daily', 'weekly', 'commit']:
        TimelineProject.insert(software.name, software.url, software.branch, software.filename, software.machine_id, software.schedule_mode)

    # even for timeline projects we do at least one run
    amount = 10 if software.schedule_mode == 'variance' else 1
    for _ in range(0,amount):
        Job.insert('run', name=software.name, url=software.url, email=software.email, branch=software.branch, filename=software.filename, machine_id=software.machine_id)

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

# pylint: disable=invalid-name
class CI_Measurement(BaseModel):
    energy_value: int
    energy_unit: str
    repo: str
    branch: str
    cpu: str
    cpu_util_avg: float
    commit_hash: str
    workflow: str   # workflow_id, change when we make API change of workflow_name being mandatory
    run_id: str
    source: str
    label: str
    duration: int
    workflow_name: str = None
    cb_company_uuid: Optional[str] = ''
    cb_project_uuid: Optional[str] = ''
    cb_machine_uuid: Optional[str] = ''
    lat: Optional[str] = ''
    lon: Optional[str] = ''
    city: Optional[str] = ''
    co2i: Optional[str] = ''
    co2eq: Optional[str] = ''

@app.post('/v1/ci/measurement/add')
async def post_ci_measurement_add(request: Request, measurement: CI_Measurement):
    for key, value in measurement.model_dump().items():
        match key:
            case 'unit':
                if value is None or value.strip() == '':
                    raise RequestValidationError(f"{key} is empty")
                if value != 'mJ':
                    raise RequestValidationError("Unit is unsupported - only mJ currently accepted")
                continue

            case 'label' | 'workflow_name' | 'cb_company_uuid' | 'cb_project_uuid' | 'cb_machine_uuid' | 'lat' | 'lon' | 'city' | 'co2i' | 'co2eq':  # Optional fields
                continue

            case _:
                if value is None:
                    raise RequestValidationError(f"{key} is empty")
                if isinstance(value, str):
                    if value.strip() == '':
                        raise RequestValidationError(f"{key} is empty")

    measurement = html_escape_multi(measurement)

    query = """
        INSERT INTO
            ci_measurements (energy_value,
                            energy_unit,
                            repo,
                            branch,
                            workflow_id,
                            run_id,
                            label,
                            source,
                            cpu,
                            commit_hash,
                            duration,
                            cpu_util_avg,
                            workflow_name,
                            lat,
                            lon,
                            city,
                            co2i,
                            co2eq
                            )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
    params = (measurement.energy_value, measurement.energy_unit, measurement.repo, measurement.branch,
            measurement.workflow, measurement.run_id, measurement.label, measurement.source, measurement.cpu,
            measurement.commit_hash, measurement.duration, measurement.cpu_util_avg, measurement.workflow_name,
            measurement.lat, measurement.lon, measurement.city, measurement.co2i, measurement.co2eq)

    DB().query(query=query, params=params)

    # If one of these is specified we add the data to the CarbonDB
    if measurement.cb_company_uuid != '' or measurement.cb_project_uuid != '' or measurement.cb_machine_uuid != '':

        if measurement.cb_machine_uuid == '':
            raise ValueError("You need to specify a machine")

        client_ip = request.headers.get("x-forwarded-for")
        if client_ip:
            client_ip = client_ip.split(",")[0]
        else:
            client_ip = request.client.host

        energydata = {
            'type': 'machine.ci',
            'energy_value': measurement.energy_value * 0.001,
            'time_stamp': int(time.time() * 1e6),
            'company': measurement.cb_company_uuid,
            'project': measurement.cb_project_uuid,
            'machine': measurement.cb_machine_uuid,
            'tags': f"{measurement.label},{measurement.repo},{measurement.branch},{measurement.workflow}"
        }

        # If there is an error the function will raise an Error
        carbondb_add(client_ip, [energydata])

    return ORJSONResponse({'success': True}, status_code=201)

@app.get('/v1/ci/measurements')
async def get_ci_measurements(repo: str, branch: str, workflow: str, start_date: date, end_date: date):

    query = """
        SELECT energy_value, energy_unit, run_id, created_at, label, cpu, commit_hash, duration, source, cpu_util_avg,
               (SELECT workflow_name FROM ci_measurements AS latest_workflow
                WHERE latest_workflow.repo = ci_measurements.repo
                AND latest_workflow.branch = ci_measurements.branch
                AND latest_workflow.workflow_id = ci_measurements.workflow_id
                ORDER BY latest_workflow.created_at DESC
                LIMIT 1) AS workflow_name, lat, lon, city, co2i, co2eq
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
        SELECT SUM(energy_value), MAX(energy_unit), MAX(run_id)
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
    energy_unit = data[1]

    [energy_value, energy_unit] = rescale_energy_value(energy_value, energy_unit)
    badge_value= f"{energy_value:.2f} {energy_unit}"

    badge = anybadge.Badge(
        label='Energy Used',
        value=xml_escape(badge_value),
        num_value_padding_chars=1,
        default_color='green')
    return Response(content=str(badge), media_type="image/svg+xml")


class EnergyData(BaseModel):
    type: str
    company: Optional[str] = None
    machine: UUID
    project: Optional[str] = None
    tags: Optional[str] = None
    time_stamp: str # is expected to be in microseconds
    energy_value: str # is expected to be in mJ

    @field_validator('company', 'project', 'tags')
    @classmethod
    def empty_str_to_none(cls, values, _):
        if values == '':
            return None
        return values

@app.post('/v1/carbondb/add')
async def add_carbondb(request: Request, energydatas: List[EnergyData]):

    client_ip = request.headers.get("x-forwarded-for")
    if client_ip:
        client_ip = client_ip.split(",")[0]
    else:
        client_ip = request.client.host

    carbondb_add(client_ip, energydatas)

    return Response(status_code=204)


@app.get('/v1/carbondb/machine/day/{machine_uuid}')
async def carbondb_get_machine_details(machine_uuid: str):

    if machine_uuid is None or not is_valid_uuid(machine_uuid):
        return ORJSONResponse({'success': False, 'err': 'machine_uuid is empty or malformed'}, status_code=400)

    query = """
        SELECT
            *
        FROM
            carbondb_energy_data_day
        WHERE
            machine = %s
        ORDER BY
            date
        ;
    """

    data = DB().fetch_all(query, (machine_uuid,))

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/v1/carbondb/{cptype}/{uuid}')
async def carbondb_get_company_project_details(cptype: str, uuid: str):

    if uuid is None or not is_valid_uuid(uuid):
        return ORJSONResponse({'success': False, 'err': 'uuid is empty or malformed'}, status_code=400)

    if cptype.lower() != 'project' and cptype.lower() != 'company':
        return ORJSONResponse({'success': False, 'err': 'type needs to be company or project'}, status_code=400)

    query = f"""
        SELECT
            machine,
            SUM(energy_sum),
            SUM(co2_sum),
            AVG(carbon_intensity_avg),
            ARRAY_AGG(DISTINCT u.tag) AS all_tags
        FROM
            public.carbondb_energy_data_day e
			LEFT JOIN LATERAL unnest(e.tags) AS u(tag) ON true
        WHERE
            {cptype.lower()}=%s
        GROUP BY
            machine
        ;
    """
    data = DB().fetch_all(query, (uuid,))

    return ORJSONResponse({'success': True, 'data': data})

if __name__ == '__main__':
    app.run() # pylint: disable=no-member
