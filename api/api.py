import yaml
import os
import sys
import psycopg2.extras
from psycopg2 import OperationalError, errorcodes, errors
import faulthandler

# It seems like FastAPI already enables faulthandler as it shows stacktrace on SEGFAULT
# Is the redundant call problematic
faulthandler.enable() # will catch segfaults and write to STDERR

sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../tools')

import error_helpers
import email_helpers
import jobs
from db import DB
from global_config import GlobalConfig

from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI()


async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        error_helpers.log_error("Error in API call:", str(Request), " with next call: ", call_next, e)
        email_helpers.send_error_email(GlobalConfig().config['admin']['email'], error_helpers.format_error("Error in API call:", str(Request), " with next call: ", call_next, e), project_id=None)
        return JSONResponse(content={'success': False, 'err': 'Technical error with getting data from the API - Please contact us: info@green-coding.org'}, status_code=500)

# Binding the Exception middleware must confusingly come BEFORE the CORS middleware. Otherwise CORS will not be sent in response
app.middleware('http')(catch_exceptions_middleware)

origins = [
    "http://metrics.green-coding.local:8000",
    "http://api.green-coding.local:8000",
    "https://metrics.green-coding.org",
    "https://api.green-coding.org",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/')
async def home():
    return RedirectResponse(url='/docs')

# A route to return all of the available entries in our catalog.
@app.get('/v1/notes/{project_id}')
async def get_notes(project_id):
    query = """
            SELECT
                project_id, container_name, note, time
            FROM
                notes
            WHERE project_id = %s
            ORDER BY
                created_at DESC  -- extremly important to order here, cause the charting library in JS cannot do that automatically!
            """
    data = DB().fetch_all(query, (project_id, ))
    if(data is None or data == []):
        return {'success': False, 'err': 'Data is empty'}

    return {"success": True, "data": data}


# A route to return all of the available entries in our catalog.
@app.get('/v1/projects')
async def get_projects():
    query = """
            SELECT
                id, name, uri, last_run
            FROM
                projects
            ORDER BY
                created_at DESC  -- extremly important to order here, cause the charting library in JS cannot do that automatically!
            """
    data = DB().fetch_all(query)
    if(data is None or data == []):
        return {'success': False, 'err': 'Data is empty'}

    return {"success": True, "data": data}

# Just copy and paste if we want to deprecate URLs
#@app.get('/v1/stats/uri', deprecated=True) # Here you can see, that URL is nevertheless accessible as variable later if supplied. Also deprecation shall be used once we move to v2 for all v1 routesthrough


# A route to return all of the available entries in our catalog.
@app.get('/v1/stats/uri')
async def get_stats_by_uri(uri: str):
    if(uri is None or uri.strip() == ''):
        return {'success': False, 'err': 'URI is empty'}

    query = """
            SELECT
                projects.id as project_id, stats.container_name, stats.time, stats.metric, stats.value
            FROM
                stats
            LEFT JOIN
                projects
            ON
                projects.id = stats.project_id
            WHERE
                projects.uri = %s
            ORDER BY
                stats.time ASC  -- extremly important to order here, cause the charting library in JS cannot do that automatically!
            """
    params = (uri,)
    data = DB().fetch_all(query, params)

    if(data is None or data == []):
        return {'success': False, 'err': 'Data is empty'}

    return {"success": True, "data": data}

# A route to return all of the available entries in our catalog.
@app.get('/v1/stats/single/{project_id}')
async def get_stats_single(project_id: str):
    if(project_id is None or project_id.strip() == ''):
        return {'success': False, 'err': 'Project_id is empty'}

    query = """
            SELECT
                stats.container_name, stats.time, stats.metric, stats.value
            FROM
                stats
            WHERE
                stats.project_id = %s
            ORDER BY
                stats.time ASC  -- extremly important to order here, cause the charting library in JS cannot do that automatically!
            """
    params = params=(project_id,)
    data = DB().fetch_all(query, params=params)

    if(data is None or data == []):
        return {'success': False, 'err': 'Data is empty'}
    return {"success": True, "data": data, "project": get_project(project_id)}

@app.get('/v1/stats/multi')
async def get_stats_multi(p: list[str] | None = Query(default=None)):
    for p_id in p:
        if(p_id is None or p_id.strip() == ''):
            return {'success': False, 'err': 'Project_id is empty'}

    query = """
            SELECT
                projects.id, projects.name, stats.container_name, stats.time, stats.metric, stats.value
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
    params = (p,)
    data = DB().fetch_all(query, params=params)

    if(data is None or data == []):
        return {'success': False, 'err': 'Data is empty'}
    return {"success": True, "data": data}

@app.get('/v1/stats/compare')
async def get_stats_compare(p: list[str] | None = Query(default=None)):
    for p_id in p:
        if(p_id is None or p_id.strip() == ''):
            return {'success': False, 'err': 'Project_id is empty'}

    query = """
            SELECT
                projects.name, stats.container_name, stats.metric, AVG(stats.value)
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
            GROUP BY projects.name, stats.container_name, stats.metric
            """
    params = (p,)
    data = DB().fetch_all(query, params=params)

    if(data is None or data == []):
        return {'success': False, 'err': 'Data is empty'}
    return {"success": True, "data": data}


class Project(BaseModel):
    name: str
    url: str
    email: str

@app.post('/v1/project/add')
async def post_project_add(project: Project):

    if(project.url is None or project.url.strip() == ''):
        return {'success': False, 'err': 'URL is empty'}

    if(project.name is None or project.name.strip() == ''):
        return {'success': False, 'err': 'Name is empty'}

    if(project.email is None or project.email.strip() == ''):
        return {'success': False, 'err': 'E-mail is empty'}

    # Note that we use uri here as the general identifier, however when adding through web interface we only allow urls
    query = """
        INSERT INTO
            projects (uri,name,email)
        VALUES (%s, %s, %s)
        RETURNING id
        """
    params = (project.url,project.name,project.email)
    project_id = DB().fetch_one(query,params=params)
    email_helpers.send_admin_email(f"New project added from Web Interface: {project.name}", project) # notify admin of new project
    jobs.insert_job("project", project_id)

    return {"success": True}

def get_project(project_id):
    query = """
            SELECT
                id, name, uri, (SELECT STRING_AGG(t.name, ', ' ) FROM unnest(projects.categories) as elements LEFT JOIN categories as t on t.id = elements) as categories, start_measurement, end_measurement, measurement_config, machine_specs, usage_scenario, last_run, created_at
            FROM
                projects
            WHERE
                id = %s
            """
    params = (project_id,)
    return DB().fetch_one(query, params=params, cursor_factory = psycopg2.extras.RealDictCursor)

if __name__ == "__main__":
    app.run()