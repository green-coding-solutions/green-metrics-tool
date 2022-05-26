# -*- coding: utf-8 -*-

import flask
from flask import request, jsonify


import yaml
import os
with open("{path}/../config.yml".format(path=os.path.dirname(os.path.realpath(__file__)))) as config_file:
    config = yaml.load(config_file,yaml.FullLoader)

import psycopg2
if config['postgresql']['host'] is None: # force domain socket connection
        conn = psycopg2.connect("user=%s dbname=%s password=%s" % (config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))
else:
        conn = psycopg2.connect("host=%s user=%s dbname=%s password=%s" % (config['postgresql']['host'], config['postgresql']['user'], config['postgresql']['dbname'], config['postgresql']['password']))

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
        SELECT container_name, time, cpu, mem, mem_max, net_in, net_out FROM stats WHERE project_id = %s ORDER BY time ASC
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
