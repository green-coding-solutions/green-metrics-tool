
# pylint: disable=import-error
# pylint: disable=no-name-in-module
# pylint: disable=wrong-import-position

import faulthandler
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../lib')
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../tools')

import uuid
from pydantic import BaseModel
from starlette.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import FastAPI, Request, Response, Query
from global_config import GlobalConfig
from db import DB
import jobs
import email_helpers
import error_helpers
import psycopg2.extras
import anybadge
from api_helpers import rescale_energy_value, is_valid_uuid, convertValue, determineComparisonCase, getPhaseStats, getPhaseStatsObject


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
    GlobalConfig().config['config']['metrics_url'],
    GlobalConfig().config['config']['api_url'],
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
            SELECT project_id, detail_name, note, time
            FROM notes
            WHERE project_id = %s
            ORDER BY created_at DESC  -- important to order here, the charting library in JS cannot do that automatically!
            """
    data = DB().fetch_all(query, (project_id,))
    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}

    return {'success': True, 'data': data}

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
        return {'success': False, 'err': 'Data is empty'}

    return {'success': True, 'data': data}

@app.get('/v1/compare')
async def compare_in_repo(ids: str):
    if(ids is None or ids.strip() == ''):
            return {'success': False, 'err': 'Project_id is empty'}
    ids = ids.split(',')

    try:
        case = determineComparisonCase(ids)
        phase_stats = getPhaseStats(ids)
        phase_stats_object = getPhaseStatsObject(phase_stats, case)
    except RuntimeError as err:
        return {'success': False, 'err': str(err)}

    return {'success': True, 'data': phase_stats_object}


# A route to return all of the available entries in our catalog.
@app.get('/v1/projects')
async def get_projects():
    query = """
            SELECT id, name, uri, branch, end_measurement, last_run, invalid_project
            FROM projects
            ORDER BY created_at DESC  -- important to order here, the charting library in JS cannot do that automatically!
            """
    data = DB().fetch_all(query)
    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}

    return {'success': True, 'data': data}


# Just copy and paste if we want to deprecate URLs
# @app.get('/v1/stats/uri', deprecated=True) # Here you can see, that URL is nevertheless accessible as variable
# later if supplied. Also deprecation shall be used once we move to v2 for all v1 routesthrough


# This route is primarily used to load phase stats it into a pandas data frame
@app.get('/v1/phase_stats/single/{project_id}')
async def get_phase_stats(project_id: str):
    if project_id is None or project_id.strip() == '':
        return {'success': False, 'err': 'Project ID is empty'}

    try:
        phase_stats = getPhaseStats([project_id])
        phase_stats_object = getPhaseStatsObject(phase_stats, None)
    except RuntimeError as err:

        return {'success': False, 'err': str(err)}

    return {'success': True, 'data': phase_stats_object}


# This route gets the stats to be displayed in a timeline chart
@app.get('/v1/stats/single/{project_id}')
async def get_stats_single(project_id: str, remove_idle: bool = False):
    if project_id is None or project_id.strip() == '':
        return {'success': False, 'err': 'Project_id is empty'}

    query = """
            WITH times AS (
                SELECT start_measurement, end_measurement FROM projects WHERE id = %s
            )
            SELECT stats.detail_name, stats.time, stats.metric, stats.value, stats.unit, stats.phase
            FROM stats
            WHERE stats.project_id = %s
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
        FROM stats
        WHERE
            stats.project_id = %s
            AND stats.time >= (SELECT start_measurement FROM times)
            AND stats.time <= (SELECT end_measurement FROM times)
            AND stats.metric LIKE %s
        GROUP BY stats.unit
    '''

    value = None
    if metric == 'ml-estimated':
        value = 'psu_energy_ac_xgboost_system'
    elif metric == 'RAPL':
        value = '%_rapl_%'
    elif metric == 'DC':
        value = 'psu_energy_dc_picolog_system'
    elif metric == 'AC':
        value = 'psu_energy_ac_powerspy2_system'
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
    machine_id: int

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

    if project.machine_id == 0:
        project.machine_id = None

    # Note that we use uri here as the general identifier, however when adding through web interface we only allow urls
    query = """
        INSERT INTO projects (uri,name,email, branch)
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
    jobs.insert_job('project', project_id, project.machine_id)

    return {'success': True}


@app.get('/v1/project/{project_id}')
async def get_project(project_id: str):
    query = """
            SELECT
                id, name, uri, branch, commit_hash,
                (SELECT STRING_AGG(t.name, ', ' ) FROM unnest(projects.categories) as elements
                    LEFT JOIN categories as t on t.id = elements) as categories,
                start_measurement, end_measurement,
                measurement_config, machine_specs, usage_scenario,
                last_run, created_at, invalid_project, phases
            FROM projects
            WHERE id = %s
            """
    params = (project_id,)
    data = DB().fetch_one(query, params=params, cursor_factory=psycopg2.extras.RealDictCursor)
    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}
    return {'success': True, 'data': data}

@app.get('/robots.txt')
async def robots_txt():
    data =  "User-agent: *\n"
    data += "Disallow: /"

    return Response(content=data, media_type='text/plain')

class Badge(BaseModel):
    value: int
    unit: str
    repo: str
    branch: str
    workflow: str
    run_id: str
    project_id: str

@app.post('/v1/ci/badge/add/')
async def post_ci_badge_add(badge: Badge):
    for i in Badge.schema()['properties'].keys():
        key_value = getattr(badge, i)
        if i == 'project_id':
            if key_value is None or key_value.strip() == '':
                badge.project_id = None
            elif not is_valid_uuid(key_value.strip()):
                return {'success': False, 'err': "project_id is not a valid uuid"}
        elif i == 'value':
            if key_value is None:
                return {'success': False, 'err': f"{i} is empty"}
        elif i == 'unit':
            if key_value is None or key_value.strip() == '':
                return {'success': False, 'err': f"{i} is empty"}
            if key_value != 'mJ':
                return {'success': False, 'err': "Unit is unsupported - only mJ currently accepted"}
        elif key_value is None or key_value.strip() == '':
            return {'success': False, 'err': f"{i} is empty"}

    query = """
        INSERT INTO
            badges (value, unit, repo ,branch, workflow, run_id, project_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
    params = (badge.value, badge.unit, badge.repo, badge.branch, badge.workflow, badge.run_id, badge.project_id)
    DB().query(query=query, params=params)

    return {'success': True}

@app.get('/v1/ci/badges/')
async def get_ci_badges(repo: str, branch: str, workflow:str):
    query = """
        SELECT value, unit, run_id, created_at
        FROM badges
        WHERE repo = %s AND branch = %s AND workflow = %s
        ORDER BY created_at DESC
    """
    params = (repo, branch, workflow)
    data = DB().fetch_all(query, params=params)
    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}

    return {'success': True, 'data': data}

@app.get('/v1/ci/badge/get/')
async def get_ci_badge_get(repo: str, branch: str, workflow:str):
    query = """
        SELECT value, unit
        FROM badges
        WHERE repo = %s AND branch = %s AND workflow = %s
        ORDER BY created_at DESC
    """
    params = (repo, branch, workflow)
    data = DB().fetch_one(query, params=params)
    if data is None or data == []:
        return {'success': False, 'err': 'Data is empty'}

    [energy_value, energy_unit] = rescale_energy_value(data[0], data[1])
    badge_value= f"{energy_value:.2f} {energy_unit}"

    badge = anybadge.Badge(
        label='Energy Used',
        value=badge_value,
        num_value_padding_chars=1,
        default_color='green')
    return Response(content=str(badge), media_type="image/svg+xml")

if __name__ == '__main__':
    app.run()
