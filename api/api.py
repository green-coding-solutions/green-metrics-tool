# -*- coding: utf-8 -*-

import yaml
import os
import sys
import psycopg2.extras
sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')

from setup_functions import get_db_connection
conn = get_db_connection()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse

app = FastAPI()

origins = [
    "http://metrics.green-coding.local:8000",
    "http://api.green-coding.local:8000",
    "https://metrics.green-coding.org",
    "https://api.green-coding.org:8000",
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
@app.get('/v1/projects')
async def get_projects():
    cur = conn.cursor()
    cur.execute("""
        SELECT
            *
        FROM
            projects
        ORDER BY
            created_at DESC  -- extremly important to order here, cause the charting library in JS cannot do that automatically!
        """
    )
    data = cur.fetchall()

    cur.close()

    if(data is None or data == []):
        response = {'success': False, 'err': 'Data is empty'}
        return response


    response = {"success": True, "data": data}
    return response

# A route to return all of the available entries in our catalog.
@app.get('/v1/stats/url')
async def get_stats_by_url():
    query_parameters = request.args
    cur = conn.cursor()
    url = query_parameters.get('url')

    if(url is None or url.strip() == ''):
        response = {'success': False, 'err': 'URL is empty'}
        return response

    cur.execute("""
        SELECT
            projects.id as project_id, stats.container_name, stats.time, stats.cpu, stats.mem, stats.mem_max, stats.net_in, stats.net_out, stats.energy, notes.note
        FROM
            stats
        LEFT JOIN
            projects
        ON
            projects.id = stats.project_id
        LEFT JOIN
            notes
        ON
            notes.project_id = stats.project_id
            AND
            notes.time = stats.time
            AND
            notes.container_name = stats.container_name
        WHERE
            projects.url = %s
        ORDER BY
            stats.time ASC  -- extremly important to order here, cause the charting library in JS cannot do that automatically!
        """,
        (url,)
    )
    data = cur.fetchall()

    cur.close()

    if(data is None or data == []):
        response = {'success': False, 'err': 'Data is empty'}
        return response


    response = {"success": True, "data": data}
    return response


# A route to return all of the available entries in our catalog.
@app.get('/v1/stats/single')
async def get_stats_single():
    query_parameters = request.args
    cur = conn.cursor()
    project_id = query_parameters.get('id')

    if(project_id is None or project_id.strip() == ''):
        response = {'success': False, 'err': 'Project_id is empty'}
        return response

    cur.execute("""
        SELECT
            stats.container_name, stats.time, stats.cpu, stats.mem, stats.mem_max, stats.net_in, stats.net_out, stats.energy, notes.note
        FROM
            stats
        LEFT JOIN
            notes
        ON
            notes.project_id = stats.project_id
            AND
            notes.time = stats.time
            AND
            notes.container_name = stats.container_name
        WHERE
            stats.project_id = %s
        ORDER BY
            stats.time ASC  -- extremly important to order here, cause the charting library in JS cannot do that automatically!
        """,
        (project_id,)
    )
    data = cur.fetchall()
    cur.close()

    if(data is None or data == []):
        response = {'success': False, 'err': 'Data is empty'}
        return response


    response = {"success": True, "data": data, "project": get_project(project_id)}
    return response

@app.post('/v1/project/add')
async def post_project_add():

    url = request.form.get('url')
    name = request.form.get('name')
    email = request.form.get('email')

    if(url is None or url.strip() == ''):
        response = {'success': False, 'err': 'URL is empty'}
        return response

    if(email is None or email.strip() == ''):
        response = {'success': False, 'err': 'E-Mail is empty'}
        return response

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO projects (url,name,email) VALUES (%s, %s, %s)
        """,
        (url,name,email)
    )
    conn.commit()

    cur.close()
    response = {"status": "success"}
    return response

def get_project(project_id):
    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            *
        FROM
            projects
        WHERE
            id = %s
        """,
        (project_id,)
    )
    project = cur.fetchone()
    cur.close()

    return project

if __name__ == "__main__":
    app.run()
