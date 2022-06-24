# -*- coding: utf-8 -*-

## TODO: Find Correct python postgres error code , refactor to catch that

import yaml
import os
import sys
import psycopg2.extras
sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../tools')

from setup_functions import get_db_connection, get_config
from send_email import send_email

conn = get_db_connection()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from pydantic import BaseModel

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
    try:
        cur.execute("""
            SELECT
                id, name, url, last_crawl
            FROM
                projects
            ORDER BY
                created_at DESC  -- extremly important to order here, cause the charting library in JS cannot do that automatically!
            """
        )
        data = cur.fetchall()
        cur.close()
    except BaseException as e:
        conn.rollback()
        cur.close()
        return {"success": False, "err": f"Exception: {str(e)}"}

    if(data is None or data == []):
        return {'success': False, 'err': 'Data is empty'}

    return {"success": True, "data": data}

# A route to return all of the available entries in our catalog.
@app.get('/v1/stats/url/{url}')
@app.get('/v1/stats/url', deprecated=True) # Here you can see, that URL is nevertheless accessible as variable later if supplied. Also deprecation shall be used once we move to v2 for all v1 routesthrough
async def get_stats_by_url(url: str):
    cur = conn.cursor()

    if(url is None or url.strip() == ''):
        return {'success': False, 'err': 'URL is empty'}

    try:
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
    except BaseException as e:
        conn.rollback()
        cur.close()
        return {"success": False, "err": f"Exception: {str(e)}"}

    if(data is None or data == []):
        return {'success': False, 'err': 'Data is empty'}

    return {"success": True, "data": data}

# A route to return all of the available entries in our catalog.
@app.get('/v1/stats/single/{project_id}')
async def get_stats_single(project_id: str):
    cur = conn.cursor()

    if(project_id is None or project_id.strip() == ''):
        return {'success': False, 'err': 'Project_id is empty'}

    try:
        cur.execute("""
            SELECT
                stats.container_name, stats.time, stats.metric, stats.value, notes.note
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
    except BaseException as e:
        conn.rollback()
        cur.close()
        return {"success": False, "err": f"Exception: {str(e)}"}

    if(data is None or data == []):
        return {'success': False, 'err': 'Data is empty'}


    return {"success": True, "data": data, "project": get_project(project_id)}

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

    try:
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO
                projects (url,name,email)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (project.url,project.name,project.email)
        )
        project_id = cur.fetchone()[0]
            
        print("Having: ", project_id)
        
        notify_admin(project.name, project_id)
        conn.commit()
        cur.close()
        return {"success": True}

    except BaseException as e:
        conn.rollback()
        cur.close()
        return {"success": False, "err": f"Problem with sending email / saving to database: {str(e)}"}
    

def notify_admin(name, project_id):
    config = get_config()
    message = """\
From: {smtp_sender}
To: {receiver_email}
Subject: Someone has added a new project

{name} has added a new project. ID: {project_id}

--
Green Coding Berlin
https://www.green-coding.org

    """
    message = message.format(
        receiver_email=config['admin']['email'],
        name=name,
        project_id=project_id,
        smtp_sender=config['smtp']['sender'])
    send_email(config, message, config['admin']['email'])

def get_project(project_id):
    cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

    try:
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
    except BaseException as e:
        conn.rollback()
        cur.close()
        return None

    return project

if __name__ == "__main__":
    app.run()