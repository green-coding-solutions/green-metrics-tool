
# pylint: disable=import-error
# pylint: disable=no-name-in-module
# pylint: disable=wrong-import-position

import json
import faulthandler
import sys
import os

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import ORJSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from starlette.responses import RedirectResponse
from pydantic import BaseModel

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../lib')
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../tools')

from global_config import GlobalConfig
from db import DB
import jobs
import email_helpers
import error_helpers
import psycopg
import anybadge
from api_helpers import (add_phase_stats_statistics, determine_comparison_case,
                         sanitize, get_phase_stats, get_phase_stats_object,
                         is_valid_uuid, rescale_energy_value)


# It seems like FastAPI already enables faulthandler as it shows stacktrace on SEGFAULT
# Is the redundant call problematic
faulthandler.enable()  # will catch segfaults and write to STDERR

app = FastAPI()

async def log_exception(request: Request, body, exc):
    error_message = f"""
        Error in API call

        URL: {request.url}

        Query-Params: {request.query_params}

        Client: {request.client}

        Headers: {str(request.headers)}

        Body: {body}

        Exception: {exc}
    """
    error_helpers.log_error(error_message)
    email_helpers.send_error_email(
        GlobalConfig().config['admin']['email'],
        error_helpers.format_error(error_message),
        project_id=None,
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    await log_exception(request, exc.body, exc)
    return ORJSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )

async def catch_exceptions_middleware(request: Request, call_next):
    #pylint: disable=broad-except
    try:
        return await call_next(request)
    except Exception as exc:
        # body = await request.body()  # This blocks the application. Unclear atm how to handle it properly
        # seems like a bug: https://github.com/tiangolo/fastapi/issues/394
        # Although the issue is closed the "solution" still behaves with same failure
        await log_exception(request, None, exc)
        return ORJSONResponse(
            content={
                'success': False,
                'err': 'Technical error with getting data from the API - Please contact us: info@green-coding.berlin',
            },
            status_code=500,
        )


# Binding the Exception middleware must confusingly come BEFORE the CORS middleware.
# Otherwise CORS will not be sent in response
app.middleware('http')(catch_exceptions_middleware)

origins = [
    GlobalConfig().config['cluster']['metrics_url'],
    GlobalConfig().config['cluster']['api_url'],
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/')
async def home():
    return RedirectResponse(url='/docs')


# A route to return all of the available entries in our catalog.
@app.get('/v1/notes/{project_id}')
async def get_notes(project_id):
    if project_id is None or not is_valid_uuid(project_id):
        return ORJSONResponse({'success': False, 'err': 'Project ID is not a valid UUID or empty'}, status_code=400)

    query = """
            SELECT project_id, detail_name, note, time
            FROM notes
            WHERE project_id = %s
            ORDER BY created_at DESC  -- important to order here, the charting library in JS cannot do that automatically!
            """
    data = DB().fetch_all(query, (project_id,))
    if data is None or data == []:
        return ORJSONResponse({'success': False, 'err': 'Data is empty'}, status_code=204)

    escaped_data = [sanitize(note) for note in data]
    return ORJSONResponse({'success': True, 'data': escaped_data})

@app.get('/v1/network/{project_id}')
async def get_network(project_id):
    if project_id is None or not is_valid_uuid(project_id):
        return ORJSONResponse({'success': False, 'err': 'Project ID is not a valid UUID or empty'}, status_code=400)

    query = """
            SELECT *
            FROM network_intercepts
            WHERE project_id = %s
            ORDER BY time
            """
    data = DB().fetch_all(query, (project_id,))
    if data is None:
        data == []

    escaped_data = [sanitize(intercept) for intercept in data]
    return ORJSONResponse({'success': True, 'data': escaped_data})


# return a list of all possible registered machines
@app.get('/v1/machines/')
async def get_machines():
    query = """
            SELECT id, description
            FROM machines
            ORDER BY description ASC
            """
    data = DB().fetch_all(query)
    if data is None or data == []:
        return ORJSONResponse({'success': False, 'err': 'Data is empty'}, status_code=204)

    return ORJSONResponse({'success': True, 'data': data})


# A route to return all of the available entries in our catalog.
@app.get('/v1/projects')
async def get_projects():
    query = """
            SELECT a.id, a.name, a.uri, COALESCE(a.branch, 'main / master'), a.end_measurement, a.last_run, a.invalid_project, a.filename, b.description
            FROM projects as a
            LEFT JOIN machines as b on a.machine_id = b.id
            ORDER BY a.created_at DESC  -- important to order here, the charting library in JS cannot do that automatically!
            """
    data = DB().fetch_all(query)
    if data is None or data == []:
        return ORJSONResponse({'success': False, 'err': 'Data is empty'}, status_code=204)

    escaped_data = [sanitize(project) for project in data]

    return ORJSONResponse({'success': True, 'data': escaped_data})


# Just copy and paste if we want to deprecate URLs
# @app.get('/v1/measurements/uri', deprecated=True) # Here you can see, that URL is nevertheless accessible as variable
# later if supplied. Also deprecation shall be used once we move to v2 for all v1 routesthrough

@app.get('/v1/compare')
async def compare_in_repo(ids: str):
    if ids is None or not ids.strip():
        return ORJSONResponse({'success': False, 'err': 'Project_id is empty'}, status_code=400)
    ids = ids.split(',')
    if not all(is_valid_uuid(id) for id in ids):
        return ORJSONResponse({'success': False, 'err': 'One of Project IDs is not a valid UUID or empty'}, status_code=400)

    try:
        case = determine_comparison_case(ids)
    except RuntimeError as err:
        return ORJSONResponse({'success': False, 'err': str(err)}, status_code=400)
    try:
        phase_stats = get_phase_stats(ids)
    except RuntimeError:
        return ORJSONResponse(None, status_code=204)
    try:
        phase_stats_object = get_phase_stats_object(phase_stats, case)
        phase_stats_object = add_phase_stats_statistics(phase_stats_object)
        phase_stats_object['common_info'] = {}

        project_info_response = await get_project(ids[0])
        project_info = json.loads(project_info_response.body)['data']

        machines_response = await get_machines()
        machines_info = json.loads(machines_response.body)['data']
        machines = {machine[0]: machine[1] for machine in machines_info}

        machine = machines[project_info['machine_id']]
        uri = project_info['uri']
        usage_scenario = project_info['usage_scenario']['name']
        branch = project_info['branch'] if project_info['branch'] is not None else 'main / master'
        commit = project_info['commit_hash']

        match case:
            case 'Repeated Run':
                # same repo, same usage scenarios, same machines, same branches, same commit hashes
                phase_stats_object['common_info']['Repository'] = uri
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
                phase_stats_object['common_info']['Usage Scenario'] = usage_scenario
                phase_stats_object['common_info']['Branch'] = branch
                phase_stats_object['common_info']['Commit'] = commit
            case 'Commit':
                # same repo, same usage scenarios, same machines, diff commit hashes
                phase_stats_object['common_info']['Repository'] = uri
                phase_stats_object['common_info']['Usage Scenario'] = usage_scenario
                phase_stats_object['common_info']['Machine'] = machine
            case 'Repository':
                # diff repo, diff usage scenarios, same machine,  same branches, diff/same commits_hashes
                phase_stats_object['common_info']['Machine'] = machine
                phase_stats_object['common_info']['Branch'] = branch
            case 'Branch':
                # same repo, same usage scenarios, same machines, diff branch
                phase_stats_object['common_info']['Repository'] = uri
                phase_stats_object['common_info']['Usage Scenario'] = usage_scenario
                phase_stats_object['common_info']['Machine'] = machine

    except RuntimeError as err:
        return ORJSONResponse({'success': False, 'err': str(err)}, status_code=500)

    return ORJSONResponse({'success': True, 'data': phase_stats_object})


# This route is primarily used to load phase stats it into a pandas data frame
@app.get('/v1/phase_stats/single/{project_id}')
async def get_phase_stats_single(project_id: str):
    if project_id is None or not is_valid_uuid(project_id):
        return ORJSONResponse({'success': False, 'err': 'Project ID is not a valid UUID or empty'}, status_code=400)

    try:
        phase_stats = get_phase_stats([project_id])
        phase_stats_object = get_phase_stats_object(phase_stats, None)
        phase_stats_object = add_phase_stats_statistics(phase_stats_object)

    except RuntimeError as err:

        return ORJSONResponse({'success': False, 'err': str(err)}, status_code=204)

    return ORJSONResponse({'success': True, 'data': phase_stats_object})


# This route gets the measurements to be displayed in a timeline chart
@app.get('/v1/measurements/single/{project_id}')
async def get_measurements_single(project_id: str):
    if project_id is None or not is_valid_uuid(project_id):
        return ORJSONResponse({'success': False, 'err': 'Project ID is not a valid UUID or empty'}, status_code=400)

    query = """
            SELECT measurements.detail_name, measurements.time, measurements.metric,
                   measurements.value, measurements.unit, measurements.phase
            FROM measurements
            WHERE measurements.project_id = %s
            """

    # extremely important to order here, cause the charting library in JS cannot do that automatically!

    query = f" {query} ORDER BY measurements.metric ASC, measurements.detail_name ASC, measurements.time ASC"

    params = params = (project_id, )

    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return ORJSONResponse({'success': False, 'err': 'Data is empty'}, status_code=204)

    return ORJSONResponse({'success': True, 'data': data})


# A route to return all of the available entries in our catalog.
@app.get('/v1/badge/single/{project_id}')
async def get_badge_single(project_id: str, metric: str = 'ml-estimated'):

    if project_id is None or not is_valid_uuid(project_id):
        return ORJSONResponse({'success': False, 'err': 'Project ID is not a valid UUID or empty'}, status_code=400)

    query = '''
        WITH times AS (
            SELECT start_measurement, end_measurement FROM projects WHERE id = %s
        ) SELECT
            (SELECT start_measurement FROM times), (SELECT end_measurement FROM times),
            SUM(measurements.value), measurements.unit
        FROM measurements
        WHERE
            measurements.project_id = %s
            AND measurements.time >= (SELECT start_measurement FROM times)
            AND measurements.time <= (SELECT end_measurement FROM times)
            AND measurements.metric LIKE %s
        GROUP BY measurements.unit
    '''

    value = None
    if metric == 'ml-estimated':
        value = 'psu_energy_ac_xgboost_machine'
    elif metric == 'RAPL':
        value = '%_rapl_%'
    elif metric == 'AC':
        value = 'psu_energy_ac_%'
    else:
        return ORJSONResponse({'success': False, 'err': f"Unknown metric '{metric}' submitted"}, status_code=400)

    params = (project_id, project_id, value)
    data = DB().fetch_one(query, params=params)

    if data is None or data == []:
        badge_value = 'No energy data yet'
    else:
        [energy_value, energy_unit] = rescale_energy_value(data[2], data[3])
        badge_value= f"{energy_value:.2f} {energy_unit} via {metric}"

    badge = anybadge.Badge(
        label='Energy cost',
        value=badge_value,
        num_value_padding_chars=1,
        default_color='cornflowerblue')
    return Response(content=str(badge), media_type="image/svg+xml")


class Project(BaseModel):
    name: str
    url: str
    email: str
    filename: str
    branch: str
    machine_id: int

@app.post('/v1/project/add')
async def post_project_add(project: Project):

    if project.url is None or project.url.strip() == '':
        return ORJSONResponse({'success': False, 'err': 'URL is empty'}, status_code=400)

    if project.name is None or project.name.strip() == '':
        return ORJSONResponse({'success': False, 'err': 'Name is empty'}, status_code=400)

    if project.email is None or project.email.strip() == '':
        return ORJSONResponse({'success': False, 'err': 'E-mail is empty'}, status_code=400)

    if project.branch.strip() == '':
        project.branch = None

    if project.filename.strip() == '':
        project.filename = 'usage_scenario.yml'

    if project.machine_id == 0:
        project.machine_id = None

    project = sanitize(project)

    # Note that we use uri here as the general identifier, however when adding through web interface we only allow urls
    query = """
        INSERT INTO projects (uri,name,email,branch,filename)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """
    params = (project.url, project.name, project.email, project.branch, project.filename)
    project_id = DB().fetch_one(query, params=params)[0]
    # This order as selected on purpose. If the admin mail fails, we currently do
    # not want the job to be queued, as we want to monitor every project execution manually
    email_helpers.send_admin_email(
        f"New project added from Web Interface: {project.name}", project
    )  # notify admin of new project
    jobs.insert_job('project', project_id, project.machine_id)

    return ORJSONResponse({'success': True}, status_code=202)


@app.get('/v1/project/{project_id}')
async def get_project(project_id: str):
    if project_id is None or not is_valid_uuid(project_id):
        return ORJSONResponse({'success': False, 'err': 'Project ID is not a valid UUID or empty'}, status_code=400)

    query = """
            SELECT
                id, name, uri, branch, commit_hash,
                (SELECT STRING_AGG(t.name, ', ' ) FROM unnest(projects.categories) as elements
                    LEFT JOIN categories as t on t.id = elements) as categories,
                start_measurement, end_measurement,
                measurement_config, machine_specs, machine_id, usage_scenario,
                last_run, created_at, invalid_project, phases, logs
            FROM projects
            WHERE id = %s
            """
    params = (project_id,)
    data = DB().fetch_one(query, params=params, row_factory=psycopg.rows.dict_row)
    if data is None or data == []:
        return ORJSONResponse({'success': False, 'err': 'Data is empty'}, status_code=204)

    data = sanitize(data)

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/robots.txt')
async def robots_txt():
    data =  "User-agent: *\n"
    data += "Disallow: /"

    return Response(content=data, media_type='text/plain')

# pylint: disable=invalid-name
class CI_Measurement(BaseModel):
    value: int
    unit: str
    repo: str
    branch: str
    cpu: str
    commit_hash: str
    workflow: str
    run_id: str
    project_id: str
    source: str
    label: str
    duration: int

@app.post('/v1/ci/measurement/add')
async def post_ci_measurement_add(measurement: CI_Measurement):
    for key, value in measurement.dict().items():
        match key:
            case 'project_id':
                if value is None or value.strip() == '':
                    measurement.project_id = None
                    continue
                if not is_valid_uuid(value.strip()):
                    return ORJSONResponse({'success': False, 'err': f"project_id '{value}' is not a valid uuid"}, status_code=400)
                continue

            case 'unit':
                if value is None or value.strip() == '':
                    return ORJSONResponse({'success': False, 'err': f"{key} is empty"}, status_code=400)
                if value != 'mJ':
                    return ORJSONResponse({'success': False, 'err': "Unit is unsupported - only mJ currently accepted"}, status_code=400)
                continue

            case 'label':  # Optional fields
                continue

            case _:
                if value is None:
                    return ORJSONResponse({'success': False, 'err': f"{key} is empty"}, status_code=400)
                if isinstance(value, str):
                    if value.strip() == '':
                        return ORJSONResponse({'success': False, 'err': f"{key} is empty"}, status_code=400)

    measurement = sanitize(measurement)

    query = """
        INSERT INTO
            ci_measurements (value, unit, repo, branch, workflow, run_id, project_id, label, source, cpu, commit_hash, duration)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
    params = (measurement.value, measurement.unit, measurement.repo, measurement.branch,
            measurement.workflow, measurement.run_id, measurement.project_id,
            measurement.label, measurement.source, measurement.cpu, measurement.commit_hash, measurement.duration)

    DB().query(query=query, params=params)
    return ORJSONResponse({'success': True}, status_code=201)

@app.get('/v1/ci/measurements')
async def get_ci_measurements(repo: str, branch: str, workflow: str):
    query = """
        SELECT value, unit, run_id, created_at, label, cpu, commit_hash, duration, source
        FROM ci_measurements
        WHERE repo = %s AND branch = %s AND workflow = %s
        ORDER BY run_id ASC, created_at ASC
    """
    params = (repo, branch, workflow)
    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return ORJSONResponse({'success': False, 'err': 'Data is empty'}, status_code=204)

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/v1/ci/projects')
async def get_ci_projects():
    query = """
        SELECT repo, branch, workflow, source, MAX(created_at)
        FROM ci_measurements
        GROUP BY repo, branch, workflow, source
        ORDER BY repo ASC
    """

    data = DB().fetch_all(query)
    if data is None or data == []:
        return ORJSONResponse({'success': False, 'err': 'Data is empty'}, status_code=204)

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/v1/ci/badge/get')
async def get_ci_badge_get(repo: str, branch: str, workflow:str):
    query = """
        SELECT SUM(value), MAX(unit), MAX(run_id)
        FROM ci_measurements
        WHERE repo = %s AND branch = %s AND workflow = %s
        GROUP BY run_id
        ORDER BY MAX(created_at) DESC
        LIMIT 1
    """

    params = (repo, branch, workflow)
    data = DB().fetch_one(query, params=params)

    if data is None or data == []:
        return ORJSONResponse({'success': False, 'err': 'Data is empty'}, status_code=204)

    energy_unit = data[1]
    energy_value = data[0]

    [energy_value, energy_unit] = rescale_energy_value(energy_value, energy_unit)
    badge_value= f"{energy_value:.2f} {energy_unit}"

    badge = anybadge.Badge(
        label='Energy Used',
        value=badge_value,
        num_value_padding_chars=1,
        default_color='green')
    return Response(content=str(badge), media_type="image/svg+xml")


if __name__ == '__main__':
    app.run()
