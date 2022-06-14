# -*- coding: utf-8 -*-

import flask
from flask import request, jsonify
import yaml
import os
import sys
import psycopg2.extras
sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')
sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../tools')

from setup_functions import get_db_connection
from send_email import send_email

conn = get_db_connection()

app = flask.Flask(__name__)
app.config["DEBUG"] = False

@app.route('/', methods=['GET'])
def home():
    return '''<h1>Welcome to the API help page</h1>
<p>The API is not made to be called with a webrowser directly. Please use XHR access to it's REST interface</p>'''

# A route to return all of the available entries in our catalog.
@app.route('/v1/projects', methods=['GET'])
def get_projects():
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
        response = flask.jsonify({'success': False, 'err': 'Data is empty'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response


    response = flask.jsonify({"success": True, "data": data})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# A route to return all of the available entries in our catalog.
@app.route('/v1/stats/url', methods=['GET'])
def get_stats_by_url():
    query_parameters = request.args
    cur = conn.cursor()
    url = query_parameters.get('url')

    if(url is None or url.strip() == ''):
        response = flask.jsonify({'success': False, 'err': 'URL is empty'})
        response.headers.add('Access-Control-Allow-Origin', '*')
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
        response = flask.jsonify({'success': False, 'err': 'Data is empty'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response


    response = flask.jsonify({"success": True, "data": data})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# A route to return all of the available entries in our catalog.
@app.route('/v1/stats/single', methods=['GET'])
def get_stats_single():
    query_parameters = request.args
    cur = conn.cursor()
    project_id = query_parameters.get('id')

    if(project_id is None or project_id.strip() == ''):
        response = flask.jsonify({'success': False, 'err': 'Project_id is empty'})
        response.headers.add('Access-Control-Allow-Origin', '*')
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
        response = flask.jsonify({'success': False, 'err': 'Data is empty'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response


    response = flask.jsonify({"success": True, "data": data, "project": get_project(project_id)})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@app.route('/v1/project/add', methods=['POST'])
def post_project_add():

    url = request.form.get('url')
    name = request.form.get('name')
    email = request.form.get('email')

    if(url is None or url.strip() == ''):
        response = flask.jsonify({'success': False, 'err': 'URL is empty'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    if(email is None or email.strip() == ''):
        response = flask.jsonify({'success': False, 'err': 'E-Mail is empty'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    cur = conn.cursor()

    cur.execute("""
        INSERT INTO projects (url,name,email) VALUES (%s, %s, %s)
        """,
        (url,name,email)
    )
    conn.commit()
    project_id = cur.fetchone()[0]

    cur.close()
    response = flask.jsonify({"status": "success"})
    response.headers.add('Access-Control-Allow-Origin', '*')
    notify_admin(name, project_id)
    return response

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
    send_email(config, message, receiver_email)

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
    app.run(host='0.0.0.0')
