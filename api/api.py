
# pylint: disable=import-error
# pylint: disable=no-name-in-module
# pylint: disable=wrong-import-position

import faulthandler
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../lib')
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../tools')

from pydantic import BaseModel
from starlette.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import Response
from fastapi import FastAPI, Request, Query
from global_config import GlobalConfig
from db import DB
import jobs
import email_helpers
import error_helpers
import psycopg2.extras
import anybadge


# It seems like FastAPI already enables faulthandler as it shows stacktrace on SEGFAULT
# Is the redundant call problematic
faulthandler.enable()  # will catch segfaults and write to STDERR

app = FastAPI()

async def catch_exceptions_middleware(request: Request, call_next):
    #pylint: disable=broad-except
    try:
        return await call_next(request)
    except Exception as exception:

        body = await request.body()
        error_message = f"""
            Error in API call

            URL: {request.url}

            Query-Params: {request.query_params}

            Client: {request.client}

            Headers: {str(request.headers)}

            Body: {body}

            Exception: {exception}
        """
        error_helpers.log_error(error_message)
        email_helpers.send_error_email(
            GlobalConfig().config['admin']['email'],
            error_helpers.format_error(error_message),
            project_id=None,
        )
        return JSONResponse(
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
    'http://metrics.green-coding.local:9142',
    'http://api.green-coding.local:9142',
    'https://metrics.green-coding.berlin',
    'https://api.green-coding.berlin',
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
    query = """
            SELECT
                project_id, detail_name, note, time
            FROM
                notes
            WHERE project_id = %s
            ORDER BY
                created_at DESC  -- important to order here, the charting library in JS cannot do that automatically!
            """
    data = DB().fetch_all(query, (project_id,))
    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}

    return {'success': True, 'data': data}


# A route to return all of the available entries in our catalog.
@app.get('/v1/projects')
async def get_projects():
    query = """
            SELECT
                id, name, uri, end_measurement, last_run
            FROM
                projects
            ORDER BY
                created_at DESC  -- important to order here, the charting library in JS cannot do that automatically!
            """
    data = DB().fetch_all(query)
    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}

    return {'success': True, 'data': data}


# Just copy and paste if we want to deprecate URLs
# @app.get('/v1/stats/uri', deprecated=True) # Here you can see, that URL is nevertheless accessible as variable
# later if supplied. Also deprecation shall be used once we move to v2 for all v1 routesthrough


# A route to return all of the available entries in our catalog.
@app.get('/v1/stats/uri')
async def get_stats_by_uri(uri: str, remove_idle: bool = False):
    if uri is None or uri.strip() == '':
        return {'success': False, 'err': 'URI is empty'}

    query = """
            WITH times AS (
                SELECT id, start_measurement, end_measurement FROM projects WHERE uri = %s
            ) SELECT
                projects.id as project_id, stats.detail_name, stats.time, stats.metric, stats.value, stats.unit
            FROM
                stats
            LEFT JOIN
                projects
            ON
                projects.id = stats.project_id
            WHERE
                projects.uri = %s
    """
    if remove_idle:
        query = f""" {query}
                AND
                stats.time > (SELECT times.start_measurement FROM times WHERE times.id = projects.id)
                AND
                stats.time < (SELECT times.end_measurement FROM times WHERE times.id = projects.id)
        """

    # extremly important to order here, cause the charting library in JS cannot do that automatically!
    query = f""" {query} ORDER BY
                stats.metric ASC, stats.detail_name ASC, stats.time ASC
            """

    params = (uri, uri)
    data = DB().fetch_all(query, params)

    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}

    return {'success': True, 'data': data}


# A route to return all of the available entries in our catalog.
@app.get('/v1/stats/single/{project_id}')
async def get_stats_single(project_id: str, remove_idle: bool = False):
    if project_id is None or project_id.strip() == '':
        return {'success': False, 'err': 'Project_id is empty'}

    query = """
            WITH times AS (
                SELECT start_measurement, end_measurement FROM projects WHERE id = %s
            ) SELECT
                stats.detail_name, stats.time, stats.metric, stats.value, stats.unit
            FROM
                stats
            WHERE
                stats.project_id = %s
            """
    if remove_idle:
        query = f""" {query}
                AND
                stats.time > (SELECT start_measurement FROM times)
                AND
                stats.time < (SELECT end_measurement FROM times)
        """

    # extremly important to order here, cause the charting library in JS cannot do that automatically!
    query = f" {query} ORDER BY stats.metric ASC, stats.detail_name ASC, stats.time ASC"

    params = params = (project_id, project_id)
    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}
    return {'success': True, 'data': data}


@app.get('/v1/stats/multi')
# pylint: disable=unsupported-binary-operation
# Here pylint does not understand the type hinting
async def get_stats_multi(pids: list[str] | None = Query(default=None)):
    for pid in pids:
        if pid is None or pid.strip() == '':
            return {'success': False, 'err': 'Project_id is empty'}

    query = """
            SELECT
                projects.id, projects.name, stats.detail_name, stats.time, stats.metric, stats.value, stats.unit
            FROM
                stats
            LEFT JOIN
                projects
            ON
                stats.project_id = projects.id
            WHERE
                stats.metric = ANY(ARRAY['cpu','mem','system-energy'])
            AND
                STATS.project_id = ANY(%s::uuid[])
            """
    params = (pids,)
    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}
    return {'success': True, 'data': data}


@app.get('/v1/stats/compare')
# pylint: disable=unsupported-binary-operation
# Here pylint does not understand the type hinting
async def get_stats_compare(pids: list[str] | None = Query(default=None)):
    for pid in pids:
        if pid is None or pid.strip() == '':
            return {'success': False, 'err': 'Project_id is empty'}

    query = """
            SELECT
                projects.name, stats.detail_name, stats.metric, stats.unit, AVG(stats.value)
            FROM
                stats
            LEFT JOIN
                projects
            ON
                stats.project_id = projects.id
            WHERE
                stats.metric = ANY(ARRAY['cpu','mem','system-energy'])
            AND
                STATS.project_id = ANY(%s::uuid[])
            GROUP BY projects.name, stats.detail_name, stats.metric
            """
    params = (pids,)
    data = DB().fetch_all(query, params=params)

    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}
    return {'success': True, 'data': data}

# A route to return all of the available entries in our catalog.
@app.get('/v1/badge/single/{project_id}')
async def get_badge_single(project_id: str, metric: str = 'ml-estimated'):

    if project_id is None or project_id.strip() == '':
        return {'success': False, 'err': 'Project_id is empty'}

    query = '''
        WITH times AS (
            SELECT start_measurement, end_measurement FROM projects WHERE id = %s
        ) SELECT
            (SELECT start_measurement FROM times), (SELECT end_measurement FROM times), SUM(stats.value), stats.unit
        FROM
            stats
        WHERE
            stats.project_id = %s
            AND stats.time >= (SELECT start_measurement FROM times)
            AND stats.time <= (SELECT end_measurement FROM times)
            AND stats.metric LIKE %s
            GROUP BY stats.unit
    '''

    value = None
    if metric == 'ml-estimated':
        value = 'psu_energy_xgboost_system'
    elif metric == 'RAPL':
        value = '%_rapl_%'
    elif metric == 'DC':
        value = 'psu_energy_dc_system'
    elif metric == 'AC':
        value = 'psu_energy_ac_system'
    else:
        raise RuntimeError('Unknown metric submitted')

    params = (project_id, project_id, value)
    data = DB().fetch_one(query, params=params)

    if data is None or data == []:
        badge_value = 'No energy stats yet'
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
    branch: str


@app.post('/v1/project/add')
async def post_project_add(project: Project):

    if project.url is None or project.url.strip() == '':
        return {'success': False, 'err': 'URL is empty'}

    if project.name is None or project.name.strip() == '':
        return {'success': False, 'err': 'Name is empty'}

    if project.email is None or project.email.strip() == '':
        return {'success': False, 'err': 'E-mail is empty'}

    if project.branch.strip() == '':
        project.branch = None

    # Note that we use uri here as the general identifier, however when adding through web interface we only allow urls
    query = """
        INSERT INTO
            projects (uri,name,email, branch)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """
    params = (project.url, project.name, project.email, project.branch)
    project_id = DB().fetch_one(query, params=params)
    # This order as selected on purpose. If the admin mail fails, we currently do
    # not want the job to be queued, as we want to monitor every project execution manually
    email_helpers.send_admin_email(
        f"New project added from Web Interface: {project.name}", project
    )  # notify admin of new project
    jobs.insert_job('project', project_id)

    return {'success': True}


@app.get('/v1/project/{project_id}')
async def get_project(project_id: str):
    query = """
            SELECT
                id, name, uri, branch, (SELECT STRING_AGG(t.name, ', ' ) FROM unnest(projects.categories) as elements \
                    LEFT JOIN categories as t on t.id = elements) as categories, start_measurement, end_measurement, \
                    measurement_config, machine_specs, usage_scenario, last_run, created_at
            FROM
                projects
            WHERE
                id = %s
            """
    params = (project_id,)
    data = DB().fetch_one(query, params=params, cursor_factory=psycopg2.extras.RealDictCursor)
    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}
    return {'success': True, 'data': data}

# Helper functions, not directly callable through routes

def rescale_energy_value(value, unit):
    # We only expect values to be mJ for energy!
    if unit != 'mJ':
        raise RuntimeError('Unexpected unit occured for energy rescaling: ', unit)

    energy_rescaled = [value, unit]

    # pylint: disable=multiple-statements
    if value > 1_000_000_000: energy_rescaled = [value/(10**12), 'GJ']
    elif value > 1_000_000_000: energy_rescaled = [value/(10**9), 'MJ']
    elif value > 1_000_000: energy_rescaled = [value/(10**6), 'kJ']
    elif value > 1_000: energy_rescaled = [value/(10**3), 'J']
    elif value < 0.001: energy_rescaled = [value*(10**3), 'nJ']

    return energy_rescaled

if __name__ == '__main__':
    app.run()
