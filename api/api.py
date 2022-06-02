# -*- coding: utf-8 -*-

import flask
from flask import request, jsonify
import yaml
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__))+'/../lib')

from setup_functions import get_db_connection

conn = get_db_connection()

app = flask.Flask(__name__)
app.config["DEBUG"] = True

@app.route('/', methods=['GET'])
def home():
    return '''<h1>Welcome to the API help page</h1>
<p>The API is not made to be called with a webrowser directly. Please use XHR access to it's REST interface</p>'''


# A route to return all of the available entries in our catalog.
@app.route('/api/v1/stats/single', methods=['GET'])
def api_all():
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


    response = flask.jsonify({"success": True, "data": data})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

@app.route('/api/v1/project/add', methods=['POST'])
def project_add():

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

    cur.close()
    response = flask.jsonify({"status": "success"})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response



if __name__ == "__main__":
    app.run(host='0.0.0.0')
