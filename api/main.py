import faulthandler

from xml.sax.saxutils import escape as xml_escape
from fastapi import FastAPI, Request, Response
from fastapi.responses import ORJSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from starlette.responses import RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from pydantic import BaseModel

import anybadge

# It seems like FastAPI already enables faulthandler as it shows stacktrace on SEGFAULT
# Is the redundant call problematic
faulthandler.enable()  # will catch segfaults and write to STDERR

from api.api_helpers import (add_phase_stats_statistics, determine_comparison_case,
                         html_escape_multi, get_phase_stats, get_phase_stats_object,
                         is_valid_uuid, rescale_energy_value, get_timeline_query,
                         get_run_info, get_machine_list)

from lib.global_config import GlobalConfig
from lib.db import DB
from lib import email_helpers
from lib import error_helpers
from tools.jobs import Job
from tools.timeline_projects import TimelineProject


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

    # This saves us from crawler requests to the IP directly, or to our DNS reverse PTR etc.
    # which would create email noise
    request_url = str(request.url).replace('https://', '').replace('http://', '')
    api_url = GlobalConfig().config['cluster']['api_url'].replace('https://', '').replace('http://', '')

    if not request_url.startswith(api_url):
        return

    if GlobalConfig().config['admin']['no_emails'] is False:
        email_helpers.send_error_email(
            GlobalConfig().config['admin']['email'],
            error_helpers.format_error(error_message),
            run_id=None,
        )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    await log_exception(request, exc.body, exc)
    return ORJSONResponse(
        status_code=422, # HTTP_422_UNPROCESSABLE_ENTITY
        content=jsonable_encoder({'success': False, 'err': exc.errors(), 'body': exc.body}),
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    await log_exception(request, exc.detail, exc)
    return ORJSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({'success': False, 'err': exc.detail}),
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
    return ORJSONResponse({'success': True, 'data': escaped_data})

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
    return ORJSONResponse({'success': True, 'data': escaped_data})


# return a list of all possible registered machines
@app.get('/v1/machines/')
async def get_machines():

    data = get_machine_list()
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/v1/repositories')
async def get_repositories(uri: str | None = None, branch: str | None = None, machine_id: int | None = None, machine: str | None = None, filename: str | None = None, ):
    query = """
            SELECT DISTINCT(r.uri)
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


    query = f"{query} ORDER BY r.uri ASC"

    data = DB().fetch_all(query, params=tuple(params))
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    escaped_data = [html_escape_multi(run) for run in data]

    return ORJSONResponse({'success': True, 'data': escaped_data})

# A route to return all of the available entries in our catalog.
@app.get('/v1/runs')
async def get_runs(uri: str | None = None, branch: str | None = None, machine_id: int | None = None, machine: str | None = None, filename: str | None = None, limit: int | None = None):

    query = """
            SELECT r.id, r.name, r.uri, COALESCE(r.branch, 'main / master'), r.created_at, r.invalid_run, r.filename, m.description, r.commit_hash, r.end_measurement
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
        branch = run_info['branch'] if run_info['branch'] is not None else 'main / master'
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

    return ORJSONResponse({'success': True, 'data': phase_stats_object})


@app.get('/v1/phase_stats/single/{run_id}')
async def get_phase_stats_single(run_id: str):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    try:
        phase_stats = get_phase_stats([run_id])
        phase_stats_object = get_phase_stats_object(phase_stats, None)
        phase_stats_object = add_phase_stats_statistics(phase_stats_object)

    except RuntimeError:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': phase_stats_object})


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

    query = f" {query} ORDER BY measurements.metric ASC, measurements.detail_name ASC, measurements.time ASC"

    params = params = (run_id, )

    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/v1/timeline')
async def get_timeline_stats(uri: str, machine_id: int, branch: str | None = None, filename: str | None = None, start_date: str | None = None, end_date: str | None = None, metrics: str | None = None, phase: str | None = None, sorting: str | None = None,):
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
    return Response(content=str(badge), media_type="image/svg+xml")


# A route to return all of the available entries in our catalog.
@app.get('/v1/badge/single/{run_id}')
async def get_badge_single(run_id: str, metric: str = 'ml-estimated'):

    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

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
    return Response(content=str(badge), media_type="image/svg+xml")


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
                    AND COALESCE(p.branch, 'main / master') = COALESCE(r.branch, 'main / master')
                    AND COALESCE(p.filename, 'usage_scenario.yml') = COALESCE(r.filename, 'usage_scenario.yml')
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
async def get_jobs():
    # Do not get the email jobs as they do not need to be display in the frontend atm
    query = """
        SELECT j.id, j.name, j.url, j.filename, j.branch, m.description, j.state, j.updated_at, j.created_at
        FROM jobs as j
        LEFT JOIN machines as m on m.id = j.machine_id
        ORDER BY j.updated_at, j.created_at ASC
    """
    data = DB().fetch_all(query)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})


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

    if not DB().fetch_one('SELECT id FROM machines WHERE id=%s AND available=TRUE', params=(software.machine_id,)):
        raise RequestValidationError('Machine does not exist')


    if software.branch.strip() == '':
        software.branch = None

    if software.filename.strip() == '':
        software.filename = 'usage_scenario.yml'

    if software.schedule_mode not in ['one-off', 'time', 'commit', 'variance']:
        raise RequestValidationError(f"Please select a valid measurement interval. ({software.schedule_mode}) is unknown.")

    # notify admin of new add
    if GlobalConfig().config['admin']['no_emails'] is False:
        email_helpers.send_admin_email(f"New run added from Web Interface: {software.name}", software)

    if software.schedule_mode == 'one-off':
        Job.insert(software.name, software.url,  software.email, software.branch, software.filename, software.machine_id)
    elif software.schedule_mode == 'variance':
        for _ in range(0,3):
            Job.insert(software.name, software.url,  software.email, software.branch, software.filename, software.machine_id)
    else:
        TimelineProject.insert(software.name, software.url, software.branch, software.filename, software.machine_id, software.schedule_mode)

    return ORJSONResponse({'success': True}, status_code=202)


@app.get('/v1/run/{run_id}')
async def get_run(run_id: str):
    if run_id is None or not is_valid_uuid(run_id):
        raise RequestValidationError('Run ID is not a valid UUID or empty')

    data = get_run_info(run_id)

    if data is None or data == []:
        return Response(status_code=204) # No-Content

    data = html_escape_multi(data)

    return ORJSONResponse({'success': True, 'data': data})

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
    workflow: str
    run_id: str
    source: str
    label: str
    duration: int

@app.post('/v1/ci/measurement/add')
async def post_ci_measurement_add(measurement: CI_Measurement):
    for key, value in measurement.model_dump().items():
        match key:
            case 'unit':
                if value is None or value.strip() == '':
                    raise RequestValidationError(f"{key} is empty")
                if value != 'mJ':
                    raise RequestValidationError("Unit is unsupported - only mJ currently accepted")
                continue

            case 'label':  # Optional fields
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
            ci_measurements (energy_value, energy_unit, repo, branch, workflow, run_id, label, source, cpu, commit_hash, duration, cpu_util_avg)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
    params = (measurement.energy_value, measurement.energy_unit, measurement.repo, measurement.branch,
            measurement.workflow, measurement.run_id,
            measurement.label, measurement.source, measurement.cpu, measurement.commit_hash,
            measurement.duration, measurement.cpu_util_avg)

    DB().query(query=query, params=params)
    return ORJSONResponse({'success': True}, status_code=201)

@app.get('/v1/ci/measurements')
async def get_ci_measurements(repo: str, branch: str, workflow: str):
    query = """
        SELECT energy_value, energy_unit, run_id, created_at, label, cpu, commit_hash, duration, source, cpu_util_avg
        FROM ci_measurements
        WHERE repo = %s AND branch = %s AND workflow = %s
        ORDER BY run_id ASC, created_at ASC
    """
    params = (repo, branch, workflow)
    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return Response(status_code=204) # No-Content

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
        return Response(status_code=204) # No-Content

    return ORJSONResponse({'success': True, 'data': data})

@app.get('/v1/ci/badge/get')
async def get_ci_badge_get(repo: str, branch: str, workflow:str):
    query = """
        SELECT SUM(energy_value), MAX(energy_unit), MAX(run_id)
        FROM ci_measurements
        WHERE repo = %s AND branch = %s AND workflow = %s
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


if __name__ == '__main__':
    app.run()
